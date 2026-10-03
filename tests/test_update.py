import copy, json, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
from scripts.update_airspace import normalize, qcircle, run, date, ROOT, risk
NOW=date('2026-10-03T00:00:00Z')
BASE={'id':'a','type':'Restricted','geometry':{'type':'Polygon','coordinates':[[[1,1],[2,1],[2,2],[1,1]]]}}
class FilteringTests(unittest.TestCase):
    def norm(self,r):return normalize(r,'JP','test',['WMR','WMW','WXX'],NOW)
    def test_polygon_and_hole(self):
        r=copy.deepcopy(BASE);r['geometry']['coordinates'].append([[1.6,1.2],[1.7,1.2],[1.7,1.3],[1.6,1.2]])
        f,u=self.norm(r);self.assertEqual(len(f['geometry']['coordinates']),2);self.assertIsNone(u)
    def test_prohibited_qcode(self):
        r=copy.deepcopy(BASE);r.pop('type');r['qcode']='QRPCA';self.assertEqual(self.norm(r)[0]['properties']['type'],'Prohibited')
    def test_user_prefix(self):
        kind,q,reasons=risk({'qcode':'QWXXW'},['WXX']);self.assertEqual(kind,'Danger');self.assertIn('configured-q-prefix',reasons)
    def test_circle_units(self):
        r={'id':'c','type':'Danger','circle':{'center':[139,35],'radius':3,'unit':'NM'}}
        self.assertEqual(self.norm(r)[0]['properties']['radius_m'],5556)
    def test_qline_envelope(self):
        c=qcircle('RJTT/QWXXW/IV/BO/W/000/999/3530N13930E010')
        self.assertEqual(c['center'],[139.5,35.5]);self.assertEqual(c['radius_m'],18520);self.assertEqual(c['accuracy'],'qline-envelope')
    def test_invalid_qline(self):
        with self.assertRaises(ValueError):qcircle('3560N13930E010')
        self.assertIsNone(qcircle('3530N13930E999'))
    def test_cancel_and_expiry(self):
        for fields in [{'status':'CANCELLED'},{'validTo':'2026-10-02T00:00:00Z'},{'notamType':'C'}]:
            self.assertEqual(self.norm({**BASE,**fields}),(None,None))
    def test_future_and_schedule(self):
        self.assertEqual(self.norm({**BASE,'validFrom':'2026-10-04T00:00:00Z'})[0]['properties']['timeStatus'],'future')
        self.assertEqual(self.norm({**BASE,'schedule':'DAILY 0900-1000'})[0]['properties']['timeStatus'],'schedule-unparsed')
    def test_bad_geometry_not_guessed(self):
        for g in [{'type':'Point','coordinates':[139,35]},{'type':'Polygon','coordinates':[[[181,0],[179,1],[179,0],[181,0]]]}]:
            f,u=self.norm({**BASE,'geometry':g});self.assertIsNone(f);self.assertIn('unplottedReason',u)
    def test_antimeridian_requires_split(self):
        f,u=self.norm({**BASE,'geometry':{'type':'Polygon','coordinates':[[[179,0],[-179,0],[-179,2],[179,0]]]}})
        self.assertIsNone(f);self.assertIsNotNone(u)
    def test_no_text_coordinate_invention(self):
        f,u=self.norm({'type':'Danger','text':'DANGER north of airport'});self.assertIsNone(f);self.assertIsNotNone(u)
    def test_fetch_failure_keeps_live_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);cfg={'countries':{'JP':{'name':'日本','region':'Asia','source':'test','api':{'snapshot_confirmed':True}}}}
            (p/'config.json').write_text(json.dumps(cfg))
            with patch('scripts.update_airspace.fetch_snapshot',return_value=[BASE]):run(p/'config.json',p/'data')
            before=json.loads((p/'data/JP.json').read_text())
            with patch('scripts.update_airspace.fetch_snapshot',side_effect=ValueError('secret')):self.assertEqual(run(p/'config.json',p/'data'),1)
            after=json.loads((p/'data/JP.json').read_text());self.assertEqual(before['features'],after['features']);self.assertEqual(before['metadata']['lastSuccess'],after['metadata']['lastSuccess']);self.assertEqual(after['metadata']['status'],'error')
    def test_replacement_and_cancel_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);cfg={'countries':{'JP':{'name':'日本','region':'Asia','source':'test','api':{'snapshot_confirmed':True}}}};(p/'cfg').write_text(json.dumps(cfg))
            with patch('scripts.update_airspace.fetch_snapshot',return_value=[BASE,{'id':'b','notamType':'C','cancels':'a'}]):run(p/'cfg',p/'out')
            self.assertEqual(json.loads((p/'out/JP.json').read_text())['features'],[])
if __name__=='__main__':unittest.main()
