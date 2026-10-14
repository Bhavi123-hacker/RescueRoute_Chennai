"""Verify read-only IAM requests, exact tagging scope and fail-closed results."""
import unittest
from unittest.mock import MagicMock, patch
import boto3
from botocore.stub import Stubber
from scripts.check_deployment_permissions import check_permissions, permission_groups

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
                with self.assertRaisesRegex(RuntimeError, 'DEFAULT version'):
                    check_permissions(iam, PRINCIPAL, ACCOUNT, REGION, STACK)

    def test_encoded_tag_endpoint_is_checked(self):
        endpoint = f'arn:aws:apigateway:{REGION}::/tags/arn%3Aaws%3Aapigateway%3A{REGION}%3A%3A%2Fv2%2Fapis%2Fpermissionprobe'
        groups = permission_groups(ACCOUNT, REGION, STACK)
        self.assertTrue(any(resource == endpoint and 'apigateway:POST' in actions
                            for resource, actions, policy in groups))
        self.assertFalse(any('cloudfront' in action.lower() for _, actions, _ in groups for action in actions))

    def test_root_and_role_sessions_are_not_silently_simulated_as_users(self):
        iam = MagicMock()
        for principal in (f'arn:aws:iam::{ACCOUNT}:root', f'arn:aws:sts::{ACCOUNT}:assumed-role/test/session'):
            with self.assertRaisesRegex(RuntimeError, 'IAM deployment-user'):
                check_permissions(iam, principal, ACCOUNT, REGION, STACK)
        iam.simulate_principal_policy.assert_not_called()


if __name__ == '__main__':
    unittest.main()
