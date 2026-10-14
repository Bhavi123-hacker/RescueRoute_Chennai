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
| CloudWatch | 14-day logs; custom metrics and dispatch alarm are optional |
| IAM | Scoped table, report-prefix and server-side Location routing permissions |
| Amazon Location, optional | Restricted browser basemap key; CalculateRouteMatrix and CalculateRoutes from Lambda |

Training uses scikit-learn locally by default. The SAM stack also creates a SageMaker execution role and `scripts/start_sagemaker_training.py` for optional cloud retraining. SNS mission alerts are enabled when you pass `AlertEmail`; WebSocket fan-out is provisioned. Active X-Ray tracing is disabled, and custom CloudWatch metrics/alarms default to disabled for a temporary review.

## Temporary review with a 1 USD monitoring budget

### AWS backend with a temporary dashboard on your PC

When CloudFront account verification blocks creation, add `--local-dashboard`.
It sets `EnableCloudFront=false` and omits the distribution, origin access control,
frontend bucket and frontend bucket policy. Lambda, HTTP/WebSocket API Gateway,
Cognito, DynamoDB, private report S3, SNS and IAM remain on AWS. API CORS permits
exactly `http://localhost:8020`; Cognito authorization remains enabled. The
CloudFront deployment is still the default.

```powershell
py -3.12 scripts/deploy_review.py --profile rescueroute-key --deploy --reuse-existing-budget --artifact-bucket YOUR_EXISTING_SAM_BUCKET --local-dashboard
```

Apply the latest generated deployment policy first, including SAM's X-Ray policy
attachment and HTTP API's encoded `/tags/arn%3Aaws...%2Fv2%2Fapis%2F*` endpoint.
The local mode runs a native, read-only IAM simulation before changing the app or
uploading artifacts. With ReadOnlyAccess attached, run it separately before a build:

```powershell
py -3.12 scripts/check_deployment_permissions.py --profile rescueroute-key
```

After permissions pass, the helper removes only a `ROLLBACK_COMPLETE` app stack
whose resources are all already `DELETE_COMPLETE`, then waits for deletion.
It preserves healthy stacks and refuses to delete retained or undeleted resources.
Preserve the budget and healthy SAM support stack/bucket.
The helper retains credit/reserve checks, budget/alert verification,
single-request artifact upload, and disabled Location/custom metrics.

The publisher writes local client configuration and uploads private model/catalog
artifacts. The helper securely provisions the dispatcher, verifies the authenticated
AWS state endpoint, and starts a separate static-server window on Windows. Open
the printed `http://localhost:8020` URL and sign in. This serves only the frontend
directory, bound to `127.0.0.1`; no public website is published. An unrelated busy
port is not terminated. Close the server window after review; AWS cleanup is
separate. On other operating systems, the printed server PID is also saved under
`.aws-sam/review/local-dashboard.pid`.

After successful stack, login, API and page checks, the helper writes
`.aws-sam/review/aws-screenshots.md`, listing actual CloudFormation resource IDs
and honest screenshot captions for your report. Capture these in your own AWS
Console. In local mode do not claim CloudFront hosting, Location routing or
SageMaker training. A SageMaker IAM role alone does not demonstrate training.

Document this mode as an AWS backend with a local dashboard. It does not establish
CloudFront usage or clear the account's verification restriction. Other account
or service restrictions may still prevent deployment, so the authenticated AWS
session must complete the actual cloud validation.

The helper first deploys `template-budget.yaml` as the separate **rescueroute-chennai-budget** CloudFormation stack in **us-east-1**. The Budgets CloudFormation resource is unavailable in the app's **eu-north-1** region, so it is absent from `template.yaml`. This budget still monitors account-wide costs across regions. Both templates are validated in their actual deployment regions before resources are created; a failed budget deployment stops the app deployment. A custom `--stack NAME` uses `NAME-budget` for this stack.

