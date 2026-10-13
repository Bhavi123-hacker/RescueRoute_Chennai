"""Verify cost controls offline; these tests never create AWS resources."""
import contextlib
import io
import json
import os
import unittest
from unittest.mock import patch

from backend import app
from scripts.deploy_review import check_credits, main


class ReviewDeploymentTests(unittest.TestCase):
    def test_default_logging_does_not_create_custom_metrics(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {"ENABLE_CUSTOM_METRICS": "false"}), \
                patch.object(app, "api", return_value=(200, {"ok": True})), \
                contextlib.redirect_stdout(stream):
            result = app.handler({"rawPath": "/api/state"}, None)
        record = json.loads(stream.getvalue())
        self.assertEqual(result["statusCode"], 200)
        self.assertNotIn("_aws", record)
        self.assertEqual(record["Operation"], "/api/state")

    def test_optional_metrics_preserve_error_signal(self):
        stream = io.StringIO()
        with patch.dict(os.environ, {"ENABLE_CUSTOM_METRICS": "true"}), \
                patch.object(app, "api", return_value=(409, {"error": "conflict"})), \
                contextlib.redirect_stdout(stream):
            app.handler({"rawPath": "/api/dispatch"}, None)
        record = json.loads(stream.getvalue())
        self.assertIn("_aws", record)
        self.assertEqual(record["RequestError"], 1)

    def test_verified_credit_balance_keeps_reserve(self):
        plan = {"accountPlanType": "PAID", "accountPlanStatus": "ACTIVE",
                "accountPlanRemainingCredits": {"amount": 100, "unit": "USD"}}
        self.assertEqual(check_credits(plan, 10), 100)

    def test_insufficient_unknown_or_inactive_balance_stops(self):
        base = {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE",
                "accountPlanRemainingCredits": {"amount": 10, "unit": "USD"}}
        variants = [base, {}, {**base, "accountPlanStatus": "EXPIRED"},
                    {**base, "accountPlanRemainingCredits": {"amount": 90, "unit": "EUR"}},
                    {**base, "accountPlanRemainingCredits": {"unit": "USD"}}]
        for plan in variants:
            with self.subTest(plan=plan), self.assertRaises(RuntimeError):
                check_credits(plan, 10)

    def test_check_only_never_invokes_sam_or_installs_dependencies(self):
        identity = {"Arn": "arn:aws:iam::123456789012:user/test", "Account": "123456789012"}
        plan = {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE",
                "accountPlanRemainingCredits": {"amount": 90, "unit": "USD"}}
        with patch("scripts.deploy_review.shutil.which", return_value="aws"), \
                patch("scripts.deploy_review.run", side_effect=[json.dumps(identity), json.dumps(plan)]) as run, \
                contextlib.redirect_stdout(io.StringIO()):
            main([])
        self.assertEqual([call.args[0][1:3] for call in run.call_args_list],
                         [["sts", "get-caller-identity"], ["freetier", "get-account-plan-state"]])

    def test_deploy_does_not_create_resources_when_credits_are_low(self):
        identity = {"Arn": "arn:aws:iam::123456789012:user/test"}
        plan = {"accountPlanType": "PAID", "accountPlanStatus": "ACTIVE",
                "accountPlanRemainingCredits": {"amount": 9, "unit": "USD"}}
        with patch("scripts.deploy_review.shutil.which", return_value="aws"), \
                patch("scripts.deploy_review.run", side_effect=[json.dumps(identity), json.dumps(plan)]) as run, \
                self.assertRaises(RuntimeError):
            main(["--deploy"])
        self.assertEqual(run.call_count, 2)

    def test_balance_drop_during_build_prevents_resource_creation(self):
        identity = {"Arn": "arn:aws:iam::123456789012:user/test"}
        initial = {"accountPlanType": "PAID", "accountPlanStatus": "ACTIVE",
                   "accountPlanRemainingCredits": {"amount": 90, "unit": "USD"}}
        low = {**initial, "accountPlanRemainingCredits": {"amount": 9, "unit": "USD"}}
        outputs = [json.dumps(identity), json.dumps(initial), None, None, None, json.dumps(low)]
        with patch("scripts.deploy_review.shutil.which", side_effect=lambda name: name), \
                patch("scripts.deploy_review.run", side_effect=outputs) as run, \
                patch("builtins.input", return_value="review@example.com"), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            main(["--deploy"])
        self.assertFalse(any(call.args[0][1] == "deploy" for call in run.call_args_list))


if __name__ == "__main__":
    unittest.main()
