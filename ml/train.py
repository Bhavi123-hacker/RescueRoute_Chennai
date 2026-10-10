"""Generate synthetic traffic observations, train, hold out entire later dates, export."""
import csv
import json
import math
from pathlib import Path
import random
import sys
from datetime import date,timedelta
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.data import EDGES
from backend.prediction import FEATURES,features

ROOT=Path(__file__).resolve().parents[1]
rng=random.Random(42)
rows=[]
for day in range(28):
    current=date(2026,1,1)+timedelta(days=day)
    for hour in (6,9,12,15,18,21):
        for edge in EDGES:
            congestion=rng.uniform(.03,.99)
            rain=rng.choice([0,0,0,1,2])
            settings={'hour':hour,'weekday':current.weekday(),'rain':rain}
            morning=math.exp(-((hour-9)/2.3)**2)
            evening=math.exp(-((hour-18)/2.5)**2)
            peak=(morning+evening)*(.35 if current.weekday()<5 else .1)
            multiplier=max(1,1+3.1*congestion**1.45+.32*rain+.22*rain*congestion+peak+.12*(edge['kind']==0)+rng.gauss(0,.1))
            travel=edge['km']/edge['speed']*60*multiplier
            row={'date':str(current),'day_index':day,'edge_id':edge['id'],'hour':hour,
                 'distance_km':edge['km'],'speed_kmh':edge['speed'],'weekday':current.weekday(),
                 'congestion':round(congestion,6),'rain':rain,'road_type':edge['kind'],
                 'travel_minutes':round(travel,6),'multiplier':round(multiplier,6),'source':'SYNTHETIC'}
            row['features']=features(edge,settings,congestion)
            rows.append(row)
train=[r for r in rows if r['day_index']<21]
test=[r for r in rows if r['day_index']>=21]
X=np.array([r['features'] for r in train]);y=np.array([r['multiplier'] for r in train])
forest=RandomForestRegressor(n_estimators=40,max_depth=9,min_samples_leaf=5,random_state=42,n_jobs=1)
forest.fit(X,y)
predicted=forest.predict([r['features'] for r in test])
actual=np.array([r['travel_minutes'] for r in test])
free=np.array([r['distance_km']/r['speed_kmh']*60 for r in test])
rf_minutes=np.maximum(1,predicted)*free
rule=np.array([(1+2.8*r['congestion'])*(1+.25*r['rain']) for r in test])*free
def metrics(values):
    return {'mae_minutes':float(mean_absolute_error(actual,values)),
            'rmse_minutes':float(np.sqrt(mean_squared_error(actual,values))), 'r2':float(r2_score(actual,values))}
report={'model':'Random Forest (40 trees, depth ≤ 9)','data_source':'SYNTHETIC', 'seed':42,
        'observations':len(rows),'training_rows':len(train),'test_rows':len(test),
        'training_dates':[train[0]['date'],train[-1]['date']],'test_dates':[test[0]['date'],test[-1]['date']],
        'split':'First 21 dates train; next 7 dates test. No random row split.',
        'random_forest':metrics(rf_minutes),'fixed_speed':metrics(free),'traffic_rule':metrics(rule),
        'feature_importance':dict(zip(FEATURES,forest.feature_importances_.tolist())),
        'limitations':'Generated observations share a synthetic mechanism; metrics do not establish real-world traffic accuracy. One final holdout evaluation; no parameter search on the test set.'}
trees=[]
for estimator in forest.estimators_:
    t=estimator.tree_
    trees.append({'left':t.children_left.tolist(),'right':t.children_right.tolist(),'feature':t.feature.tolist(),
                  'threshold':t.threshold.tolist(),'value':t.value[:,0,0].tolist()})
models=ROOT/'backend'/'models';models.mkdir(exist_ok=True)
(models/'traffic_forest.json').write_text(json.dumps({'feature_names':FEATURES,'target':'travel_time_multiplier','trees':trees},separators=(',',':')))
(models/'model_report.json').write_text(json.dumps(report,indent=2))
dataset=ROOT/'ml'/'synthetic_traffic.csv'
columns=[k for k in rows[0] if k!='features']
with dataset.open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader()
    writer.writerows({k:v for k,v in r.items() if k!='features'} for r in rows)
checks=[]
for i,r in enumerate(test[:20]):
    checks.append({'edge':{'km':r['distance_km'],'speed':r['speed_kmh'],'kind':r['road_type']},
                   'settings':{'hour':r['hour'],'weekday':r['weekday'],'rain':r['rain'],'use_ml':True},
                   'congestion':r['features'][5],'expected_minutes':float(rf_minutes[i])})
(models/'inference_checks.json').write_text(json.dumps(checks,indent=2))
import shutil
(ROOT/'frontend'/'assets').mkdir(exist_ok=True)
shutil.copyfile(dataset,ROOT/'frontend'/'assets'/'synthetic_traffic.csv')
preview=[{k:v for k,v in r.items() if k not in ('features','multiplier','day_index')} for r in rows[:12]]
(models/'dataset_preview.json').write_text(json.dumps({'rows':preview,'total':len(rows),'source':'SYNTHETIC'},indent=2))
print(json.dumps(report,indent=2))
