"""Advance an existing simulated mission using the actual local/AWS API."""
import argparse
import json
import os
import time
from urllib.request import Request,urlopen
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--api',default='http://localhost:8000');p.add_argument('--mission',required=True);p.add_argument('--interval',type=float,default=2.5);a=p.parse_args()
    if a.interval<.5:raise SystemExit('Use an interval of at least 0.5 seconds.')
    token=os.environ.get('RESCUEROUTE_OPERATOR_TOKEN','')
    for _ in range(80):
        payload={'mission_id':a.mission,'command_id':str(__import__('uuid').uuid4())}
        req=Request(a.api.rstrip('/')+'/api/advance',data=json.dumps(payload).encode(),headers={'Content-Type':'application/json',**({'Authorization':token} if token else {})})
        with urlopen(req,timeout=25) as response:data=json.load(response)
        m=data['state']['missions'][a.mission]
        print(m['phase'],'ETA',m['remaining_min'],'modeled elapsed',round(m['elapsed_min'],2))
        if m['phase'] in ('ARRIVED','COMPLETED','NO_ROUTE'):break
        time.sleep(a.interval)
