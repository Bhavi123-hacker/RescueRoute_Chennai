"""Offline checks for AWS-backed local hosting and preservation of CloudFront mode."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import urllib.error
import yaml
from scripts import deploy_review, local_dashboard
from scripts.publish_frontend import publish
from scripts.upload_review_artifact import TemplateLoader


class LocalDashboardTests(unittest.TestCase):
    def test_local_mode_omits_cdn_and_preserves_jwt_auth_and_exact_origin(self):
        template = yaml.load((deploy_review.ROOT / 'template.yaml').read_text(), Loader=TemplateLoader)
        self.assertEqual(template['Parameters']['EnableCloudFront']['Default'], 'true')
        for name in ('Distribution', 'OriginAccess', 'FrontendPolicy', 'FrontendBucket'):
            self.assertEqual(template['Resources'][name]['Condition'], 'CloudFrontEnabled')
        for name in ('DistributionId', 'FrontendBucket'):
            self.assertEqual(template['Outputs'][name]['Condition'], 'CloudFrontEnabled')
        api = template['Resources']['Api']['Properties']
        self.assertEqual(api['Auth']['DefaultAuthorizer'], 'OperatorAuth')
        self.assertEqual(api['CorsConfiguration']['AllowOrigins'][0]['Fn::If'][2], 'http://localhost:8020')
        self.assertEqual(template['Outputs']['WebsiteUrl']['Value']['Fn::If'][2], 'http://localhost:8020')

    def test_publishing_both_modes_and_private_artifacts(self):
        for local in (True, False):
            with self.subTest(local=local), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'frontend').mkdir()
                (root / 'frontend/index.html').write_text('RescueRoute')
                session = MagicMock()
                out = {'ApiUrl': 'https://api.example', 'ClientId': 'public-client-id',
                       'ReportBucket': 'private-reports', 'WebsiteUrl': 'http://localhost:8020',
                       'HostingMode': 'local' if local else 'cloudfront'}
                if not local:
                    out.update(DistributionId='DISTRIBUTION', FrontendBucket='private-frontend')
                with contextlib.redirect_stdout(io.StringIO()):
                    publish(session, out, root, 'eu-north-1')
                config = (root / 'frontend/config.js').read_text()
                self.assertIn(out['ApiUrl'], config)
                self.assertIn(out['ClientId'], config)
                self.assertNotIn('password', config.lower())
                services = [c.args[0] for c in session.client.call_args_list]
                self.assertEqual('cloudfront' in services, not local)
                uploads = session.client.return_value.upload_file.call_args_list
                self.assertEqual(len(uploads), 4 if local else 6)
                reports = [c for c in uploads if c.args[1] == 'private-reports']
                self.assertEqual(len(reports), 4)
                self.assertTrue(all(c.kwargs['ExtraArgs'] == {'ServerSideEncryption': 'AES256'} for c in reports))

    def test_entire_local_deployment_flow_keeps_cloud_controls_and_verifies_api_and_dashboard(self):
        plan = {'accountPlanType': 'FREE', 'accountPlanStatus': 'ACTIVE',
                'accountPlanRemainingCredits': {'amount': 90, 'unit': 'USD'}}
        identity = {'Arn': 'arn:aws:iam::123456789012:user/test', 'Account': '123456789012'}
        out = {'ApiUrl': 'https://api.example', 'WebsiteUrl': 'http://localhost:8020',
               'HostingMode': 'local', 'UserPoolId': 'pool', 'ClientId': 'client'}
        session, cf, cognito = MagicMock(), MagicMock(), MagicMock()
        cf.describe_stacks.return_value = {'Stacks': [{'Outputs': [
            {'OutputKey': k, 'OutputValue': v} for k, v in out.items()]}]}
        cognito.initiate_auth.return_value = {'AuthenticationResult': {'IdToken': 'test-token'}}
        session.client.side_effect = lambda name: cf if name == 'cloudformation' else cognito
        def run(command, *args, **kwargs):
            if command[1:3] == ['sts', 'get-caller-identity']:
                return json.dumps(identity)
            if command[1:3] == ['freetier', 'get-account-plan-state']:
                return json.dumps(plan)
        response = MagicMock()
        response.__enter__.return_value.status = 200
        response.__enter__.return_value.read.return_value = b'RescueRoute https://api.example'
        with patch.object(deploy_review.shutil, 'which', side_effect=lambda name: name), \
                patch.object(deploy_review, 'run', side_effect=run) as commands, \
                patch('builtins.input', return_value='review@example.com'), \
                patch('boto3.Session', return_value=session), \
                patch.object(deploy_review.getpass, 'getpass', return_value='local-test-password'), \
                patch.object(deploy_review, 'fetch_json', return_value={}) as state, \
                patch.object(deploy_review, 'start_dashboard', return_value=MagicMock(pid=1234)) as start, \
                patch.object(deploy_review.urllib.request, 'urlopen', return_value=response), \
                contextlib.redirect_stdout(io.StringIO()):
            deploy_review.main(['--deploy', '--reuse-existing-budget', '--artifact-bucket', 'existing-bucket',
                                '--local-dashboard'])
        calls = [c.args[0] for c in commands.call_args_list]
        application = next(c for c in calls if c[:2] == ['sam', 'deploy'])
        for setting in ('EnableCloudFront=false', 'EnableLocation=false', 'EnableCustomMetrics=false'):
            self.assertIn(setting, application)
        self.assertIn('.aws-sam/review/template.json', application)
        self.assertTrue(any(c[1] == 'scripts/verify_review_budget.py' for c in calls))
        state.assert_called_once_with('https://api.example/api/state', 'test-token')
        start.assert_called_once()

    def test_server_reuses_only_matching_configuration_and_page(self):
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'RescueRoute https://api.example'
        with patch.object(local_dashboard.urllib.request, 'urlopen', return_value=response), \
                patch.object(local_dashboard.subprocess, 'Popen') as popen, \
                contextlib.redirect_stdout(io.StringIO()):
            self.assertIsNone(local_dashboard.start_dashboard(Path('example'), {}, 'https://api.example'))
        popen.assert_not_called()

    def test_server_wont_take_over_occupied_port_and_starts_loopback_only(self):
        for busy in (True, False):
            with self.subTest(busy=busy), tempfile.TemporaryDirectory() as directory:
                probe = MagicMock()
                if busy:
                    probe.__enter__.return_value.bind.side_effect = OSError('busy')
                process = MagicMock(pid=1234)
                with patch.object(local_dashboard.urllib.request, 'urlopen', side_effect=urllib.error.URLError('offline')), \
                        patch.object(local_dashboard.socket, 'socket', return_value=probe), \
                        patch.object(local_dashboard.subprocess, 'Popen', return_value=process) as popen, \
                        contextlib.redirect_stdout(io.StringIO()):
                    if busy:
                        with self.assertRaisesRegex(RuntimeError, 'occupied'):
                            local_dashboard.start_dashboard(Path(directory), {}, 'https://api.example')
                        popen.assert_not_called()
                    else:
                        local_dashboard.start_dashboard(Path(directory), {}, 'https://api.example')
                        command = popen.call_args.args[0]
                        self.assertEqual(command[command.index('--bind') + 1], '127.0.0.1')
                        self.assertEqual(command[command.index('--directory') + 1], str(Path(directory) / 'frontend'))


if __name__ == '__main__':
    unittest.main()
