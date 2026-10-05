#!/usr/bin/env python3
"""Complete country snapshots -> compact GeoJSON. No database; no guessed boundaries."""
import argparse, copy, hashlib, json, math, os, re, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urljoin

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None

HTTP = build_opener(NoRedirect())
ROOT = Path(__file__).resolve().parents[1]
TYPES = {'restricted':'Restricted', 'danger':'Danger', 'prohibited':'Prohibited'}
KEYWORDS = re.compile(r'\b(RESTRICTED|DANGER|PROHIBITED)\b|制限区域|危険区域|飛行禁止区域', re.I)
ACTIVITY = re.compile(r'\b(MISSILE(?:S)?|ROCKET(?:S)?|FIRING|GUNFIRE|LIVE[ -]FIRE|MILITARY EXERCISE|EXERCISES?|EXER|GUNNERY)\b|ミサイル|ロケット|射撃|軍事演習', re.I)
QCODE = re.compile(r'\bQ[A-Z]{4}\b')
QAREA = re.compile(r'(\d{2})(\d{2})([NS])(\d{3})(\d{2})([EW])(\d{3})\s*$')

def utcnow():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')

def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n'
    if path.exists() and path.read_text() == raw:
        return
    tmp = path.with_suffix('.tmp')
    tmp.write_text(raw)
    tmp.replace(path)

def date(value):
    if not value or value == 'PERM':
        return None
    dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('timestamp must include timezone')
    return dt

def position(p):
    if not isinstance(p, list) or len(p) != 2 or any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in p):
        raise ValueError('invalid coordinate')
    if not -180 <= p[0] <= 180 or not -90 <= p[1] <= 90:
        raise ValueError('coordinate out of range')
    return p

def polygon_geometry(g):
    if not isinstance(g, dict) or g.get('type') not in ('Polygon', 'MultiPolygon'):
        raise ValueError('expected Polygon or MultiPolygon')
    polygons = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    if not polygons:
        raise ValueError('empty geometry')
    for poly in polygons:
        if not poly:
            raise ValueError('empty polygon')
        for ring in poly:
            if len(ring) < 4 or ring[0] != ring[-1]:
                raise ValueError('ring must be explicitly closed')
            for p in ring:
                position(p)
            if len({tuple(p) for p in ring}) < 3:
                raise ValueError('degenerate ring')
    # Provider must supply valid topology and split antimeridian polygons according to RFC 7946.
    for poly in polygons:
        for ring in poly:
            if any(abs(a[0]-b[0]) > 180 for a,b in zip(ring,ring[1:])):
                raise ValueError('antimeridian polygon must be split by provider adapter')
    return {'type':g['type'], 'coordinates':g['coordinates']}

def qcircle(qline):
    m = QAREA.search(qline.strip())
    if not m:
        return None
    latd,latm,ns,lond,lonm,ew,radius=m.groups()
    if int(latm)>=60 or int(lonm)>=60:
        raise ValueError('invalid Q coordinates')
    lat=(int(latd)+int(latm)/60)*(-1 if ns=='S' else 1)
    lon=(int(lond)+int(lonm)/60)*(-1 if ew=='W' else 1)
    position([lon,lat])
    if int(radius) in (0,999):
        return None # No usable extent / special whole-FIR radius: never invent a boundary.
    return {'center':[lon,lat], 'radius_m':int(radius)*1852, 'accuracy':'qline-envelope'}

def risk(record, prefixes):
    q = str(record.get('qcode') or '').upper().strip()
    if not q:
        match=QCODE.search(str(record.get('qline','')).upper())
        q=match.group(0) if match else ''
    text=str(record.get('text',''))
    kind=TYPES.get(str(record.get('type','')).lower())
    reason=[]
    if kind: reason.append('type')
    subject=q[1:3] if re.fullmatch(r'Q[A-Z]{4}',q) else ''
    if subject in ('RR','RD','RP'):
        kind=kind or {'RR':'Restricted','RD':'Danger','RP':'Prohibited'}[subject]
        reason.append('qcode-subject')
    # Prefixes are user filters, NOT a table of official full five-letter Q codes.
    if any(q.removeprefix('Q').startswith(p.removeprefix('Q')) for p in prefixes if p):
        kind=kind or 'Danger';reason.append('configured-q-prefix')
    if ACTIVITY.search(text):
        kind=kind or 'Danger';reason.append('activity-keyword-candidate')
    match=KEYWORDS.search(text)
    if match:
        token=match.group().upper()
        kind=kind or ('Prohibited' if token in ('PROHIBITED','飛行禁止区域') else 'Restricted' if token in ('RESTRICTED','制限区域') else 'Danger')
        reason.append('keyword-candidate')
    return kind,q,reason

