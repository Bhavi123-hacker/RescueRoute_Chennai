"""Check the generated deployment policy's account and privilege boundaries."""
import json
import fnmatch
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

    def test_api_management_covers_stage_tagging_only_in_the_selected_region(self):
        api = next(s for s in self.policy["Statement"] if "apigateway:*" in s["Action"])
        self.assertEqual(api["Resource"], ["arn:aws:apigateway:eu-north-1::/apis",
                                          "arn:aws:apigateway:eu-north-1::/apis/*",
                                          "arn:aws:apigateway:eu-north-1::/tags/arn%3Aaws%3Aapigateway%3Aeu-north-1%3A%3A%2Fv2%2Fapis%2F*"])
        for resource in ("arn:aws:apigateway:eu-north-1::/apis/example/stages",
                         "arn:aws:apigateway:eu-north-1::/apis/example/stages/prod"):
            self.assertTrue(any(fnmatch.fnmatchcase(resource, scope) for scope in api["Resource"]))
        for resource in ("arn:aws:apigateway:us-east-1::/apis/example/stages",
                         "arn:aws:apigateway:eu-north-1::/domainnames/example.com"):
            self.assertFalse(any(fnmatch.fnmatchcase(resource, scope) for scope in api["Resource"]))

    def test_sam_transform_versioning_and_failed_support_stack_cleanup(self):
        def resources_for(action):
            return [r for s in self.policy["Statement"] if s["Effect"] == "Allow"
                    and action in s["Action"] for r in s["Resource"]]
        self.assertIn("arn:aws:cloudformation:eu-north-1:aws:transform/Serverless-2016-10-31",
                      resources_for("cloudformation:CreateChangeSet"))
        self.assertIn("arn:aws:cloudformation:eu-north-1:123456789012:stack/aws-sam-cli-managed-default/*",
                      resources_for("cloudformation:DeleteStack"))
        for action in ("s3:PutBucketVersioning", "s3:DeleteBucket"):
            self.assertIn("arn:aws:s3:::aws-sam-cli-managed-default-*", resources_for(action))
        self.assertEqual(resources_for("dynamodb:UpdateTimeToLive"),
                         ["arn:aws:dynamodb:eu-north-1:123456789012:table/rescueroute-chennai-*"])

    def test_role_attachments_cover_sam_generated_policies_without_admin_policy_grants(self):
        attachments = next(s for s in self.policy["Statement"] if "iam:AttachRolePolicy" in s["Action"])
        self.assertEqual(set(attachments["Condition"]["ArnEquals"]["iam:PolicyARN"]), {
            "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
            "arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess",
            "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"})
        self.assertEqual(attachments["Resource"], [
            "arn:aws:iam::123456789012:role/rescueroute-chennai-BackendRole-*"])

    def test_http_api_encoded_tag_endpoint_matches_the_actual_failure_arn(self):
        api = next(s for s in self.policy["Statement"] if "apigateway:*" in s["Action"])
        actual = "arn:aws:apigateway:eu-north-1::/tags/arn%3Aaws%3Aapigateway%3Aeu-north-1%3A%3A%2Fv2%2Fapis%2F*"
        self.assertTrue(any(fnmatch.fnmatchcase(actual, scope) for scope in api["Resource"]))
        unrelated = "arn:aws:apigateway:eu-north-1::/tags/arn%3Aaws%3Aapigateway%3Aeu-north-1%3A%3A%2Fdomainnames%2Fexample.com"
        self.assertFalse(any(fnmatch.fnmatchcase(unrelated, scope) for scope in api["Resource"]))


if __name__ == "__main__":
    unittest.main()
