"""Generate Chennai-calibrated synthetic traffic, train RF, hold out later dates, export."""
import csv
import json
import math
import random
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.data import EDGES
from backend.prediction import FEATURES, features

ROOT = Path(__file__).resolve().parents[1]
rng = random.Random(42)
np_rng = np.random.default_rng(42)

# 150 dates: late monsoon → dry winter/spring × 24h × 65 edges ≈ 234k rows.
DAYS = 150
TRAIN_DAYS = 112
HOURS = list(range(24))
rows = []

for day in range(DAYS):
    current = date(2025, 10, 1) + timedelta(days=day)
    month = current.month
    # Graded NE monsoon intensity so the feature is not a pure month dummy.
    monsoon_season = {10: 0.85, 11: 1.0, 12: 0.9, 1: 0.15, 2: 0.05}.get(month, 0.0)
    festival = 1.0 if current.day in (1, 14, 15, 26) and month in (1, 8, 10, 11) else 0.0
    for hour in HOURS:
        # Spatially correlated congestion shock per hour (city-wide pulse).
        city_pulse = float(np.clip(np_rng.normal(0.35, 0.18), 0.05, 0.95))
        for edge in EDGES:
            corridor_bias = {
                'Local streets': 0.08, 'Central corridor': 0.22, 'Ring road': 0.12, 'Express link': 0.05,
            }[edge['corridor']]
            base = city_pulse * 0.55 + corridor_bias + rng.uniform(0.0, 0.25)
            morning = math.exp(-((hour - 9) / 1.8) ** 2)
            evening = math.exp(-((hour - 18.5) / 2.0) ** 2)
            lunch = 0.35 * math.exp(-((hour - 13) / 1.4) ** 2)
            night = 0.55 if hour <= 5 or hour >= 23 else 0.0
            weekday = current.weekday()
            peak = (morning + evening + lunch) * (0.42 if weekday < 5 else 0.14)
            rain = rng.choices([0, 1, 2], weights=[0.62, 0.28, 0.10 if monsoon_season else 0.05])[0]
            if monsoon_season and hour in (15, 16, 17, 18):
                rain = max(rain, rng.choice([0, 1, 2]))
            congestion = float(np.clip(base + peak * 0.55 + 0.08 * rain - night * 0.25 + festival * 0.12, 0.02, 0.99))
            event_shock = 1.0 if congestion > 0.85 or (festival and hour in (17, 18, 19)) else 0.0
            corridor_load = {
                'Local streets': 0.35, 'Central corridor': 0.85, 'Ring road': 0.55, 'Express link': 0.4,
            }[edge['corridor']]
            extras = {'monsoon': monsoon_season, 'corridor_load': corridor_load, 'event_shock': event_shock}
            settings = {'hour': hour, 'weekday': weekday, 'rain': rain}
            weekend_relief = 0.12 if weekday >= 5 else 0.0
            multiplier = max(
                1.0,
                1
                + 2.75 * congestion ** 1.35
                + 0.28 * rain
                + 0.18 * rain * congestion
                + peak
                + 0.35 * monsoon_season * (rain / 2)
                + 0.22 * event_shock
                + 0.15 * (edge['kind'] == 0)
                + 0.1 * corridor_load
                - weekend_relief
                + rng.gauss(0, 0.08),
            )
            travel = edge['km'] / edge['speed'] * 60 * multiplier
            row = {
                'date': str(current), 'day_index': day, 'edge_id': edge['id'], 'hour': hour,
                'distance_km': edge['km'], 'speed_kmh': edge['speed'], 'weekday': weekday,
                'congestion': round(congestion, 6), 'rain': rain, 'road_type': edge['kind'],
                'is_weekend': int(weekday >= 5), 'monsoon': int(monsoon_season),
                'corridor_load': round(corridor_load, 4), 'event_shock': int(event_shock),
                'travel_minutes': round(travel, 6), 'multiplier': round(multiplier, 6),
                'source': 'SYNTHETIC_CHENNAI_CALIBRATED',
            }
            row['features'] = features(edge, settings, congestion, extras)
            rows.append(row)

