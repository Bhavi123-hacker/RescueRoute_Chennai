"""Offline SDK contract tests. No AWS account or network calls are used."""
import json
import os
import unittest
from unittest.mock import patch
try:
    import boto3
    from botocore.stub import Stubber, ANY
except ImportError:
    boto3 = None
from backend import app
from backend.data import initial_state, NODES

@unittest.skipUnless(boto3, 'Install requirements-aws.txt to run SDK contract tests')
class AwsContractTests(unittest.TestCase):
    def client(self, service):
        return boto3.client(service, region_name='eu-north-1', aws_access_key_id='test', aws_secret_access_key='test')

    def test_location_route_request_and_response_schema(self):
        state = initial_state(); aid='AMB-01'; hid='H03'
        origin=NODES[state['fleet'][aid]['current_node']]; destination=state['hospitals'][hid]
        expected={'Origin':[origin['lon'],origin['lat']], 'Destination':[destination['lon'],destination['lat']],
                  'TravelMode':'Car','DepartNow':True,'OptimizeRoutingFor':'FastestRoute','LegGeometryFormat':'Simple',
                  'Traffic':{'Usage':'UseTrafficData'}}
        coords=[[origin['lon'],origin['lat']],[destination['lon'],destination['lat']]]
        client=self.client('geo-routes')
        response={'Routes':[{'Legs':[{'Geometry':{'LineString':coords},'TravelMode':'Car','Type':'Vehicle'}],
                            'Summary':{'Distance':5000,'Duration':600},'MajorRoadLabels':[]}],
                  'Notices':[], 'PricingBucket':'Core', 'LegGeometryFormat':'Simple'}
        with Stubber(client) as stub, patch.dict(os.environ,{'ENABLE_LOCATION':'true'}), patch('boto3.client',return_value=client):
            stub.add_response('calculate_routes',response,expected)
            status,result=app.reference_route(state,{'ambulance_id':aid,'hospital_id':hid})
            self.assertEqual(status,200);self.assertEqual(result['distance_km'],5);self.assertEqual(result['minutes'],10)
            self.assertEqual(result['coordinates'],coords);stub.assert_no_pending_responses()

    def test_live_matrix_ranking_and_alternative_geometry_contract(self):
        from backend.live_routes import live_plan
        from backend.engine import hospital_options,request
        from backend.data import DIRECTORY_BY_ID
        state=initial_state();data={'pickup':'N22','preferred_hospital':'H03','category':'trauma','emergency':'critical'}
        hospitals,_=hospital_options(state,request(data));src=NODES['N22'];origin=[src['lon'],src['lat']]
        entries=[{'Distance':1000+i*100,'Duration':1200-i*20} for i,h in enumerate(hospitals)]
        entries[0]={'Error':'RouteNotFound','Distance':0,'Duration':0}
        expected={'Origins':[{'Position':origin}],'Destinations':[{'Position':[h['lon'],h['lat']]} for h in hospitals],
            'RoutingBoundary':{'Geometry':{'BoundingBox':[79.95,12.7,80.45,13.35]}},'DepartNow':True,'TravelMode':'Car',
            'OptimizeRoutingFor':'FastestRoute','Traffic':{'Usage':'UseTrafficData'}}
        target=DIRECTORY_BY_ID['H03'];coords=[origin,[target['lon'],target['lat']]]
        response={'Routes':[{'Legs':[{'Geometry':{'LineString':coords},'TravelMode':'Car','Type':'Vehicle'}],
                    'Summary':{'Distance':5000,'Duration':600},'MajorRoadLabels':[]}],
                  'Notices':[],'PricingBucket':'Core','LegGeometryFormat':'Simple'}
        client=self.client('geo-routes')
        with Stubber(client) as stub,patch.dict(os.environ,{'ENABLE_LOCATION':'true'}):
            stub.add_response('calculate_route_matrix',{'RouteMatrix':[entries],'ErrorCount':1,
                'RoutingBoundary':expected['RoutingBoundary'],'PricingBucket':'Core'},expected)
            stub.add_response('calculate_routes',response,{'Origin':origin,'Destination':[target['lon'],target['lat']],
                'DepartNow':True,'TravelMode':'Car','OptimizeRoutingFor':'FastestRoute','LegGeometryFormat':'Simple',
                'MaxAlternatives':2,'LegAdditionalFeatures':['TypicalDuration'],'Traffic':{'Usage':'UseTrafficData'}})
            code,result=live_plan(state,data,client)
            self.assertEqual(code,200);self.assertEqual(result['selected_hospital']['hospital_id'],'H03')
            self.assertEqual(result['failed_hospitals'],1);self.assertEqual(len(result['top_hospitals']),5)
            self.assertEqual([x['minutes'] for x in result['top_hospitals']],sorted(x['minutes'] for x in result['top_hospitals']))
            self.assertEqual(result['routes'][0]['minutes'],10);stub.assert_no_pending_responses()

    def test_s3_private_report_contract(self):
        client=self.client('s3')
        with Stubber(client) as stub, patch.dict(os.environ,{'REPORT_BUCKET':'demo-report-bucket'}), patch('boto3.client',return_value=client):
            stub.add_response('put_object',{}, {'Bucket':'demo-report-bucket','Key':ANY,'Body':ANY,
                                               'ContentType':'application/json','ServerSideEncryption':'AES256'})
            result=app.export_report(initial_state(),{})
            self.assertEqual(result['stored_in'],'S3');self.assertEqual(result['expires_seconds'],300)
            self.assertTrue(result['report']['simulation']);stub.assert_no_pending_responses()

    def test_lambda_http_api_response_and_malformed_body(self):
        with patch.object(app,'api',return_value=(200,{'ok':True})):
            result=app.handler({'rawPath':'/api/state','requestContext':{'http':{'method':'GET'}}},None)
            self.assertEqual(result['statusCode'],200);self.assertEqual(json.loads(result['body']),{'ok':True})
            self.assertEqual(app.handler({'body':'{broken'},None)['statusCode'],400)

if __name__=='__main__':unittest.main()
