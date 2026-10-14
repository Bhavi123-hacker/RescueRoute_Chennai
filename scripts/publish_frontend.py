"""Publish CloudFront assets or prepare a local dashboard; upload private AWS data."""
import argparse
import json
import mimetypes
from pathlib import Path
import boto3
import time

def publish(session, out, root, region):
    local = out.get('HostingMode') == 'local'
    if not local and (not out.get('DistributionId') or not out.get('FrontendBucket')):
        raise RuntimeError('CloudFront stack outputs are incomplete; publication stopped.')
    config={'apiUrl':out['ApiUrl'],'region':region,'clientId':out['ClientId'],
            'locationEnabled':out.get('LocationEnabled')=='true','mapKey':'',
            'websocketUrl':out.get('WebSocketUrl','')}
    if config['locationEnabled']:
        config['mapKey']=session.client('location').describe_key(KeyName=out['MapKeyName'])['Key']
    (root/'frontend'/'config.js').write_text('window.APP_CONFIG = '+json.dumps(config)+';\n', encoding='utf-8')
    s3=session.client('s3')
    if not local:
        for file in sorted((root/'frontend').rglob('*')):
            if file.is_file():
                key=file.relative_to(root/'frontend').as_posix()
                s3.upload_file(str(file),out['FrontendBucket'],key,ExtraArgs={'ContentType':mimetypes.guess_type(file.name)[0] or 'application/octet-stream','CacheControl':'max-age=300'})
    for file,key in [(root/'ml'/'synthetic_traffic.csv','training/synthetic_traffic.csv'),
                     (root/'backend'/'city'/'hospitals.json','city/chennai_hospitals.json'),
                     (root/'backend'/'models'/'model_report.json','training/model_report.json'),
                     (root/'backend'/'models'/'traffic_forest.json','training/traffic_forest.json')]:
        s3.upload_file(str(file),out['ReportBucket'],key,ExtraArgs={'ServerSideEncryption':'AES256'})
    if not local:
        session.client('cloudfront').create_invalidation(DistributionId=out['DistributionId'],InvalidationBatch={'Paths':{'Quantity':1,'Items':['/*']},'CallerReference':str(time.time_ns())})
    print('Dashboard:',out['WebsiteUrl'])
    print('Training artifacts uploaded to the private report bucket.')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stack', default='rescueroute-chennai')
    parser.add_argument('--region', default='eu-north-1')
    args = parser.parse_args(argv)
    session = boto3.Session(region_name=args.region)
    raw = session.client('cloudformation').describe_stacks(StackName=args.stack)['Stacks'][0]['Outputs']
    out = {item['OutputKey']: item['OutputValue'] for item in raw}
    publish(session, out, Path(__file__).resolve().parents[1], args.region)


if __name__ == '__main__':
    main()
