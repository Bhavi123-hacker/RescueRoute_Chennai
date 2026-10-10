"""Rebuild attributed, directed street data from the bundled Overpass snapshot."""
from collections import Counter
from pathlib import Path
import json,math
ROOT=Path(__file__).resolve().parents[1]
SPEEDS={'motorway':70,'trunk':60,'primary':45,'secondary':35,'tertiary':30,'residential':22,'unclassified':22,'living_street':12,'service':15}
def distance(a,b):
 lat1,lat2=map(math.radians,[a[1],b[1]]);dl=lat2-lat1;do=math.radians(b[0]-a[0]);return 12742*math.asin(min(1,math.sqrt(math.sin(dl/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(do/2)**2)))
def speed(tags):
 raw=str(tags.get('maxspeed','')).lower().strip()
 try:
  v=float(raw.replace('mph','').strip())*(1.60934 if 'mph' in raw else 1)
  if 5<=v<=120:return v,'OSM_MAXSPEED'
 except ValueError:pass
 return SPEEDS.get(tags['highway'].replace('_link',''),22),'CLASS_ASSUMPTION'
def build(raw):
 ways=[];counts=Counter();skipped=0
 for w in raw['elements']:
  t=w.get('tags',{})
  if len(w.get('geometry',[]))!=len(w.get('nodes',[])) or len(w.get('nodes',[]))<2:continue
  access=t.get('motorcar',t.get('motor_vehicle',t.get('vehicle',t.get('access','yes'))))
  if access in ('no','private') or t.get('service') in ('driveway','parking_aisle') or t.get('oneway') in ('reversible','alternating'):
   skipped+=1;continue
  v,source=speed(t)
  oneway=t.get('oneway:motor_vehicle',t.get('oneway', 'yes' if t.get('junction')=='roundabout' or t['highway']=='motorway' else 'no'))
  fwd=oneway!='-1' and t.get('motor_vehicle:forward',t.get('vehicle:forward','yes'))!='no'
  bwd=oneway not in ('yes','1','true') and t.get('motor_vehicle:backward',t.get('vehicle:backward','yes'))!='no'
  if not (fwd or bwd):continue
  coords=[[round(g['lon'],7),round(g['lat'],7)] for g in w['geometry']]
  ways.append({'id':str(w['id']),'name':t.get('name',t.get('ref','Unnamed '+t['highway'].replace('_',' ')+' road')),'kind':t['highway'],'speed':v,'speed_source':source,'forward':fwd,'backward':bwd,'nodes':[str(n) for n in w['nodes']],'coordinates':coords})
  counts.update(set(w['nodes']))
 nodes={};edges=[]
 for w in ways:
  ids=w['nodes'];coords=w['coordinates'];start=0;km=0;idx=0
  for i in range(1,len(ids)):
   km+=distance(coords[i-1],coords[i])
   if i!=len(ids)-1 and counts[int(ids[i])]<2 and km<.2:continue
   a,b=ids[start],ids[i];nodes[a]=coords[start];nodes[b]=coords[i]
   if a!=b and km>.000001:edges.append({'id':w['id']+':'+str(idx),'a':a,'b':b,'way':w['id'],'km':round(km,6),'coordinates':coords[start:i+1]})
   idx+=1;start=i;km=0
 meta={'source':'OPENSTREETMAP_STREET_SNAPSHOT','timestamp':raw['osm3s']['timestamp_osm_base'],'license':'ODbL 1.0','attribution':'© OpenStreetMap contributors','bounds':[80.05,12.8,80.35,13.25],'ways':len(ways),'nodes':len(nodes),'segments':len(edges),'oneway_ways':sum(w['forward']!=w['backward'] for w in ways),'excluded_restricted_ways':skipped,'notice':'One-way/access screening implemented. Turn restrictions, conditional access, gates/barriers and real traffic are not modeled. Endpoint connectors are approximate.'}
 compactways={w['id']:{k:v for k,v in w.items() if k not in ('nodes','coordinates')} for w in ways}
 graph={'metadata':meta,'nodes':nodes,'edges':edges,'ways':compactways}
 display={'metadata':meta,'roads':[{k:w[k] for k in ('id','name','kind','coordinates','forward','backward')} for w in ways]}
 return graph,display
if __name__=='__main__':
 graph,display=build(json.loads((ROOT/'backend/city/roads_snapshot.json').read_text()))
 for p,data in [(ROOT/'backend/city/street_graph.json',graph),(ROOT/'frontend/assets/chennai_streets.json',display)]:p.write_text(json.dumps(data,separators=(',',':')),encoding='utf-8')
 print(json.dumps(graph['metadata'],indent=2))