The budget is **account-wide and monthly with a 1 USD limit**, with email alerts above 0.50, 0.80 and 1.00 USD. `BudgetAlertEmail` is required on the budget template and separate from optional mission-alert recipients. Credits and refunds are excluded from this budget so credit-covered usage remains visible. Other AWS resources and earlier usage in the same month also count; alerts may therefore fire immediately. This is not an incremental project budget, an account spending cap, or a guarantee of free usage. Budgets notifications can arrive after charges have accrued. The budget resets each month and does not monitor lifetime spending.

Run the helper directly in your own PowerShell terminal if the coding agent's shell is stalled. It uses the named profile, verifies an active account plan and more than 10 USD remaining credits, checks again immediately before deployment, keeps Location/custom metrics disabled, builds/publishes the app, sets up the dispatcher and checks the public dashboard plus authenticated state API. It does not upgrade the account or run SageMaker training. Default execution is read-only:

```powershell
py -3.12 scripts/deploy_review.py --profile rescueroute-key
```

After prerequisites and deployment permissions are ready, explicitly deploy:

```powershell
py -3.12 scripts/deploy_review.py --profile rescueroute-key --deploy
```

Enter your budget-alert email and dispatcher password locally when prompted. Do not share access keys, passwords, authentication URLs or tokens. Check `aws sts get-caller-identity --profile rescueroute-key` first. IAM `ReadOnlyAccess` can authenticate and inspect resources but cannot deploy this stack; the helper reports service errors and never grants itself permissions. If the Free Tier plan API is unsupported or denied, it stops without deploying. AWS account verification restrictions also cannot be bypassed.

