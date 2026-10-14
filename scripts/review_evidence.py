"""Write a screenshot checklist from the actual successfully deployed AWS stack."""
import argparse
from pathlib import Path
import boto3

SERVICES = {
    'AWS::Lambda::Function': ('AWS Lambda', 'Backend function; open Monitor after running the demo.'),
    'AWS::ApiGatewayV2::Api': ('Amazon API Gateway', 'HTTP or WebSocket API endpoints.'),
    'AWS::Cognito::UserPool': ('Amazon Cognito', 'User pool and dispatcher account.'),
    'AWS::DynamoDB::Table': ('Amazon DynamoDB', 'Project table; inspect items after running a mission.'),
    'AWS::S3::Bucket': ('Amazon S3', 'Private project bucket; inspect actual model/export objects.'),
    'AWS::SNS::Topic': ('Amazon SNS', 'Provisioned topic. Claim message delivery only if demonstrated.'),
    'AWS::Logs::LogGroup': ('Amazon CloudWatch', 'Lambda log group; inspect invocation log events.'),
    'AWS::IAM::Role': ('AWS IAM', 'Execution role and scoped policies. SageMaker role alone is not a training job.'),
    'AWS::CloudFront::Distribution': ('Amazon CloudFront', 'Only claim this service if this resource exists.'),
}


def write_evidence(cf, stack, region, root):
    deployed = cf.describe_stacks(StackName=stack)['Stacks'][0]
    if deployed['StackStatus'] not in {'CREATE_COMPLETE', 'UPDATE_COMPLETE'}:
        raise RuntimeError('Screenshot checklist requires a successfully deployed stack.')
    rows = []
    for page in cf.get_paginator('list_stack_resources').paginate(StackName=stack):
        for resource in page['StackResourceSummaries']:
            kind = resource['ResourceType']
            if kind in SERVICES and resource['ResourceStatus'] in {'CREATE_COMPLETE', 'UPDATE_COMPLETE'}:
                service, caption = SERVICES[kind]
                rows.append(f"| {service} | {resource['LogicalResourceId']} | `{resource['PhysicalResourceId']}` | {caption} |")
    mode = {item['OutputKey']: item['OutputValue'] for item in deployed.get('Outputs', [])}.get('HostingMode')
    content = f'# RescueRoute AWS screenshot checklist\n\nStack: `{stack}`. Region: `{region}`. Status: `{deployed["StackStatus"]}`.\n\n'
    content += 'Take screenshots in your authenticated AWS Console, with the resource name visible. These IDs come from CloudFormation; this file is a checklist, not screenshots or proof of every feature.\n\n'
    content += '| Service | Stack resource | Actual AWS resource | Screenshot and caption |\n| --- | --- | --- | --- |\n' + '\n'.join(rows) + '\n\n'
    if mode == 'local':
        content += 'Hosting: dashboard on the PC at http://localhost:8020; backend on AWS. CloudFront is omitted. Amazon Location and SageMaker training are disabled in this review workflow.\n\n'
    content += 'Also capture CloudFormation Resources and Outputs, the existing $1 monthly AWS Budget with its alerts (us-east-1), and the signed-in dashboard after completing a demo mission. A provisioned service is distinct from demonstrated feature use.\n'
    path = Path(root) / '.aws-sam/review/aws-screenshots.md'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding='utf-8')
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='rescueroute-key')
    parser.add_argument('--region', default='eu-north-1')
    parser.add_argument('--stack', default='rescueroute-chennai')
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    path = write_evidence(session.client('cloudformation'), args.stack, args.region, Path(__file__).resolve().parents[1])
    print('AWS screenshot checklist with actual resource IDs:', path)


if __name__ == '__main__':
    main()
