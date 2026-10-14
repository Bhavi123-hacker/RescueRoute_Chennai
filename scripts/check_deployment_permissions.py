"""Read-only IAM simulation of permissions used by the temporary AWS backend."""
import argparse
import sys
import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


def permission_groups(account, region, stack):
    role = f"arn:aws:iam::{account}:role/{stack}-BackendRole-permissionprobe"
    prefix = f"arn:aws:apigateway:{region}::"
    groups = [
        (f"arn:aws:cloudformation:{region}:{account}:stack/{stack}/permissionprobe",
         ["cloudformation:CreateStack", "cloudformation:UpdateStack", "cloudformation:CreateChangeSet",
          "cloudformation:ExecuteChangeSet", "cloudformation:DeleteChangeSet", "cloudformation:DeleteStack"], None),
        (f"arn:aws:cloudformation:{region}:aws:transform/Serverless-2016-10-31",
         ["cloudformation:CreateChangeSet"], None),
        (f"arn:aws:s3:::{stack}-reportbucket-permissionprobe",
         ["s3:CreateBucket", "s3:PutBucketPublicAccessBlock", "s3:PutEncryptionConfiguration",
          "s3:PutBucketTagging", "s3:DeleteBucket"], None),
        (f"arn:aws:s3:::{stack}-reportbucket-permissionprobe/training/test.json",
         ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"], None),
        (f"arn:aws:dynamodb:{region}:{account}:table/{stack}-ConnectionsTable-permissionprobe",
         ["dynamodb:CreateTable", "dynamodb:UpdateTable", "dynamodb:UpdateTimeToLive",
          "dynamodb:TagResource", "dynamodb:DeleteTable"], None),
        (role, ["iam:CreateRole", "iam:PutRolePolicy", "iam:DeleteRolePolicy", "iam:TagRole",
                "iam:DeleteRole", "iam:PassRole"], None),
        (f"arn:aws:iam::{account}:role/{stack}-SageMakerRole-permissionprobe",
         ["iam:CreateRole", "iam:PutRolePolicy", "iam:TagRole", "iam:DeleteRolePolicy", "iam:DeleteRole"], None),
        (f"arn:aws:lambda:{region}:{account}:function:{stack}-Backend-permissionprobe",
         ["lambda:CreateFunction", "lambda:UpdateFunctionCode", "lambda:AddPermission",
          "lambda:RemovePermission", "lambda:TagResource", "lambda:DeleteFunction"], None),
        (f"arn:aws:cognito-idp:{region}:{account}:userpool/{region}_permissionprobe",
         ["cognito-idp:CreateUserPool", "cognito-idp:CreateUserPoolClient", "cognito-idp:TagResource",
          "cognito-idp:AdminGetUser", "cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword",
          "cognito-idp:DeleteUserPoolClient", "cognito-idp:DeleteUserPool"], None),
        (f"arn:aws:sns:{region}:{account}:{stack}-mission-alerts",
         ["sns:CreateTopic", "sns:SetTopicAttributes", "sns:TagResource", "sns:DeleteTopic"], None),
        (f"arn:aws:logs:{region}:{account}:log-group:/aws/lambda/{stack}-Backend-permissionprobe",
         ["logs:CreateLogGroup", "logs:PutRetentionPolicy", "logs:TagResource", "logs:DeleteLogGroup"], None),
    ]
    for path in ("/apis", "/apis/permissionprobe", "/apis/permissionprobe/stages",
                 f"/tags/arn%3Aaws%3Aapigateway%3A{region}%3A%3A%2Fv2%2Fapis%2Fpermissionprobe"):
        groups.append((prefix + path, ["apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE"], None))
    for policy in ("service-role/AWSLambdaBasicExecutionRole", "AWSXrayWriteOnlyAccess", "AWSXRayDaemonWriteAccess"):
        groups.append((role, ["iam:AttachRolePolicy", "iam:DetachRolePolicy"], f"arn:aws:iam::aws:policy/{policy}"))
    return groups


def check_permissions(iam, principal, account, region, stack):
    if not principal.startswith(f"arn:aws:iam::{account}:user/"):
        raise RuntimeError("Use the IAM deployment-user profile for this permission check.")
    denied = []
    checked = 0
    for resource, actions, policy in permission_groups(account, region, stack):
        values = {"aws:RequestTag/Project": "RescueRoute", "aws:ResourceTag/Project": "RescueRoute",
                  "iam:PassedToService": "lambda.amazonaws.com"}
        if policy:
            values["iam:PolicyARN"] = policy
        request = {"PolicySourceArn": principal, "ActionNames": actions, "ResourceArns": [resource],
                   "ContextEntries": [{"ContextKeyName": name, "ContextKeyValues": [value],
                                       "ContextKeyType": "string"} for name, value in values.items()]}
        results = []
        while True:
            response = iam.simulate_principal_policy(**request)
            results.extend(response["EvaluationResults"])
            if not response.get("IsTruncated"):
                break
            request["Marker"] = response["Marker"]
        decisions = {item["EvalActionName"]: item for item in results}
        for action in actions:
            checked += 1
            result = decisions.get(action, {})
            if result.get("EvalDecision") != "allowed":
                denied.append(f"{action} on {resource}: {result.get('EvalDecision', 'no result')}")
    if denied:
        raise RuntimeError("Permission preflight failed; update the deployment policy's DEFAULT version first:\n"
                           + "\n".join(denied))
    return checked


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", default="rescueroute-key")
    parser.add_argument("--region", default="eu-north-1")
    parser.add_argument("--stack", default="rescueroute-chennai")
    args = parser.parse_args(argv)
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    identity = session.client("sts").get_caller_identity()
    iam = session.client("iam", config=Config(connect_timeout=15, read_timeout=30,
                         retries={"mode": "standard", "total_max_attempts": 3}))
    count = check_permissions(iam, identity["Arn"], identity["Account"], args.region, args.stack)
    print(f"IAM permission preflight passed: {count} action/resource checks; no resources created.")
    print("Simulation does not establish account verification, service availability, quotas, or successful deployment.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, BotoCoreError, ClientError, KeyError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
