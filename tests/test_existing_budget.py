"""Verify reuse preserves alert requirements and cannot silently bypass budget checks."""
import contextlib
import copy
from datetime import datetime, timedelta, timezone
import io
import json
import unittest
from unittest.mock import MagicMock, patch

import boto3
from botocore.exceptions import ClientError
from botocore.stub import Stubber
from scripts import deploy_review
from scripts.verify_review_budget import verify_budget


class ExistingBudgetTests(unittest.TestCase):
    def setUp(self):
        self.account = "123456789012"
        self.name = "rescueroute-chennai-monthly"
        self.email = "review@example.com"
        self.budget = {"BudgetName": self.name, "BudgetType": "COST", "TimeUnit": "MONTHLY",
                       "BudgetLimit": {"Amount": "1.00", "Unit": "USD"},
                       "CostTypes": {"IncludeCredit": False, "IncludeRefund": False, "IncludeTax": True}}
        self.client = MagicMock()
        self.client.describe_budget.return_value = {"Budget": self.budget}
        self.client.describe_subscribers_for_notification.return_value = {
            "Subscribers": [{"SubscriptionType": "EMAIL", "Address": self.email}]}

    def verify(self):
        verify_budget(self.client, self.account, self.name, self.email)

    def test_matching_existing_budget_is_read_only_and_checks_each_alert(self):
        self.verify()
        calls = self.client.describe_subscribers_for_notification.call_args_list
        self.assertEqual([c.kwargs["Notification"]["Threshold"] for c in calls], [50, 80, 100])
        for call in calls:
            self.assertEqual(call.kwargs["AccountId"], self.account)
            self.assertEqual(call.kwargs["BudgetName"], self.name)
            self.assertEqual(call.kwargs["Notification"]["ThresholdType"], "PERCENTAGE")
            self.assertEqual(call.kwargs["Notification"]["NotificationType"], "ACTUAL")
        self.assertEqual({call[0] for call in self.client.method_calls},
                         {"describe_budget", "describe_subscribers_for_notification"})

    def test_real_sdk_accepts_the_verification_requests(self):
        client = boto3.client("budgets", region_name="us-east-1",
                              aws_access_key_id="testing", aws_secret_access_key="testing")
        common = {"AccountId": self.account, "BudgetName": self.name}
        with Stubber(client) as stub:
            stub.add_response("describe_budget", {"Budget": self.budget}, common)
            for threshold in (50, 80, 100):
                request = {**common, "Notification": {"NotificationType": "ACTUAL",
                    "ComparisonOperator": "GREATER_THAN", "Threshold": threshold, "ThresholdType": "PERCENTAGE"}}
                stub.add_response("describe_subscribers_for_notification",
                    {"Subscribers": [{"SubscriptionType": "EMAIL", "Address": self.email}]}, request)
            verify_budget(client, self.account, self.name, self.email)
            stub.assert_no_pending_responses()

    def test_missing_budget_or_access_denied_stops_reuse(self):
        for code in ("NotFoundException", "AccessDeniedException"):
            self.client.describe_budget.side_effect = ClientError({"Error": {"Code": code}}, "DescribeBudget")
            with self.subTest(code=code), self.assertRaises(ClientError):
                self.verify()
        self.client.describe_subscribers_for_notification.assert_not_called()

    def test_wrong_limit_scope_accounting_or_period_is_rejected(self):
        cases = [{"BudgetLimit": {"Amount": "100", "Unit": "USD"}},
                 {"BudgetLimit": {"Amount": "1", "Unit": "EUR"}}, {"TimeUnit": "DAILY"},
                 {"CostTypes": {"IncludeCredit": True, "IncludeRefund": False, "IncludeTax": True}},
                 {"CostFilters": {"Service": ["Amazon EC2"]}},
                 {"FilterExpression": {"Dimensions": {"Key": "SERVICE", "Values": ["Amazon EC2"]}}},
                 {"AutoAdjustData": {"AutoAdjustType": "HISTORICAL"}},
                 {"TimePeriod": {"End": datetime.now(timezone.utc) - timedelta(days=1)}}]
        for change in cases:
            self.client.describe_budget.return_value = {"Budget": {**copy.deepcopy(self.budget), **change}}
            with self.subTest(change=change), self.assertRaises(RuntimeError):
                self.verify()
        self.client.describe_subscribers_for_notification.assert_not_called()

    def test_missing_alert_or_wrong_recipient_stops_reuse(self):
        self.client.describe_subscribers_for_notification.return_value = {"Subscribers": []}
        with self.assertRaises(RuntimeError):
            self.verify()
        self.client.describe_subscribers_for_notification.return_value = {
            "Subscribers": [{"SubscriptionType": "EMAIL", "Address": "other@example.com"}]}
        with self.assertRaises(RuntimeError):
            self.verify()

    def test_each_notification_must_have_the_requested_email(self):
        self.client.describe_subscribers_for_notification.side_effect = [
            {"Subscribers": [{"SubscriptionType": "EMAIL", "Address": self.email}]},
            {"Subscribers": []}]
        with self.assertRaisesRegex(RuntimeError, "80%"):
            self.verify()

    def test_subscriber_pagination_keeps_verification_strict(self):
        self.client.describe_subscribers_for_notification.side_effect = [
            {"Subscribers": [], "NextToken": "next"},
            {"Subscribers": [{"SubscriptionType": "EMAIL", "Address": self.email}]},
            {"Subscribers": [{"SubscriptionType": "EMAIL", "Address": self.email}]},
            {"Subscribers": [{"SubscriptionType": "EMAIL", "Address": self.email}]}]
        self.verify()
        self.assertEqual(self.client.describe_subscribers_for_notification.call_args_list[1].kwargs["NextToken"], "next")

    def deployment_commands(self, verification=None, artifact=False):
        identity = {"Arn": "arn:aws:iam::123456789012:user/test", "Account": self.account}
        plan = {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE",
                "accountPlanRemainingCredits": {"amount": 90, "unit": "USD"}}
        replies = [json.dumps(identity), json.dumps(plan), None, None, None, None,
                   json.dumps(plan), verification, json.dumps(plan), RuntimeError("offline app stop")]
        args = ["--deploy", "--reuse-existing-budget"]
        if artifact:
            args += ["--artifact-bucket", "existing-bucket"]
            replies.insert(-1, None)
        with patch("scripts.deploy_review.shutil.which", side_effect=lambda name: name), \
                patch("scripts.deploy_review.run", side_effect=replies) as run, \
                patch("builtins.input", return_value=self.email), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            deploy_review.main(args)
        return [call.args[0] for call in run.call_args_list]

    def test_verified_budget_allows_app_without_cloudformation_budget_update(self):
        commands = self.deployment_commands()
        self.assertFalse(any(c[1:3] == ["cloudformation", "deploy"] for c in commands))
        verifier = next(c for c in commands if c[1] == "scripts/verify_review_budget.py")
        self.assertEqual(verifier[verifier.index("--account") + 1], self.account)
        self.assertEqual(verifier[verifier.index("--email") + 1], self.email)
        application = next(c for c in commands if c[:2] == ["sam", "deploy"])
        self.assertLess(commands.index(verifier), commands.index(application))
        self.assertTrue(deploy_review.AWS_CHANGES_STARTED)

    def test_failed_existing_budget_verification_prevents_any_aws_writes(self):
        commands = self.deployment_commands(RuntimeError("budget not verified"))
        self.assertFalse(any(c[:2] == ["sam", "deploy"] for c in commands))
        self.assertFalse(any(c[1:3] == ["cloudformation", "deploy"] for c in commands))
        self.assertFalse(deploy_review.AWS_CHANGES_STARTED)

    def test_budget_reuse_combines_with_single_request_artifact_upload(self):
        commands = self.deployment_commands(artifact=True)
        verifier = next(c for c in commands if c[1] == "scripts/verify_review_budget.py")
        upload = next(c for c in commands if c[1] == "scripts/upload_review_artifact.py")
        application = next(c for c in commands if c[:2] == ["sam", "deploy"])
        self.assertLess(commands.index(verifier), commands.index(upload))
        self.assertLess(commands.index(upload), commands.index(application))
        self.assertIn(".aws-sam/review/template.json", application)
        self.assertNotIn("--resolve-s3", application)
        self.assertFalse(any(c[1:3] == ["cloudformation", "deploy"] for c in commands))


if __name__ == "__main__":
    unittest.main()
