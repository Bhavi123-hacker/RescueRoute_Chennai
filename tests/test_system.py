import concurrent.futures
import copy
import csv
import json
import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from backend import app
from backend.data import ACTIVE_PHASES,EDGES,NODES,initial_state,haversine
from backend.engine import advance,complete,dispatch,gps,hospital_options,plan,update_hospital,update_road,update_settings
from backend.prediction import model_report,predict
from backend.routing import build_graph,compare,search
from backend.store import Conflict,Store

class AlgorithmTests(unittest.TestCase):
    def test_astar_matches_dijkstra_all_pairs_in_three_profiles(self):
        s=initial_state()
        for profile in ('normal','rush','disruption'):
            s['settings']['traffic']=profile;bundle=build_graph(s,'critical')
            for a in NODES:
                for b in NODES:
                    self.assertAlmostEqual(search(bundle,a,b,'astar')['cost'],search(bundle,a,b,'dijkstra')['cost'],places=8)

    def test_independent_floyd_warshall_cost_oracle(self):
        bundle=build_graph(initial_state());dist={(a,b):0 if a==b else math.inf for a in NODES for b in NODES}
        for e in bundle[1].values():dist[e['a'],e['b']]=dist[e['b'],e['a']]=e['cost']
        for k in NODES:
            for a in NODES:
                for b in NODES:dist[a,b]=min(dist[a,b],dist[a,k]+dist[k,b])
        for a in NODES:
            for b in NODES:self.assertAlmostEqual(search(bundle,a,b)['cost'],dist[a,b],places=8)

    def test_heuristic_consistent_for_every_edge_and_goal(self):
        graph,edges,lower=build_graph(initial_state())
        for goal in NODES:
            for e in edges.values():
                h1=haversine(NODES[e['a']],NODES[goal])*lower;h2=haversine(NODES[e['b']],NODES[goal])*lower
                self.assertLessEqual(abs(h1-h2),e['cost']+1e-8)

    def test_bfs_baseline_can_have_higher_cost(self):
        s=initial_state();s['settings']['use_ml']=False
        s['roads']['N00-N11']={'congestion':1,'closed':False}
        b=build_graph(s)
        bfs=search(b,'N00','N11','bfs');astar=search(b,'N00','N11')
        self.assertEqual(len(bfs['roads']),1);self.assertGreater(bfs['cost'],astar['cost'])

    def test_closures_excluded_and_complete_disconnect(self):
        s=initial_state();road=search(build_graph(s),'N00','N55')['roads'][0]
        s['roads'][road]={'closed':True};self.assertNotIn(road,search(build_graph(s),'N00','N55')['roads'])
        s['roads']={e['id']:{'closed':True} for e in EDGES};self.assertIsNone(search(build_graph(s),'N00','N55'))

    def test_same_node_zero_travel(self):
        p=search(build_graph(initial_state()),'N22','N22');self.assertEqual(p['minutes'],0);self.assertEqual(p['nodes'],['N22'])

class PredictionTests(unittest.TestCase):
    def test_exported_inference_matches_sklearn_predictions(self):
        checks=json.loads((Path(__file__).parents[1]/'backend/models/inference_checks.json').read_text())
        for c in checks:self.assertAlmostEqual(predict(c['edge'],c['settings'],c['congestion'],c.get('extras'))[0],c['expected_minutes'],places=10)

    def test_physical_floor_and_rain_congestion_response(self):
        e=EDGES[12];s=initial_state()['settings'];free=e['km']/e['speed']*60
        clear=predict(e,s,.1)[0];rain=predict(e,{**s,'rain':2},.9)[0]
        self.assertGreaterEqual(clear,free);self.assertGreater(rain,clear)

    def test_dataset_has_disjoint_temporal_split_and_expected_rows(self):
        report=model_report();self.assertEqual(report['observations'],234000)
        self.assertGreaterEqual(report.get('feature_count',0),12)
        self.assertLess(report['training_dates'][-1],report['test_dates'][0])
        self.assertEqual(report['training_rows']+report['test_rows'],report['observations'])
        with (Path(__file__).parents[1]/'ml/synthetic_traffic.csv').open() as f:
            rows=list(csv.DictReader(f));self.assertEqual(len(rows),report['observations']);self.assertTrue(all('SYNTHETIC' in r['source'] for r in rows))

    def test_synthetic_holdout_model_beats_both_declared_baselines(self):
        r=model_report();self.assertLess(r['random_forest']['mae_minutes'],r['traffic_rule']['mae_minutes']);self.assertLess(r['random_forest']['mae_minutes'],r['fixed_speed']['mae_minutes'])

