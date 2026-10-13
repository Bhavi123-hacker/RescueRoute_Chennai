# RescueRoute Chennai — Emergency Ambulance Route Optimizer

A demonstrable AWS serverless project with real mapped Chennai hospital locations, patient-selected pickup and destination, five earliest hospital suggestions, a mapped street atlas, dark/light themes, traffic scenarios, trained ML and a complete simulated ambulance journey.

## Run locally

Install Python 3.12+, extract the ZIP, and open a terminal inside `RescueRoute_Chennai`:

```bash
python local_server.py
```

On Windows, use `py local_server.py` if `python` is unavailable. Open http://localhost:8020 (or the port printed by the server). Local serving requires only the Python standard library. Click **Guided demo** to start a repeatable critical-trauma mission; try road closure, hospital unavailability, next GPS step and completion. Local state persists in `rescueroute-chennai.sqlite3`. Reset the shared demo from the AWS tab when you need a fresh run.

## Choose source, destination and five earliest hospitals

1. Select a Chennai neighborhood, click a map point, enter latitude/longitude or use browser location. Sources must lie inside the bundled metro bounding box.
2. Choose emergency category/level and calculate. The top-five cards list distinct hospitals in ascending pickup-to-hospital travel minutes, with distance and capacity provenance.
3. **Suitable demo care** filters configured profiles for required care, acceptance, beds and ICU. **Directory travel** compares 621 name/tag-screened transport candidates from the directory; suitability and capacity remain unverified.
4. Search and choose any of the 868 directory records as your preferred destination. Unknown profiles need operator configuration before simulated dispatch. A selected hospital remains the destination; an unavailable selection pauses the mission unless you explicitly allow an alternative.
5. Change normal/rush/incident traffic, weather or individual road congestion/closures. Routes change when another feasible path becomes preferable. A different route is not guaranteed on every change.

The street-map top-five ranking minimizes scenario travel minutes on the directed OSM road network, including approximate pickup/hospital connectors. The 36-anchor A* mission simulator remains separate. It excludes ambulance response, on-scene time, rough-road penalty and hospital handover wait. The ambulance assignment objective separately considers those factors, so its automatic destination may differ from the first travel-only card.

## What is real and what is modeled

| Component | Status |
| --- | --- |
| 868 named hospital map records | OpenStreetMap snapshot dated 8 October 2026; source links and coordinates included |
| Directory scope | Metro bounding box, including surrounding municipalities; not an exhaustive official hospital register |
| Default hospital operations | 16 operator demonstration profiles; other records have unknown capacity/care |
| A* city roads | 36 approximate neighborhood anchors and 65 modeled links; not surveyed street routing |
| Local traffic, weather, beds and ambulance GPS | Simulation / operator demonstration inputs |
| Street map | 10,740 mapped OSM driving-corridor ways; all 868 hospital records through clusters |
| AWS road/traffic preview | Real provider road geometry and traffic estimates where available, only when enabled after AWS deployment |
| ML | Trained Random Forest on synthetic traffic; no real Chennai accuracy claim |

The directory contains possible map tagging errors, duplicates or outdated entries. Travel preview applies a name/ER-tag screen, not a medical verification. Addresses/phone/website fields are present only where mapped. OSM emergency tags are source metadata, not validated service availability. Real hospital beds and physical ambulance telemetry are not connected. This application is an educational demonstration, not an emergency dispatch service.

The street map shows all 868 records by default, groups nearby records into count clusters and expands them as you zoom. Search any hospital, fit all hospitals, or filter the layer. The city directory includes search, filters, map focus, hospital source links and a CSV download. Exact selected pickup coordinates are stored with demo missions and sent to Amazon Location when a provider preview is requested. Use demonstration locations for presentations.

## ML and algorithms

A* plans weighted missions; Dijkstra, BFS and shortest-distance baselines use the same graph snapshot. Dynamic replanning reruns A*, rather than implementing D* Lite. The directed street preview applies the same Random Forest family when ML mode is on, so street ETAs and mission costs share one traffic narrative. Exported inference fixtures verify the JSON forest matches scikit-learn.

The CSV has **234,000** Chennai-calibrated synthetic observations (65 roads × 24 hours × 150 dates spanning monsoon → dry season) with monsoon intensity, weekend relief, corridor load and festival shocks. A chronological split uses 112 training dates and 38 holdout dates across **12 features**. Retrain locally or via the SageMaker-ready job script after deploy. See `docs/DATA_CARD.md`.

Optional retraining:

```bash
python -m pip install -r ml/requirements.txt
python ml/train.py
```

## AWS deployment

