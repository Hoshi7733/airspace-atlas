#!/usr/bin/env python3
"""Official NOTAM-only publishing entry point. No weather or third-party API."""
import argparse, json
from pathlib import Path
from urllib.parse import urlsplit
from update_airspace import ROOT, run, utcnow, write_json

def publish(config_path, output):
    config=json.loads(Path(config_path).read_text()); output=Path(output)
    active={}; pending={}
    for code,info in config['countries'].items():
        spec=info.get('api',{})
        if not spec.get('url'):
            pending[code]=info;continue
        host=urlsplit(spec['url']).hostname or ''
        if not any(host==d or host.endswith('.'+d) for d in ('faa.gov','icao.int')):
            raise ValueError('Only official FAA or ICAO sources are enabled')
        if info.get('provider') not in ('FAA','ICAO'):
            raise ValueError('Explicit official provider is required')
        if spec.get('schema_verified') is not True:
            raise ValueError('Verify the issued API specification before enabling a provider')
        active[code]=info
    stamp=utcnow(); index={'schemaVersion':1,'demo':False,'generatedAt':stamp,'countries':[]};errors=0
    if active:
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'sources.json';write_json(path,{**config,'countries':active})
            errors=run(path,output)
        index=json.loads((output/'index.json').read_text())
    for code,info in pending.items():
        data={'type':'FeatureCollection','features':[],'unplotted':[], 'metadata':{'country':code,'demo':False,'status':'unconfigured','lastAttempt':stamp,'lastSuccess':None,'source':'FAA / ICAO 接続待ち'}}
        write_json(output/(code+'.json'),data)
        index['countries'].append({'code':code,'name':info['name'],'region':info['region'],'file':code+'.json','count':0,'unplotted':0,**data['metadata']})
    index['connection']='NOTAM ONLY';write_json(output/'index.json',index)
    return errors

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'config/sources.json'));p.add_argument('--output',default=str(ROOT/'web/data'));p.add_argument('--report',default='')
    a=p.parse_args();errors=publish(a.config,a.output)
    if a.report:Path(a.report).write_text(str(errors))
    print('NOTAM source failures:',errors)
