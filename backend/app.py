import base64
import json
import logging
import os
import time
from pathlib import Path
if __package__:
    from .data import NODES,EDGES,PROFILES,DIRECTORY,CITY_BOUNDS
    from .engine import dispatch,advance,complete,update_settings,update_road,update_hospital,gps,reset,plan,capacities
    from .prediction import model_report
    from .routing import build_graph,compare
    from .store import Store,Conflict
    from .live_routes import live_plan
    from .streets import street_plan
    from .places import search_places
    from .realtime import register,unregister,broadcast
else:
    from data import NODES,EDGES,PROFILES,DIRECTORY,CITY_BOUNDS
    from engine import dispatch,advance,complete,update_settings,update_road,update_hospital,gps,reset,plan,capacities
    from prediction import model_report
    from routing import build_graph,compare
    from store import Store,Conflict
    from live_routes import live_plan
    from streets import street_plan
    from places import search_places
    from realtime import register,unregister,broadcast

_store=None
def get_store():
    global _store
    if _store is None:_store=Store()
    return _store

def snapshot(state):
    graph=build_graph(state)
    public={k:v for k,v in state.items() if k!='commands'}
    active_plans={m['id']:plan(state,m['request'],m['ambulance_id'],m['id'],m['picked_up'],m.get('hospital_id'))
                  for m in state['missions'].values() if m['phase'] in ('TO_PICKUP','ON_SCENE','TO_HOSPITAL','NO_ROUTE')}
    return {'state':public,'nodes':NODES,'edges':EDGES,'weighted_roads':graph[1],
            'reservations':capacities(state),'active_plans':active_plans,'profiles':list(PROFILES),'model':model_report(),'city':{k:v for k,v in DIRECTORY.items() if k!='hospitals'},'city_bounds':CITY_BOUNDS,
            'deployment':{'mode':'AWS' if os.environ.get('TABLE_NAME') else 'LOCAL',
                          'location_enabled':os.environ.get('ENABLE_LOCATION')=='true',
                          'alerts_enabled':bool(os.environ.get('ALERT_TOPIC_ARN')),
                          'realtime_enabled':bool(os.environ.get('CONNECTIONS_TABLE')),
                          'sagemaker_ready':bool(os.environ.get('MODEL_BUCKET')),
                          'websocket_url':os.environ.get('WEBSOCKET_URL',''),
                          'tracking_source':'SIMULATED / OPERATOR TEST GPS','graph_source':'MODELED CHENNAI NEIGHBORHOOD GRAPH','hospital_source':'OPENSTREETMAP DIRECTORY / DEMO CAPACITY'}}

def reference_route(state,data):
    if os.environ.get('ENABLE_LOCATION')!='true':
        return 409,{'error':'Amazon Location reference routing is disabled. Deploy with EnableLocation=true.'}
    import boto3
    aid=data.get('ambulance_id');hid=data.get('hospital_id')
    if aid not in state['fleet'] or hid not in state['hospitals']:raise ValueError('Select a valid ambulance and hospital.')
    origin=NODES[state['fleet'][aid]['current_node']];destination=state['hospitals'][hid]
    arguments={'Origin':[origin['lon'],origin['lat']],'Destination':[destination['lon'],destination['lat']],
               'TravelMode':'Car','DepartNow':True,'OptimizeRoutingFor':'FastestRoute','LegGeometryFormat':'Simple',
               'Traffic':{'Usage':'UseTrafficData'}}
    pickup=data.get('pickup')
    if pickup is not None:
        if pickup not in NODES:raise ValueError('Unknown reference pickup.')
        n=NODES[pickup];arguments['Waypoints']=[{'Position':[n['lon'],n['lat']]}]
    response=boto3.client('geo-routes').calculate_routes(**arguments)
    routes=response.get('Routes',[])
    if not routes:return 422,{'error':'Amazon Location returned no route.'}
    route=routes[0];coords=[]
    for leg in route.get('Legs',[]):coords.extend(leg.get('Geometry',{}).get('LineString',[]))
    summary=route.get('Summary',{});overview=summary.get('Overview',summary)
    return 200,{'source':'AMAZON_LOCATION_REAL_ROAD_REFERENCE','coordinates':coords,
                'distance_km':overview.get('Distance',0)/1000,'minutes':overview.get('Duration',0)/60,
                'notice':'Provider road route is independent of the modeled A* graph and synthetic ML predictions.',
                'attributions':response.get('PricingBucket','Amazon Location Service')}

