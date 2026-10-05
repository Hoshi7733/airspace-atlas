import copy,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sync_global as g
from notam_text import extract
from test_publish_faa import feature,REFS,NOW,payload

class GlobalTests(unittest.TestCase):
 def test_explicit_circle(self):
  shape,warn=extract('MISSILE FIRING WI 5NM RADIUS OF 350000N 1400000E')
  self.assertEqual(shape['circle'],{'center':[140,35],'radius':5,'unit':'NM'})
 def test_polygon(self):
  shape,warn=extract('DANGER AREA BOUNDED BY 350000N1400000E - 360000N1400000E - 360000N1410000E')
  self.assertEqual(shape['geometry']['coordinates'][0][0],shape['geometry']['coordinates'][0][-1])
 def test_arc_not_joined(self):
  self.assertIsNone(extract('AREA BOUNDED BY 350000N1400000E THEN ARC TO 360000N1410000E')[0])
 def test_unlabelled_points_not_polygon(self):
  self.assertIsNone(extract('350000N1400000E 360000N1400000E 360000N1410000E')[0])
 def test_delta_cancels_and_nonrisk_updates(self):
  f=feature();initial=g.apply({},[f],REFS,NOW,'INTERNATIONAL');self.assertEqual(len(initial),1)
  cancelled=copy.deepcopy(f);cancelled['properties']['coreNOTAMData']['notam']['type']='C'
  self.assertEqual(g.apply(initial,[cancelled],REFS,NOW),{})
  f['properties']['coreNOTAMData']['notam']['text']='RWY LIGHT U/S';self.assertEqual(g.apply(initial,[f],REFS,NOW),{})
 def test_delta_keeps_unchanged(self):
  initial=g.apply({},[feature()],REFS,NOW,'INTERNATIONAL')
  self.assertEqual(g.apply(initial,[],REFS,NOW),initial)
 def test_baseline_does_not_erase_other_class(self):
  initial=g.apply({},[feature()],REFS,NOW,'INTERNATIONAL')
  self.assertEqual(g.apply(initial,[],REFS,NOW,'DOMESTIC'),initial)
  self.assertEqual(g.apply(initial,[],REFS,NOW,'INTERNATIONAL'),{})
 def test_global_sync_then_cooldown(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(g,'authenticate',return_value='fake'),patch.object(g,'request_json',return_value=payload(feature())) as request,patch.object(g.time,'sleep'),patch.object(g,'utcnow',return_value=NOW.isoformat()),patch.object(g,'reference_tables',return_value=REFS):
   state=Path(temp)/'state.json';output=Path(temp)/'output'
   self.assertEqual(g.sync(state,output),0)
   urls=[c.args[0] for c in request.call_args_list]
   self.assertEqual(len(urls),6);self.assertTrue(any('classification=INTERNATIONAL' in u for u in urls));self.assertTrue('lastUpdatedDate=' in urls[-1])
   index=json.loads((output/'index.json').read_text());self.assertTrue(index['coverageComplete'])
   self.assertEqual(g.sync(state,output),0);self.assertEqual(request.call_count,6)
