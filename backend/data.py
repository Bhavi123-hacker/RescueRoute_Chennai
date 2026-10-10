"""Georeferenced DEMONSTRATION graph, not a surveyed Chennai street network."""
import math

def haversine(a, b):
    lat1, lat2 = math.radians(a['lat']), math.radians(b['lat'])
    dlat = lat2-lat1
    dlon = math.radians(b['lon']-a['lon'])
    return 6371 * 2 * math.asin(min(1, math.sqrt(math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2)))

# Approximate neighborhood anchors. Road connections are a modeled network, not surveyed streets.
AREAS=[
 [('Ambattur',13.114,80.154),('Kolathur',13.126,80.211),('Perambur',13.118,80.232),('Vyasarpadi',13.118,80.256),('Tondiarpet',13.132,80.287),('Tiruvottiyur',13.164,80.303)],
 [('Mogappair',13.083,80.174),('Anna Nagar',13.085,80.210),('Kilpauk',13.078,80.242),('Purasawalkam',13.088,80.255),('Chennai Central',13.083,80.275),('Royapuram',13.115,80.294)],
 [('Maduravoyal',13.064,80.164),('Koyambedu',13.069,80.195),('Arumbakkam',13.065,80.209),('Chetpet',13.071,80.241),('Egmore',13.074,80.260),('George Town',13.096,80.284)],
 [('Porur',13.036,80.157),('Vadapalani',13.050,80.211),('Kodambakkam',13.052,80.225),('T. Nagar',13.041,80.234),('Thousand Lights',13.058,80.251),('Royapettah',13.052,80.267)],
 [('Manapakkam',13.020,80.177),('Guindy',13.010,80.218),('Saidapet',13.023,80.227),('Alwarpet',13.035,80.255),('Mylapore',13.035,80.267),('Adyar',13.007,80.257)],
 [('Chromepet',12.952,80.143),('Pallavaram',12.969,80.150),('Nanganallur',12.978,80.191),('Velachery',12.979,80.221),('Perungudi',12.963,80.247),('Thiruvanmiyur',12.985,80.259)]
]
CITY_BOUNDS={'west':80.05,'east':80.35,'south':12.80,'north':13.25}
def project(lat,lon):return (75+(lon-80.05)/.3*745,40+(13.25-lat)/.45*590)
NODES={}
for r,row in enumerate(AREAS):
 for c,(name,lat,lon) in enumerate(row):
  x,y=project(lat,lon);nid=f'N{r}{c}'
  NODES[nid]={'id':nid,'x':round(x,2),'y':round(y,2),'lat':lat,'lon':lon,'name':name,'coordinate_source':'Approximate neighborhood anchor'}
from pathlib import Path
import json
DIRECTORY=json.loads((Path(__file__).parent/'city'/'hospitals.json').read_text())
DIRECTORY_BY_ID={h['id']:h for h in DIRECTORY['hospitals']}
EDGES=[]
def edge(a,b,speed,kind,corridor,rough=0):
    EDGES.append({'id':f'{a}-{b}','a':a,'b':b,'km':round(haversine(NODES[a],NODES[b])*1.08,5),
                  'speed':speed,'kind':kind,'corridor':corridor,'rough':rough})
for r in range(6):
    for c in range(6):
        if c<5:
            edge(f'N{r}{c}',f'N{r}{c+1}',55 if r in (1,3) else 32,1 if r in (1,3) else 0,
                 'Central corridor' if r in (1,3) else 'Local streets',1 if (r+c)%7==0 else 0)
        if r<5:
            edge(f'N{r}{c}',f'N{r+1}{c}',65 if c in (0,5) else 30,2 if c in (0,5) else 0,
                 'Ring road' if c in (0,5) else 'Local streets')
for r in range(5):
    edge(f'N{r}{r}',f'N{r+1}{r+1}',60,2,'Express link')
