# Synthetic traffic dataset and trained model

## Provenance and intended use

`ml/train.py` generates the supplied 10,920 observations with seed 42: 65 modeled Chennai links × six sampled hours × 28 dates. It includes no patient identities, real ambulance journeys or observed Chennai congestion. Geographic link lengths are approximate model inputs. Intended use: demonstrate supervised regression and model-assisted graph search.

Training dates: 1–21 January 2026, 8,190 rows. Holdout dates: 22–28 January, 2,730 rows. Roads recur across both periods. The evaluation measures future synthetic dates on known modeled roads, not unseen-road/city performance. No hyperparameter search used the holdout.

## Features and inference

| Feature | Unit / meaning |
| --- | --- |
| distance_km | Modeled link length |
| speed_kmh | Assumed free-flow speed |
| hour_sin, hour_cos | Cyclic hour encoding, period 24 |
| weekday | Day of week 0–6 |
| congestion | Synthetic/operator congestion index 0–1 |
| rain | Synthetic weather level 0, 1 or 2 |
| road_type | Encoded model road kind |

The target is a travel-time multiplier relative to free-flow minutes. Synthetic labels follow a nonlinear congestion/weather/time mechanism plus random variation. Target minutes are not an input feature. RandomForestRegressor uses 40 trees, max_depth=9, min_samples_leaf=5, seed 42. Exported JSON tree arrays support standard-library runtime inference: average leaf predictions, clamp multiplier to at least one, then multiply by free-flow minutes. Twenty fixtures compare exported predictions with sklearn.

## Final synthetic holdout results

| Predictor | MAE minutes | RMSE minutes | R-squared |
| --- | ---: | ---: | ---: |
| Random Forest | 0.624 | 0.916 | 0.995 |
| Traffic-rule baseline | 1.333 | 1.922 | 0.976 |
| Fixed free-flow speed | 11.050 | 14.781 | -0.398 |

Metrics are per-link errors, not full mission arrival errors. Congestion contributes about 87.1% and rain 11.6% of impurity importance. They describe the synthetic generator, not causal real-world evidence. High R-squared is expected when train/test share that generator. These results do not establish real Chennai travel accuracy.

The hospital top-five list minimizes predicted travel minutes. Mission A* adds a rough-road penalty (0.8 critical / 0.25 urgent minutes per roughness unit); assignment also includes readiness, on-scene time, handover wait and approximate connectors. Disabling ML selects the traffic-rule baseline. A* correctness applies to supplied graph weights, not to their real-world prediction accuracy.

## Reproduction / extension

```bash
python -m pip install -r ml/requirements.txt
python ml/train.py
```

Training regenerates CSV, model JSON, report JSON and prediction fixtures. Replacing a CSV alone does not retrain this model. For real data, obtain authorized de-identified road/trip measurements, document provenance/units/missing values, use chronological train/validation/test splits, tune only on training/validation, compare simple baselines and calibration, and evaluate route/mission error including outages and drift. Amazon Location preview data is not used to train the supplied forest.
