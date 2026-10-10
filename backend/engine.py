"""Hospital constraints, live mission state, graph updates, and A* replanning."""
import hashlib
import json
import math
import time
import uuid
if __package__:
    from .data import ACTIVE_PHASES,EDGES,HOSPITALS,NODES,PROFILES,CITY_BOUNDS,DIRECTORY_BY_ID,directory_transport_candidates,haversine,initial_state
    from .routing import build_graph,compare,search
    from .store import Conflict
else:
    from data import ACTIVE_PHASES,EDGES,HOSPITALS,NODES,PROFILES,CITY_BOUNDS,DIRECTORY_BY_ID,directory_transport_candidates,haversine,initial_state
    from routing import build_graph,compare,search
    from store import Conflict

def finite(value,minimum,maximum,label):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not minimum<=value<=maximum:
        raise ValueError(f'{label} must be between {minimum} and {maximum}.')
    return value

def request(data):
    if not isinstance(data,dict):raise ValueError('A JSON object is required.')
    pickup=data.get('pickup','N22');category=data.get('category','general');emergency=data.get('emergency','urgent')
    if not isinstance(pickup,str) or pickup not in NODES:raise ValueError('Unknown pickup junction.')
    if category not in ('general','trauma','cardiac') or emergency not in ('urgent','critical'):raise ValueError('Unknown emergency category or level.')
    needs_icu=data.get('needs_icu',False)
    if not isinstance(needs_icu,bool):raise ValueError('ICU requirement must be true or false.')
    location=data.get('pickup_location')
    if location is not None:
        if not isinstance(location,dict):raise ValueError('Pickup location must be an object.')
        lat=finite(location.get('lat'),CITY_BOUNDS['south'],CITY_BOUNDS['north'],'Pickup latitude')
        lon=finite(location.get('lon'),CITY_BOUNDS['west'],CITY_BOUNDS['east'],'Pickup longitude')
        node=min(NODES.values(),key=lambda n:haversine(n,{'lat':lat,'lon':lon}));pickup=node['id']
        location={'lat':lat,'lon':lon,'label':str(location.get('label','Selected Chennai location'))[:160],
                  'source':'BROWSER_LOCATION' if location.get('source')=='BROWSER_LOCATION' else 'USER_SELECTED'}
    preferred=data.get('preferred_hospital') or None
    if preferred is not None and (not isinstance(preferred,str) or preferred not in DIRECTORY_BY_ID):raise ValueError('Unknown preferred hospital.')
    scope=data.get('ranking_scope','configured')
    if scope not in ('configured','directory'):raise ValueError('Unknown hospital ranking scope.')
    fallback=data.get('allow_alternative',False)
    if not isinstance(fallback,bool):raise ValueError('Alternative hospital flag must be true or false.')
    return {'pickup':pickup,'pickup_location':location,'preferred_hospital':preferred,'allow_alternative':fallback,
            'ranking_scope':scope,'category':category,'emergency':emergency,'needs_icu':needs_icu or emergency=='critical','on_scene_min':2 if emergency=='critical' else 3}


def capacities(state,exclude=None):
    counts={h:{'beds':0,'icu':0} for h in state['hospitals']}
    for m in state['missions'].values():
        if m['id']!=exclude and not m.get('reservation_pending') and m['phase'] in ACTIVE_PHASES and m.get('hospital_id') in counts:
            c=counts[m['hospital_id']];c['beds']+=1;c['icu']+=int(m['request']['needs_icu'])
    return counts

def hospital_options(state,req,exclude=None):
    counts=capacities(state,exclude);options=[];rejected=[]
    for h in state['hospitals'].values():
        reasons=[]
        if h.get('status_source')=='UNKNOWN':reasons.append('Capacity and care profile not configured; operator confirmation required')
        if not h['accepting']:reasons.append('Not accepting emergencies')
        if req['category'] not in h['capabilities']:reasons.append('Required capability unavailable')
        if h['beds']-counts[h['id']]['beds']<=0:reasons.append('No unreserved emergency beds')
        if req['needs_icu'] and h['icu']-counts[h['id']]['icu']<=0:reasons.append('No unreserved ICU beds')
        if reasons:rejected.append({'hospital_id':h['id'],'name':h['name'],'reasons':reasons})
        else:options.append(h)
    return options,rejected

