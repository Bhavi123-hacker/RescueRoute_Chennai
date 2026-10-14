"""Generate a customer-managed deployment policy locally; never attach it automatically.

Also retain AWS's ReadOnlyAccess managed policy for service inspection. API Gateway
and origin-access-control writes cannot be restricted by a generated stack name;
their scope is documented below. This is not an AWS spending cap.
"""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess


def deployment_policy(account, region, stack):
    if not re.fullmatch(r"\d{12}", account):
        raise ValueError("Expected a 12-digit AWS account ID.")
    if not re.fullmatch(r"[a-z]{2}(?:-[a-z]+)+-\d", region):
        raise ValueError("Expected an AWS commercial region name.")
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9-]{0,31}", stack):
        raise ValueError("Use a stack name of at most 32 characters for generated resource prefixes.")
    statements = []

    def allow(actions, resources, condition=None):
        statement = {"Effect": "Allow", "Action": actions, "Resource": resources}
        if condition:
            statement["Condition"] = condition
        statements.append(statement)

    cf = f"arn:aws:cloudformation:{region}:{account}:stack/"
    budget_stack = f"arn:aws:cloudformation:us-east-1:{account}:stack/{stack}-budget/*"
    allow(["cloudformation:CreateStack", "cloudformation:UpdateStack", "cloudformation:CreateChangeSet",
           "cloudformation:ExecuteChangeSet", "cloudformation:DeleteChangeSet", "cloudformation:TagResource",
           "cloudformation:UntagResource"], [cf + stack + "/*", cf + "aws-sam-cli-managed-default/*", budget_stack])
    allow(["cloudformation:DeleteStack"], [cf + stack + "/*", cf + "aws-sam-cli-managed-default/*", budget_stack])
    allow(["cloudformation:CreateChangeSet"],
          [f"arn:aws:cloudformation:{region}:aws:transform/Serverless-2016-10-31"])
    buckets = [f"arn:aws:s3:::{stack.lower()}-*", "arn:aws:s3:::aws-sam-cli-managed-default-*"]
    allow(["s3:CreateBucket", "s3:PutBucketPolicy", "s3:DeleteBucketPolicy", "s3:PutBucketPublicAccessBlock",
           "s3:PutBucketOwnershipControls", "s3:PutEncryptionConfiguration", "s3:PutBucketTagging",
           "s3:PutBucketVersioning"], buckets)
    allow(["s3:DeleteBucket"], buckets)
    allow(["s3:PutObject", "s3:DeleteObject", "s3:AbortMultipartUpload"], [bucket + "/*" for bucket in buckets])
    roles = [f"arn:aws:iam::{account}:role/{stack}-BackendRole-*",
             f"arn:aws:iam::{account}:role/{stack}-SageMakerRole-*"]
    allow(["iam:CreateRole", "iam:DeleteRole", "iam:UpdateAssumeRolePolicy", "iam:PutRolePolicy",
           "iam:DeleteRolePolicy", "iam:TagRole", "iam:UntagRole"], roles)
    allow(["iam:AttachRolePolicy", "iam:DetachRolePolicy"], [roles[0]],
          {"ArnEquals": {"iam:PolicyARN": ["arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                                          "arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess",
                                          "arn:aws:iam::aws:policy/AWSXRayDaemonWriteAccess"]}})
    allow(["iam:PassRole"], [roles[0]], {"StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}})
    allow(["lambda:CreateFunction", "lambda:UpdateFunctionCode", "lambda:UpdateFunctionConfiguration",
           "lambda:DeleteFunction", "lambda:AddPermission", "lambda:RemovePermission",
           "lambda:TagResource", "lambda:UntagResource"],
          [f"arn:aws:lambda:{region}:{account}:function:{stack}-*"])
    allow(["dynamodb:CreateTable", "dynamodb:UpdateTable", "dynamodb:DeleteTable", "dynamodb:UpdateTimeToLive",
           "dynamodb:TagResource", "dynamodb:UntagResource"],
          [f"arn:aws:dynamodb:{region}:{account}:table/{stack}-*"])
    # CloudFormation stage creation checks TagResource, which isn't listed as a
    # named IAM action in API Gateway's public HTTP-verb authorization model.
    # Cover its management actions on the same selected-region API paths only.
    allow(["apigateway:*"],
          [f"arn:aws:apigateway:{region}::/apis", f"arn:aws:apigateway:{region}::/apis/*",
           f"arn:aws:apigateway:{region}::/tags/arn%3Aaws%3Aapigateway%3A{region}%3A%3A%2Fv2%2Fapis%2F*"])
    project_tag = {"StringEquals": {"aws:ResourceTag/Project": "RescueRoute"}}
    allow(["cognito-idp:CreateUserPool"], ["*"],
          {"StringEquals": {"aws:RequestTag/Project": "RescueRoute"}})
    allow(["cognito-idp:UpdateUserPool", "cognito-idp:DeleteUserPool", "cognito-idp:CreateUserPoolClient",
           "cognito-idp:UpdateUserPoolClient", "cognito-idp:DeleteUserPoolClient", "cognito-idp:AdminGetUser",
           "cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword",
           "cognito-idp:TagResource", "cognito-idp:UntagResource"],
          [f"arn:aws:cognito-idp:{region}:{account}:userpool/*"], project_tag)
    allow(["cloudfront:CreateDistribution", "cloudfront:CreateConnectionGroup"], ["*"],
          {"StringEquals": {"aws:RequestTag/Project": "RescueRoute"}})
    allow(["cloudfront:UpdateDistribution", "cloudfront:DeleteDistribution", "cloudfront:CreateInvalidation",
           "cloudfront:TagResource", "cloudfront:UntagResource"],
          [f"arn:aws:cloudfront::{account}:distribution/*"], project_tag)
    allow(["cloudfront:TagResource"], [f"arn:aws:cloudfront::{account}:distribution/*",
                                       f"arn:aws:cloudfront::{account}:connection-group/*"],
          {"StringEquals": {"aws:RequestTag/Project": "RescueRoute"}})
    allow(["cloudfront:CreateOriginAccessControl", "cloudfront:UpdateOriginAccessControl",
           "cloudfront:DeleteOriginAccessControl"], ["*"])
    topic = f"arn:aws:sns:{region}:{account}:{stack}-mission-alerts"
    allow(["sns:CreateTopic", "sns:SetTopicAttributes", "sns:DeleteTopic", "sns:Subscribe", "sns:Unsubscribe",
           "sns:TagResource", "sns:UntagResource"], [topic, topic + ":*"])
    allow(["logs:CreateLogGroup", "logs:PutRetentionPolicy", "logs:DeleteRetentionPolicy", "logs:DeleteLogGroup",
           "logs:TagLogGroup", "logs:UntagLogGroup", "logs:TagResource", "logs:UntagResource"],
          [f"arn:aws:logs:{region}:{account}:log-group:/aws/lambda/{stack}-*",
           f"arn:aws:logs:{region}:{account}:log-group:/aws/lambda/{stack}-*:*" ])
    allow(["budgets:ModifyBudget", "budgets:ViewBudget", "budgets:TagResource", "budgets:UntagResource"],
          [f"arn:aws:budgets::{account}:budget/{stack}-monthly"])
    allow(["freetier:GetAccountPlanState"], ["*"])
    statements.append({"Effect": "Deny", "Action": ["freetier:UpgradeAccountPlan", "organizations:*",
                        "sagemaker:CreateTrainingJob", "sagemaker:CreateEndpoint",
                        "geo-routes:*", "geo-places:*", "geo-maps:*"], "Resource": "*"})
    policy = {"Version": "2012-10-17", "Statement": statements}
    if len(json.dumps(policy, separators=(",", ":"))) > 6144:
        raise ValueError("Policy exceeds the customer-managed policy size limit.")
    return policy


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="rescueroute-key")
    parser.add_argument("--region", default="eu-north-1")
    parser.add_argument("--stack", default="rescueroute-chennai")
    args = parser.parse_args()
    aws = shutil.which("aws")
    if not aws:
        parser.error("Install AWS CLI v2 first.")
    result = subprocess.run([aws, "sts", "get-caller-identity", "--profile", args.profile,
                             "--region", args.region, "--output", "json", "--no-cli-pager"],
                            capture_output=True, text=True, timeout=60)
    if result.returncode:
        parser.error(result.stderr.strip())
    account = json.loads(result.stdout)["Account"]
    policy = deployment_policy(account, args.region, args.stack)
    path = Path(__file__).resolve().parents[1] / "review-deployment-policy.json"
    path.write_text(json.dumps(policy, indent=2) + "\n", encoding="utf-8")
    print("Generated:", path)
    print("In your root/admin console: IAM > Policies > Create policy > JSON. Paste this file,")
    print("name it RescueRouteReviewDeployment, then attach it to your IAM deployment user.")
    print("Retain ReadOnlyAccess. This generator only reads STS and writes a local file; it never attaches policies.")
    print("API Gateway writes cover APIs in the selected region; OAC writes are not stack-name scoped.")
    print("Remove this deployment policy and deactivate its access key when the project is removed after review.")
