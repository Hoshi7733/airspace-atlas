import copy,json,tempfile,unittest,sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import sync_global as g
from datetime import timedelta
from notam_text import extract
from test_publish_faa import feature,REFS,NOW,payload

class GlobalTests(unittest.TestCase):
 def test_explicit_circle(self):
  shape,warn=extract('MISSILE FIRING WI 5NM RADIUS OF 350000N 1400000E')
  self.assertEqual(shape['circle'],{'center':[140,35],'radius':5,'unit':'NM'})
 def test_faa_tfr_radius_wording(self):
  shape,warn=extract('ALL ACFT FLT OPS ARE PROHIBITED: WI AN AREA DEFINED AS 1NM RADIUS OF 260419N0970949W')
  self.assertEqual(shape['circle']['radius'],1)
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
 def test_reparse_saved_circle_without_api_request(self):
  records=g.apply({},[feature()],REFS,NOW,'INTERNATIONAL')
  f=next(iter(records.values()));f['geometry']=None
  f['properties'].update(accuracy='reference-point',originalText='WI AN AREA DEFINED AS 1NM RADIUS OF 260419N0970949W',unplottedReason='missing')
  with tempfile.TemporaryDirectory() as temp,patch.object(g,'utcnow',return_value=NOW.isoformat()),patch.object(g,'authenticate') as auth:
   state=Path(temp)/'state.json';state.write_text(json.dumps(dict(records=records,lastAttempt=NOW.isoformat())))
   self.assertEqual(g.sync(state,Path(temp)/'out'),0);auth.assert_not_called()
   saved=next(iter(json.loads(state.read_text())['records'].values()))
   self.assertEqual(saved['properties']['accuracy'],'text-circle');self.assertEqual(saved['properties']['radius_m'],1852)
   self.assertNotIn('unplottedReason',saved['properties'])
 def test_staggered_rebaseline_clears_gap_only_when_complete(self):
  stamp=NOW.isoformat();gap=(NOW-timedelta(hours=2)).isoformat()
  with tempfile.TemporaryDirectory() as temp,patch.object(g,'authenticate',return_value='fake'),patch.object(g,'request_json',return_value=payload(feature())) as request,patch.object(g,'utcnow',return_value=stamp),patch.object(g,'reference_tables',return_value=REFS):
   state=Path(temp)/'state.json';output=Path(temp)/'output'
   values=dict(records={},baselineAttempts={c:stamp for c in g.CLASSES},baselineSuccess={c:stamp for c in g.CLASSES},watermark=(NOW-timedelta(hours=1)).isoformat(),gapSince=gap,coverageGap=True)
   values['baselineSuccess']['INTERNATIONAL']=(NOW-timedelta(days=1)).isoformat()
   state.write_text(json.dumps(values));self.assertEqual(g.sync(state,output),0)
   saved=json.loads(state.read_text());self.assertTrue(saved['coverageGap'])
   saved['baselineSuccess']['INTERNATIONAL']=stamp;saved.pop('lastAttempt');state.write_text(json.dumps(saved))
   self.assertEqual(g.sync(state,output),0);self.assertFalse(json.loads(state.read_text())['coverageGap'])
   self.assertEqual(request.call_count,2)
 def test_global_sync_then_cooldown(self):
  with tempfile.TemporaryDirectory() as temp,patch.object(g,'authenticate',return_value='fake'),patch.object(g,'request_json',return_value=payload(feature())) as request,patch.object(g.time,'sleep'),patch.object(g,'utcnow',return_value=NOW.isoformat()),patch.object(g,'reference_tables',return_value=REFS):
   state=Path(temp)/'state.json';output=Path(temp)/'output'
   self.assertEqual(g.sync(state,output),0)
   urls=[c.args[0] for c in request.call_args_list]
   self.assertEqual(len(urls),6);self.assertTrue(any('classification=INTERNATIONAL' in u for u in urls));self.assertTrue('lastUpdatedDate=' in urls[-1])
   index=json.loads((output/'index.json').read_text());self.assertTrue(index['coverageComplete'])
   self.assertEqual(g.sync(state,output),0);self.assertEqual(request.call_count,6)
