"""Optional provider roads/traffic. No synthetic fallback is ever labeled live."""
import os
import time
if __package__:
    from .data import NODES, DIRECTORY_BY_ID, CITY_BOUNDS, directory_transport_candidates
    from .engine import request, hospital_options
else:
    from data import NODES, DIRECTORY_BY_ID, CITY_BOUNDS, directory_transport_candidates
    from engine import request, hospital_options

def live_plan(state,data,client=None):
    if os.environ.get('ENABLE_LOCATION')!='true':
        return 409,{'error':'Live road traffic requires AWS deployment with EnableLocation=true. Local traffic scenarios are simulated.'}
    req=request(data);eligible,rejections=hospital_options(state,req)
    if req['ranking_scope']=='directory':eligible=directory_transport_candidates(state)
    if req['preferred_hospital'] and req['ranking_scope']=='directory' and not any(h['id']==req['preferred_hospital'] for h in eligible):
        eligible.append(state['hospitals'][req['preferred_hospital']])
    if not eligible:return 422,{'error':'No hospitals meet the configured care/capacity requirements. Directory records do not establish live bed availability.'}
    if req['preferred_hospital'] and not any(h['id']==req['preferred_hospital'] for h in eligible) and not req['allow_alternative']:
        return 422,{'error':'The chosen hospital does not meet the configured requirements. Choose another or update its operator demo profile.'}
    source=req['pickup_location'] or NODES[req['pickup']]
    origin=[source['lon'],source['lat']]
    if client is None:
        import boto3
        from botocore.config import Config
        client=boto3.client('geo-routes',config=Config(connect_timeout=4,read_timeout=15,retries={'max_attempts':1}))
    # Chunk the destination list at the service limit. Usually only the 16 demo profiles qualify.
    ranked=[];pairs=0;errors=0
    for offset in range(0,len(eligible),500):
        group=eligible[offset:offset+500]
        result=client.calculate_route_matrix(Origins=[{'Position':origin}],
            Destinations=[{'Position':[h['lon'],h['lat']]} for h in group],
            RoutingBoundary={'Geometry':{'BoundingBox':[79.95,12.7,80.45,13.35]}},
            DepartNow=True,TravelMode='Car',OptimizeRoutingFor='FastestRoute',Traffic={'Usage':'UseTrafficData'})
        entries=result.get('RouteMatrix',[[]])[0];pairs+=len(group)
        for i,h in enumerate(group):
            e=entries[i] if i<len(entries) else {'Error':'MissingResult'}
            if e.get('Error') or not isinstance(e.get('Duration'),(int,float)) or not isinstance(e.get('Distance'),(int,float)):
                errors+=1;continue
            ranked.append({'hospital_id':h['id'],'name':h['name'],'minutes':e['Duration']/60,'distance_km':e['Distance']/1000,
                           'capacity_source':h['status_source'],'route_source':'AMAZON_LOCATION_TRAFFIC','wait_min':h['wait_min']})
    ranked.sort(key=lambda h:(h['minutes'],h['hospital_id']))
    if not ranked:return 422,{'error':'The traffic provider could not find a route to a configured hospital.'}
    selected=next((h for h in ranked if h['hospital_id']==req['preferred_hospital']),None) if req['preferred_hospital'] else None
    if req['preferred_hospital'] and selected is None and not req['allow_alternative']:
        return 422,{'error':'No provider route reaches the selected hospital.'}
    selected=selected or ranked[0];hospital=DIRECTORY_BY_ID[selected['hospital_id']]
    response=client.calculate_routes(Origin=origin,Destination=[hospital['lon'],hospital['lat']],
        DepartNow=True,TravelMode='Car',OptimizeRoutingFor='FastestRoute',LegGeometryFormat='Simple',
        MaxAlternatives=2,LegAdditionalFeatures=['TypicalDuration'],Traffic={'Usage':'UseTrafficData'})
    routes=[]
    for r in response.get('Routes',[]):
        coords=[]
        for leg in r.get('Legs',[]):coords.extend(leg.get('Geometry',{}).get('LineString',[]))
        summary=r.get('Summary',{});summary=summary.get('Overview',summary)
        routes.append({'coordinates':coords,'minutes':summary.get('Duration',0)/60,'distance_km':summary.get('Distance',0)/1000})
    if not routes:return 422,{'error':'Provider returned a matrix estimate but no drawable road route. Refresh and retry.'}
    routes.sort(key=lambda r:r['minutes'])
    return 200,{'source':'AMAZON_LOCATION_TRAFFIC','fetched_at':time.time(),'revision':state['revision'],
        'pickup':source,'request':req,'top_hospitals':ranked[:5],'selected_hospital':selected,'routes':routes,
        'ranking_scope':req['ranking_scope'],'compared_hospitals':len(ranked),'failed_hospitals':errors,'billed_matrix_pairs':pairs,
        'notice':'Directory scope ranks travel only and does not certify emergency suitability. Provider car-road estimates use traffic data as available at request time. Hospital capacity/care profiles and ambulance GPS remain operator demonstration inputs. This road preview is independent of modeled A* missions.'}
