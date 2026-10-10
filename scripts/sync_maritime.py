"""Official NGA active navigational warnings, independent of FAA limits.
One bounded request per 30 minutes; failed fetch retains the last valid snapshot.
NGA's supplied areas are not a guarantee of global NAVAREA coverage.
"""
import json,re
from pathlib import Path
from urllib.request import Request,build_opener
from update_airspace import ROOT,NoRedirect,write_json,utcnow,date
from hazard_rules import classify,altitude
from notam_text import extract
URL='https://msi.nga.mil/api/publications/broadcast-warn?output=json'
SOURCE='NGA Maritime Safety Information — Navigational Warnings'

def build(payload,stamp):
    rows=payload.get('broadcast-warn') if isinstance(payload,dict) else None
    if not isinstance(rows,list):raise ValueError('schema')
    features=[];unplotted=[];ids=set()
    for r in rows:
        if not isinstance(r,dict) or not all(k in r for k in ('text','msgYear','msgNumber','navArea','status')):raise ValueError('row schema')
        if r['status']!='A' or r.get('cancelDate'):continue
        text=r['text'];reasons=classify(text)
        if not reasons:continue
        ident='NGA:'+str(r['navArea'])+':'+str(r['msgYear'])+':'+str(r['msgNumber'])
        if ident in ids:continue
        ids.add(ident);shape,warning=extract(text);geometry=None
        props=dict(id=ident,country='ZZ',countryBasis='航行警報海域・国への帰属は未判定',layer='NAVWARN',type='Danger',name='NAVAREA '+str(r['navArea'])+' '+str(r['msgNumber'])+'/'+str(r['msgYear']),source=SOURCE,sourceURL=URL,authority=r.get('authority'),navArea=r['navArea'],text=text,originalText=text,issued=r.get('issueDate'),validFrom=None,validTo=None,timeStatus='source-active-schedule-unparsed',schedule='公式フィードの有効警報。個別の実施日時・取消は原文を確認',criticalReasons=reasons,altitude=altitude(''),fetchedAt=stamp)
        if shape and 'geometry' in shape:geometry=shape['geometry'];props['accuracy']='text-boundary'
        elif shape and 'circle' in shape:
            c=shape['circle'];geometry={'type':'Point','coordinates':c['center']};props.update(accuracy='text-circle',radius_m=c['radius']*{'NM':1852,'KM':1000,'M':1}[c['unit']])
        if warning:props['textGeometryWarning']=warning
        if geometry:features.append(dict(type='Feature',id=ident,geometry=geometry,properties=props))
        else:unplotted.append(dict(props,featureId=ident,unplottedReason=warning or '本文から境界を確定できません'))
    return dict(type='FeatureCollection',features=features,unplotted=unplotted,metadata=dict(status='ok',source=SOURCE,sourceURL=URL,lastAttempt=stamp,lastSuccess=stamp,received=len(rows),retained=len(ids),coverage='NGA配信分のみ。全NAVAREA・全世界の網羅性は保証しません。'))

def sync(path):
    path=Path(path);stamp=utcnow();old=json.loads(path.read_text()) if path.exists() else None
    if old and old['metadata'].get('lastAttempt') and (date(stamp)-date(old['metadata']['lastAttempt'])).total_seconds()<1800:return 0
    try:
        req=Request(URL,headers={'Accept':'application/json','User-Agent':'ALTA-SYSTEM-Research/2.0'})
        with build_opener(NoRedirect()).open(req,timeout=40) as r:
            raw=r.read(20_000_001)
            if len(raw)>20_000_000:raise ValueError('size')
        result=build(json.loads(raw),stamp);write_json(path,result)
        print('NAVWARN_PUBLISHED='+str(result['metadata']['retained']));return 0
    except Exception:
        old=old or dict(type='FeatureCollection',features=[],unplotted=[],metadata={})
        old['metadata'].update(status='error',lastAttempt=stamp,error='公式航行警報の取得・検証に失敗。前回の成功分を保持。',source=SOURCE,sourceURL=URL)
        write_json(path,old);print('NAVWARN_FAILED');return 1
if __name__=='__main__':
    result=sync(ROOT/'web/maritime/nga.json')
    Path('/tmp/maritime-errors').write_text(str(result))
