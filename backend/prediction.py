"""Dependency-free inference for an exported, genuinely trained Random Forest."""
import json
import math
from functools import lru_cache
from pathlib import Path

FEATURES=['distance_km','speed_kmh','hour_sin','hour_cos','weekday','congestion','rain','road_type']
def features(edge, settings, congestion):
    hour=settings['hour']
    return [edge['km'],edge['speed'],math.sin(hour*math.pi/12),math.cos(hour*math.pi/12),
            settings['weekday'],congestion,settings['rain'],edge['kind']]

@lru_cache(maxsize=1)
def model():
    return json.loads((Path(__file__).parent/'models'/'traffic_forest.json').read_text())

def predict(edge, settings, congestion):
    baseline=edge['km']/edge['speed']*60
    if not settings.get('use_ml',True):
        return baseline*(1+2.8*congestion)*(1+.25*settings['rain']), 'RULE_BASELINE'
    vector=features(edge,settings,congestion)
    forest=model()
    values=[]
    for tree in forest['trees']:
        i=0
        while tree['left'][i]!=-1:
            i=tree['left'][i] if vector[tree['feature'][i]]<=tree['threshold'][i] else tree['right'][i]
        values.append(tree['value'][i])
    # Trained target is travel-time multiplier. Clamping enforces model physical bound.
    return baseline*max(1.0,sum(values)/len(values)), 'RANDOM_FOREST_SYNTHETIC'

def model_report():
    return json.loads((Path(__file__).parent/'models'/'model_report.json').read_text())