AMBULANCES=[
    {'id':'AMB-01','node':'N00','name':'North response unit','ready_min':.5},
    {'id':'AMB-02','node':'N24','name':'Central response unit','ready_min':.4},
    {'id':'AMB-03','node':'N50','name':'Airport response unit','ready_min':.7},
    {'id':'AMB-04','node':'N05','name':'Coastal response unit','ready_min':.6},
]
# Diversified operator demo profiles across the 16 seeded hospitals (still not live clinical data).
DEMO_CAPABILITIES={
 'H01':(['general','cardiac'],14,4,3),
 'H02':(['general','trauma'],10,0,4),
 'H03':(['general','trauma','cardiac'],18,5,2),
 'H04':(['general','cardiac'],12,3,3),
 'H05':(['general','trauma','cardiac'],22,6,5),
 'H06':(['general','trauma'],16,3,4),
 'H07':(['general','trauma','cardiac'],20,5,3),
 'H08':(['general','cardiac'],11,2,3),
 'H09':(['general','trauma'],9,2,4),
 'H10':(['general','cardiac'],10,2,3),
 'H11':(['general','trauma'],13,2,5),
 'H12':(['general','trauma','cardiac'],15,3,4),
 'H13':(['general'],8,1,3),
 'H14':(['general','cardiac'],12,4,3),
 'H15':(['general','trauma'],9,1,3),
 'H16':(['general','trauma','cardiac'],11,2,4),
}
HOSPITALS=[]
for h in DIRECTORY['hospitals']:
 node=min(NODES.values(),key=lambda n:haversine(n,h))
 enabled=h.get('demo_enabled',False)
 # Care profiles and capacity are explicitly scenario assumptions, not verified clinical facts.
 caps,beds,icu,wait=DEMO_CAPABILITIES.get(h['id'],([],0,0,0)) if enabled else ([],0,0,0)
 HOSPITALS.append({'id':h['id'],'node':node['id'],'name':h['name'],'short':h['short'],
                  'lat':h['lat'],'lon':h['lon'],'connector_km':round(haversine(node,h)*1.2,4),
                  'capabilities':caps,'beds':beds,'icu':icu,
                  'accepting':enabled,'wait_min':wait,'status_source':'DEMO_ASSUMPTION' if enabled else 'UNKNOWN'})
PROFILES={
    'normal':{'Local streets':.15,'Central corridor':.2,'Ring road':.1,'Express link':.1},
    'rush':{'Local streets':.62,'Central corridor':.93,'Ring road':.22,'Express link':.3},
    'disruption':{'Local streets':.4,'Central corridor':.99,'Ring road':.12,'Express link':.15},
}
ACTIVE_PHASES={'TO_PICKUP','ON_SCENE','TO_HOSPITAL','NO_ROUTE'}

def initial_state():
    import copy
    return {'revision':0,'schema_version':3,'settings':{'traffic':'normal','hour':12,'weekday':1,'rain':0,'use_ml':True},
            'roads':{},'fleet':{a['id']:{**a,'current_node':a['node'],'status':'AVAILABLE','mission_id':None,'gps_source':'SIMULATED'} for a in AMBULANCES},
            'hospitals':{h['id']:copy.deepcopy(h) for h in HOSPITALS},'missions':{},'events':[], 'commands':{}}

def directory_transport_candidates(state):
    """Name/tag screen for travel previews; does not certify clinical suitability."""
    candidates=[]
    for h in state['hospitals'].values():
        entry=DIRECTORY_BY_ID[h['id']];name=entry['name'].lower()
        hospital_named=any(s in name for s in ('hospital','medical centre','medical center','medical college','medical foundation'))
        if entry['emergency_tag']=='no':continue
        if not hospital_named and entry['emergency_tag']!='yes':continue
        # Obvious specialty-only/retail records remain searchable but aren't general transport suggestions.
        if any(s in name for s in ('eye','dental','fertility','optical','pharmacy')) and entry['emergency_tag']!='yes':continue
        candidates.append(h)
    return candidates
