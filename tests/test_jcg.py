import sys,unittest,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from sync_jcg import geometry,listings,bodies,build
from sync_maritime import combine
class JCGTests(unittest.TestCase):
 def test_fullwidth_polygon(self):
  s,w=geometry('射撃、３４−２０−００Ｎ　１２４−３０−００Ｅ　３４−２０−００Ｎ　１２５−４９−５３Ｅ　３３−４５−００Ｎ　１２５−４９−５３Ｅ　３３−４５−００Ｎ　１２４−３０−００Ｅで囲まれる海面。')
  self.assertEqual(s['geometry']['type'],'Polygon');self.assertAlmostEqual(s['geometry']['coordinates'][0][0][0],124.5)
 def test_japanese_circle(self):
  s,w=geometry('射撃、４１−４３．０Ｎ　１４１−２９．４Ｅを中心とする半径５海里の円内。');self.assertEqual(s['circle']['radius'],5)
 def test_sector_not_full_circle(self):self.assertIsNone(geometry('１９−１４．６Ｎ　０８４−５３．７Ｅを中心とする半径４１海里の円のうち１００−１８０度の扇形海面。')[0])
 def test_parallel_rectangle(self):
  s,w=geometry('３７−３０−０５Ｎ　３７−４０−０５Ｎ　１３１−１２−００Ｅ　１３１−２５−００Ｅの各線で囲まれる海面。');self.assertEqual(len(s['geometry']['coordinates'][0]),5)
 def test_html_batch_ids(self):
  d=bodies('<STRONG>番号：26-3999</STRONG><br>射撃<hr><STRONG>NO.26-0430</STRONG><br>GUNNERY');self.assertEqual(set(d),{'263999','260430'})
 def test_official_origin_and_filter(self):
  rows=[dict(tana='260001',title='射撃',categoly='訓練試験'),dict(tana='260002',title='灯台消灯',categoly='航路標識')]
  shape='AREA BOUNDED BY 3500N14000E 3600N14000E 3600N14100E'
  d=build(rows,{'260001':'GUNNERY '+shape,'260002':'BUOY '+shape},'NAVAREA11','2026-10-11T00:00:00Z');self.assertEqual(len(d['features']),1)
  p=d['features'][0]['properties'];self.assertEqual(p['layer'],'NAVWARN');self.assertTrue(p['sourceURL'].startswith('https://www1.kaiho.mlit.go.jp/'))
 def test_invalid_list_does_not_become_empty(self):
  with self.assertRaises(ValueError):listings('<html/>')
 def test_aggregate_failure_keeps_source_status(self):
  with tempfile.TemporaryDirectory() as t:
   paths=[]
   for i,status in enumerate(['ok','error']):
    p=Path(t)/f'{i}.json';p.write_text(json.dumps(dict(type='FeatureCollection',features=[],unplotted=[],metadata=dict(status=status,lastSuccess='2026-10-10T00:00:00Z'))));paths.append(p)
   out=Path(t)/'out.json';combine(paths,out);d=json.loads(out.read_text());self.assertEqual(d['metadata']['status'],'error');self.assertEqual(len(d['metadata']['sources']),2)
