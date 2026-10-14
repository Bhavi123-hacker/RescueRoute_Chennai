import tempfile
from pathlib import Path
import unittest
from unittest.mock import MagicMock
from botocore.exceptions import ClientError
from scripts.prepare_review_stack import prepare_stack
from scripts.review_evidence import write_evidence


class ReviewRecoveryTests(unittest.TestCase):
    def client(self, status, resources):
        cf = MagicMock()
        cf.describe_stacks.return_value = {'Stacks': [{'StackStatus': status}]}
        cf.get_paginator.return_value.paginate.return_value = [{'StackResourceSummaries': resources}]
        return cf

    def test_only_empty_fully_rolled_back_stack_is_deleted(self):
        cf = self.client('ROLLBACK_COMPLETE', [{'ResourceStatus': 'DELETE_COMPLETE'}])
        prepare_stack(cf, 'rescueroute-chennai')
        cf.delete_stack.assert_called_once_with(StackName='rescueroute-chennai')
        cf.get_waiter.return_value.wait.assert_called_once()

    def test_busy_failed_and_retained_resources_are_preserved(self):
        for status, resources in [('CREATE_IN_PROGRESS', []), ('ROLLBACK_FAILED', []),
                                  ('DELETE_FAILED', []), ('ROLLBACK_COMPLETE', [{'ResourceStatus': 'DELETE_SKIPPED'}]),
                                  ('ROLLBACK_COMPLETE', [{'ResourceStatus': 'DELETE_FAILED'}]),
                                  ('ROLLBACK_COMPLETE', [{'ResourceStatus': 'CREATE_COMPLETE'}])]:
            cf = self.client(status, resources)
            with self.subTest(status=status, resources=resources), self.assertRaises(RuntimeError):
                prepare_stack(cf, 'rescueroute-chennai')
            cf.delete_stack.assert_not_called()

    def test_healthy_or_nonexistent_stack_is_preserved(self):
        for status in ('CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'):
            cf = self.client(status, [])
            prepare_stack(cf, 'rescueroute-chennai')
            cf.delete_stack.assert_not_called()
        cf = MagicMock()
        cf.describe_stacks.side_effect = ClientError({'Error': {'Code': 'ValidationError',
                                                   'Message': 'Stack does not exist'}}, 'DescribeStacks')
        prepare_stack(cf, 'rescueroute-chennai')
        cf.delete_stack.assert_not_called()
        cf.describe_stacks.side_effect = ClientError({'Error': {'Code': 'AccessDenied',
                                                   'Message': 'Denied'}}, 'DescribeStacks')
        with self.assertRaises(ClientError):
            prepare_stack(cf, 'rescueroute-chennai')

    def test_checklist_uses_real_successful_resources_and_does_not_claim_cloudfront(self):
        cf = self.client('CREATE_COMPLETE', [
            {'ResourceType': 'AWS::Lambda::Function', 'LogicalResourceId': 'Backend',
             'PhysicalResourceId': 'real-backend-id', 'ResourceStatus': 'CREATE_COMPLETE'},
            {'ResourceType': 'AWS::CloudFront::Distribution', 'LogicalResourceId': 'Distribution',
             'PhysicalResourceId': 'failed-cdn-id', 'ResourceStatus': 'DELETE_COMPLETE'}])
        cf.describe_stacks.return_value['Stacks'][0]['Outputs'] = [{'OutputKey': 'HostingMode', 'OutputValue': 'local'}]
        with tempfile.TemporaryDirectory() as directory:
            path = write_evidence(cf, 'rescueroute-chennai', 'eu-north-1', directory)
            content = path.read_text()
            self.assertIn('real-backend-id', content)
            self.assertNotIn('failed-cdn-id', content)
            self.assertIn('CloudFront is omitted', content)
            self.assertIn('not screenshots', content)
        cf = self.client('ROLLBACK_COMPLETE', [])
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(RuntimeError):
            write_evidence(cf, 'rescueroute-chennai', 'eu-north-1', directory)
        self.assertFalse(any(Path(directory).glob('*.md')))


if __name__ == '__main__':
    unittest.main()
