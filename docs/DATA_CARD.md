# Synthetic traffic dataset and trained model

## Provenance and intended use

`ml/train.py` generates **234,000** Chennai-calibrated synthetic observations with seed 42: 65 modeled links × 24 hours × 150 dates (1 Oct 2025 → 27 Feb 2026). It includes no patient identities, real ambulance journeys or measured Chennai congestion. Geographic link lengths are approximate model inputs. Intended use: demonstrate supervised regression, model-assisted graph search and street-preview travel weights.

Training dates: first 112 calendar days (174,720 rows). Holdout dates: remaining 38 days (59,280 rows). Roads recur across both periods. The evaluation measures future synthetic dates on known modeled roads, not unseen-road/city performance. No hyperparameter search used the holdout.

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
| is_weekend | Weekend relief flag |
| monsoon | Graded NE monsoon intensity |
| corridor_load | Corridor class load prior |
| event_shock | Festival / extreme congestion shock |

The target is a travel-time multiplier relative to free-flow minutes. Labels follow nonlinear congestion/weather/time/monsoon/festival mechanisms plus noise. RandomForestRegressor uses 80 trees, max_depth=12, min_samples_leaf=4, max_features=sqrt, seed 42. Exported JSON tree arrays support standard-library runtime inference. Street preview reuses the same RF family via `street_multiplier`.

## Final synthetic holdout results

See `backend/models/model_report.json` for the exact metrics from the last training run. The Random Forest must beat both the traffic-rule and fixed-speed baselines on holdout MAE. High R-squared is expected when train/test share the generator. These results do **not** establish real Chennai travel accuracy.

## Reproduction / extension

```bash
python -m pip install -r ml/requirements.txt
python ml/train.py
```

After AWS deploy, optional cloud retrain:

```bash
python scripts/start_sagemaker_training.py --stack rescueroute-chennai --region eu-north-1
```
