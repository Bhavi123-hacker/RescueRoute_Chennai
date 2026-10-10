# AWS deployment — Chennai edition

## Current status

The project contains deployable SAM infrastructure and publishing/operator scripts. No resources were deployed to your AWS account during this revision: opening your supplied console URL in the connected browser returned **Site Unavailable**. This does not reveal the current account-verification status. If the earlier verification-in-progress error still appears, complete AWS account activation/support steps first. Code cannot bypass account activation.

Use an activated account and an AWS-configured local computer or CloudShell. Never paste AWS secret keys/passwords into chat or put credentials in source/client configuration.

## Services and responsibilities

| Service | Implemented role |
| --- | --- |
| Cognito | Admin-created operator account and short-lived ID token |
| API Gateway HTTP API | JWT validation, website CORS and throttling |
| Lambda | Planning, directed street preview, JSON RF inference, mission/state edits, exports and optional provider routes |
| DynamoDB | One shared demo world with consistent reads and conditional revision writes |
| S3 + CloudFront | Private static frontend with Origin Access Control |
| Private report S3 bucket | JSON mission exports, synthetic training/model artifacts and city catalog |
| CloudWatch | Seven-day logs, latency/error metrics and dispatch-error alarm |
| IAM | Scoped table, report-prefix and server-side Location routing permissions |
| Amazon Location, optional | Restricted browser basemap key; CalculateRouteMatrix and CalculateRoutes from Lambda |

Training uses scikit-learn locally, not SageMaker. There is no SMS/email service integration.

## Prerequisites and deployment

Install Python 3.12+, AWS CLI v2 and AWS SAM CLI. Configure a deployment identity with permissions to create the SAM/CloudFormation resources. An STS identity check proves credentials work, not that every service/account permission is enabled. Run from the extracted `RescueRoute_Chennai` root:

```bash
aws configure
aws sts get-caller-identity
sam build
sam deploy --guided --stack-name rescueroute-chennai --region eu-north-1
```

Confirm IAM role creation when SAM requests it. Initially keep EnableLocation=false. The same region must be used in every script. If the current Location features are unavailable in your chosen region, select a supported region and use it consistently.

```bash
python -m pip install -r requirements-aws.txt
python scripts/publish_frontend.py --stack rescueroute-chennai --region eu-north-1
python scripts/setup_user.py --stack rescueroute-chennai --region eu-north-1 --username dispatcher
```

Publishing uploads the frontend and city CSV/JSON, writes public client configuration, uploads private dataset/model/catalog artifacts and invalidates CloudFront. User setup securely prompts for a 12+ character password, suppresses Cognito messaging and creates/updates the operator. Open the printed Dashboard URL and sign in as dispatcher.

## Enable actual roads / traffic

After the basic stack works:

```bash
sam deploy --stack-name rescueroute-chennai --region eu-north-1 --parameter-overrides EnableLocation=true
python scripts/publish_frontend.py --stack rescueroute-chennai --region eu-north-1
```

The template creates a map-only API key restricted to the CloudFront referer. It is intentionally public for browser map loading and is not an AWS access key. Routing uses Lambda IAM. The AWS map loads MapLibre from a CDN. Click **Real roads & traffic** for actual provider routing; requests are explicit rather than automatic.

Lambda compares eligible configured hospitals or directory transport candidates using CalculateRouteMatrix (actual source/hospital coordinates, DepartNow, Car, FastestRoute, UseTrafficData). It sorts successful provider durations for the five earliest hospitals and fetches geometry plus up to two alternatives for the chosen destination. Traffic availability depends on provider coverage. The exact pickup coordinates are sent to the provider for this request.

Directory mode compares 621 candidates in this snapshot and can bill hundreds of matrix pairs per click, plus route/map requests. Configured-care mode is smaller. The dashboard shows timestamp, scope, requested pairs and capacity provenance. Local scenario sliders do not affect provider traffic. Provider preview is independent of the A* simulator; physical GPS, live beds, emergency driving exemptions and signal preemption are not implemented. Unknown-capacity entries are travel suggestions only.

When provider routing is disabled or fails, the app displays an error/disabled notice; it never labels modeled fallback data as live traffic.

## Check the running cloud stack

1. Open the CloudFront URL, sign in and confirm the 868-record directory loads.
2. Select a pickup and preferred hospital. Confirm five unique cards and respected destination.
3. Guided dispatch, road closure, hospital update and completion should update shared state in another signed-in window.
4. Inspect DynamoDB WORLD/DEMO and its revision after actions.
5. Export a report; verify a private S3 reports/ object and five-minute signed URL.
6. Inspect Lambda logs and RescueRoute RequestLatency/RequestError metrics.
7. If Location is enabled, request provider traffic, inspect real geometry/alternatives and shown timestamp. Check CloudWatch/provider errors if unavailable.

Save stack outputs and your own cloud screenshots for submission. Bundled local screenshots and offline SDK tests do not prove deployment.

## Costs / removal

Services can incur charges; consult current regional pricing and set an AWS Budget. Free-tier coverage is not guaranteed. Directory matrix requests are a material variable cost. To remove only your project, retain needed reports, empty its frontend/report buckets, then run:

```bash
sam delete --stack-name rescueroute-chennai --region eu-north-1
```

This deletes project resources and state. Do not empty unrelated buckets or delete unrelated stacks.

## Troubleshooting

- Activation error: complete account verification/support steps before deployment.
- 401: sign in again; confirm generated API URL, Cognito client and region.
- 409: shared revision changed; calculate a fresh plan. Live mode also returns 409 when disabled.
- No suitable destination: configure an operator demo profile, beds/ICU/care and acceptance; unknown records are excluded from dispatch.
- Location missing/timeout: confirm EnableLocation, republish, regional availability, routing IAM, key referer and CloudWatch/network errors. Provider calls can exceed the HTTP API time budget in large directory mode; configured-care scope is smaller.
- AWS script imports: install requirements-aws.txt with the same Python interpreter.

## Primary references

- AWS SAM: https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html
- HTTP API JWT: https://docs.aws.amazon.com/apigateway/latest/developerguide/http-api-jwt-authorizer.html
- DynamoDB conditional writes: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Expressions.ConditionExpressions.html
- CloudFront OAC: https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
- CalculateRouteMatrix: https://docs.aws.amazon.com/location/latest/APIReference/API_CalculateRouteMatrix.html
- CalculateRoutes: https://docs.aws.amazon.com/location/latest/APIReference/API_CalculateRoutes.html
- OSM license: https://www.openstreetmap.org/copyright
- Chennai district hospital directory: https://chennai.nic.in/public-utility-category/hospitals/

## Street atlas endpoint

The SAM stack now includes authenticated `POST /api/street-plan` and 512MB Lambda memory. The bundled directed road graph is packaged with Lambda; display geometry and vendored Leaflet assets are published to S3 by the existing script. This mode requires no Location API calls and uses scenario speed estimates. Street preview closures remain local to the browser request. Rebuild/redeploy and republish the new package to expose the feature in AWS.

Optional OSM tiles are loaded only for the visible map when requested. Attribution is visible; no bulk tile download/prefetch is implemented. Configure `tileUrl` in public frontend configuration to use another compatible provider if needed. Tile requests reveal the viewed area to the provider; selected source coordinates are not sent to a public routing demo.
