"""Package the built backend and upload without multipart transfer; never create buckets."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
import yaml

ROOT = Path(__file__).resolve().parents[1]


class TemplateLoader(yaml.SafeLoader):
    """Expand CloudFormation shorthand without executing arbitrary YAML objects."""


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node, deep=True)
    else:
        value = loader.construct_mapping(node, deep=True)
    if tag == "GetAtt" and isinstance(value, str):
        value = value.split(".", 1)
    return {tag if tag in {"Ref", "Condition"} else "Fn::" + tag: value}


TemplateLoader.add_multi_constructor("!", intrinsic)


def package_backend(source, target):
    """Preserve Lambda's directory layout and Unix permissions in a repeatable ZIP."""
    files = sorted(path for path in source.rglob("*") if path.is_file())
    if not files or not (source / "app.py").is_file():
        raise RuntimeError("Built backend is missing. Run sam build first.")
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            if path.is_symlink():
                raise RuntimeError("Unexpected symlink in built backend.")
            info = zipfile.ZipInfo(path.relative_to(source).as_posix(), (1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (0o100755 if path.stat().st_mode & 0o111 else 0o100644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    if target.stat().st_size > 100 * 1024 * 1024:
        raise RuntimeError("Package exceeds this demo's 100 MiB single-upload limit.")


def upload_verified(s3, archive, bucket, account):
    data = archive.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    key = "rescueroute-review/backend-" + digest + ".zip"

    def matching_object():
        try:
            result = s3.head_object(Bucket=bucket, Key=key, ExpectedBucketOwner=account)
        except ClientError as error:
            if error.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise
        return (result["ContentLength"] == len(data)
                and result.get("Metadata", {}).get("sha256") == digest)

    if not matching_object():
        print(f"Uploading {len(data) / 1024 / 1024:.1f} MiB in one request; retries may take several minutes.", flush=True)
        with archive.open("rb") as body:
            s3.put_object(Bucket=bucket, Key=key, Body=body, ContentLength=len(data),
                          ContentType="application/zip", ServerSideEncryption="AES256",
                          ContentMD5=base64.b64encode(hashlib.md5(data, usedforsecurity=False).digest()).decode(),
                          Metadata={"sha256": digest}, ExpectedBucketOwner=account)
        if not matching_object():
            raise RuntimeError("Uploaded artifact verification failed; app deployment stopped.")
    print("Verified S3 artifact:", key, flush=True)
    return key


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", required=True)
    parser.add_argument("--region", required=True)
    parser.add_argument("--bucket", required=True)
    args = parser.parse_args(argv)
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    account = session.client("sts").get_caller_identity()["Account"]
    s3 = session.client("s3", config=Config(
        connect_timeout=30, read_timeout=300,
        retries={"mode": "standard", "total_max_attempts": 4},
        request_checksum_calculation="when_required",
        s3={"addressing_style": "path"}))
    location = s3.get_bucket_location(Bucket=args.bucket, ExpectedBucketOwner=account)["LocationConstraint"]
    if (location or "us-east-1") != args.region:
        raise RuntimeError("Artifact bucket is in a different region. No upload attempted.")
    build = ROOT / ".aws-sam" / "build"
    template = yaml.load((build / "template.yaml").read_text(encoding="utf-8"), Loader=TemplateLoader)
    backend = template["Resources"]["Backend"]["Properties"]
    source = (build / backend["CodeUri"]).resolve()
    if not source.is_relative_to(build.resolve()):
        raise RuntimeError("Backend CodeUri is outside the build directory.")
    destination = ROOT / ".aws-sam" / "review"
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "backend.zip"
    package_backend(source, archive)
    key = upload_verified(s3, archive, args.bucket, account)
    backend["CodeUri"] = {"Bucket": args.bucket, "Key": key}
    (destination / "template.json").write_text(json.dumps(template, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, BotoCoreError, ClientError, OSError, KeyError, yaml.YAMLError) as error:
        if isinstance(error, ClientError):
            detail = error.response["Error"].get("Message", "AWS rejected the request.")
        elif isinstance(error, BotoCoreError):
            detail = type(error).__name__ + ": upload connection failed after configured retries. Try another network."
        else:
            detail = str(error)
        print("Artifact upload stopped:", detail, file=sys.stderr)
        sys.exit(1)
