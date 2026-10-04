import sys, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import faa_staging_test as faa

class StagingTests(unittest.TestCase):
    def test_nested_geojson(self):
        payload={'status':'Success','data':{'geojson':[{'properties':{'coreNOTAMData':{'notam':{'selectionCode':'QWMLW','text':'MISSILE FIRING'}}},'geometry':{'type':'GeometryCollection','geometries':[{'type':'Point','coordinates':[140,35]},{'type':'Polygon','coordinates':[[[140,35],[141,35],[141,36],[140,35]]]}]}}]}}
        result=faa.summarize(payload)
        self.assertEqual(result['risk_candidates'],1)
        self.assertEqual(result['valid_polygon_parts'],1)
        self.assertEqual(result['point_parts'],1)
    def test_failure_not_empty_success(self):
        with self.assertRaises(faa.SafeFailure):faa.summarize({'status':'Failure','data':{'geojson':[]}})
    def test_no_redirect(self):
        self.assertIsNone(faa.NoRedirect().redirect_request(None,None,None,None,None,None))
    def test_missing_token(self):
        with patch.object(faa,'load_credentials',return_value=type('C',(),{'client_id':'dummy','client_secret':'dummy'})()),patch.object(faa,'request_json',return_value={}):
            with self.assertRaises(faa.SafeFailure):faa.authenticate()
