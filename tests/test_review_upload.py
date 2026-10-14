"""Exercise package fidelity, upload failures, and deployment gating without AWS calls."""
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import zipfile

from botocore.exceptions import ClientError, ReadTimeoutError
import yaml

from scripts.upload_review_artifact import TemplateLoader, package_backend, upload_verified
from scripts.deploy_review import main


class ReviewUploadTests(unittest.TestCase):
    def test_repeatable_zip_keeps_dependencies_at_lambda_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "Backend"
            (source / "boto3").mkdir(parents=True)
            (source / "app.py").write_text("def handler(event, context): pass\n")
            (source / "boto3" / "__init__.py").write_text("# dependency\n")
            first, second = root / "one.zip", root / "two.zip"
            package_backend(source, first)
            package_backend(source, second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), ["app.py", "boto3/__init__.py"])
                self.assertEqual(archive.read("app.py"), (source / "app.py").read_bytes())

    def test_yaml_intrinsics_keep_their_cloudformation_meaning(self):
        template = yaml.load("""Ref: !Ref Bucket
Attribute: !GetAtt Backend.Arn
LongAttribute: !GetAtt [Backend, Arn]
Sub: !Sub ['${Name}', {Name: !Ref Bucket}]
Conditional: !If [Enabled, !Ref Bucket, '']
Condition: !Condition Enabled
""", Loader=TemplateLoader)
        self.assertEqual(template["Ref"], {"Ref": "Bucket"})
        self.assertEqual(template["Attribute"], {"Fn::GetAtt": ["Backend", "Arn"]})
        self.assertEqual(template["LongAttribute"], template["Attribute"])
        self.assertEqual(template["Sub"], {"Fn::Sub": ["${Name}", {"Name": {"Ref": "Bucket"}}]})
        self.assertEqual(template["Conditional"], {"Fn::If": ["Enabled", {"Ref": "Bucket"}, ""]})
        self.assertEqual(template["Condition"], {"Condition": "Enabled"})

    def test_upload_uses_one_put_and_verifies_length_digest_and_owner(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "test.zip"
            archive.write_bytes(b"archive bytes")
            s3 = MagicMock()
            missing = ClientError({"Error": {"Code": "404"}}, "HeadObject")
            def head(**kwargs):
                if not s3.put_object.called:
                    raise missing
                request = s3.put_object.call_args.kwargs
                return {"ContentLength": request["ContentLength"], "Metadata": request["Metadata"]}
            s3.head_object.side_effect = head
            with contextlib.redirect_stdout(io.StringIO()):
                key = upload_verified(s3, archive, "bucket", "123456789012")
            request = s3.put_object.call_args.kwargs
            self.assertEqual(request["Key"], key)
            self.assertEqual(request["ExpectedBucketOwner"], "123456789012")
            self.assertEqual(request["ServerSideEncryption"], "AES256")
            self.assertEqual(request["ContentLength"], len(b"archive bytes"))
            self.assertIn("ContentMD5", request)
            s3.put_object.assert_called_once()
            s3.create_multipart_upload.assert_not_called()
            s3.upload_part.assert_not_called()
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(upload_verified(s3, archive, "bucket", "123456789012"), key)
            s3.put_object.assert_called_once()

    def test_access_denied_or_connection_failure_does_not_report_success(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = Path(directory) / "test.zip"
            archive.write_bytes(b"archive")
            denied = ClientError({"Error": {"Code": "403"}}, "HeadObject")
            missing = ClientError({"Error": {"Code": "404"}}, "HeadObject")
            s3 = MagicMock()
            s3.head_object.side_effect = denied
            with self.assertRaises(ClientError):
                upload_verified(s3, archive, "bucket", "123456789012")
            s3.put_object.assert_not_called()
            s3.head_object.side_effect = missing
            s3.put_object.side_effect = ReadTimeoutError(endpoint_url="https://example.invalid")
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ReadTimeoutError):
                upload_verified(s3, archive, "bucket", "123456789012")

    def deployment_commands(self, upload_result=None):
        identity = {"Arn": "arn:aws:iam::123456789012:user/test"}
        plan = {"accountPlanType": "FREE", "accountPlanStatus": "ACTIVE",
                "accountPlanRemainingCredits": {"amount": 90, "unit": "USD"}}
        replies = [json.dumps(identity), json.dumps(plan), None, None, None, None,
                   json.dumps(plan), None, json.dumps(plan), upload_result, RuntimeError("offline stop")]
        with patch("scripts.deploy_review.shutil.which", side_effect=lambda name: name), \
                patch("scripts.deploy_review.run", side_effect=replies) as run, \
                patch("builtins.input", return_value="review@example.com"), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            main(["--deploy", "--artifact-bucket", "existing-bucket"])
        return [call.args[0] for call in run.call_args_list]

    def test_failed_artifact_upload_prevents_app_deployment(self):
        commands = self.deployment_commands(RuntimeError("upload failed"))
        self.assertFalse(any(command[:2] == ["sam", "deploy"] for command in commands))

    def test_app_uses_packaged_template_and_existing_bucket_after_upload(self):
        commands = self.deployment_commands()
        upload = next(c for c in commands if c[1] == "scripts/upload_review_artifact.py")
        application = next(c for c in commands if c[:2] == ["sam", "deploy"])
        self.assertLess(commands.index(upload), commands.index(application))
        self.assertEqual(upload[upload.index("--profile") + 1], "rescueroute-key")
        self.assertEqual(application[application.index("--s3-bucket") + 1], "existing-bucket")
        self.assertEqual(application[application.index("--template-file") + 1], ".aws-sam/review/template.json")
        self.assertNotIn("--resolve-s3", application)
        self.assertIn("EnableLocation=false", application)


if __name__ == "__main__":
    unittest.main()
