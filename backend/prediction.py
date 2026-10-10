"""Dependency-free inference for an exported, genuinely trained Random Forest."""
import json
import math
from functools import lru_cache
from pathlib import Path

FEATURES = [
    'distance_km', 'speed_kmh', 'hour_sin', 'hour_cos', 'weekday', 'congestion',
    'rain', 'road_type', 'is_weekend', 'monsoon', 'corridor_load', 'event_shock',
]

def features(edge, settings, congestion, extras=None):
    hour = settings['hour']
    weekday = settings['weekday']
    rain = settings['rain']
    extras = extras or {}
    is_weekend = 1.0 if weekday >= 5 else 0.0
    # Chennai NE monsoon proxy: Nov–Dec (months 11–12) or heavy rain days marked in training.
    monsoon = float(extras.get('monsoon', 1.0 if rain >= 2 else 0.0))
    corridor_load = float(extras.get('corridor_load', {
        'Local streets': 0.35, 'Central corridor': 0.85, 'Ring road': 0.55, 'Express link': 0.4,
    }.get(edge.get('corridor'), 0.45)))
    event_shock = float(extras.get('event_shock', 1.0 if congestion > 0.85 else 0.0))
    return [
        edge['km'], edge['speed'],
        math.sin(hour * math.pi / 12), math.cos(hour * math.pi / 12),
        weekday, congestion, rain, edge['kind'],
        is_weekend, monsoon, corridor_load, event_shock,
    ]

@lru_cache(maxsize=1)
def model():
    return json.loads((Path(__file__).parent / 'models' / 'traffic_forest.json').read_text())

def predict(edge, settings, congestion, extras=None):
    baseline = edge['km'] / edge['speed'] * 60
    if not settings.get('use_ml', True):
        weekend = 0.85 if settings['weekday'] >= 5 else 1.0
        return baseline * (1 + 2.8 * congestion) * (1 + 0.25 * settings['rain']) * weekend, 'RULE_BASELINE'
    vector = features(edge, settings, congestion, extras)
    forest = model()
    values = []
    for tree in forest['trees']:
        i = 0
        while tree['left'][i] != -1:
            i = tree['left'][i] if vector[tree['feature'][i]] <= tree['threshold'][i] else tree['right'][i]
        values.append(tree['value'][i])
    # Trained target is travel-time multiplier. Clamping enforces model physical bound.
    return baseline * max(1.0, sum(values) / len(values)), 'RANDOM_FOREST_SYNTHETIC'

@lru_cache(maxsize=1024)
def _street_multiplier_cached(kind_code, speed_i, hour, weekday, rain, traffic, use_ml):
    corridor = 'Express link' if kind_code == 2 else 'Central corridor' if kind_code == 1 else 'Local streets'
    profile = {'normal': 0.25, 'rush': 0.78, 'disruption': 0.92}.get(traffic, 0.25)
    edge = {'km': 1.0, 'speed': max(12.0, float(speed_i)), 'kind': kind_code, 'corridor': corridor}
    settings = {'hour': hour, 'weekday': weekday, 'rain': rain, 'use_ml': use_ml}
    minutes, source = predict(edge, settings, profile)
    free = edge['km'] / edge['speed'] * 60
    return max(1.0, minutes / free), source

def street_multiplier(kind, speed, settings, tide='balanced', closed=False):
    """Apply the same RF family to OSM street classes for a unified traffic narrative."""
    if closed:
        return 99.0
    kind_code = 2 if kind in ('motorway', 'trunk') else 1 if kind in ('primary', 'secondary') else 0
    factor, source = _street_multiplier_cached(
        kind_code, int(round(float(speed))), int(settings.get('hour', 12)), int(settings.get('weekday', 1)),
        int(settings.get('rain', 0)), str(settings.get('traffic', 'normal')), bool(settings.get('use_ml', True)),
    )
    if tide in ('east', 'west'):
        factor *= 1.12
    return factor, source

def model_report():
    return json.loads((Path(__file__).parent / 'models' / 'model_report.json').read_text())