class MissionTests(unittest.TestCase):
    def setUp(self):self.s=initial_state()
    def create(self):return dispatch(self.s,{'pickup':'N22','category':'trauma','emergency':'critical'})['mission_id']

    def test_icu_and_capability_filter(self):
        p=plan(self.s,{'category':'trauma','emergency':'critical'})
        self.assertNotIn('H02',{c['hospital_id'] for c in p['candidates']})
        self.assertTrue(any('ICU' in ' '.join(h['reasons']) for h in p['hospital_rejections'] if h['hospital_id']=='H02'))

    def test_busy_fleet_excluded_and_reserved_capacity_counted(self):
        mid=self.create();m=self.s['missions'][mid];p=plan(self.s,{'category':'trauma','emergency':'critical'})
        self.assertNotIn(m['ambulance_id'],{c['ambulance_id'] for c in p['candidates']})
        h=self.s['hospitals'][m['hospital_id']];h['icu']=1
        self.assertNotIn(h['id'],{c['hospital_id'] for c in plan(self.s,{'category':'trauma','emergency':'critical'})['candidates']})

    def test_accident_replans_from_current_position(self):
        mid=self.create();m=self.s['missions'][mid];road=m['remaining_route']['roads'][0];a=self.s['fleet'][m['ambulance_id']]
        update_road(self.s,{'road_id':road,'closed':True})
        self.assertNotIn(road,m['remaining_route']['roads']);self.assertEqual(m['remaining_route']['nodes'][0],a['current_node']);self.assertEqual(m['reroutes'],1)

    def test_hospital_unavailability_switches_destination(self):
        mid=self.create();m=self.s['missions'][mid];old=m['hospital_id'];update_hospital(self.s,{'hospital_id':old,'accepting':False})
        self.assertNotEqual(m['hospital_id'],old);self.assertIn(m['phase'],ACTIVE_PHASES);self.assertGreater(m['reroutes'],0)

    def test_no_feasible_hospital_pauses_then_recovers(self):
        mid=self.create();m=self.s['missions'][mid]
        for h in self.s['hospitals'].values():update_hospital(self.s,{'hospital_id':h['id'],'accepting':False})
        self.assertEqual(m['phase'],'NO_ROUTE')
        update_hospital(self.s,{'hospital_id':'H03','accepting':True});self.assertNotEqual(m['phase'],'NO_ROUTE')

    def test_entire_journey_consumes_capacity_and_releases_at_hospital(self):
        mid=self.create();m=self.s['missions'][mid];initial_icu={h['id']:h['icu'] for h in self.s['hospitals'].values()}
        for _ in range(50):
            if m['phase']=='ARRIVED':break
            advance(self.s,{'mission_id':mid})
        self.assertEqual(m['phase'],'ARRIVED');h=self.s['hospitals'][m['hospital_id']];self.assertEqual(h['icu'],initial_icu[h['id']]-1)
        a=self.s['fleet'][m['ambulance_id']];self.assertEqual(a['current_node'],h['node']);complete(self.s,{'mission_id':mid})
        self.assertEqual(a['status'],'AVAILABLE');self.assertEqual(a['current_node'],h['node']);self.assertEqual(m['phase'],'COMPLETED')
        complete(self.s,{'mission_id':mid})

    def test_tracking_progress_is_not_counted_as_dynamic_reroute(self):
        mid=self.create();advance(self.s,{'mission_id':mid});self.assertEqual(self.s['missions'][mid]['reroutes'],0)

    def test_dispatch_and_step_idempotency(self):
        body={'pickup':'N22','command_id':'command-1'};first=dispatch(self.s,body);self.assertEqual(dispatch(self.s,body),first);self.assertEqual(len(self.s['missions']),1)
        mid=first['mission_id'];body={'mission_id':mid,'command_id':'step-1'};advance(self.s,body);count=self.s['missions'][mid]['gps_updates'];advance(self.s,body);self.assertEqual(self.s['missions'][mid]['gps_updates'],count)
        with self.assertRaises(Conflict):dispatch(self.s,{'pickup':'N23','command_id':'command-1'})

    def test_complete_before_arrival_is_rejected(self):
        with self.assertRaises(Conflict):complete(self.s,{'mission_id':self.create()})

    def test_test_gps_bounds_and_graph_snap(self):
        n=NODES['N10'];result=gps(self.s,{'ambulance_id':'AMB-01','lat':n['lat'],'lon':n['lon']})
        self.assertEqual(result['snapped_node'],'N10')
        with self.assertRaises(ValueError):gps(self.s,{'ambulance_id':'AMB-01','lat':0,'lon':0})

    def test_invalid_capacity_and_conditions(self):
        with self.assertRaises(ValueError):update_hospital(self.s,{'hospital_id':'H03','beds':1,'icu':2})
        with self.assertRaises(ValueError):update_settings(self.s,{'rain':float('nan')})

