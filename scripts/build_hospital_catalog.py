"""Rebuild the attributed directory from the bundled OSM snapshot (stdlib only)."""
import argparse,csv,json,math
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def normalize(raw,seeds):
    rows=[]
    for e in raw['elements']:
        tags=e.get('tags',{});name=tags.get('name:en') or tags.get('name');point=e if 'lat' in e else e.get('center',{})
        if not name or 'lat' not in point:continue
        source=f"{e['type']}/{e['id']}"
        rows.append({'id':f"OSM-{e['type'][0]}{e['id']}",'name':name,'lat':point['lat'],'lon':point['lon'],
          'address':tags.get('addr:full') or ', '.join(tags.get(k,'') for k in ['addr:housenumber','addr:street','addr:suburb','addr:city','addr:postcode'] if tags.get(k)),
          'phone':tags.get('contact:phone',tags.get('phone','')),'website':tags.get('contact:website',tags.get('website','')),
          'emergency_tag':tags.get('emergency','unknown'),'speciality_tags':tags.get('healthcare:speciality',''),'operator_type':tags.get('operator:type','unknown'),
          'source_url':'https://www.openstreetmap.org/'+source,'coordinate_source':'OSM point' if 'lat' in e else 'OSM area center','source_ids':[source]})
    rows.sort(key=lambda x:(x['name'].lower(),x['id']));clean=[]
    key=lambda n:''.join(c for c in n.lower() if c.isalnum())
    for h in rows:
        old=next((o for o in clean if key(o['name'])==key(h['name']) and math.hypot(o['lat']-h['lat'],o['lon']-h['lon'])<.003),None)
        if old:
            old['source_ids']+=h['source_ids']
            for k in ('address','phone','website'):
                if not old[k]:old[k]=h[k]
        else:clean.append(h)
    for h in clean:
        seed=next((seeds[x] for x in h['source_ids'] if x in seeds),None)
        h['directory_id']=h['id'];h['demo_enabled']=bool(seed)
        if seed:h.update(seed)
        else:h['short']=h['name'][:34]
    return rows,clean
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,default=ROOT/'backend/city/osm_snapshot.json');parser.add_argument('--output',type=Path,default=ROOT/'backend/city/hospitals.json');args=parser.parse_args()
    raw=json.loads(args.input.read_text());seeds=json.loads((ROOT/'backend/city/demo_seed_profiles.json').read_text())
    named,clean=normalize(raw,seeds)
    previous=json.loads((ROOT/'backend/city/hospitals.json').read_text());previous.update({'osm_timestamp':raw['osm3s']['timestamp_osm_base'],'raw_elements':len(raw['elements']),'named_elements':len(named),'records':len(clean),'demo_hospital_count':sum(h['demo_enabled'] for h in clean),'hospitals':clean})
    args.output.write_text(json.dumps(previous,ensure_ascii=False,indent=2));print('Rebuilt',len(clean),'mapped directory records:',args.output)
    if args.output.resolve()==(ROOT/'backend/city/hospitals.json').resolve():
        (ROOT/'frontend/assets/chennai_hospitals.json').write_text(args.output.read_text())
        columns=['id','name','address','lat','lon','phone','website','emergency_tag','coordinate_source','source_url']
        with (ROOT/'frontend/assets/chennai_hospitals.csv').open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows({k:h[k] for k in columns} for h in clean)