The SAM template implements Cognito, HTTP API, WebSocket API, Lambda, DynamoDB, SNS alerts, private S3/CloudFront, IAM, CloudWatch, Budgets and a SageMaker training role. Amazon Location (maps, Places, traffic routes) is optional. Review defaults disable active X-Ray tracing and custom CloudWatch metrics, lower API throttling and create a **1 USD account-wide monthly budget before credits**, with required `BudgetAlertEmail` notifications. The budget is an alert, not a hard spending cap. See `docs/AWS_DEPLOYMENT.md` for limits, permissions and cleanup.

For a temporary review, run the helper in your authenticated local terminal (not a stalled agent shell):

```powershell
py -3.12 scripts/deploy_review.py --profile rescueroute-key
# After check-only succeeds and deployment permissions are ready:
py -3.12 scripts/deploy_review.py --profile rescueroute-key --deploy
```

It checks remaining credits, keeps a 10 USD reserve, builds/publishes the dashboard, prompts locally for the operator password, and verifies the website plus an authenticated API. It never upgrades the account or starts cloud training. Read-only IAM permissions cannot deploy; missing permissions or unverified credits stop the helper. A current balance check cannot guarantee future charges remain below the budget.

```bash
aws configure
aws sts get-caller-identity
sam build
sam deploy --guided --stack-name rescueroute-chennai --region eu-north-1
# Optional parameters: EnableLocation=true  AlertEmail=you@example.com
python -m pip install -r requirements-aws.txt
python scripts/publish_frontend.py --stack rescueroute-chennai --region eu-north-1
python scripts/setup_user.py --stack rescueroute-chennai --region eu-north-1 --username dispatcher
# Optional cloud retrain:
python scripts/start_sagemaker_training.py --stack rescueroute-chennai --region eu-north-1
```

Start with `EnableLocation=false`. To enable provider traffic, Places search and AWS maps, redeploy with `EnableLocation=true` and republish; see `docs/AWS_DEPLOYMENT.md`.

**Deployment status:** no resources were deployed to your account during this revision. The connected browser returned “Site Unavailable” at your AWS console URL. Your earlier account-verification message may also need resolution if AWS still shows it. Local screenshots and SDK tests do not prove cloud deployment.

## Verify

```bash
python -m unittest discover -s tests -v
```

There are 58 tests: 54 core and four optional AWS SDK adapter tests. Install `requirements-aws.txt` to run the adapter tests; otherwise they skip. The graph suite includes 3,888 A*/Dijkstra endpoint comparisons and independent Floyd–Warshall checks.

Browser checks require Node and Playwright:

```bash
npm install
npx playwright install chromium
npm run test:browser
```

Optional infrastructure lint: `cfn-lint template.yaml`. Read `docs/VERIFICATION.md`, `docs/DEMO_GUIDE.md`, `docs/PROJECT_DESIGN.md` and the PDF report. Screenshots and a sample mission export are in `docs/`.

## Directory reproduction and license

```bash
python scripts/build_hospital_catalog.py
```

This rebuilds the normalized catalog and CSV from the included OSM raw snapshot and demo seed mapping; it does not fetch new data. Directory use is attributed to © OpenStreetMap contributors under ODbL 1.0. See `backend/city/LICENSE.txt` and the snapshot metadata. Application code and synthetic examples are distinct from the licensed map data.

## Street map and different return routes

The decorative Bay of Bengal / extruded city illustration was replaced with an actual mapped road atlas. The bundled road snapshot works without an online tile server. Optional Street labels / basemap loads normal online OSM tiles when requested. Bundled street and area labels remain available offline.

**One city. Three journeys.** The preview separately searches ambulance → pickup, pickup → hospital, and hospital → pickup or ambulance base. Return is never implemented as a reversed outgoing path. OSM one-way, roundabout and motor-vehicle access screening constrain direction. A route can legitimately coincide in both directions; the UI explains when it does.

Try Arumbakkam → MIOT, Compare return, then change Eastbound / Westbound congestion. The checked balanced example uses different outgoing and return paths. Click a mapped street to close/reopen it in a browser-local what-if preview. These closures are separate from the shared 36-anchor mission controls. Road playback and the progress slider animate the selected leg; playback is not physical GPS.

The road snapshot contains 10,740 accepted ways, 25,595 segments and 21,905 graph nodes; 6,010 ways are one-way. It covers selected driving-corridor classes, not every Chennai residential alley. Travel estimates use mapped speed limits where present or assumed class speeds, plus scenario/directional weights. They are not live traffic or the synthetic RF output. Access connectors are dotted and approximate. Turn restrictions, conditional access and barriers are not modeled; do not use the preview as navigation instructions.

```bash
python scripts/build_street_network.py
```

This reproduces graph/display files from the bundled raw source. See `docs/STREET_MAP_UPDATE.md` for operation and design boundaries.
