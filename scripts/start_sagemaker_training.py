"""Launch a SageMaker training job that runs ml/sagemaker_entry.py against this project."""
import argparse
import time
from pathlib import Path
import boto3
import tarfile
import tempfile

def package_source(root: Path) -> Path:
    staging = Path(tempfile.mkdtemp()) / 'sourcedir.tar.gz'
    with tarfile.open(staging, 'w:gz') as tar:
        for rel in ('ml', 'backend/data.py', 'backend/prediction.py', 'backend/__init__.py',
                    'ml/requirements.txt'):
            path = root / rel
            if path.is_dir():
                tar.add(path, arcname=rel)
            elif path.exists():
                tar.add(path, arcname=rel)
    return staging

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--stack', default='rescueroute-chennai')
    p.add_argument('--region', default='eu-north-1')
    p.add_argument('--instance-type', default='ml.m5.large')
    a = p.parse_args()
    session = boto3.Session(region_name=a.region)
    cf = session.client('cloudformation')
    outs = {o['OutputKey']: o['OutputValue'] for o in cf.describe_stacks(StackName=a.stack)['Stacks'][0]['Outputs']}
    bucket, role = outs['ReportBucket'], outs['SageMakerRoleArn']
    root = Path(__file__).resolve().parents[1]
    archive = package_source(root)
    key = f'training/source/{int(time.time())}-sourcedir.tar.gz'
    s3 = session.client('s3')
    s3.upload_file(str(archive), bucket, key)
    job = f"rescueroute-rf-{int(time.time())}"
    sm = session.client('sagemaker')
    sm.create_training_job(
        TrainingJobName=job,
        RoleArn=role,
        AlgorithmSpecification={
            'TrainingImage': f'763104351884.dkr.ecr.{a.region}.amazonaws.com/sklearn:1.2-1-cpu-py3',
            'TrainingInputMode': 'File',
            'ContainerEntrypoint': ['python', 'ml/sagemaker_entry.py'],
        },
        InputDataConfig=[{
            'ChannelName': 'training',
            'DataSource': {'S3DataSource': {
                'S3DataType': 'S3Prefix',
                'S3Uri': f's3://{bucket}/training/',
                'S3DataDistributionType': 'FullyReplicated',
            }},
        }],
        OutputDataConfig={'S3OutputPath': f's3://{bucket}/training/sagemaker-output/'},
        ResourceConfig={'InstanceType': a.instance_type, 'InstanceCount': 1, 'VolumeSizeInGB': 20},
        StoppingCondition={'MaxRuntimeInSeconds': 3600},
        HyperParameters={},
        Environment={'SM_MODULE_DIR': '/opt/ml/code'},
    )
    # Attach source for Script Mode style layouts when using custom entry.
    print('Training job:', job)
    print('Source package:', f's3://{bucket}/{key}')
    print('Monitor: aws sagemaker describe-training-job --training-job-name', job, '--region', a.region)

if __name__ == '__main__':
    main()
