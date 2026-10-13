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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="rescueroute-key")
    parser.add_argument("--region", default="eu-north-1")
    parser.add_argument("--stack", default="rescueroute-chennai")
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
    run([sam, "validate", "--lint", "--region", args.region], environment, timeout=120)
    run([sam, "build"], environment, timeout=600)
    # Recheck after the build, before uploading artifacts or creating resources.
    plan = json.loads(run([aws, "freetier", "get-account-plan-state", *billing], environment, capture=True))
    check_credits(plan, args.reserve_usd)
    run([sam, "deploy", "--stack-name", args.stack, "--region", args.region,
         "--resolve-s3", "--capabilities", "CAPABILITY_IAM", "--no-confirm-changeset",
         "--no-fail-on-empty-changeset", "--parameter-overrides", "EnableLocation=false",
         "EnableCustomMetrics=false", "AlertEmail=''", f"BudgetAlertEmail={email}"], environment, timeout=3600)
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
    for attempt in range(6):
        try:
            with urllib.request.urlopen(out["WebsiteUrl"], timeout=20) as response:
                if response.status != 200 or b"RescueRoute" not in response.read():
                    raise RuntimeError("Dashboard check failed.")
            break
        except (urllib.error.URLError, RuntimeError):
            if attempt == 5:
                raise
            time.sleep(5)
    print("Verified: dashboard HTTP 200 and authenticated /api/state HTTP 200.")
    print("Dashboard:", out["WebsiteUrl"])
    print("Sign in as dispatcher. Run the guided mission to verify the full review journey.")
    print("After review, follow docs/AWS_DEPLOYMENT.md to remove project resources and check retained resources.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.TimeoutExpired, KeyboardInterrupt) as error:
        print(f"Stopped: {error}", file=sys.stderr)
        print("A failed deployment may leave resources. Inspect CloudFormation before retrying or deleting anything.", file=sys.stderr)
        sys.exit(1)
