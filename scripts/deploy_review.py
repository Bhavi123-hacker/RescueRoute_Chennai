"""Run locally with an authenticated AWS profile; check-only unless --deploy is set."""
import argparse
import getpass
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
AWS_CHANGES_STARTED = False
if __package__:
    from .local_dashboard import start_dashboard
else:
    from local_dashboard import start_dashboard


def check_credits(plan, reserve):
    """Keep a reserve; this is a point-in-time check, not a spending cap."""
    if plan.get("accountPlanType") not in {"FREE", "PAID"}:
        raise RuntimeError("AWS did not return a recognized account plan.")
    if plan.get("accountPlanStatus") != "ACTIVE":
        raise RuntimeError("The account plan is not active. Resolve this with AWS first.")
    credit = plan.get("accountPlanRemainingCredits") or {}
    amount = credit.get("amount")
    if credit.get("unit") != "USD" or not isinstance(amount, (float, int)) or not math.isfinite(amount):
        raise RuntimeError("Could not verify remaining USD credits; no deployment attempted.")
    if amount <= reserve:
        raise RuntimeError(f"Remaining credits do not exceed the ${reserve:g} reserve; stopping.")
    return amount


def run(command, environment, capture=False, timeout=60):
    result = subprocess.run(command, cwd=ROOT, env=environment, text=True,
                            capture_output=capture, timeout=timeout)
    if result.returncode:
        detail = (result.stderr or result.stdout or "").strip() if capture else "See the command output above."
        raise RuntimeError(f"{Path(command[0]).name} {command[1]} failed. {detail}")
    return result.stdout if capture else None


def fetch_json(url, token=None):
    headers = {"Cache-Control": "no-cache"}
    if token:
        headers["Authorization"] = token
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=30) as response:
        if response.status != 200:
            raise RuntimeError(f"Website/API check returned HTTP {response.status}.")
        return json.loads(response.read())