def plan(state,data,fixed_ambulance=None,exclude=None,picked_up=False,target_hospital=None):
    req=request(data);bundle=build_graph(state,req['emergency']);hospitals,rejections=hospital_options(state,req,exclude)
    eligible=hospitals[:]
    preferred=req['preferred_hospital']
    if target_hospital:hospitals=[h for h in hospitals if h['id']==target_hospital]
    elif preferred:
        requested=[h for h in hospitals if h['id']==preferred]
        if requested or not req['allow_alternative']:hospitals=requested
    source=req['pickup_location'] or NODES[req['pickup']]
    source_km=haversine(NODES[req['pickup']],source)*1.2
    # Approximate connectors are labeled separately; they are not surveyed roads.
    connector_factor=(1+2.8*PROFILES[state['settings']['traffic']]['Local streets'])*(1+.25*state['settings']['rain'])
    source_min=source_km/25*60*connector_factor
    top=[];ranking_cache={};second_cache={}
    if not picked_up:
        for h in (eligible if req['ranking_scope']=='configured' else directory_transport_candidates(state)):
            if h['node'] not in ranking_cache:ranking_cache[h['node']]=search(bundle,req['pickup'],h['node'],objective='minutes')
            route=ranking_cache[h['node']]
            if route is None:continue
            connector=h.get('connector_km',0)/25*60*connector_factor
            top.append({'hospital_id':h['id'],'name':h['name'],'node':h['node'],'minutes':source_min+route['minutes']+connector,
                        'distance_km':source_km+route['km']+h.get('connector_km',0),'wait_min':h['wait_min'],
                        'capacity_source':h.get('status_source','DEMO_ASSUMPTION'),'route_source':'MODELED_ASTAR_PLUS_APPROXIMATE_CONNECTORS'})
        top.sort(key=lambda x:(x['minutes'],x['hospital_id']))

    fleet=[state['fleet'][fixed_ambulance]] if fixed_ambulance else [a for a in state['fleet'].values() if a['status']=='AVAILABLE']
    candidates=[]
    for a in fleet:
        start=a['current_node'];pickup=start if picked_up else req['pickup']
        first=search(bundle,start,pickup)
        if first is None:continue
        for h in hospitals:
            if h['node'] not in second_cache:second_cache[h['node']]=search(bundle,pickup,h['node'])
            second=second_cache[h['node']]
            if second is None:continue
            ready=0 if fixed_ambulance else a['ready_min'];scene=0 if picked_up else req['on_scene_min']
            connector=h.get('connector_km',0)/25*60*connector_factor
            extra=connector+(0 if picked_up else 2*source_min)
            arrival=ready+first['minutes']+scene+second['minutes']+extra
            score=ready+first['cost']+scene+second['cost']+h['wait_min']+extra
            candidates.append({'ambulance_id':a['id'],'hospital_id':h['id'],'hospital_name':h['name'],
                               'pickup_route':first,'hospital_route':second,'response_min':ready+first['minutes']+(0 if picked_up else source_min),
                               'arrival_min':arrival,'score_min':score,'wait_min':h['wait_min'],'connector_minutes':extra,
                               'risk_penalty_min':first['penalty']+second['penalty'],'distance_km':first['km']+second['km']+h.get('connector_km',0)+(0 if picked_up else 2*source_km)})
    candidates.sort(key=lambda c:(c['score_min'],c['arrival_min'],c['ambulance_id'],c['hospital_id']))
    best=candidates[0] if candidates else None
    comparison=[]
    if best:
        # Same ambulance/hospital and same graph for a fair algorithm comparison.
        a=state['fleet'][best['ambulance_id']];start=a['current_node'];pickup=start if picked_up else req['pickup']
        for algorithm,objective,label in [('astar','cost','A*'),('dijkstra','cost','Dijkstra'),('bfs','cost','BFS — fewest roads'),('dijkstra','km','Shortest distance')]:
            x=search(bundle,start,pickup,algorithm,objective);y=search(bundle,pickup,state['hospitals'][best['hospital_id']]['node'],algorithm,objective)
            if x and y:
                comparison.append({'label':label,'algorithm':algorithm,'minutes':x['minutes']+y['minutes'],
                                   'cost_min':x['cost']+y['cost'],'km':x['km']+y['km'],'expanded':x['expanded']+y['expanded'],
                                   'runtime_ms':x['runtime_ms']+y['runtime_ms'],'nodes':x['nodes']+y['nodes'][1:]})
    return {'revision':state['revision'],'request':req,'candidates':candidates,'best':best,'top_hospitals':top[:5],'hospital_rejections':rejections,'comparison':comparison}

