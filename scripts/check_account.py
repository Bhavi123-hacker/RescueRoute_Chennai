"""Read-only AWS preflight; prints no account IDs, user ARNs, or credentials."""
import argparse
import boto3
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--region',default='eu-north-1');a=p.parse_args()
    session=boto3.Session(region_name=a.region)
    session.client('sts').get_caller_identity()
    print('AWS authentication works. Selected region:',a.region)
    print('This check does not prove CloudShell activation or deployment permissions.')
