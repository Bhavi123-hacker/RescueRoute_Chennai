"""Read and verify an existing review budget; never create, update or delete it."""
import argparse
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import sys

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


def verify_budget(client, account, name, email):
    common = {"AccountId": account, "BudgetName": name}
    budget = client.describe_budget(**common)["Budget"]
    limit = budget.get("BudgetLimit", {})
    try:
        one_dollar = Decimal(str(limit.get("Amount"))) == Decimal("1")
    except InvalidOperation:
        one_dollar = False
    if (budget.get("BudgetName") != name or budget.get("BudgetType") != "COST"
            or budget.get("TimeUnit") != "MONTHLY" or not one_dollar or limit.get("Unit") != "USD"):
        raise RuntimeError("Existing budget must be a monthly 1 USD COST budget; app deployment stopped.")
    expression = budget.get("FilterExpression")
    if expression:
        # The current console stores charge exclusions as a negated RECORD_TYPE
        # dimension and omits the deprecated CostTypes field. Accept precisely
        # Credit/Refund exclusions; service, region and tax exclusions still fail.
        negated = expression.get("Not", {})
        dimensions = negated.get("Dimensions", {})
        values = dimensions.get("Values", [])
        options = dimensions.get("MatchOptions", [])
        if (set(expression) != {"Not"} or set(negated) != {"Dimensions"}
                or set(dimensions) - {"Key", "Values", "MatchOptions"}
                or dimensions.get("Key") != "RECORD_TYPE"
                or not isinstance(values, list) or not all(isinstance(v, str) for v in values)
                or set(values) != {"Credit", "Refund"}
                or not isinstance(options, list) or not all(isinstance(v, str) for v in options)
                or set(options) - {"EQUALS", "CASE_SENSITIVE"}):
            raise RuntimeError("Saved budget filter must exclude only Credit and Refund, keeping Tax included. "
                               "Correct the filter and save the budget; app deployment stopped.")
    else:
        cost_types = budget.get("CostTypes") or {}
        if (cost_types.get("IncludeCredit") is not False
                or cost_types.get("IncludeRefund") is not False or cost_types.get("IncludeTax") is not True):
            raise RuntimeError("Existing budget must exclude credits/refunds and include tax; app deployment stopped.")
    if any(budget.get(key) for key in ("CostFilters", "AutoAdjustData", "PlannedBudgetLimits")):
        raise RuntimeError("Existing budget must be fixed and account-wide; app deployment stopped.")
    now = datetime.now(timezone.utc)
    period = budget.get("TimePeriod", {})
    if ((period.get("Start") and period["Start"] > now)
            or (period.get("End") and period["End"] <= now)):
        raise RuntimeError("Existing budget is outside its active period; app deployment stopped.")
    for threshold in (50, 80, 100):
        # Query the exact notification rather than treating incomplete list
        # responses as proof of the configured threshold type.
        notification = {"NotificationType": "ACTUAL", "ComparisonOperator": "GREATER_THAN",
                        "Threshold": threshold, "ThresholdType": "PERCENTAGE"}
        subscribers = []
        token = None
        while True:
            request = {**common, "Notification": notification}
            if token:
                request["NextToken"] = token
            result = client.describe_subscribers_for_notification(**request)
            subscribers.extend(result.get("Subscribers", []))
            token = result.get("NextToken")
            if not token:
                break
        if not any(item.get("SubscriptionType") == "EMAIL" and item.get("Address") == email
                   for item in subscribers):
            raise RuntimeError(f"Existing budget lacks the requested email alert at {threshold}%; app deployment stopped.")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--account", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--email", required=True)
    args = parser.parse_args(argv)
    session = boto3.Session(profile_name=args.profile, region_name="us-east-1")
    identity = session.client("sts").get_caller_identity()
    if identity["Account"] != args.account:
        raise RuntimeError("AWS profile resolved to a different account; app deployment stopped.")
    client = session.client("budgets", config=Config(connect_timeout=15, read_timeout=30,
                            retries={"mode": "standard", "total_max_attempts": 3}))
    verify_budget(client, args.account, args.name, args.email)
    print("Verified existing monthly $1 budget and all three email alerts. No budget changes made.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, BotoCoreError, ClientError, KeyError) as error:
        print("Existing budget verification stopped:", error, file=sys.stderr)
        sys.exit(1)
