import json,sys,tempfile,unittest
from pathlib import Path
from datetime import datetime,timezone
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import publish_faa as m
NOW=datetime(2026,10,4,tzinfo=timezone.utc)
REFS={'icao':{'RJTT':'JP','KJFK':'US'},'faaLocal':{'JFK':'US'}}
def feature():
 return {'type':'Feature','properties':{'coreNOTAMData':{'notam':{'id':'test1','text':'MISSILE FIRING','type':'N','location':'RJTT','icaoLocation':'RJTT','selectionCode':'QWMLW','effectiveStart':'2026-10-01T00:00:00Z','effectiveEnd':'2026-10-10T00:00:00Z','radius':'20'},'notamTranslation':[]}},'geometry':{'type':'GeometryCollection','geometries':[{'type':'Point','coordinates':[140,35]}]}}
def payload(f):return {'status':'Success','data':{'geojson':[f]}}
class PublishTests(unittest.TestCase):
 def test_point_is_not_fabricated_circle(self):
  groups,stats=m.build(payload(feature()),REFS,NOW)
  p=groups['JP'][0];self.assertEqual(p['properties']['accuracy'],'reference-point');self.assertNotIn('radius_m',p['properties']);self.assertEqual(p['geometry']['type'],'MultiPoint')
 def test_qline_circle(self):
  f=feature();f['properties']['coreNOTAMData']['notamTranslation']=[{'formattedText':'Q) RJJJ/QWMLW/IV/BO/W/000/100/3500N14000E020\nA) RJTT'}]
  p=m.build(payload(f),REFS,NOW)[0]['JP'][0];self.assertEqual(p['properties']['radius_m'],20*1852);self.assertEqual(p['properties']['accuracy'],'qline-envelope')
 def test_unknown_country_retained(self):
  f=feature();f['properties']['coreNOTAMData']['notam']['icaoLocation']='ZZZZ';f['properties']['coreNOTAMData']['notam']['location']='ZZZZ'
  self.assertIn('ZZ',m.build(payload(f),REFS,NOW)[0])
 def test_expiry_and_cancellation(self):
  f=feature();f['properties']['coreNOTAMData']['notam']['effectiveEnd']='2026-10-03T00:00:00Z'
  groups,stats=m.build(payload(f),REFS,NOW);self.assertEqual(stats['retained'],0);self.assertEqual(stats['excludedInactive'],1)
  f=feature();f['properties']['coreNOTAMData']['notam']['type']='C';self.assertEqual(m.build(payload(f),REFS,NOW)[1]['excludedInactive'],1)
 def test_null_geometry_retained(self):
  f=feature();f['geometry']=None;self.assertEqual(m.build(payload(f),REFS,NOW)[1]['unplotted'],1)
 def test_invalid_polygon_not_repaired(self):
  f=feature();f['geometry']={'type':'Polygon','coordinates':[[[1,1],[2,2]]]};self.assertEqual(m.build(payload(f),REFS,NOW)[1]['unplotted'],1)
 def test_invalid_time_flagged(self):
  f=feature();f['properties']['coreNOTAMData']['notam']['effectiveEnd']='bad'
  p=m.build(payload(f),REFS,NOW)[0]['JP'][0];self.assertEqual(p['properties']['timeStatus'],'invalid-time')
 def test_failure_preserves_snapshot_and_throttles(self):
  with tempfile.TemporaryDirectory() as d:
   index={'environment':'staging','lastAttempt':'2026-10-01T00:00:00Z','lastSuccess':'2026-10-01T00:00:00Z','countries':[]}
   Path(d,'index.json').write_text(json.dumps(index));Path(d,'JP.json').write_text('unchanged')
   with patch.object(m,'authenticate',side_effect=m.SafeFailure('http_429')) as auth:
    self.assertEqual(m.publish(d),1);self.assertEqual(Path(d,'JP.json').read_text(),'unchanged')
    self.assertEqual(json.loads(Path(d,'index.json').read_text())['lastSuccess'],index['lastSuccess'])
    m.publish(d);self.assertEqual(auth.call_count,1)
 def test_publish_success(self):
  with tempfile.TemporaryDirectory() as d,patch.object(m,'authenticate',return_value='not-a-real-token'),patch.object(m,'request_json',return_value=payload(feature())),patch.object(m,'reference_tables',return_value=REFS),patch.object(m,'utcnow',return_value=NOW.isoformat()):
   self.assertEqual(m.publish(d),0);self.assertEqual(json.loads(Path(d,'JP.json').read_text())['metadata']['environment'],'staging')
