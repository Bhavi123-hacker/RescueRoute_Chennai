import csv
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from backend.data import DIRECTORY, DIRECTORY_BY_ID, NODES, initial_state
from backend.engine import dispatch, plan, update_hospital, update_road, request, hospital_options
from backend.routing import build_graph, search
from backend.live_routes import live_plan
from backend.store import Store

class CityTests(unittest.TestCase):
    def test_directory_provenance_coordinates_and_csv_agree(self):
        self.assertEqual(DIRECTORY['records'],868)
        self.assertEqual(len(DIRECTORY_BY_ID),868)
        for h in DIRECTORY['hospitals']:
            self.assertTrue(12.8<=h['lat']<=13.25 and 80.05<=h['lon']<=80.35)
            self.assertTrue(h['source_url'].startswith('https://www.openstreetmap.org/'))
        with (Path(__file__).parents[1]/'frontend/assets/chennai_hospitals.csv').open() as f:
            self.assertEqual(len(list(csv.DictReader(f))),868)

    def test_five_unique_hospitals_ranked_from_source(self):
        p=plan(initial_state(),{'pickup':'N22','category':'trauma','emergency':'critical'})
        rows=p['top_hospitals'];self.assertEqual(len(rows),5);self.assertEqual(len({h['hospital_id'] for h in rows}),5)
        self.assertEqual([h['minutes'] for h in rows],sorted(h['minutes'] for h in rows))
        self.assertTrue(all(h['route_source']=='MODELED_ASTAR_PLUS_APPROXIMATE_CONNECTORS' for h in rows))

    def test_directory_travel_ranking_excludes_obvious_specialty_only_names(self):
        p=plan(initial_state(),{'pickup':'N22','ranking_scope':'directory'})
        self.assertEqual(len(p['top_hospitals']),5)
        self.assertTrue(all('eye' not in h['name'].lower() and 'dental' not in h['name'].lower() for h in p['top_hospitals']))
        self.assertTrue(any(h['capacity_source']=='UNKNOWN' for h in p['top_hospitals']))

    def test_earliest_ranking_uses_minimum_travel_time_not_assignment_score(self):
        s=initial_state();p=plan(s,{'pickup':'N22','category':'trauma','emergency':'critical'})
        hospitals,_=hospital_options(s,p['request']);bundle=build_graph(s,'critical')
        expected=[]
        for h in hospitals:
            route=search(bundle,'N22',h['node'],algorithm='dijkstra',objective='minutes')
            if route:
                # Initial normal scenario: local-street congestion .15, no rain.
                from backend.data import PROFILES
                connector=h['connector_km']/25*60*(1+2.8*PROFILES[s['settings']['traffic']]['Local streets'])
                expected.append((route['minutes']+connector,h['id']))
        expected.sort()
        self.assertEqual([h['hospital_id'] for h in p['top_hospitals']],[h[1] for h in expected[:5]])
        for actual,want in zip(p['top_hospitals'],expected):self.assertAlmostEqual(actual['minutes'],want[0])

    def test_requested_hospital_is_respected_and_unavailability_pauses(self):
        s=initial_state();mid=dispatch(s,{'pickup':'N22','preferred_hospital':'H03','category':'trauma','emergency':'critical'})['mission_id'];m=s['missions'][mid]
        self.assertEqual(m['hospital_id'],'H03')
        road=m['remaining_route']['roads'][0];update_road(s,{'road_id':road,'closed':True});self.assertEqual(m['hospital_id'],'H03')
        update_hospital(s,{'hospital_id':'H03','accepting':False});self.assertEqual(m['phase'],'NO_ROUTE')

    def test_explicit_alternative_permission_allows_destination_change(self):
        s=initial_state();mid=dispatch(s,{'pickup':'N22','preferred_hospital':'H03','allow_alternative':True,'category':'trauma','emergency':'critical'})['mission_id']
        update_hospital(s,{'hospital_id':'H03','accepting':False})
        self.assertNotEqual(s['missions'][mid]['hospital_id'],'H03');self.assertNotEqual(s['missions'][mid]['phase'],'NO_ROUTE')

    def test_exact_source_bounds_and_backend_snap(self):
        n=NODES['N43'];r=request({'pickup':'N00','pickup_location':{'lat':n['lat'],'lon':n['lon'],'label':'My pickup'}})
        self.assertEqual(r['pickup'],'N43');self.assertEqual(r['pickup_location']['label'],'My pickup')
        with self.assertRaises(ValueError):request({'pickup_location':{'lat':0,'lon':0}})
        with self.assertRaises(ValueError):request({'preferred_hospital':'unknown'})

    def test_unknown_hospital_excluded_until_operator_profile(self):
        s=initial_state();hid=next(h for h in s['hospitals'] if s['hospitals'][h]['status_source']=='UNKNOWN')
        p=plan(s,{'preferred_hospital':hid});self.assertIsNone(p['best'])
        update_hospital(s,{'hospital_id':hid,'beds':5,'icu':2,'accepting':True,'capabilities':['general','trauma']})
        p=plan(s,{'preferred_hospital':hid,'category':'trauma','emergency':'critical'})
        self.assertEqual(p['best']['hospital_id'],hid);self.assertEqual(s['hospitals'][hid]['status_source'],'OPERATOR_DEMO_INPUT')

    def test_initial_world_fits_dynamodb_item_guard(self):
        self.assertLess(len(Store.encode(initial_state()).encode()),300000)

    def test_live_mode_never_falls_back_to_simulated_traffic(self):
        with patch.dict('os.environ',{'ENABLE_LOCATION':'false'}):
            code,p=live_plan(initial_state(),{});self.assertEqual(code,409);self.assertIn('simulated',p['error'])

if __name__=='__main__':unittest.main()
