"""FAA global classifications: daily baselines, durable incremental changes.
No raw responses/tokens on disk. State contains only normalized candidate NOTAMs.
Bulk classifications are requested at most daily; requests spaced >=181 seconds.
"""
import argparse, hashlib, json, re, time
from collections import defaultdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import quote
from faa_client import authenticate, request_json, SafeFailure
from publish_faa import candidate, reference_tables, SOURCE
from notam_text import extract
from hazard_rules import classify, altitude
from update_airspace import ROOT, utcnow, date, write_json

CLASSES=('INTERNATIONAL','DOMESTIC','FDC','MILITARY','LOCAL_MILITARY')
ALIASES={'INTL':'INTERNATIONAL','INT':'INTERNATIONAL','DOM':'DOMESTIC','MIL':'MILITARY','LMIL':'LOCAL_MILITARY'}

def features(payload):
    if not isinstance(payload,dict) or str(payload.get('status','')).lower()!='success' or payload.get('errors'):raise SafeFailure('response_failure')
    values=payload.get('data',{}).get('geojson')
    if not isinstance(values,list):raise SafeFailure('geojson_schema')
    for f in values:
        if not isinstance(f,dict) or not isinstance(f.get('properties',{}).get('coreNOTAMData',{}).get('notam'),dict):raise SafeFailure('notam_schema')
        if not f['properties']['coreNOTAMData']['notam'].get('id'):raise SafeFailure('missing_notam_id')
    return values

def apply(records, incoming, refs, now, baseline=None):
    result={k:v for k,v in records.items() if not baseline or v['properties'].get('feedClassification')!=baseline}
    for f in incoming:
        n=f['properties']['coreNOTAMData']['notam'];ident=str(n['id'])
        previous=result.get(ident)
        if previous and not baseline:
            try:
                if date(previous['properties'].get('lastUpdated')) and date(n.get('lastUpdated')) and date(n['lastUpdated'])<date(previous['properties']['lastUpdated']):continue
            except (ValueError,TypeError):pass
        item,status=candidate(f,refs,now)
        result.pop(ident,None)
        if item:
            c=str(n.get('classification','')).upper()
            item['properties']['feedClassification']=baseline or ALIASES.get(c,c)
            result[ident]=item
    return {k:v for k,v in result.items() if not expired(v,now)}

def expired(f,now):
    end=f['properties'].get('validTo')
    return bool(end and end!='PERM' and date(end)<=now)

def publish(state,output,status='ok',error=None):
    now=utcnow();groups=defaultdict(list)
    catalog={c['code']:c for c in json.loads((ROOT/'web/countries.json').read_text())['countries']}
    catalog['ZZ']={'code':'ZZ','name':'国未特定','region':'Other'}
    for f in state['records'].values():
        if not expired(f,date(now)):
            code=f['properties']['country']
            if code not in catalog:
                f=dict(f,properties=dict(f['properties'],country='ZZ',countryBasis='参照国コードを分類できません'))
                code='ZZ'
            groups[code].append(f)
    generation=hashlib.sha256((now+str(len(state['records']))).encode()).hexdigest()[:20]
    stats=dict(received=state.get('lastReceived',0),riskCandidates=len(state['records']),retained=sum(map(len,groups.values())),excludedInactive=0,plotted=0,unplotted=0,referencePoints=0,approximateCircles=0,textShapes=0)
    entries=[]
    for code,records in sorted(groups.items()):
        plotted=[f for f in records if f['geometry']];unplotted=[dict(f['properties'],featureId=f['id']) for f in records if not f['geometry']]
        meta=dict(country=code,demo=False,environment='production',status=status,source=SOURCE,lastAttempt=state.get('lastAttempt'),lastSuccess=state.get('lastSuccess'),generation=generation)
        write_json(output/(code+'.json'),dict(type='FeatureCollection',features=plotted,unplotted=unplotted,metadata=meta))
        entries.append(dict(code=code,name=catalog[code]['name'],region=catalog[code]['region'],file=code+'.json',count=len(plotted),unplotted=len(unplotted),**meta))
        stats['plotted']+=len(plotted);stats['unplotted']+=len(unplotted)
        for f in records:
            accuracy=f['properties'].get('accuracy');stats['referencePoints']+=accuracy=='reference-point';stats['approximateCircles']+=accuracy=='qline-envelope';stats['textShapes']+=accuracy in ('text-boundary','text-circle')
    coverage={c:state.get('baselineSuccess',{}).get(c) for c in CLASSES}
    complete=all(coverage.values()) and bool(state.get('watermark'))
    index=dict(schemaVersion=1,demo=False,environment='production',source=SOURCE,status=status,generatedAt=now,lastAttempt=state.get('lastAttempt'),lastSuccess=state.get('lastSuccess'),generation=generation,scope='FAA five classifications; supplied records only, not guaranteed worldwide completeness',stats=stats,countries=entries,coverage=coverage,coverageComplete=complete,deltaSince=state.get('watermark'),syncMode=state.get('mode'),coverageGap=state.get('coverageGap',False))
    if error:index['error']=error
    write_json(output/'index.json',index)