def log(state,kind,text,mission=None,extra=None):
    item={'id':str(uuid.uuid4()),'at':time.time(),'kind':kind,'text':text,'mission_id':mission}
    if extra:item.update(extra)
    state['events'].insert(0,item);state['events']=state['events'][:120]

def remember(state,data,operation,result):
    key=data.get('command_id')
    if key:
        if not isinstance(key,str) or len(key)>100:raise ValueError('Invalid command ID.')
        state['commands'][key]={'operation':operation,'fingerprint':fingerprint(data),'result':result}
        while len(state['commands'])>100:state['commands'].pop(next(iter(state['commands'])))

def fingerprint(data):return hashlib.sha256(json.dumps({k:v for k,v in data.items() if k!='command_id'},sort_keys=True).encode()).hexdigest()
def repeated(state,data,operation):
    key=data.get('command_id')
    if not key:return None
    if not isinstance(key,str) or len(key)>100:raise ValueError('Invalid command ID.')
    old=state['commands'].get(key)
    if old:
        if old['operation']!=operation or old['fingerprint']!=fingerprint(data):raise Conflict('Command ID reused with different parameters.')
        return old['result']
    return None

def apply_plan(state,mission,result,reason):
    old_hospital=mission.get('hospital_id');old_route=mission.get('remaining_route');old_eta=mission.get('remaining_min')
    best=result['best'];a=state['fleet'][mission['ambulance_id']]
    if not best:
        mission.update({'phase':'NO_ROUTE','hospital_id':None,'remaining_route':None,'remaining_min':None})
        a['status']='NO_ROUTE'
        log(state,'NO_ROUTE','No feasible hospital route. Ambulance paused; capacity or road conditions must change.',mission['id'])
        return
    phase='TO_HOSPITAL' if mission['picked_up'] else ('ON_SCENE' if a['current_node']==mission['request']['pickup'] else 'TO_PICKUP')
    route=best['hospital_route'] if mission['picked_up'] else best['pickup_route']
    mission.update({'phase':phase,'hospital_id':best['hospital_id'],'remaining_route':route,
                    'hospital_route':best['hospital_route'],'remaining_min':best['arrival_min'],
                    'score_min':best['score_min'],'response_min':best['response_min']})
    a['status']=phase
    changed=reason!='Position update' and old_hospital and (old_hospital!=best['hospital_id'] or (old_route and old_route['roads']!=route['roads']))
    if changed:
        mission['reroutes']+=1
        log(state,'REROUTE',f"A* replanned from {a['current_node']}: {reason}.",mission['id'],
            {'previous_eta_min':old_eta,'new_eta_min':mission['remaining_min'],'previous_hospital_id':old_hospital,'hospital_id':mission['hospital_id']})
    log(state,'HOSPITAL_ETA',f"ETA updated for {state['hospitals'][mission['hospital_id']]['short']}: {mission['remaining_min']:.1f} modeled min.",mission['id'],
        {'hospital_id':mission['hospital_id'],'eta_min':mission['remaining_min']})

def replan_active(state,reason):
    # Earlier missions retain priority when reported capacity falls.
    active=sorted((m for m in state['missions'].values() if m['phase'] in ACTIVE_PHASES),key=lambda m:m['created'])
    for m in active:m['reservation_pending']=True
    for m in active:
        apply_plan(state,m,plan(state,m['request'],m['ambulance_id'],m['id'],m['picked_up']),reason)
        m.pop('reservation_pending',None)