def normalize(record, country, source, prefixes, now):
    if not isinstance(record,dict):
        raise ValueError('record must be an object')
    # Canonical adapter contract: current full snapshot, explicit lifecycle fields.
    if str(record.get('status','')).upper() in ('CANCELLED','CANCELED','INACTIVE') or record.get('notamType')=='C':
        return None,None
    end=date(record.get('validTo'));start=date(record.get('validFrom'))
    if start and end and end < start:
        raise ValueError('invalid time interval')
    if end and end <= now:
        return None,None
    kind,q,reasons=risk(record,prefixes)
    if not kind:
        return None,None
    ident=str(record.get('id') or hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()[:16])
    props={'id':ident,'country':country,'type':kind,'name':str(record.get('name') or ident),
           'qcode':q,'text':str(record.get('text','')),'source':source,
           'validFrom':record.get('validFrom'),'validTo':record.get('validTo'),
           'lower':record.get('lower'),'upper':record.get('upper'),
           'schedule':record.get('schedule'),'matches':reasons,
           'timeStatus':'future' if start and start>now else 'window' if start or end else 'unknown'}
    if record.get('schedule'):
        props['timeStatus']='schedule-unparsed'
    geometry=None
    try:
        if record.get('geometry'):
            geometry=polygon_geometry(record['geometry']);props['accuracy']='provider-boundary'
        elif record.get('circle'):
            c=record['circle'];position(c['center'])
            unit=c.get('unit','').upper()
            if unit not in ('M','KM','NM'):raise ValueError('unknown radius unit')
            r=c['radius']*{'M':1,'KM':1000,'NM':1852}[unit]
            if not isinstance(r,(int,float)) or isinstance(r,bool) or not math.isfinite(r) or r<=0:raise ValueError('invalid radius')
            geometry={'type':'Point','coordinates':c['center']}
            props.update(radius_m=r,accuracy='provider-circle')
        else:
            c=qcircle(str(record.get('qline','')))
            if c:
                geometry={'type':'Point','coordinates':c['center']}
                props.update(radius_m=c['radius_m'],accuracy=c['accuracy'])
    except (ValueError,KeyError,TypeError):
        props['unplottedReason']='invalid-or-unsupported-geometry'
    if geometry is None:
        props.setdefault('unplottedReason','no-explicit-boundary-or-usable-qline')
        return None,props
    return {'type':'Feature','id':country+':'+ident,'properties':props,'geometry':geometry},None

def get_path(obj, path):
    for part in path.split('.') if path else []:
        obj=obj[part]
    return obj

def adapt(payload, spec):
    """Map verified provider keys to canonical keys. Override for AIXM/DMS/deltas."""
    records=get_path(payload,spec.get('records_path','items'))
    if not isinstance(records,list):raise ValueError('records path is not a list')
    mapping=spec.get('field_map',{})
    if not mapping:return records
    return [{key:get_path(r,path) for key,path in mapping.items()} for r in records]

