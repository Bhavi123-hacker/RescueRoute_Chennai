import unittest,json
from pathlib import Path
from backend.streets import StreetNetwork,street_plan,network
from backend.data import initial_state
from scripts.build_street_network import build

class DirectedStreetTests(unittest.TestCase):
 def triangle(self):
  points={'a':[80.21,13.06],'b':[80.212,13.06],'c':[80.211,13.062]}
  ways={x:{'name':x,'kind':'primary','speed':40,'forward':True,'backward':False} for x in ('ab','bc','ca')}
  edges=[{'id':w,'a':a,'b':b,'way':w,'km':.2,'coordinates':[points[a],points[b]]} for a,b,w in [('a','b','ab'),('b','c','bc'),('c','a','ca')]]
  return StreetNetwork({'metadata':{},'nodes':points,'ways':ways,'edges':edges})
 def test_return_uses_other_oneway_streets_instead_of_reversing_transport(self):
  n=self.triangle();s={'traffic':'normal','rain':0}
  forward=n.route('a','b',n.search('a',s),{'lon':80.21,'lat':13.06},{'lon':80.212,'lat':13.06})
  back=n.route('b','a',n.search('b',s),{'lon':80.212,'lat':13.06},{'lon':80.21,'lat':13.06})
  self.assertEqual(forward['arcs'],[['ab',False]])
  self.assertEqual(back['arcs'],[['bc',False],['ca',False]])
  self.assertNotEqual(back['coordinates'],list(reversed(forward['coordinates'])))
 def test_closed_street_blocks_return_without_inventing_connection(self):
  n=self.triangle();s={'traffic':'normal','rain':0};best,_=n.search('b',s,closed=['bc'])
  self.assertNotIn('a',best)
 def test_directional_congestion_changes_only_matching_direction_cost(self):
  n=self.triangle();s={'traffic':'normal','rain':0}
  balanced=n.edge_minutes('a','b','ab',False,s,'balanced')
  self.assertAlmostEqual(n.edge_minutes('a','b','ab',False,s,'east'),balanced*2)
  self.assertAlmostEqual(n.edge_minutes('a','b','ab',False,s,'west'),balanced)
 def test_route_geometry_and_endpoint_connectors_remain_separate(self):
  n=self.triangle();s={'traffic':'normal','rain':0}
  r=n.route('a','b',n.search('a',s),{'lon':80.209,'lat':13.06},{'lon':80.213,'lat':13.06})
  self.assertEqual(r['coordinates'],[n.nodes['a'],n.nodes['b']]);self.assertGreater(r['connector_km'],0)
  self.assertGreater(r['minutes'],r['road_minutes']);self.assertEqual(r['source_connector'][0],[80.209,13.06])
 def test_normalizer_reverse_oneway_roundabout_access(self):
  def way(i,t):return {'id':i,'tags':{'highway':'primary',**t},'nodes':[i*10,i*10+1],'geometry':[{'lat':13.06,'lon':80.21},{'lat':13.061,'lon':80.212}]}
  g,_=build({'osm3s':{'timestamp_osm_base':'test'},'elements':[way(1,{'oneway':'-1'}),way(2,{'junction':'roundabout'}),way(3,{'motor_vehicle':'no'}),way(4,{'maxspeed':'30 mph'})]})
  self.assertFalse(g['ways']['1']['forward']);self.assertTrue(g['ways']['1']['backward'])
  self.assertFalse(g['ways']['2']['backward']);self.assertNotIn('3',g['ways'])
  self.assertAlmostEqual(g['ways']['4']['speed'],48.2802)
 def test_snap_uses_connected_network(self):
  n=self.triangle();nearest,km=n.snap({'lon':80.212,'lat':13.06});self.assertEqual(nearest,'b');self.assertAlmostEqual(km,0)
 def test_city_preview_provenance_five_ordered_and_legal_arcs(self):
  r=street_plan(initial_state(),{'pickup':'N22','preferred_hospital':'H03','ranking_scope':'directory'})
  self.assertEqual(r['selected_hospital'],'H03');self.assertEqual(len(r['top_hospitals']),5)
  self.assertEqual(len({h['hospital_id'] for h in r['top_hospitals']}),5)
  self.assertEqual([h['minutes'] for h in r['top_hospitals']],sorted(h['minutes'] for h in r['top_hospitals']))
  self.assertGreater(r['metadata']['oneway_ways'],0)
  n=network()
  for leg in r['legs'].values():
   self.assertIsNotNone(leg)
   for eid,rev in leg['arcs']:
    way=n.ways[n.edges[eid]['way']];self.assertTrue(way['backward'] if rev else way['forward'])
 def test_invalid_preview_controls_rejected(self):
  for data in [{'directional_traffic':'garbage'},{'closed_streets':['bad']},{'return_to':'nowhere'}]:
   with self.assertRaises(ValueError):street_plan(initial_state(),data)

if __name__=='__main__':unittest.main()