def dispatch(state,data):
    old=repeated(state,data,'dispatch')
    if old:return old
    if data.get('expected_revision',state['revision'])!=state['revision']:raise Conflict('The planning snapshot changed. Calculate a fresh plan before dispatch.')
    result=plan(state,data)
    if not result['best']:raise Conflict('No available ambulance and compatible hospital route.')
    best=result['best'];a=state['fleet'][best['ambulance_id']];mid=str(uuid.uuid4())
    mission={'id':mid,'created':time.time(),'request':result['request'],'ambulance_id':a['id'],'hospital_id':None,
             'phase':'TO_PICKUP','picked_up':False,'elapsed_min':a['ready_min'],'original_eta_min':best['arrival_min'],
             'reroutes':0,'gps_updates':0,'distance_travelled_km':0}
    state['missions'][mid]=mission;a['mission_id']=mid
    best['arrival_min']-=a['ready_min'];best['response_min']-=a['ready_min'];best['score_min']-=a['ready_min']
    apply_plan(state,mission,result,'Initial dispatch')
    log(state,'DISPATCH',f"{a['id']} assigned to pickup {result['request']['pickup']}.",mid)
    done={'mission_id':mid};remember(state,data,'dispatch',done)
    # Bound stored history to keep the DynamoDB demo document below its item limit.
    completed=sorted([m for m in state['missions'].values() if m['phase']=='COMPLETED'],key=lambda m:m['created'])
    for m in completed[:-30]:state['missions'].pop(m['id'])
    return done

def advance(state,data):
    old=repeated(state,data,'advance')
    if old:return old
    mid=data.get('mission_id');m=state['missions'].get(mid)
    if not m:raise ValueError('Unknown mission.')
    a=state['fleet'][m['ambulance_id']]
    if m['phase']=='NO_ROUTE':raise Conflict('Ambulance is paused: no feasible route.')
    if m['phase'] not in ACTIVE_PHASES:return {'mission_id':mid}
    if m['phase']=='ON_SCENE':
        m['picked_up']=True;m['elapsed_min']+=m['request']['on_scene_min']
        if m['request'].get('pickup_location'):
            connector_km=haversine(NODES[m['request']['pickup']],m['request']['pickup_location'])*1.2
            factor=(1+2.8*PROFILES[state['settings']['traffic']]['Local streets'])*(1+.25*state['settings']['rain'])
            m['elapsed_min']+=2*connector_km/25*60*factor;m['distance_travelled_km']+=2*connector_km

        log(state,'PATIENT_PICKUP','Modeled on-scene interval completed; transport begins.',mid)
    else:
        route=m['remaining_route']
        if len(route['nodes'])>1:
            edge_id=route['roads'][0];bundle=build_graph(state,m['request']['emergency']);e=bundle[1].get(edge_id)
            if e is None:raise Conflict('Route changed. Refresh before the next GPS step.')
            a['current_node']=route['nodes'][1];m['elapsed_min']+=e['minutes'];m['distance_travelled_km']+=e['km'];m['gps_updates']+=1
            log(state,'GPS',f"{a['id']} simulated GPS at {a['current_node']}.",mid)
    result=plan(state,m['request'],m['ambulance_id'],mid,m['picked_up'])
    # Keep hospital destination stable for ordinary tracking updates unless no longer feasible.
    if m.get('hospital_id'):
        retained=next((c for c in result['candidates'] if c['hospital_id']==m['hospital_id']),None)
        if retained:result['best']=retained
    apply_plan(state,m,result,'Position update')
    if m['picked_up'] and m['hospital_id'] and a['current_node']==state['hospitals'][m['hospital_id']]['node']:
        m['elapsed_min']+=result['best']['connector_minutes']
        m['distance_travelled_km']+=state['hospitals'][m['hospital_id']].get('connector_km',0)
        h=state['hospitals'][m['hospital_id']];h['beds']-=1
        if m['request']['needs_icu']:h['icu']-=1
        m['phase']='ARRIVED';m['remaining_min']=0;a['status']='ARRIVED'
        log(state,'ARRIVAL',f"{a['id']} arrived at {h['short']}; modeled bed allocated.",mid)
    done={'mission_id':mid};remember(state,data,'advance',done);return done

def complete(state,data):
    mid=data.get('mission_id');m=state['missions'].get(mid)
    if not m:raise ValueError('Unknown mission.')
    if m['phase']=='COMPLETED':return {'mission_id':mid}
    if m['phase']!='ARRIVED':raise Conflict('Complete the simulated journey before releasing the ambulance.')
    m['phase']='COMPLETED';a=state['fleet'][m['ambulance_id']];a['status']='AVAILABLE';a['mission_id']=None
    log(state,'COMPLETE',f"{a['id']} released at the hospital location, not teleported to base.",mid)
    return {'mission_id':mid}

