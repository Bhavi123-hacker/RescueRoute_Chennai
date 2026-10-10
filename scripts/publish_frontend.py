"""Publish dashboard plus private training artifacts after SAM deployment."""
import argparse
import json
import mimetypes
from pathlib import Path
import boto3

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--stack',default='rescueroute-chennai');p.add_argument('--region',default='eu-north-1');a=p.parse_args()
    session=boto3.Session(region_name=a.region)
    raw=session.client('cloudformation').describe_stacks(StackName=a.stack)['Stacks'][0]['Outputs']
    out={x['OutputKey']:x['OutputValue'] for x in raw};root=Path(__file__).resolve().parents[1]
    config={'apiUrl':out['ApiUrl'],'region':a.region,'clientId':out['ClientId'],
            'locationEnabled':out.get('LocationEnabled')=='true','mapKey':'',
            'websocketUrl':out.get('WebSocketUrl','')}
    if config['locationEnabled']:
        config['mapKey']=session.client('location').describe_key(KeyName=out['MapKeyName'])['Key']
    (root/'frontend'/'config.js').write_text('window.APP_CONFIG = '+json.dumps(config)+';\n')
    s3=session.client('s3')
    for file in sorted((root/'frontend').rglob('*')):
        if file.is_file():
            key=file.relative_to(root/'frontend').as_posix()
            s3.upload_file(str(file),out['FrontendBucket'],key,ExtraArgs={'ContentType':mimetypes.guess_type(file.name)[0] or 'application/octet-stream','CacheControl':'max-age=300'})
    for file,key in [(root/'ml'/'synthetic_traffic.csv','training/synthetic_traffic.csv'),
                     (root/'backend'/'city'/'hospitals.json','city/chennai_hospitals.json'),
                     (root/'backend'/'models'/'model_report.json','training/model_report.json'),
                     (root/'backend'/'models'/'traffic_forest.json','training/traffic_forest.json')]:
        s3.upload_file(str(file),out['ReportBucket'],key,ExtraArgs={'ServerSideEncryption':'AES256'})
    session.client('cloudfront').create_invalidation(DistributionId=out['DistributionId'],InvalidationBatch={'Paths':{'Quantity':1,'Items':['/*']},'CallerReference':str(__import__('time').time_ns())})
    print('Dashboard:',out['WebsiteUrl'])
    print('Training artifacts uploaded to the private report bucket.')
