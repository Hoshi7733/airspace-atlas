import sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import faa_client as client
import publish_faa as publisher

class ProductionTests(unittest.TestCase):
 def test_oauth_production_target_and_form(self):
  self.assertEqual(client.HOST,'https://api-nms.aim.faa.gov')
  with patch.object(client,'load_credentials',return_value=SimpleNamespace(client_id='test',client_secret='test')),patch.object(client,'request_json',return_value={'access_token':'test-token'}) as request:
   self.assertEqual(client.authenticate(),'test-token')
   args=request.call_args.args
   self.assertEqual(args[0],'/v1/auth/token')
   self.assertEqual(args[2],b'grant_type=client_credentials')
   self.assertEqual(args[1]['Content-Type'],'application/x-www-form-urlencoded')
 def test_publisher_uses_production_client(self):
  self.assertIs(publisher.authenticate,client.authenticate)
  self.assertIs(publisher.request_json,client.request_json)
  self.assertNotIn('STAGING',publisher.SOURCE)