def sync(state_path,output):
    state_path=Path(state_path);output=Path(output)
    state=json.loads(state_path.read_text()) if state_path.exists() else dict(version=1,records={},baselineAttempts={},baselineSuccess={})
    now=date(utcnow())
    # Parser updates can improve saved geometry without any additional FAA call.
    reparsed=state.get('parserVersion')!='critical-v3'
    state['records']={k:f for k,f in state['records'].items() if classify(f['properties'].get('text',''),f['properties'].get('qcode',''))}
    state['parserVersion']='critical-v3'
    for f in state['records'].values():
        props=f['properties']
        props.update(layer='NOTAM',criticalReasons=classify(props.get('text',''),props.get('qcode','')),altitude=altitude(props.get('text',''),props.get('lower'),props.get('upper'),props.get('qline','')))
        if props.get('accuracy') not in ('reference-point','qline-envelope',None):continue
        shape,warning=extract(props.get('originalText') or props.get('text',''))
        if shape and 'circle' in shape:
            c=shape['circle'];f['geometry']={'type':'Point','coordinates':c['center']}
            props.update(radius_m=c['radius']*{'NM':1852,'KM':1000,'M':1}[c['unit']],accuracy='text-circle');reparsed=True
        elif shape and 'geometry' in shape:
            f['geometry']=shape['geometry'];props['accuracy']='text-boundary';reparsed=True
        if shape:props.pop('unplottedReason',None);props.pop('textGeometryWarning',None)
    if reparsed:write_json(state_path,state);publish(state,output,'error' if state.get('error') else 'ok',state.get('error'))
    if state.get('lastAttempt') and (now-date(state['lastAttempt'])).total_seconds()<1800:
        print('FAA_GLOBAL_COOLDOWN');return int(state.get('error') is not None)
    state['lastAttempt']=utcnow();state.setdefault('bootstrapStart',utcnow())
    if (now-date(state.get('watermark') or state['bootstrapStart'])).total_seconds()>86300:
        state['coverageGap']=True
        state.setdefault('gapSince',state['lastAttempt'])
    if state.get('coverageGap'):state.setdefault('gapSince',state['lastAttempt'])
    write_json(state_path,state)
    refs=reference_tables()
    last_call=None
    def pull(path):
        nonlocal last_call
        wait=0 if last_call is None else 181-(time.monotonic()-last_call)
        if wait>0:time.sleep(wait)
        token=authenticate()
        last_call=time.monotonic()
        headers={'Authorization':'Bearer '+token,'nmsResponseFormat':'GEOJSON','Accept':'application/json'}
        payload=request_json(path,headers,limit=128*1024*1024)
        content=payload.get('data',{}).get('url')
        if content:
            # Never follow cloud/signed URLs or forward credentials off FAA origin.
            if not isinstance(content,str) or not re.fullmatch(r'/(?:nmsapi/)?v1/content/[A-Za-z0-9_\-=%.]+',content):raise SafeFailure('unsafe_content_url')
            path=content if content.startswith('/nmsapi/') else '/nmsapi'+content
            payload=request_json(path,headers,limit=128*1024*1024)
        del token,headers
        return features(payload)
    try:
        count=0;used_bulk=False
        for classification in CLASSES:
            last=state['baselineAttempts'].get(classification)
            if last and (now-date(last)).total_seconds()<86400:continue
            state['baselineAttempts'][classification]=utcnow();write_json(state_path,state)
            incoming=pull('/nmsapi/v1/notams?classification='+classification+'&allowRedirect=false')
            state['records']=apply(state['records'],incoming,refs,date(utcnow()),classification)
            state['baselineSuccess'][classification]=utcnow();count+=len(incoming);used_bulk=True
            state['lastSuccess']=utcnow();state['mode']='baseline';state['lastReceived']=count
            write_json(state_path,state)
            print('FAA_GLOBAL_CLASS='+classification+'; received='+str(len(incoming)),flush=True)
        # Query from the beginning of the previous request, overlapping one minute.
        since=state.get('watermark') or state['bootstrapStart']
        age=(date(utcnow())-date(since)).total_seconds()
        if age>86300:
            state['coverageGap']=True
            if not used_bulk:raise SafeFailure('delta_window_exceeded_wait_for_daily_baseline')
            since=state['lastAttempt']
        watermark=utcnow()
        incoming=pull('/nmsapi/v1/notams?lastUpdatedDate='+quote((date(since)-timedelta(seconds=60)).strftime('%Y-%m-%dT%H:%M:%SZ'),safe=''))
        state['records']=apply(state['records'],incoming,refs,date(utcnow()))
        state.update(watermark=watermark,lastSuccess=utcnow(),lastReceived=count+len(incoming),mode='baseline+delta' if used_bulk else 'delta')
        if state.get('gapSince') and all(state['baselineSuccess'].get(c) and date(state['baselineSuccess'][c])>=date(state['gapSince']) for c in CLASSES):
            state['coverageGap']=False;state.pop('gapSince',None)
        state.pop('error',None);write_json(state_path,state);publish(state,output)
        print('FAA_GLOBAL_PUBLISHED='+str(len(state['records'])),flush=True);return 0
    except Exception as exc:
        category=str(exc) if isinstance(exc,SafeFailure) and re.fullmatch('[a-z0-9_]+',str(exc)) else 'validation_or_configuration_error'
        state['error']=category;write_json(state_path,state)
        publish(state,output,'error',category)
        print('FAA_GLOBAL_FAILED='+category,flush=True);return 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--report',default='');args=parser.parse_args()
    errors=sync(ROOT/'state/faa-sync.json',ROOT/'web/production')
    if args.report:Path(args.report).write_text(str(errors))