def export_report(state,data):
    report={'project':'RescueRoute Chennai','generated_at':time.time(),'simulation':True,'revision':state['revision'],
            'settings':state['settings'],'model':model_report(),'missions':list(state['missions'].values()),'events':state['events'],
            'sources':{'graph':'MODELED','traffic':'SIMULATED_CHENNAI_CALIBRATED','gps':'SIMULATED / OPERATOR_TEST','hospitals':'OSM_DIRECTORY / OPERATOR_DEMO_CAPACITY','city':'CHENNAI'}}
    bucket=os.environ.get('REPORT_BUCKET')
    if bucket:
        import boto3
        key=f"reports/{int(time.time())}-{state['revision']}.json"
        client=boto3.client('s3');client.put_object(Bucket=bucket,Key=key,Body=json.dumps(report).encode(),ContentType='application/json',ServerSideEncryption='AES256')
        url=client.generate_presigned_url('get_object',Params={'Bucket':bucket,'Key':key},ExpiresIn=300)
        return {'report':report,'download_url':url,'stored_in':'S3','expires_seconds':300}
    return {'report':report,'stored_in':'LOCAL_DOWNLOAD'}

def api(method,path,body=None,store=None):
    store=store or get_store();body={} if body is None else body
    try:
        if method=='GET' and path=='/api/state':return 200,snapshot(store.read())
        if method=='GET' and path=='/api/dataset':
            path=Path(__file__).parent/'models'/'dataset_preview.json'
            return 200,json.loads(path.read_text())
        if not isinstance(body,dict):raise ValueError('Request must be a JSON object.')
        if method=='POST' and path=='/api/plan':return 200,plan(store.read(),body)
        if method=='POST' and path=='/api/analyze':
            state=store.read();m=state['missions'].get(body.get('mission_id'))
            if not m:raise ValueError('Select a valid mission.')
            return 200,plan(state,m['request'],m['ambulance_id'],m['id'],m['picked_up'],m.get('hospital_id'))
        if method=='POST' and path=='/api/benchmark':
            start=body.get('origin','N00');end=body.get('destination','N55')
            if start not in NODES or end not in NODES:raise ValueError('Unknown benchmark junction.')
            state=store.read()
            return 200,{'rows':compare(build_graph(state,body.get('emergency','urgent')),start,end),'origin':start,'destination':end,'revision':state['revision']}
        if method=='POST' and path=='/api/live-plan':return live_plan(store.read(),body)
        if method=='POST' and path=='/api/street-plan':return 200,street_plan(store.read(),body)
        if method=='POST' and path=='/api/reference-route':return reference_route(store.read(),body)
        if method=='POST' and path=='/api/places':return search_places(body.get('query',''),body.get('max_results',8))
        if method=='POST' and path=='/api/export':return 200,export_report(store.read(),body)
        operations={'dispatch':dispatch,'advance':advance,'complete':complete,'settings':update_settings,'road':update_road,'hospital':update_hospital,'gps':gps,'reset':reset}
        name=path.removeprefix('/api/')
        if method=='POST' and path.startswith('/api/') and name in operations:
            state,result=store.mutate(lambda s:operations[name](s,body))
            try:broadcast({'type':'state','revision':state['revision']})
            except Exception:pass
            return 200,{'result':result,**snapshot(state)}
        return 404,{'error':'Endpoint not found.'}
    except (ValueError,TypeError,KeyError) as exc:return 400,{'error':str(exc)}
    except Conflict as exc:return 409,{'error':str(exc)}
    except Exception:
        logging.exception('Request failed')
        return 503,{'error':'Service temporarily unavailable. Check logs and retry.'}

def handler(event,context):
    # WebSocket routes share this Lambda when route key is $connect/$disconnect/$default.
    rc=event.get('requestContext') or {}
    route=rc.get('routeKey')
    if route in ('$connect','$disconnect','$default'):
        cid=rc.get('connectionId')
        if route=='$connect':
            register(cid)
            return {'statusCode':200,'body':'connected'}
        if route=='$disconnect':
            unregister(cid)
            return {'statusCode':200,'body':'disconnected'}
        return {'statusCode':200,'body':'ok'}

    started=time.perf_counter()
    try:
        body=event.get('body') or '{}'
        if event.get('isBase64Encoded'):body=base64.b64decode(body,validate=True).decode()
        if len(body.encode())>32768:raise ValueError('Request exceeds 32 KiB.')
        payload=json.loads(body)
    except (ValueError,UnicodeError):return {'statusCode':400,'body':json.dumps({'error':'Invalid JSON or oversized request.'})}
    method=rc.get('http',{}).get('method','GET')
    status,result=api(method,event.get('rawPath','/'),payload)
    # Embedded metrics are emitted in CloudWatch; never log credentials or request body.
    print(json.dumps({'_aws':{'Timestamp':int(time.time()*1000),'CloudWatchMetrics':[{'Namespace':'RescueRoute','Dimensions':[['Operation']],'Metrics':[{'Name':'RequestLatency','Unit':'Milliseconds'},{'Name':'RequestError','Unit':'Count'}]}]},
                      'Operation':event.get('rawPath','/'),'RequestLatency':(time.perf_counter()-started)*1000,'RequestError':int(status>=400),'status':status}))
    return {'statusCode':status,'headers':{'content-type':'application/json','cache-control':'no-store'},'body':json.dumps(result,allow_nan=False)}
