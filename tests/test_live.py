import tempfile, unittest, json
from pathlib import Path
from unittest.mock import patch
from scripts.update_airspace import risk
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from scripts.update_live import publish
class LiveTests(unittest.TestCase):
    def test_activity_candidate(self):
        self.assertEqual(risk({'text':'MISSILE FIRING EXERCISE'},[])[0],'Danger')
    def test_unconfigured_never_calls_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Path(tmp)/'config.json';c.write_text(json.dumps({'countries':{'JP':{'name':'日本','region':'Asia','api':{}}}}))
            with patch('scripts.update_live.run') as fetch:
                self.assertEqual(publish(c,Path(tmp)/'out'),0);fetch.assert_not_called()
            d=json.loads((Path(tmp)/'out/JP.json').read_text())
            self.assertEqual(d['metadata']['status'],'unconfigured');self.assertEqual(d['features'],[])
    def test_reject_nonofficial_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=Path(tmp)/'c.json';c.write_text(json.dumps({'countries':{'JP':{'api':{'url':'https://example.com'}}}}))
            with self.assertRaises(ValueError):publish(c,Path(tmp)/'out')