def fetch_snapshot(spec, country):
    url=spec['url'].replace('{country}',country)
    if urlsplit(url).scheme!='https':raise ValueError('HTTPS is required')
    origin=urlsplit(url).netloc
    headers={'Accept':'application/json','User-Agent':'Alta-system-Research/1.0'}
    for header,env in spec.get('headers_env',{}).items():
        value=os.environ.get(env)
        if not value:raise ValueError('missing API secret')
        headers[header]=value
    all_records=[];seen=set()
    for page in range(100):
        if url in seen:raise ValueError('pagination loop')
        seen.add(url)
        body=None
        for attempt in range(3):
            try:
                with HTTP.open(Request(url,headers=headers),timeout=25) as res:
                    if urlsplit(res.url).netloc!=origin:raise ValueError('cross-origin redirect')
                    raw=res.read(20_000_001)
                    if len(raw)>20_000_000:raise ValueError('response too large')
                    body=json.loads(raw)
                break
            except HTTPError as err:
                if err.code not in (429,500,502,503,504) or attempt==2:raise
            except (URLError,TimeoutError):
                if attempt==2:raise
            time.sleep(2**attempt)
        if spec.get('complete_path') and get_path(body,spec['complete_path']) is not True:
            raise ValueError('provider did not confirm complete page')
        all_records.extend(adapt(body,spec))
        next_url=get_path(body,spec['next_path']) if spec.get('next_path') else None
        if not next_url:return all_records
        url=urljoin(url,next_url)
        if urlsplit(url).netloc!=origin or urlsplit(url).scheme!='https':raise ValueError('unsafe pagination URL')
    raise ValueError('pagination limit')

def run(config_path, output, demo=False):
    config=json.loads(Path(config_path).read_text()); output=Path(output)
    stamp=utcnow();now=date(stamp);index={'schemaVersion':1,'generatedAt':stamp,'demo':demo,'countries':[]};failed=0
    for country,info in config['countries'].items():
        if not re.fullmatch('[A-Z]{2}',country):raise ValueError('invalid country code')
        path=output/f'{country}.json'
        try:
            old=json.loads(path.read_text()) if path.exists() else None
        except (OSError, ValueError):
            old=None
        # Do not carry fictional data into live mode or data belonging to a different country.
        if old and (old.get('metadata',{}).get('demo')!=demo or old.get('metadata',{}).get('country')!=country):old=None
        try:
            if demo:
                records=json.loads((ROOT/'fixtures'/f'{country}.json').read_text())['items']; source='Fictional demo'
            else:
                spec=info['api']
                if spec.get('snapshot_confirmed') is not True:raise ValueError('adapter not configured as full current snapshot')
                records=fetch_snapshot(spec,country);source=info['source']
            # Cancellation/replacement targets in this snapshot supersede earlier records.
            removed={str(r[k]) for r in records for k in ('replaces','cancels') if r.get(k)}
            features={};unplotted=[]
            for record in records:
                if str(record.get('id')) in removed:continue
                feature,missing=normalize(record,country,source,config.get('q_prefixes',[]),now)
                if feature:features[feature['id']]=feature
                if missing:unplotted.append(missing)
            data={'type':'FeatureCollection','features':sorted(features.values(),key=lambda f:f['id']),
                'unplotted':unplotted,'metadata':{'country':country,'demo':demo,'source':source,'lastAttempt':stamp,'lastSuccess':None if demo else stamp,'status':'demo' if demo else 'ok','received':len(records)}}
        except Exception as err:
            failed+=1
            data=copy.deepcopy(old) if old else {'type':'FeatureCollection','features':[],'unplotted':[],'metadata':{'country':country,'demo':demo,'lastSuccess':None}}
            data['metadata'].update(status='error',lastAttempt=stamp,error='取得失敗・設定を確認してください')
            # Never print URLs, headers or provider exception bodies (may contain secrets).
            print(f'{country}: failed ({type(err).__name__}); previous snapshot retained')
        write_json(path,data)
        index['countries'].append({'code':country,'name':info['name'],'region':info['region'],'file':f'{country}.json','count':len(data['features']),'unplotted':len(data['unplotted']),**data['metadata']})
    write_json(output/'index.json',index)
    return failed

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--config',default=str(ROOT/'config/sources.json'));p.add_argument('--output',default=str(ROOT/'web/data'));p.add_argument('--demo',action='store_true');p.add_argument('--report',default='')
    a=p.parse_args();errors=run(a.config,a.output,a.demo)
    if a.report:Path(a.report).write_text(str(errors))
    # Publish stale status even on errors; CI marks failure after the Pages deploy.
    print(f'Countries with errors: {errors}')
