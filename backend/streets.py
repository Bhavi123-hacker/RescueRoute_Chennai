"""Offline directed OSM road preview. Traffic/speeds are scenario estimates, not live."""
import heapq,json,math,time
from functools import lru_cache
from pathlib import Path
if __package__:
 from .data import DIRECTORY_BY_ID,NODES,haversine,directory_transport_candidates
 from .engine import request,hospital_options
else:
 from data import DIRECTORY_BY_ID,NODES,haversine,directory_transport_candidates
 from engine import request,hospital_options

class StreetNetwork:
 def __init__(self,data):
  self.metadata=data['metadata'];self.nodes=data['nodes'];self.ways=data['ways'];self.edges={e['id']:e for e in data['edges']};self.graph={n:[] for n in self.nodes};self.cells={}
  for e in data['edges']:
   w=self.ways[e['way']]
   if w['forward']:self.graph[e['a']].append((e['b'],e['id'],False))
   if w['backward']:self.graph[e['b']].append((e['a'],e['id'],True))
  # Snap to the largest weak component: isolated map pieces are never joined by fake streets.
  undirected={n:set() for n in self.nodes}
  for e in data['edges']:undirected[e['a']].add(e['b']);undirected[e['b']].add(e['a'])
  unseen=set(self.nodes);largest=set()
  while unseen:
   start=min(unseen);unseen.remove(start);component={start};stack=[start]
   while stack:
    for n in undirected[stack.pop()]:
     if n in unseen:unseen.remove(n);component.add(n);stack.append(n)
   if len(component)>len(largest):largest=component
  self.connected=largest
  for n in largest:
   lon,lat=self.nodes[n];self.cells.setdefault((math.floor(lon/.003),math.floor(lat/.003)),[]).append(n)
 def snap(self,point):
  lon,lat=point['lon'],point['lat'];cx,cy=math.floor(lon/.003),math.floor(lat/.003);found=[]
  for radius in range(1,16):
   found=[n for x in range(cx-radius,cx+radius+1) for y in range(cy-radius,cy+radius+1) for n in self.cells.get((x,y),[])]
   if found:
    nearest=min(found,key=lambda n:self.km(point,self.nodes[n]));dist=self.km(point,self.nodes[nearest])
    # Search until a point farther away than all unseen cells has been found.
    if dist<max(0,(radius-1))*.003*108 or radius==15:return nearest,dist
  raise ValueError('No connected mapped road near this location. Choose a point closer to a mapped driving corridor.')
 @staticmethod
 def km(point,coords):return haversine(point,{'lon':coords[0],'lat':coords[1]})
 def edge_minutes(self,n,nxt,eid,reverse,settings,tide):
  e=self.edges[eid];w=self.ways[e['way']];kind=w['kind'].replace('_link','')
  a,b=self.nodes[n],self.nodes[nxt]
  if settings.get('use_ml',True):
   try:
    if __package__:from .prediction import street_multiplier
    else:from prediction import street_multiplier
    factor,_=street_multiplier(kind,w['speed'],settings,'balanced')
   except Exception:
    factor=1.35
  else:
   scenario=settings['traffic'];factor=1.15 if scenario=='normal' else (2.5 if kind in ('primary','secondary','tertiary') else 1.6) if scenario=='rush' else (2.8 if kind in ('primary','secondary') else 1.4)
   factor*=1+.2*settings['rain']
  if tide=='east' and b[0]>a[0]+.00001 or tide=='west' and b[0]<a[0]-.00001:factor*=2
  return e['km']/w['speed']*60*factor
 def search(self,start,settings,tide='balanced',closed=(),goal=None,goals=None):
  best={start:0.};previous={};queue=[(0.,start)];blocked=set(closed)
  pending=set(goals or ())
  if goal is not None:pending.add(goal)
  while queue:
   cost,n=heapq.heappop(queue)
   if cost>best[n]+1e-10:continue
   if pending:
    pending.discard(n)
    if not pending:break
   elif n==goal:break
   for nxt,eid,reverse in self.graph[n]:
    if self.edges[eid]['way'] in blocked:continue
    value=cost+self.edge_minutes(n,nxt,eid,reverse,settings,tide)
    if value<best.get(nxt,math.inf)-1e-10:
     best[nxt]=value;previous[nxt]=(n,eid,reverse);heapq.heappush(queue,(value,nxt))
  return best,previous
 def route(self,start,end,result,source,destination):
  best,prev=result
  if end not in best:return None
  arcs=[];n=end
  while n!=start:
   before,eid,reverse=prev[n];arcs.append((eid,reverse));n=before
  arcs.reverse();coords=[];km=0;streets=[]
  for eid,reverse in arcs:
   e=self.edges[eid];shape=list(reversed(e['coordinates'])) if reverse else e['coordinates'];coords.extend(shape if not coords else shape[1:]);km+=e['km'];w=self.ways[e['way']]
   if not streets or streets[-1]['way_id']!=e['way']:streets.append({'way_id':e['way'],'name':w['name'],'oneway':w['forward']!=w['backward'],'distance_km':e['km']})
   else:streets[-1]['distance_km']+=e['km']
  if not coords:coords=[self.nodes[start],self.nodes[end]]
  source_km=self.km(source,self.nodes[start]);end_km=self.km(destination,self.nodes[end]);connector=source_km+end_km
  return {'coordinates':coords,'minutes':best[end]+connector/15*60,'road_minutes':best[end],'distance_km':km+connector,'road_distance_km':km,'connector_km':connector,'source_connector':[[source['lon'],source['lat']],self.nodes[start]],'destination_connector':[self.nodes[end],[destination['lon'],destination['lat']]],'streets':streets,'arcs':[[a,r] for a,r in arcs],'oneway_segments':sum(self.ways[self.edges[eid]['way']]['forward']!=self.ways[self.edges[eid]['way']]['backward'] for eid,_ in arcs)}