train = [r for r in rows if r['day_index'] < TRAIN_DAYS]
test = [r for r in rows if r['day_index'] >= TRAIN_DAYS]
X = np.array([r['features'] for r in train])
y = np.array([r['multiplier'] for r in train])
forest = RandomForestRegressor(
    n_estimators=80, max_depth=12, min_samples_leaf=4, max_features='sqrt',
    random_state=42, n_jobs=-1,
)
forest.fit(X, y)
predicted = forest.predict([r['features'] for r in test])
actual = np.array([r['travel_minutes'] for r in test])
free = np.array([r['distance_km'] / r['speed_kmh'] * 60 for r in test])
rf_minutes = np.maximum(1, predicted) * free
rule = np.array([
    (1 + 2.8 * r['congestion']) * (1 + 0.25 * r['rain']) * (0.85 if r['weekday'] >= 5 else 1.0)
    for r in test
]) * free

def metrics(values):
    return {
        'mae_minutes': float(mean_absolute_error(actual, values)),
        'rmse_minutes': float(np.sqrt(mean_squared_error(actual, values))),
        'r2': float(r2_score(actual, values)),
    }

report = {
    'model': 'Random Forest (80 trees, depth ≤ 12, 12 features)',
    'data_source': 'SYNTHETIC_CHENNAI_CALIBRATED',
    'seed': 42,
    'observations': len(rows),
    'training_rows': len(train),
    'test_rows': len(test),
    'training_dates': [train[0]['date'], train[-1]['date']],
    'test_dates': [test[0]['date'], test[-1]['date']],
    'split': f'First {TRAIN_DAYS} dates train; remaining {DAYS - TRAIN_DAYS} dates test. No random row split.',
    'hours_per_day': len(HOURS),
    'feature_count': len(FEATURES),
    'calibration_notes': (
        'Synthetic generator encodes Chennai-like morning/evening peaks, weekend relief, '
        'NE monsoon rain bias, corridor load and festival shocks. Still not measured field traffic.'
    ),
    'random_forest': metrics(rf_minutes),
    'fixed_speed': metrics(free),
    'traffic_rule': metrics(rule),
    'feature_importance': dict(zip(FEATURES, forest.feature_importances_.tolist())),
    'limitations': (
        'Generated observations share a synthetic mechanism calibrated to plausible metro patterns; '
        'metrics do not establish real-world Chennai traffic accuracy. One final holdout evaluation; '
        'no parameter search on the test set.'
    ),
}

trees = []
for estimator in forest.estimators_:
    t = estimator.tree_
    trees.append({
        'left': t.children_left.tolist(),
        'right': t.children_right.tolist(),
        'feature': t.feature.tolist(),
        'threshold': t.threshold.tolist(),
        'value': t.value[:, 0, 0].tolist(),
    })

models = ROOT / 'backend' / 'models'
models.mkdir(exist_ok=True)
(models / 'traffic_forest.json').write_text(json.dumps({
    'feature_names': FEATURES, 'target': 'travel_time_multiplier', 'trees': trees,
}, separators=(',', ':')))
(models / 'model_report.json').write_text(json.dumps(report, indent=2))

dataset = ROOT / 'ml' / 'synthetic_traffic.csv'
columns = [k for k in rows[0] if k != 'features']
with dataset.open('w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=columns)
    writer.writeheader()
    writer.writerows({k: v for k, v in r.items() if k != 'features'} for r in rows)

checks = []
for i, r in enumerate(test[:24]):
    checks.append({
        'edge': {'km': r['distance_km'], 'speed': r['speed_kmh'], 'kind': r['road_type'],
                 'corridor': next(e['corridor'] for e in EDGES if e['id'] == r['edge_id'])},
        'settings': {'hour': r['hour'], 'weekday': r['weekday'], 'rain': r['rain'], 'use_ml': True},
        'congestion': r['features'][5],
        'extras': {
            'monsoon': r['monsoon'], 'corridor_load': r['corridor_load'], 'event_shock': r['event_shock'],
        },
        'expected_minutes': float(rf_minutes[i]),
    })
(models / 'inference_checks.json').write_text(json.dumps(checks, indent=2))

(ROOT / 'frontend' / 'assets').mkdir(exist_ok=True)
shutil.copyfile(dataset, ROOT / 'frontend' / 'assets' / 'synthetic_traffic.csv')
preview = [{k: v for k, v in r.items() if k not in ('features', 'multiplier', 'day_index')} for r in rows[:16]]
(models / 'dataset_preview.json').write_text(json.dumps({
    'rows': preview, 'total': len(rows), 'source': 'SYNTHETIC_CHENNAI_CALIBRATED',
}, indent=2))
print(json.dumps(report, indent=2))