class PersistenceTests(unittest.TestCase):
    def setUp(self):self.temp=tempfile.TemporaryDirectory(ignore_cleanup_errors=True);self.path=str(Path(self.temp.name)/'world.sqlite3');self.store=Store(self.path)
    def tearDown(self):
        try:self.temp.cleanup()
        except OSError:pass

    def test_concurrent_stale_plan_allows_exactly_one_dispatch(self):
        revision=self.store.read()['revision']
        def attempt(i):
            try:Store(self.path).mutate(lambda s:dispatch(s,{'pickup':'N22','expected_revision':revision,'command_id':str(i)}));return True
            except Conflict:return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(sum(pool.map(attempt,range(4))),1)
        self.assertEqual(len(self.store.read()['missions']),1)

    def test_invalid_mutation_rolls_back(self):
        before=self.store.read()
        with self.assertRaises(ValueError):self.store.mutate(lambda s:update_hospital(s,{'hospital_id':'H03','beds':1,'icu':2}))
        self.assertEqual(before,self.store.read())

    def test_persistence_and_idempotent_retry_across_store_instances(self):
        body={'pickup':'N22','command_id':'persistent-retry'}
        _,r=self.store.mutate(lambda s:dispatch(s,body));other=Store(self.path);_,retry=other.mutate(lambda s:dispatch(s,body))
        self.assertEqual(r,retry);self.assertEqual(len(other.read()['missions']),1)

    def test_api_plan_snapshot_and_conflict(self):
        status,p=app.api('POST','/api/plan',{},self.store);self.assertEqual(status,200)
        app.api('POST','/api/settings',{'traffic':'rush'},self.store)
        self.assertEqual(app.api('POST','/api/dispatch',{'expected_revision':p['revision']},self.store)[0],409)

    def test_benchmark_api_returns_comparable_cost_units(self):
        status,result=app.api('POST','/api/benchmark',{'origin':'N00','destination':'N55'},self.store)
        self.assertEqual(status,200)
        self.assertAlmostEqual(result['rows'][0]['cost_min'],result['rows'][1]['cost_min'],places=8)
        self.assertTrue(all(isinstance(r['cost_min'],float) for r in result['rows']))

    def test_api_invalid_input_reset_confirmation_and_bad_json(self):
        self.assertEqual(app.api('POST','/api/plan',[],self.store)[0],400)
        self.assertEqual(app.api('POST','/api/reset',{},self.store)[0],400)
        self.assertEqual(app.handler({'body':'not-json'},None)['statusCode'],400)
        self.assertEqual(app.handler({'body':'x'*40000},None)['statusCode'],400)
        self.assertEqual(app.api('GET','/api/missing',store=self.store)[0],404)

    def test_report_contains_sources_and_model_without_commands(self):
        _,report=app.api('POST','/api/export',{},self.store);self.assertTrue(report['report']['simulation']);self.assertIn('SYNTHETIC',report['report']['model']['data_source'])

class DynamoAdapterTests(unittest.TestCase):
    class ConditionalError(Exception):pass
    class Fake:
        def __init__(self,owner):self.item=None;self.fail_once=False;self.exceptions=type('Errors',(),{'ConditionalCheckFailedException':owner.ConditionalError})
        def get_item(self,**kw):return {'Item':copy.deepcopy(self.item)} if self.item else {}
        def put_item(self,**kw):
            if self.fail_once:self.fail_once=False;raise DynamoAdapterTests.ConditionalError()
            if self.item and kw['ConditionExpression']=='attribute_not_exists(revision)':raise DynamoAdapterTests.ConditionalError()
            if self.item and 'ExpressionAttributeValues' in kw and self.item['revision']!=kw['ExpressionAttributeValues'][':old']:raise DynamoAdapterTests.ConditionalError()
            self.item=copy.deepcopy(kw['Item'])

    def test_conditional_initialization_retry_and_readback(self):
        client=self.Fake(self);client.fail_once=True;store=Store(client=client,table='test')
        state,result=store.mutate(lambda s:dispatch(s,{'pickup':'N22','command_id':'cloud-1'}))
        self.assertEqual(state['revision'],1);self.assertEqual(store.read()['missions'][result['mission_id']]['phase'],'TO_HOSPITAL')
        store.mutate(lambda s:update_settings(s,{'traffic':'rush'}));self.assertEqual(store.read()['revision'],2)

if __name__=='__main__':unittest.main()