@lru_cache(maxsize=1)
def network():return StreetNetwork(json.loads((Path(__file__).parent/'city/street_graph.json').read_text()))
@lru_cache(maxsize=1)
def hospital_snaps():
 net=network();result={}
 for h in DIRECTORY_BY_ID.values():
  try:result[h['id']]=net.snap(h)
  except ValueError:pass
 return result

def street_plan(state,data):
 req=request(data);net=network();tide=data.get('directional_traffic','balanced');ret=data.get('return_to','pickup')
 if tide not in ('balanced','east','west'):raise ValueError('Unknown directional traffic scenario.')
 if ret not in ('pickup','base'):raise ValueError('Unknown return destination.')
 closed=data.get('closed_streets',[])
 if not isinstance(closed,list) or len(closed)>20 or any(not isinstance(w,str) or w not in net.ways for w in closed):raise ValueError('Choose at most 20 known mapped streets to close.')
 src=req['pickup_location'] or NODES[req['pickup']];start,source_snap=net.snap(src);settings=state['settings']
 hospitals,_=hospital_options(state,req)
 if req['ranking_scope']=='directory':hospitals=directory_transport_candidates(state)
 snaps=hospital_snaps();failed=0
 # Rank nearby candidates first so Dijkstra can stop once their snap nodes are settled.
 ranked_seed=sorted(hospitals,key=lambda h:haversine(src,h))[:24]
 goal_nodes={snaps[h['id']][0] for h in ranked_seed if h['id'] in snaps and snaps[h['id']][1]<=1.5}
 result=net.search(start,settings,tide,closed,goals=goal_nodes or None)
 rows=[]
 for h in ranked_seed:
  point=snaps.get(h['id'])
  if not point or point[0] not in result[0] or point[1]>1.5:failed+=1;continue
  connector=source_snap+point[1]
  rows.append({'hospital_id':h['id'],'name':h['name'],'minutes':result[0][point[0]]+connector/15*60,'distance_km':0,'capacity_source':h['status_source'],'route_source':'OSM_DIRECTED_ROADS_RF_SPEEDS' if settings.get('use_ml',True) else 'OSM_DIRECTED_ROADS_SCENARIO_SPEEDS','connector_km':connector})
 rows.sort(key=lambda h:(h['minutes'],h['hospital_id']))
 for h in rows[:5]:h['distance_km']=net.route(start,snaps[h['hospital_id']][0],result,src,DIRECTORY_BY_ID[h['hospital_id']])['distance_km']
 chosen=req['preferred_hospital'] or data.get('hospital_id') or (rows[0]['hospital_id'] if rows else None)
 if chosen and chosen not in DIRECTORY_BY_ID:raise ValueError('Unknown route-preview hospital.')
 # Ensure preferred hospital is reachable even if outside the nearby seed.
 if chosen and chosen in snaps and (not rows or chosen not in {r['hospital_id'] for r in rows}):
  result=net.search(start,settings,tide,closed,goal=snaps[chosen][0])
 target=DIRECTORY_BY_ID.get(chosen);end=snaps.get(chosen)
 transport=net.route(start,end[0],result,src,target) if end and end[1]<=1.5 and end[0] in result[0] else None
 aid=data.get('ambulance_id') or min(state['fleet'].values(),key=lambda a:haversine(src,NODES[a['current_node']]))['id']
 if aid not in state['fleet']:raise ValueError('Unknown preview ambulance.')
 ambulance=state['fleet'][aid];origin=NODES[ambulance['current_node']];base=NODES[ambulance['node']];response=None;back=None
 simple=bool(data.get('simple',False))
 if target and transport and not simple:
  astart,_=net.snap(origin);response=net.route(astart,start,net.search(astart,settings,tide,closed,goal=start),origin,src)
  back_to=src if ret=='pickup' else base;bend,_=net.snap(back_to)
  back=net.route(end[0],bend,net.search(end[0],settings,tide,closed,goal=bend),target,back_to)
 shared=[];same=False
 if transport and back and ret=='pickup':
  outgoing=transport['arcs'];incoming=back['arcs'];same=incoming==[[eid,not rev] for eid,rev in reversed(outgoing)]
  a={x[0] for x in outgoing};b={x[0] for x in incoming};shared=sorted(a&b)
 return {'source':'OSM_DIRECTED_ROADS_RF_SPEEDS' if settings.get('use_ml',True) else 'OSM_DIRECTED_ROADS_SCENARIO_SPEEDS','revision':state['revision'],'request':req,'metadata':net.metadata,'top_hospitals':rows[:5],'compared_hospitals':len(rows),'unreachable_hospitals':failed,'selected_hospital':chosen,'pickup':src,'hospital':target,'ambulance_id':aid,'base':base,'return_to':ret,'directional_traffic':tide,'closed_streets':closed,'legs':{'response':response,'transport':transport,'return':back},'return_uses_reversed_path':same,'shared_segments':len(shared),'notice':'Mapped street geometry with RF/scenario travel estimates (not live provider traffic). Dotted connectors are approximate. Turn restrictions/gates are not modeled. Preview is separate from the 36-anchor A* mission simulator.'}