def main(argv=None):
    global AWS_CHANGES_STARTED
    AWS_CHANGES_STARTED = False
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="rescueroute-key")
    parser.add_argument("--region", default="eu-north-1")
    parser.add_argument("--stack", default="rescueroute-chennai")
    parser.add_argument("--artifact-bucket", help="Use a verified single-request upload to this existing S3 bucket")
    parser.add_argument("--reuse-existing-budget", action="store_true",
                        help="Verify the existing $1 budget and alerts without updating its CloudFormation stack")
    parser.add_argument("--local-dashboard", action="store_true",
                        help="Deploy the AWS backend without CloudFront; serve the dashboard on this PC")
    parser.add_argument("--reserve-usd", type=float, default=10)
    parser.add_argument("--deploy", action="store_true", help="Create/update AWS resources and publish the demo")
    args = parser.parse_args(argv)
    if args.reserve_usd < 10:
        raise RuntimeError("Keep at least $10 in reserve for delayed billing and other account usage.")
    if sys.version_info < (3, 12):
        raise RuntimeError("Run this script with Python 3.12 or newer. The Lambda build requires Python 3.12.")
    aws = shutil.which("aws")
    if not aws:
        raise RuntimeError("Install AWS CLI v2 first.")
    environment = os.environ.copy()
    environment.update(AWS_PROFILE=args.profile, AWS_DEFAULT_REGION=args.region,
                       AWS_REGION=args.region, AWS_PAGER="", SAM_CLI_TELEMETRY="0")
    # An explicit named profile should not accidentally inherit different credentials.
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        environment.pop(name, None)
    common = ["--profile", args.profile, "--region", args.region, "--output", "json", "--no-cli-pager"]
    billing = ["--profile", args.profile, "--region", "us-east-1", "--output", "json", "--no-cli-pager"]
    identity = json.loads(run([aws, "sts", "get-caller-identity", *common], environment, capture=True))
    if identity["Arn"].endswith(":root"):
        raise RuntimeError("Use IAM deployment credentials rather than root access keys.")
    plan = json.loads(run([aws, "freetier", "get-account-plan-state", *billing], environment, capture=True))
    remaining = check_credits(plan, args.reserve_usd)
    print(f"AWS authentication works. Plan: {plan['accountPlanType']}. Remaining credits: ${remaining:.2f}.")
    print("The $1 budget is account-wide, monthly, before credits/refunds. It is an alert, not a hard cap.")
    print("Other account resources can consume credits. This check does not estimate every resource's future cost.")
    if not args.deploy:
        print("Check-only complete. No resources created. Add --deploy when ready.")
        return
    sam = shutil.which("sam")
    if not sam:
        raise RuntimeError("Install AWS SAM CLI and reopen PowerShell. No deployment attempted.")
    email = input("Email to receive the $1 budget alerts: ").strip()
    if "@" not in email or any(char.isspace() for char in email):
        raise RuntimeError("Enter a valid budget notification email. No deployment attempted.")
    run([sys.executable, "-m", "pip", "install", "-r", "requirements-aws.txt"], environment, timeout=600)
    run([sam, "validate", "--lint", "--template-file", "template.yaml", "--region", args.region], environment, timeout=120)
    run([sam, "validate", "--lint", "--template-file", "template-budget.yaml", "--region", "us-east-1"], environment, timeout=120)
    run([sam, "build"], environment, timeout=600)
    # Recheck after the build, before uploading artifacts or creating resources.
    plan = json.loads(run([aws, "freetier", "get-account-plan-state", *billing], environment, capture=True))
    check_credits(plan, args.reserve_usd)
    # Budgets is account-wide, but its CloudFormation resource is unavailable in
    # eu-north-1. Establish alerts in us-east-1 before creating the application.
    if args.reuse_existing_budget:
        run([sys.executable, "scripts/verify_review_budget.py", "--profile", args.profile,
             "--account", identity["Account"], "--name", args.stack + "-monthly",
             "--email", email], environment, timeout=180)
        print(f"Existing $1 budget and alerts verified; app will deploy in {args.region}.")
    else:
        AWS_CHANGES_STARTED = True
        run([aws, "cloudformation", "deploy", "--template-file", "template-budget.yaml",
             "--stack-name", args.stack + "-budget", "--profile", args.profile, "--region", "us-east-1",
             "--no-fail-on-empty-changeset", "--parameter-overrides", f"BudgetName={args.stack}-monthly",
             f"BudgetAlertEmail={email}", "--tags", "Project=RescueRoute"], environment, timeout=600)
        print(f"Budget stack {args.stack}-budget deployed in us-east-1; app will deploy in {args.region}.")
    plan = json.loads(run([aws, "freetier", "get-account-plan-state", *billing], environment, capture=True))
    check_credits(plan, args.reserve_usd)
    AWS_CHANGES_STARTED = True
    artifact_options = ["--resolve-s3"]
    if args.artifact_bucket:
        run([sys.executable, "scripts/upload_review_artifact.py", "--profile", args.profile,
             "--region", args.region, "--bucket", args.artifact_bucket], environment, timeout=1800)
        artifact_options = ["--s3-bucket", args.artifact_bucket, "--template-file",
                            ".aws-sam/review/template.json"]
    run([sam, "deploy", "--stack-name", args.stack, "--region", args.region,
         *artifact_options, "--capabilities", "CAPABILITY_IAM", "--no-confirm-changeset",
         "--no-fail-on-empty-changeset", "--parameter-overrides", "EnableLocation=false",
         "EnableCustomMetrics=false", f"EnableCloudFront={'false' if args.local_dashboard else 'true'}",
         "AlertEmail=''"], environment, timeout=3600)
    run([sys.executable, "scripts/publish_frontend.py", "--stack", args.stack,
         "--region", args.region], environment, timeout=600)
    # The publishing SDK must use exactly the same profile as the CLI.
    os.environ.update(environment)
    for name in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_SECURITY_TOKEN"):
        os.environ.pop(name, None)
    import boto3
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    outputs = session.client("cloudformation").describe_stacks(StackName=args.stack)["Stacks"][0]["Outputs"]
    out = {item["OutputKey"]: item["OutputValue"] for item in outputs}
    username = "dispatcher"
    cognito = session.client("cognito-idp")
    exists = False
    try:
        cognito.admin_get_user(UserPoolId=out["UserPoolId"], Username=username)
        exists = True
    except cognito.exceptions.UserNotFoundException:
        pass
    prompt = "Existing dispatcher password: " if exists else "Set dispatcher password (12+ chars, upper/lower case, number, symbol): "
    password = getpass.getpass(prompt)
    if not exists:
        if (len(password) < 12 or not any(c.isupper() for c in password)
                or not any(c.islower() for c in password) or not any(c.isdigit() for c in password)
                or not any(not c.isalnum() and not c.isspace() for c in password)):
            raise RuntimeError("Password does not meet the policy. No operator account was created.")
        cognito.admin_create_user(UserPoolId=out["UserPoolId"], Username=username, MessageAction="SUPPRESS")
        cognito.admin_set_user_password(UserPoolId=out["UserPoolId"], Username=username, Password=password, Permanent=True)
    tokens = cognito.initiate_auth(ClientId=out["ClientId"], AuthFlow="USER_PASSWORD_AUTH",
                                  AuthParameters={"USERNAME": username, "PASSWORD": password})
    password = None
    token = tokens["AuthenticationResult"]["IdToken"]
    state = fetch_json(out["ApiUrl"] + "/api/state", token)
    if not isinstance(state, dict):
        raise RuntimeError("Authenticated state endpoint did not return an object.")
    token = None
    local_process = None
    if args.local_dashboard:
        if out.get("HostingMode") != "local" or out["WebsiteUrl"] != "http://localhost:8020":
            raise RuntimeError("Stack outputs do not match local dashboard hosting; stopping.")
        local_process = start_dashboard(ROOT, environment, out["ApiUrl"])
    for attempt in range(6):
        try:
            with urllib.request.urlopen(out["WebsiteUrl"], timeout=20) as response:
                if response.status != 200 or b"RescueRoute" not in response.read():
                    raise RuntimeError("Dashboard check failed.")
            if args.local_dashboard:
                with urllib.request.urlopen(out["WebsiteUrl"] + "/config.js", timeout=20) as response:
                    if out["ApiUrl"].encode() not in response.read():
                        raise RuntimeError("Local dashboard configuration does not match the AWS backend.")
            break
        except (urllib.error.URLError, RuntimeError):
            if attempt == 5:
                raise
            time.sleep(5)
    print("Verified: dashboard HTTP 200 and authenticated /api/state HTTP 200.")
    print("Dashboard:", out["WebsiteUrl"])
    print("Sign in as dispatcher. Run the guided mission to verify the full review journey.")
    print("After review, follow docs/AWS_DEPLOYMENT.md to remove project resources and check retained resources.")
    if args.local_dashboard:
        print("Dashboard runs on this PC; API, authentication, data and exports use AWS.")
        print("Close the dashboard server window to stop local serving. AWS resources require separate cleanup.")
        if local_process is not None:
            print("Local dashboard server PID:", local_process.pid)


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        if AWS_CHANGES_STARTED:
            print("A failed deployment may leave resources. Inspect the budget stack in us-east-1 and app stack in the chosen region before retrying or deleting anything.", file=sys.stderr)
        else:
            print("Stopped during preflight. No AWS resource creation was attempted by this run.", file=sys.stderr)
        sys.exit(1)
