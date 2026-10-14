"""Remove only an empty, completely rolled-back app stack before a deployment retry."""
import argparse
import boto3
from botocore.exceptions import ClientError


def prepare_stack(cf, stack):
    try:
        status = cf.describe_stacks(StackName=stack)['Stacks'][0]['StackStatus']
    except ClientError as error:
        if error.response['Error']['Code'] == 'ValidationError' and 'does not exist' in error.response['Error']['Message']:
            return
        raise
    if status in {'CREATE_COMPLETE', 'UPDATE_COMPLETE', 'UPDATE_ROLLBACK_COMPLETE'}:
        return
    if status != 'ROLLBACK_COMPLETE':
        raise RuntimeError(f'{stack} is {status}; inspect its events before retrying. No stack deleted.')
    resources = [resource for page in cf.get_paginator('list_stack_resources').paginate(StackName=stack)
                 for resource in page['StackResourceSummaries']]
    if any(resource['ResourceStatus'] != 'DELETE_COMPLETE' for resource in resources):
        raise RuntimeError('Failed stack still contains retained or undeleted resources. No stack deleted.')
    print(f'Removing empty ROLLBACK_COMPLETE app stack {stack}; its resources are already deleted.')
    cf.delete_stack(StackName=stack)
    cf.get_waiter('stack_delete_complete').wait(StackName=stack, WaiterConfig={'Delay': 5, 'MaxAttempts': 60})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', default='rescueroute-key')
    parser.add_argument('--region', default='eu-north-1')
    parser.add_argument('--stack', default='rescueroute-chennai')
    args = parser.parse_args()
    session = boto3.Session(profile_name=args.profile, region_name=args.region)
    prepare_stack(session.client('cloudformation'), args.stack)


if __name__ == '__main__':
    main()