def update_settings(state,data):
    s=state['settings'];value=data.get('traffic',s['traffic'])
    if value not in PROFILES:raise ValueError('Unknown traffic profile.')
    s['traffic']=value
    s['hour']=finite(data.get('hour',s['hour']),0,23,'Hour')
    s['weekday']=finite(data.get('weekday',s['weekday']),0,6,'Weekday')
    s['rain']=finite(data.get('rain',s['rain']),0,2,'Rain')
    if 'use_ml' in data:
        if not isinstance(data['use_ml'],bool):raise ValueError('ML mode must be true or false.')
        s['use_ml']=data['use_ml']
    log(state,'TRAFFIC','Traffic/time/weather weights updated. Active missions replanned.')
    replan_active(state,'Traffic/time/weather changed');return {'updated':True}

def update_road(state,data):
    road=data.get('road_id')
    if not isinstance(road,str) or road not in {e['id'] for e in EDGES}:raise ValueError('Unknown road.')
    closed=data.get('closed',False)
    if not isinstance(closed,bool):raise ValueError('Road closure must be true or false.')
    override={'closed':closed}
    if 'congestion' in data:override['congestion']=finite(data['congestion'],0,1,'Congestion')
    state['roads'][road]=override
    log(state,'ROAD_CLOSURE' if closed else 'TRAFFIC',f"{road}: {'closed' if closed else 'road condition updated'}.")
    replan_active(state,'Road condition changed');return {'updated':True}

def update_hospital(state,data):
    hid=data.get('hospital_id')
    if hid not in state['hospitals']:raise ValueError('Unknown hospital.')
    h=state['hospitals'][hid]
    if 'capabilities' in data:
        values=data['capabilities']
        if not isinstance(values,list) or any(v not in ('general','trauma','cardiac') for v in values):raise ValueError('Invalid care profile.')
        h['capabilities']=sorted(set(values))
    h['status_source']='OPERATOR_DEMO_INPUT'
    for key in ('beds','icu'):
        if key in data:
            value=finite(data[key],0,100,key)
            if int(value)!=value:raise ValueError('Bed counts must be whole numbers.')
            h[key]=int(value)
    if h['icu']>h['beds']:raise ValueError('ICU beds cannot exceed emergency beds.')
    if 'accepting' in data:
        if not isinstance(data['accepting'],bool):raise ValueError('Acceptance must be true or false.')
        h['accepting']=data['accepting']
    if 'wait_min' in data:h['wait_min']=finite(data['wait_min'],0,60,'Handover wait')
    log(state,'HOSPITAL_STATUS',f"{h['short']} availability updated.")
    replan_active(state,'Hospital availability changed');return {'updated':True}

def gps(state,data):
    """Accept an operator/simulator coordinate, snap only within 250 m of model graph."""
    aid=data.get('ambulance_id')
    if aid not in state['fleet']:raise ValueError('Unknown ambulance.')
    lat=finite(data.get('lat'),-90,90,'Latitude');lon=finite(data.get('lon'),-180,180,'Longitude')
    node=min(NODES.values(),key=lambda n:haversine(n,{'lat':lat,'lon':lon}))
    if haversine(node,{'lat':lat,'lon':lon})>.25:raise ValueError('GPS is outside the demonstration graph snapping range (250 m).')
    a=state['fleet'][aid]
    if a['status'] in ('ON_SCENE','ARRIVED'):raise Conflict('Use the mission step controls for pickup or arrival transitions.')
    a['current_node']=node['id'];a['gps_source']='OPERATOR_TEST_GPS'
    if a['mission_id']:
        m=state['missions'][a['mission_id']];m['gps_updates']+=1
        apply_plan(state,m,plan(state,m['request'],aid,m['id'],m['picked_up']),'Test GPS update')
    log(state,'GPS',f"Operator test GPS received for {aid}; snapped to {node['id']}.")
    return {'snapped_node':node['id'],'source':'OPERATOR_TEST_GPS'}

def reset(state,data):
    if data.get('confirm')!='RESET_DEMO':raise ValueError('Explicit RESET_DEMO confirmation is required.')
    revision=state['revision'];state.clear();state.update(initial_state());state['revision']=revision
    log(state,'RESET','Shared demonstration reset to initial data.')
    return {'reset':True}
