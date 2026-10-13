"""Check the generated deployment policy's account and privilege boundaries."""
import json
import unittest

from scripts.make_deployment_policy import deployment_policy


class DeploymentPolicyTests(unittest.TestCase):
    def setUp(self):
        self.policy = deployment_policy("123456789012", "eu-north-1", "rescueroute-chennai")

    def test_managed_policy_fits_and_excludes_unrestricted_admin_grants(self):
        self.assertLessEqual(len(json.dumps(self.policy, separators=(",", ":"))), 6144)
        for statement in self.policy["Statement"]:
            if statement["Effect"] == "Allow":
                self.assertNotIn("*", statement["Action"])
                self.assertNotIn("iam:*", statement["Action"])
                self.assertNotIn("AdministratorAccess", json.dumps(statement))

    def test_budget_is_named_and_account_scoped_and_role_passing_is_limited(self):
        budget = next(s for s in self.policy["Statement"] if "budgets:ModifyBudget" in s["Action"])
        self.assertEqual(budget["Resource"], ["arn:aws:budgets::123456789012:budget/rescueroute-chennai-monthly"])
        passing = next(s for s in self.policy["Statement"] if "iam:PassRole" in s["Action"])
        self.assertEqual(passing["Condition"]["StringEquals"]["iam:PassedToService"], "lambda.amazonaws.com")
        self.assertEqual(passing["Resource"], ["arn:aws:iam::123456789012:role/rescueroute-chennai-BackendRole-*"])

    def test_upgrade_training_and_location_are_denied(self):
        denied = {action for s in self.policy["Statement"] if s["Effect"] == "Deny" for action in s["Action"]}
        self.assertTrue({"freetier:UpgradeAccountPlan", "organizations:*", "sagemaker:CreateTrainingJob",
                         "sagemaker:CreateEndpoint", "geo-routes:*", "geo-places:*", "geo-maps:*"} <= denied)

    def test_budget_stack_can_be_created_and_removed_only_at_its_named_arn(self):
        arn = "arn:aws:cloudformation:us-east-1:123456789012:stack/rescueroute-chennai-budget/*"
        for action in ("cloudformation:CreateChangeSet", "cloudformation:ExecuteChangeSet", "cloudformation:DeleteStack"):
            statement = next(s for s in self.policy["Statement"] if action in s["Action"])
            self.assertIn(arn, statement["Resource"])
            self.assertNotIn("*", statement["Resource"])

    def test_invalid_identifiers_are_rejected(self):
        for args in [("bad", "eu-north-1", "rescueroute-chennai"),
                     ("123456789012", "bad region", "rescueroute-chennai"),
                     ("123456789012", "eu-north-1", "*")]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                deployment_policy(*args)


if __name__ == "__main__":
    unittest.main()
