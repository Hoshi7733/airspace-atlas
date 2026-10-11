import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from hazard_rules import classify,altitude
from notam_text import extract
from sync_maritime import build
class MonitorTests(unittest.TestCase):
 def test_exclude_generic_and_nonmilitary(self):
  for text,q in [('DANGER WIND TURBINE','QWXXW'),('RESTRICTED RWY LIGHT U/S','QMRLC'),('MILITARY AIRPORT TWY CLOSED','QMXLC'),('VOLCANIC ASH','QWWLW'),('NO LIVE FIRING','QWXXW')]:self.assertEqual(classify(text,q),[])
 def test_accept_critical(self):
  for text,q in [('MISSILE FIRING',''),('WEAPON EXERCISE',''),('NATIONAL SECURITY RESTRICTION','QRRCA'),('MILITARY EXERCISE','QWELW'),('AREA ACTIVATED','QWMLW')]:self.assertTrue(classify(text,q))
 def test_q_cancellation(self):self.assertFalse(classify('MISSILE FIRING','QWMCN'))
 def test_sector_is_not_a_full_circle(self):
  for text in ['FAN SHAPED AREA WITHIN 10KM RADIUS OF 410403N1412312E BTN 043DEG AND 133DEG','SECTOR WITHIN 5NM OF 350000N1400000E']:
   shape,warning=extract(text);self.assertIsNone(shape);self.assertTrue(warning)
 def test_dm_rectangle(self):
  x,w=extract('FIRING AREA BOUND BY 22-00.0N 159-00.0W, 23-00.0N 159-00.0W, 23-00.0N 160-00.0W, 22-00.0N 160-00.0W.')
  self.assertEqual(x['geometry']['coordinates'][0][0],[-159,22]);self.assertEqual(len(x['geometry']['coordinates'][0]),5)
 def test_separate_areas(self):
  text='AREA 1: 350000N1400000E - 360000N1400000E - 360000N1410000E AREA 2: 370000N1420000E - 380000N1420000E - 380000N1430000E'
  x,w=extract(text);self.assertEqual(x['geometry']['type'],'MultiPolygon');self.assertEqual(len(x['geometry']['coordinates']),2)
 def test_numbered_airspaces_and_word_ending_e(self):
  text='(1)AIRSPACE: BOUNDED BY FLW POINTS 264419N1275729E - 255619N1275729E - 255619N1272129E - 264419N1272129E (NAHA) (2)AIRSPACE: BOUNDED BY FLW POINTS 251802N1253730E - 243002N1253730E - 243002N1250130E - 251802N1250130E RMK: INFO ZONE) ARE EXCLUDED'
  x,w=extract(text);self.assertEqual(x['geometry']['type'],'MultiPolygon');self.assertEqual(len(x['geometry']['coordinates']),2)
 def test_lettered_maritime_areas(self):
  x,w=extract('ROCKET LAUNCH IN AREAS BOUND BY: A. 21-29.63N 128-41.38E, 21-37.99N 129-53.83E, 18-29.72N 130-17.60E. B. 12-45.04N 129-26.03E, 12-55.28N 131-04.99E, 08-14.81N 131-34.22E. 2. CANCEL THIS MSG 140543Z OCT 26.')
  self.assertEqual(x['geometry']['type'],'MultiPolygon')
 def test_altitude_reference(self):
  a=altitude('F) SFC G) FL250');self.assertEqual(a['lower']['reference'],'surface');self.assertEqual(a['upper']['value'],250)
  a=altitude('F) 2500 FT AGL G) 10000 FT AMSL');self.assertEqual(a['lower']['reference'],'AGL');self.assertEqual(a['upper']['reference'],'AMSL')
 def test_q_altitude_is_envelope(self):
  a=altitude('',qline='RJJJ/QWMLW/IV/BO/W/000/100/3500N14000E020');self.assertEqual(a['basis'],'Q-line envelope');self.assertEqual(a['upper']['value'],100)
 def test_maritime_full_snapshot_filters_and_separates(self):
  r=dict(msgText='MISSILE FIRING AREA BOUND BY 2200N15900W, 2300N15900W, 2300N16000W',createdOn='101200Z OCT 2026',msgSqncNumber=1,msgType='NAVAREA XII',navArea='NAVAREA XII',status='INFORCE')
  x=build({'smaps':[r,dict(r,status='CANCELED',msgSqncNumber=2),dict(r,msgText='BUOY MISSING',msgSqncNumber=3)]},'2026-10-10T00:00:00Z')
  self.assertEqual(len(x['features']),1);self.assertEqual(x['features'][0]['properties']['layer'],'NAVWARN')
 def test_reject_crossing_polygon(self):
  self.assertIsNone(extract('AREA BOUNDED BY 3500N14000E - 3600N14100E - 3500N14100E - 3600N14000E')[0])
