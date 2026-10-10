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
 def test_dm_rectangle(self):
  x,w=extract('FIRING AREA BOUND BY 22-00.0N 159-00.0W, 23-00.0N 159-00.0W, 23-00.0N 160-00.0W, 22-00.0N 160-00.0W.')
  self.assertEqual(x['geometry']['coordinates'][0][0],[-159,22]);self.assertEqual(len(x['geometry']['coordinates'][0]),5)
 def test_separate_areas(self):
  text='AREA 1: 350000N1400000E - 360000N1400000E - 360000N1410000E AREA 2: 370000N1420000E - 380000N1420000E - 380000N1430000E'
  x,w=extract(text);self.assertEqual(x['geometry']['type'],'MultiPolygon');self.assertEqual(len(x['geometry']['coordinates']),2)
 def test_altitude_reference(self):
  a=altitude('F) SFC G) FL250');self.assertEqual(a['lower']['reference'],'surface');self.assertEqual(a['upper']['value'],250)
  a=altitude('F) 2500 FT AGL G) 10000 FT AMSL');self.assertEqual(a['lower']['reference'],'AGL');self.assertEqual(a['upper']['reference'],'AMSL')
 def test_q_altitude_is_envelope(self):
  a=altitude('',qline='RJJJ/QWMLW/IV/BO/W/000/100/3500N14000E020');self.assertEqual(a['basis'],'Q-line envelope');self.assertEqual(a['upper']['value'],100)
 def test_maritime_full_snapshot_filters_and_separates(self):
  r=dict(text='MISSILE FIRING AREA BOUND BY 2200N15900W, 2300N15900W, 2300N16000W',msgYear=2026,msgNumber=1,navArea='12',status='A')
  x=build({'broadcast-warn':[r,dict(r,status='C',msgNumber=2),dict(r,text='BUOY MISSING',msgNumber=3)]},'2026-10-10T00:00:00Z')
  self.assertEqual(len(x['features']),1);self.assertEqual(x['features'][0]['properties']['layer'],'NAVWARN')
 def test_reject_crossing_polygon(self):
  self.assertIsNone(extract('AREA BOUNDED BY 3500N14000E - 3600N14100E - 3500N14100E - 3600N14000E')[0])
