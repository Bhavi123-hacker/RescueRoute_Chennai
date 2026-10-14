"""Verify read-only IAM requests, exact tagging scope and fail-closed results."""
import unittest
import json
from urllib.parse import quote
from unittest.mock import MagicMock, patch
import boto3
from botocore.stub import Stubber
from scripts.check_deployment_permissions import (check_permissions, permission_groups, scoped_policy_checks,
                                                  check_scoped_grants, attached_policy_documents)
from scripts.make_deployment_policy import deployment_policy

ACCOUNT = '778977181828'
PRINCIPAL = f'arn:aws:iam::{ACCOUNT}:user/bhavygarg'
REGION = 'eu-north-1'
STACK = 'rescueroute-chennai'


class DeploymentPermissionsTests(unittest.TestCase):
    def test_real_sdk_request_schema_and_paginated_decisions(self):
        iam = boto3.client('iam', region_name=REGION, aws_access_key_id='offline',
                           aws_secret_access_key='offline')
        resource = f'arn:aws:iam::{ACCOUNT}:role/{STACK}-BackendRole-probe'
        policy = 'arn:aws:iam::aws:policy/AWSXrayWriteOnlyAccess'
        actions = ['iam:AttachRolePolicy', 'iam:DetachRolePolicy']
        request = {'PolicySourceArn': PRINCIPAL, 'ActionNames': actions, 'ResourceArns': [resource],
                   'ContextEntries': [
                       {'ContextKeyName': name, 'ContextKeyValues': [value], 'ContextKeyType': 'string'}
                       for name, value in [('aws:RequestTag/Project', 'RescueRoute'),
                                           ('aws:ResourceTag/Project', 'RescueRoute'),
                                           ('iam:PassedToService', 'lambda.amazonaws.com'),
                                           ('iam:PolicyARN', policy)]]}
        def decision(action):
            return {'EvalActionName': action, 'EvalResourceName': resource, 'EvalDecision': 'allowed'}
        with Stubber(iam) as stub, patch('scripts.check_deployment_permissions.permission_groups',
                                       return_value=[(resource, actions, policy)]):
            stub.add_response('simulate_principal_policy', {'EvaluationResults': [decision(actions[0])],
                              'IsTruncated': True, 'Marker': 'next'}, request)
            stub.add_response('simulate_principal_policy', {'EvaluationResults': [decision(actions[1])],
                              'IsTruncated': False}, {**request, 'Marker': 'next'})
            self.assertEqual(check_permissions(iam, PRINCIPAL, ACCOUNT, REGION, STACK), 2)
            stub.assert_no_pending_responses()

    def test_denied_or_missing_results_stop(self):
        for results in ([], [{'EvalActionName': 'apigateway:POST', 'EvalDecision': 'implicitDeny'}],
                        [{'EvalActionName': 'apigateway:POST', 'EvalDecision': 'explicitDeny'}]):
            with self.subTest(results=results), patch('scripts.check_deployment_permissions.permission_groups',
                    return_value=[('arn:aws:apigateway:eu-north-1::/apis', ['apigateway:POST'], None)]):
                iam = MagicMock()
                iam.simulate_principal_policy.return_value = {'EvaluationResults': results}
                with self.assertRaisesRegex(RuntimeError, 'simulation stopped'):
                    check_permissions(iam, PRINCIPAL, ACCOUNT, REGION, STACK)

    def test_encoded_tag_endpoint_is_checked(self):
        endpoint = f'arn:aws:apigateway:{REGION}::/tags/arn%3Aaws%3Aapigateway%3A{REGION}%3A%3A%2Fv2%2Fapis%2Fpermissionprobe'
        groups = permission_groups(ACCOUNT, REGION, STACK)
        self.assertIn(('apigateway:POST', endpoint), scoped_policy_checks(REGION))
        self.assertIn(('apigateway:DELETE', endpoint), scoped_policy_checks(REGION))
        self.assertNotIn(('apigateway:PATCH', endpoint), scoped_policy_checks(REGION))
        self.assertFalse(any(resource == endpoint for resource, _, _ in groups))
        self.assertFalse(any('cloudfront' in action.lower() for _, actions, _ in groups for action in actions))

    def test_cognito_creation_is_simulated_on_star_separately_from_pool_actions(self):
        groups = permission_groups(ACCOUNT, REGION, STACK)
        creation = [(r, a) for r, a, _ in groups if 'cognito-idp:CreateUserPool' in a]
        self.assertEqual(creation, [('*', ['cognito-idp:CreateUserPool'])])

    def test_scoped_checks_require_real_attached_grants(self):
        policy = deployment_policy(ACCOUNT, REGION, STACK)
        self.assertEqual(check_scoped_grants([policy], REGION), 3)
        for action in ('cloudformation:CreateChangeSet', 'apigateway:*'):
            altered = {'Statement': [s for s in policy['Statement'] if action not in s['Action']]}
            with self.subTest(action=action), self.assertRaisesRegex(RuntimeError, 'lacks'):
                check_scoped_grants([altered], REGION)
        with self.assertRaisesRegex(RuntimeError, 'lacks'):
            check_scoped_grants([policy], 'us-west-2')

    def test_explicit_deny_and_unevaluated_conditions_never_get_overridden(self):
        policy = deployment_policy(ACCOUNT, REGION, STACK)
        for deny in ({'Effect': 'Deny', 'Action': 'cloudformation:*', 'Resource': '*'},
                     {'Effect': 'Deny', 'NotAction': 's3:*', 'Resource': '*'}):
            with self.subTest(deny=deny), self.assertRaisesRegex(RuntimeError, 'deny'):
                check_scoped_grants([policy, {'Statement': deny}], REGION)
        conditional = {'Statement': [{**s, 'Condition': {'Bool': {'aws:MultiFactorAuthPresent': 'true'}}}
                                     if 'apigateway:*' in s['Action'] else s for s in policy['Statement']]}
        with self.assertRaisesRegex(RuntimeError, 'lacks'):
            check_scoped_grants([conditional], REGION)

    def test_reads_default_managed_versions_and_inline_group_policies(self):
        iam = MagicMock()
        iam.get_user.return_value = {'User': {}}
        pages = {
            'list_user_policies': [{'PolicyNames': ['inline-user']}],
            'list_attached_user_policies': [{'AttachedPolicies': [{'PolicyArn': 'arn:policy'}]}],
            'list_groups_for_user': [{'Groups': [{'GroupName': 'deployers'}]}],
            'list_group_policies': [{'PolicyNames': ['inline-group']}],
            'list_attached_group_policies': [{'AttachedPolicies': [{'PolicyArn': 'arn:policy'}]}],
        }
        def paginator(name):
            result = MagicMock()
            result.paginate.return_value = pages[name]
            return result
        iam.get_paginator.side_effect = paginator
        iam.get_user_policy.return_value = {'PolicyDocument': {'Statement': []}}
        iam.get_group_policy.return_value = {'PolicyDocument': {'Statement': []}}
        iam.get_policy.return_value = {'Policy': {'DefaultVersionId': 'v4'}}
        iam.get_policy_version.return_value = {'PolicyVersion': {'Document': {'Statement': []}}}
        self.assertEqual(len(attached_policy_documents(iam, 'bhavygarg')), 3)
        iam.get_policy_version.assert_called_once_with(PolicyArn='arn:policy', VersionId='v4')
        policy = {'Statement': [{'Resource': 'arn%3Aaws%3Aapigateway'}]}
        for document in (policy, json.dumps(policy), quote(json.dumps(policy))):
            iam.get_policy_version.return_value = {'PolicyVersion': {'Document': document}}
            self.assertEqual(attached_policy_documents(iam, 'bhavygarg')[-1], policy)
        iam.get_user.return_value = {'User': {'PermissionsBoundary': {'PermissionsBoundaryArn': 'arn:boundary'}}}
        with self.assertRaisesRegex(RuntimeError, 'boundary'):
            attached_policy_documents(iam, 'bhavygarg')

    def test_root_and_role_sessions_are_not_silently_simulated_as_users(self):
        iam = MagicMock()
        for principal in (f'arn:aws:iam::{ACCOUNT}:root', f'arn:aws:sts::{ACCOUNT}:assumed-role/test/session'):
            with self.assertRaisesRegex(RuntimeError, 'IAM deployment-user'):
                check_permissions(iam, principal, ACCOUNT, REGION, STACK)
        iam.simulate_principal_policy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
