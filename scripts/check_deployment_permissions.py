"""Read-only IAM simulation of permissions used by the temporary AWS backend."""
import argparse
import fnmatch
import json
import sys
from urllib.parse import unquote
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
        ("*", ["cognito-idp:CreateUserPool"], None),
        (f"arn:aws:cognito-idp:{region}:{account}:userpool/{region}_permissionprobe",
         ["cognito-idp:CreateUserPoolClient", "cognito-idp:TagResource",
          "cognito-idp:AdminGetUser", "cognito-idp:AdminCreateUser", "cognito-idp:AdminSetUserPassword",
          "cognito-idp:DeleteUserPoolClient", "cognito-idp:DeleteUserPool"], None),
        (f"arn:aws:sns:{region}:{account}:{stack}-mission-alerts",
         ["sns:CreateTopic", "sns:SetTopicAttributes", "sns:TagResource", "sns:DeleteTopic"], None),
        (f"arn:aws:logs:{region}:{account}:log-group:/aws/lambda/{stack}-Backend-permissionprobe",
         ["logs:CreateLogGroup", "logs:PutRetentionPolicy", "logs:TagResource", "logs:DeleteLogGroup"], None),
    ]
    for path in ("/apis", "/apis/permissionprobe", "/apis/permissionprobe/stages"):
        groups.append((prefix + path, ["apigateway:POST", "apigateway:PUT", "apigateway:PATCH", "apigateway:DELETE"], None))
    for policy in ("service-role/AWSLambdaBasicExecutionRole", "AWSXrayWriteOnlyAccess", "AWSXRayDaemonWriteAccess"):
        groups.append((role, ["iam:AttachRolePolicy", "iam:DetachRolePolicy"], f"arn:aws:iam::aws:policy/{policy}"))
    return groups


def scoped_policy_checks(region):
    # The simulator's action/resource catalog does not reliably model these
    # service-authorized paths. Check their real attached default policy grants.
    tag = f"arn:aws:apigateway:{region}::/tags/arn%3Aaws%3Aapigateway%3A{region}%3A%3A%2Fv2%2Fapis%2Fpermissionprobe"
    return [("cloudformation:CreateChangeSet", f"arn:aws:cloudformation:{region}:aws:transform/Serverless-2016-10-31"),
            ("apigateway:POST", tag), ("apigateway:DELETE", tag)]


def attached_policy_documents(iam, username):
    user = iam.get_user(UserName=username)['User']
    if user.get('PermissionsBoundary'):
        raise RuntimeError('Scoped policy inspection cannot establish permissions with a permissions boundary; inspect it in IAM.')
    documents, managed = [], set()
    def collect(kind, name):
        key = 'UserName' if kind == 'user' else 'GroupName'
        for page in iam.get_paginator(f'list_{kind}_policies').paginate(**{key: name}):
            for policy_name in page['PolicyNames']:
                documents.append(getattr(iam, f'get_{kind}_policy')(**{key: name, 'PolicyName': policy_name})['PolicyDocument'])
        for page in iam.get_paginator(f'list_attached_{kind}_policies').paginate(**{key: name}):
            managed.update(policy['PolicyArn'] for policy in page['AttachedPolicies'])
    collect('user', username)
    for page in iam.get_paginator('list_groups_for_user').paginate(UserName=username):
        for group in page['Groups']:
            collect('group', group['GroupName'])
    for arn in sorted(managed):
        version = iam.get_policy(PolicyArn=arn)['Policy']['DefaultVersionId']
        documents.append(iam.get_policy_version(PolicyArn=arn, VersionId=version)['PolicyVersion']['Document'])
    decoded = []
    for document in documents:
        if isinstance(document, str):
            try:
                document = json.loads(document)
            except json.JSONDecodeError:
                document = json.loads(unquote(document))
        decoded.append(document)
    return decoded


def check_scoped_grants(documents, region):
    """Require unconditional scoped grants; never treat this as a full IAM evaluator."""
    statements = []
    for document in documents:
        value = document.get('Statement', [])
        statements.extend([value] if isinstance(value, dict) else value)
    def values(value):
        return [value] if isinstance(value, str) else value
    for action, resource in scoped_policy_checks(region):
        def matches_action(statement):
            return any(fnmatch.fnmatchcase(action.lower(), pattern.lower())
                       for pattern in values(statement.get('Action', [])))
        # Refuse ambiguous denies even if a condition or resource might narrow
        # them. Do not bypass a deny or implement an incomplete condition engine.
        if any(s.get('Effect') == 'Deny' and ('NotAction' in s or matches_action(s)) for s in statements):
            raise RuntimeError(f'Attached deny requires IAM review for {action}; scoped inspection stopped.')
        if not any(s.get('Effect') == 'Allow' and not s.get('Condition') and matches_action(s)
                   and any(fnmatch.fnmatchcase(resource, scope) for scope in values(s.get('Resource', [])))
                   for s in statements):
            raise RuntimeError(f'Attached DEFAULT policy lacks an unconditional grant: {action} on {resource}. Regenerate/update the deployment policy.')
    return len(scoped_policy_checks(region))


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
        raise RuntimeError("IAM simulation stopped; inspect the attached policy/default version and missing context:\n"
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
    documents = attached_policy_documents(iam, identity['Arn'].rsplit('/', 1)[1])
    scoped = check_scoped_grants(documents, args.region)
    print(f"Permission preflight passed: {count} native IAM checks and {scoped} attached-default-policy scope checks; no resources created.")
    print('Transform and API tagging grants were inspected in attached policies; this is not a live authorization test.')
    print("Simulation does not establish account verification, service availability, quotas, or successful deployment.")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, BotoCoreError, ClientError, KeyError) as error:
        print(error, file=sys.stderr)
        sys.exit(1)