If preflight reports `AccessDeniedException` for `freetier:GetAccountPlanState`, an account administrator can add the following inline policy to the IAM deployment user. This only permits the balance/plan check; it does not grant deployment rights or permission to upgrade the account. Free Tier actions do not support resource-scoped ARNs, so this single read action requires `Resource: "*"`.

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": "freetier:GetAccountPlanState",
    "Resource": "*"
  }]
}
```

Test the read operation in `us-east-1` before retrying deployment:

```powershell
aws freetier get-account-plan-state --profile rescueroute-key --region us-east-1
```

Policy reference: https://docs.aws.amazon.com/service-authorization/latest/reference/list_freetier.html

### Retry an interrupted artifact upload

If SAM's multipart upload repeatedly times out or closes its connection, preserve
the healthy SAM support stack and pass its existing bucket to the review helper:

```powershell
py -3.12 scripts/deploy_review.py --profile rescueroute-key --deploy --artifact-bucket YOUR_EXISTING_SAM_BUCKET
```

This option packages the built backend into a repeatable ZIP, uploads it with one
S3 PutObject request (no multipart transfer), and supplies SAM a template with the
remote artifact reference. The upload uses a 300-second response timeout, up to
four SDK attempts, an MD5 integrity check, SHA-256 object metadata, and SSE-S3
encryption. A matching existing object is reused. The bucket's owner and region
are checked; no bucket is created and no TLS checks are disabled. Deployment
stops if upload or verification fails. A persistently broken network can still
prevent upload; try another connection if the new method also fails.

### Deployment permissions for the review

If a budget stack update reports that the same budget name exists with a different
internal ID, preserve the existing budget. Add `--reuse-existing-budget` to the
review helper and enter the email already subscribed to it. This path reads the
named budget and verifies a fixed account-wide monthly 1 USD COST limit, exclusion
of credits/refunds, inclusion of tax, an active period, and email notifications
at 50%, 80%, and 100% of actual spend. It makes no CloudFormation budget update
and no direct budget changes. Missing budgets, denied reads, mismatched settings,
or missing alerts stop application deployment. The option can be combined with
`--artifact-bucket`. It verifies monitoring without repairing the budget stack's
CloudFormation resource identity; inspect that identity before later cleanup.

Budget verification supports both legacy `CostTypes` flags and the current
console's `FilterExpression`. The accepted modern expression excludes exactly
the `RECORD_TYPE` values `Credit` and `Refund` using `Not`; it keeps tax included
and does not restrict services or regions. An expression excluding `Tax` fails
with instructions to save the correct filter. Unsaved console edits do not alter
the API response. Check the saved budget before rebuilding the app:

```powershell
py -3.12 scripts/verify_review_budget.py --profile rescueroute-key --account YOUR_ACCOUNT_ID --name rescueroute-chennai-monthly --email YOUR_BUDGET_EMAIL
```

If the IAM user only has `ReadOnlyAccess`, generate the additional deployment policy locally:

```powershell
py -3.12 scripts/make_deployment_policy.py --profile rescueroute-key
notepad review-deployment-policy.json
```

The generator only reads STS and creates a local JSON file, which is ignored by Git. In your existing root/admin console, open **IAM > Policies > Create policy > JSON**, paste that JSON and create the customer-managed policy **RescueRouteReviewDeployment**. Then open **IAM > Users > your deployment user > Permissions > Add permissions > Attach policies directly** and attach it. Retain `ReadOnlyAccess` for service inspection. This policy is over the inline-user-policy size limit; create it as a customer-managed policy, not an inline user policy.

The policy includes the Free Tier plan read, CloudFormation, packaging/publishing, operator setup and the stack's services. CloudFormation grants include only the named application/budget stacks and the shared SAM packaging stack. If you previously generated the policy before the budget was split out, regenerate it and replace the JSON in **IAM > Policies > RescueRouteReviewDeployment > Edit > JSON**, then save the new default version. This adds the named budget stack permissions in `us-east-1`; reattaching the same policy is unnecessary.

Named resources are limited to the stack prefixes; Cognito/CloudFront modifications use the `Project=RescueRoute` tag, which the template explicitly applies. API Gateway management uses `apigateway:*` only on `/apis` and `/apis/*` in the selected region, including stage tagging checked by CloudFormation. API IDs are allocated during creation; this grant therefore also covers other APIs in that region. It does not cover custom domains, other regions, or other AWS services. CloudFront origin-access-control writes are not name-scoped; new distribution tagging can apply the project tag. These broader grants should only be used by a trusted deployment operator and removed after review. The shared SAM artifact bucket also has upload/delete permissions; never delete unrelated artifacts or its healthy shared stack.

The corrected generator includes SAM transform access, SAM bucket versioning and
failed-support-stack cleanup, and DynamoDB TTL configuration. Existing users must
regenerate `review-deployment-policy.json` and replace the customer-managed
policy's JSON, saving the new version as default. This does not alter AWS resource
state by itself. If the app stack is `ROLLBACK_COMPLETE` after a failed initial
creation, inspect its Events and Resources first. Once all its attempted resources
are deleted (as shown in the supplied stage-tagging failure log), remove only the
failed application stack and wait for deletion before retrying. Preserve the
healthy budget and shared SAM stack/bucket.

It explicitly denies account-plan upgrade, Organizations operations, Location API calls and SageMaker training/endpoint creation for this user. This is not a permissions boundary for Lambda execution roles or a spending cap. Service control policies, permission boundaries, expired credentials or account verification can still block a deployment. No policy is created or attached automatically by the helper.

API throttling is 2 requests/second with a burst of 5. DynamoDB remains on demand for the review: the shared world is a large document, so a blind switch to a very small provisioned table can throttle normal mutations. On-demand requests consume credits or accrue charges. Reserve funds and current balance checks reduce risk but do not account for all future usage, attacks, taxes, expired credits or unrelated resources. A private/unshared URL is not a cost control. Keep the demo short, close unused tabs, avoid repeated benchmarks and remove resources after review.

The authenticated dispatcher protects API operations, while frontend assets remain publicly hosted through CloudFront. Budget notifications, low traffic and these defaults do not enforce an absolute 1 USD or 100 USD ceiling.

## Prerequisites and deployment

Install Python 3.12+, AWS CLI v2 and AWS SAM CLI. Configure a deployment identity with permissions to create the SAM/CloudFormation resources. An STS identity check proves credentials work, not that every service/account permission is enabled. Run from the extracted `RescueRoute_Chennai` root:

```bash
aws configure
aws sts get-caller-identity
aws cloudformation deploy --template-file template-budget.yaml --stack-name rescueroute-chennai-budget --region us-east-1 --parameter-overrides BudgetName=rescueroute-chennai-monthly BudgetAlertEmail=you@example.com --no-fail-on-empty-changeset
sam build
sam deploy --guided --stack-name rescueroute-chennai --region eu-north-1
```

Replace the example email with your own for cost notifications. Confirm IAM role creation when SAM requests it. Initially keep EnableLocation=false and EnableCustomMetrics=false. Use the same application region in the app scripts; only the budget stack deploys in us-east-1. If the current Location features are unavailable in your chosen region, select a supported region and use it consistently.

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
6. Inspect Lambda logs. RescueRoute custom metrics/dispatch alarm require EnableCustomMetrics=true and can incur charges.
7. If Location is enabled, request provider traffic, inspect real geometry/alternatives and shown timestamp. Check CloudWatch/provider errors if unavailable.

Save stack outputs and your own cloud screenshots for submission. Bundled local screenshots and offline SDK tests do not prove deployment.

## Costs / removal

Services can incur charges; consult current regional pricing and set an AWS Budget. Free-tier coverage is not guaranteed. Directory matrix requests are a material variable cost. To remove only your project, retain needed reports, empty its frontend/report buckets, then run:

```bash
sam delete --stack-name rescueroute-chennai --region eu-north-1
```

Confirm application cleanup before removing its monitoring budget. Then remove the separate budget stack:

```powershell
aws cloudformation delete-stack --stack-name rescueroute-chennai-budget --region us-east-1 --profile rescueroute-key
aws cloudformation wait stack-delete-complete --stack-name rescueroute-chennai-budget --region us-east-1 --profile rescueroute-key
```

This deletes project resources and state. Do not empty unrelated buckets or delete unrelated stacks. The shared SAM packaging stack/bucket is separate; leave unrelated artifacts intact. Remove the deployment policy and deactivate its access key after cleanup.

## Troubleshooting

If CloudFront reports "Your account must be verified before you can add new
CloudFront resources", stop retrying deployment and contact AWS Support through
an Account and billing case. Include the exact error, eu-north-1 application
region and request ID from the failed distribution event. IAM permissions cannot
resolve this account-verification restriction. The CloudFront-based architecture
remains blocked until AWS clears it; no account upgrade is required by this workflow.

For the separate BackendRole AttachRolePolicy failure, the deployment generator
now permits the exact AWSXrayWriteOnlyAccess policy that SAM automatically adds
when the Tracing property is present, along with the basic Lambda logging policy
and the template's explicit AWSXRayDaemonWriteAccess. The attachment grant remains
limited to the project's BackendRole prefix and those three policies. Regenerate the
deployment policy and update its default JSON before a later retry. PassThrough
tracing remains configured; this permission does not enable active tracing.

For `Api CREATE_FAILED` with `apigateway:POST` on an encoded `/tags/arn%3Aaws...`
resource, regenerate the deployment policy and replace its DEFAULT JSON version.
The grant covers only encoded HTTP/WebSocket API tagging paths in the chosen region;
it does not include domain or unrelated regional management paths. The temporary
backend permission preflight checks this exact path before another deployment.
IAM simulation cannot establish account verification, service availability or
quotas; successful live deployment and demonstration still need your AWS session.

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

The SAM stack now includes authenticated `POST /api/street-plan` and 1024MB Lambda memory. The bundled directed road graph is packaged with Lambda; display geometry and vendored Leaflet assets are published to S3 by the existing script. This mode requires no Location API calls and uses scenario speed estimates. Street preview closures remain local to the browser request. Rebuild/redeploy and republish the new package to expose the feature in AWS.

Optional OSM tiles are loaded only for the visible map when requested. Attribution is visible; no bulk tile download/prefetch is implemented. Configure `tileUrl` in public frontend configuration to use another compatible provider if needed. Tile requests reveal the viewed area to the provider; selected source coordinates are not sent to a public routing demo.
