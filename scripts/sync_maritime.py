"""Official NGA active navigational warnings, independent of FAA limits.
Five bounded requests per 30 minutes; failed fetch retains the last valid snapshot.
NGA's supplied areas are not a guarantee of global NAVAREA coverage.
"""
import json,re
from pathlib import Path
from urllib.request import Request,build_opener
from update_airspace import ROOT,NoRedirect,write_json,utcnow,date
from hazard_rules import classify,altitude
from notam_text import extract
URL='https://msi.nga.mil/api/publications/smaps'
AREAS=('4','12','A','P','C')
VERSION='smaps-v1'
SOURCE='NGA Maritime Safety Information — Navigational Warnings'

def build(payload,stamp):
    rows=payload.get('smaps') if isinstance(payload,dict) else None
    if not isinstance(rows,list):raise ValueError('schema')
    features=[];unplotted=[];ids=set()
    for r in rows:
        if not isinstance(r,dict) or not all(k in r for k in ('msgText','msgSqncNumber','msgType','status')):raise ValueError('row schema')
        if r['status']!='INFORCE' or r.get('cancelledOn'):continue
        text=r['msgText'].replace('\\n','\n');reasons=classify(text)
        if not reasons:continue
        year=re.search(r'\b(20\d{2})\b',r.get('createdOn') or '')
        if not year:raise ValueError('missing issue year')
        ident='NGA:'+str(r['msgType'])+':'+year[1]+':'+str(r['msgSqncNumber'])
        if ident in ids:continue
        ids.add(ident);shape,warning=extract(text);geometry=None
        props=dict(id=ident,country='ZZ',countryBasis='航行警報海域・国への帰属は未判定',layer='NAVWARN',type='Danger',name=str(r['msgType'])+' '+str(r['msgSqncNumber'])+'/'+year[1],source=SOURCE,sourceURL='https://msi.nga.mil/NavWarnings',authority='NGA',navArea=r.get('navArea'),series=r['msgType'],text=text,originalText=text,issued=r.get('createdOn'),validFrom=None,validTo=None,timeStatus='source-active-schedule-unparsed',schedule='公式フィードの有効警報。個別の実施日時・取消は原文を確認',criticalReasons=reasons,altitude=altitude(''),fetchedAt=stamp)
        if shape and 'geometry' in shape:geometry=shape['geometry'];props['accuracy']='text-boundary'
        elif shape and 'circle' in shape:
            c=shape['circle'];geometry={'type':'Point','coordinates':c['center']};props.update(accuracy='text-circle',radius_m=c['radius']*{'NM':1852,'KM':1000,'M':1}[c['unit']])
        if warning:props['textGeometryWarning']=warning
        if geometry:features.append(dict(type='Feature',id=ident,geometry=geometry,properties=props))
        else:unplotted.append(dict(props,featureId=ident,unplottedReason=warning or '本文から境界を確定できません'))
    return dict(type='FeatureCollection',features=features,unplotted=unplotted,metadata=dict(status='ok',parserVersion=VERSION,source=SOURCE,sourceURL=URL,lastAttempt=stamp,lastSuccess=stamp,received=len(rows),retained=len(ids),series=list(AREAS),coverage='NGA現行5系列（NAVAREA IV/XII、HYDROLANT/HYDROPAC/HYDROARC）。全21 NAVAREAの完全収録ではありません。'))

def sync(path):
    path=Path(path);stamp=utcnow();old=json.loads(path.read_text()) if path.exists() else None
    if old and old['metadata'].get('parserVersion')==VERSION and old['metadata'].get('lastAttempt') and (date(stamp)-date(old['metadata']['lastAttempt'])).total_seconds()<1800:return 0
    try:
        rows=[]
        for area in AREAS:
            req=Request(URL+'?navArea='+area+'&status=active&category=14&output=json',headers={'Accept':'application/json','User-Agent':'ALTA-SYSTEM-Research/2.0'})
            with build_opener(NoRedirect()).open(req,timeout=60) as r:
                raw=r.read(20_000_001)
                if len(raw)>20_000_000:raise ValueError('size')
            payload=json.loads(raw)
            if not isinstance(payload.get('smaps'),list):raise ValueError('schema')
            rows.extend(payload['smaps'])
        result=build({'smaps':rows},stamp);write_json(path,result)
        print('NAVWARN_PUBLISHED='+str(result['metadata']['retained']));return 0
    except Exception:
        old=old or dict(type='FeatureCollection',features=[],unplotted=[],metadata={})
        old['metadata'].update(status='error',lastAttempt=stamp,error='公式航行警報の取得・検証に失敗。前回の成功分を保持。',source=SOURCE,sourceURL=URL)
        write_json(path,old);print('NAVWARN_FAILED');return 1
def combine(paths,output):
    feeds=[json.loads(Path(p).read_text()) for p in paths]
    metadata=[f['metadata'] for f in feeds]
    features=[f for feed in feeds for f in feed['features']]
    unplotted=[p for feed in feeds for p in feed['unplotted']]
    ok=all(m.get('status')=='ok' for m in metadata)
    stamps=[m.get('lastSuccess') for m in metadata if m.get('lastSuccess')]
    meta=dict(status='ok' if ok else 'error',source='Official maritime warnings: NGA + Japan Coast Guard',sources=metadata,lastAttempt=utcnow(),lastSuccess=min(stamps) if len(stamps)==len(feeds) else None,received=sum(m.get('received',0) for m in metadata),retained=len(features)+len(unplotted),plotted=len(features),unplotted=len(unplotted),coverage='NGA、JCG NAVAREA XI、日本航行警報の配信分。全世界網羅ではありません。')
    if not ok:meta['error']='海域の一部ソースで取得失敗。各ソースの最終成功分を表示。'
    write_json(Path(output),dict(type='FeatureCollection',features=features,unplotted=unplotted,metadata=meta))

if __name__=='__main__':
    from sync_jcg import sync as sync_jcg
    folder=ROOT/'web/maritime'
    result=sync(folder/'nga.json')
    result+=sync_jcg('NAVAREA11',folder/'jcg_navarea11.json')
    result+=sync_jcg('JAPANNW',folder/'jcg_japannw.json')
    combine([folder/'nga.json',folder/'jcg_navarea11.json',folder/'jcg_japannw.json'],folder/'index.json')
    Path('/tmp/maritime-errors').write_text(str(result))
