#!/usr/bin/env python3
"""FAA NMS production AIRSPACE snapshots. Secrets and bearer tokens stay in memory.
Full filtered snapshot replaces prior data only after schema validation. Two HTTP
requests per fetch; no automatic retry. Never falls back to staging data.
"""
import argparse, base64, gzip, hashlib, json, re
from collections import defaultdict
from notam_text import extract
from datetime import datetime, timezone
from pathlib import Path
from faa_client import authenticate, request_json, SafeFailure
from update_airspace import ROOT, risk, normalize, polygon_geometry, position, date, utcnow, write_json

SOURCE='FAA NMS — PRODUCTION / 本番環境'
PREFIXES=['WMR','WMW','WXX']

def reference_tables():
    path=ROOT/'config/airport-countries.json.gz.b64'
    refs=json.loads(gzip.decompress(base64.b64decode(path.read_text())))
    prefixes=defaultdict(set)
    for code,country in refs['icao'].items():prefixes[code[:2]].add(country)
    refs['prefixes']={k:next(iter(v)) for k,v in prefixes.items() if len(v)==1}
    return refs

def country_for(n, refs):
    # Country of the referenced location, not a claim about national airspace.
    for key in ('icaoLocation','location'):
        value=str(n.get(key) or '').upper().strip()
        if value in refs['icao']:
            return refs['icao'][value], '参照地点のICAOコード（OurAirports照合）'
    location=str(n.get('location') or '').upper().strip()
    if str(n.get('classification') or '').upper() in ('DOM','DOMESTIC','FDC','LMIL','LOCAL_MILITARY') and location in refs['faaLocal']:
        return refs['faaLocal'][location], '参照地点のFAAローカルコード（OurAirports照合）'
    for key in ('icaoLocation','location','affectedFir'):
        value=str(n.get(key) or '').upper().strip()
        if re.fullmatch('[A-Z]{4}',value) and value[:2] in refs.get('prefixes',{}):
            return refs['prefixes'][value[:2]], 'ICAO接頭辞から推定（OurAirportsの単一国対応・領域帰属ではありません）'
    if str(n.get('classification') or '').upper() in ('FDC','DOM','DOMESTIC','LMIL','LOCAL_MILITARY'):
        return 'US','FAA国内発行分類（区域の領域帰属ではありません）'
    return 'ZZ','国を確定できる所在地コードなし'

def text(value):
    return '' if value is None else str(value)

def parts(g):
    if not isinstance(g,dict):return []
    if g.get('type')=='GeometryCollection':
        return [p for child in g.get('geometries',[]) for p in parts(child)]
    return [g]

def candidate(feature,refs,now):
    core=feature['properties']['coreNOTAMData'];n=core['notam']
    translations=core.get('notamTranslation') or []
    if not isinstance(translations,list):raise SafeFailure('translation_schema')
    original=text(n.get('text'))
    translated='\n\n'.join(text(t.get('formattedText') or t.get('simpleText')) for t in translations if isinstance(t,dict))
    qmatch=re.search(r'(?:^|\n)\s*Q\)\s*([^\r\n]+)',translated)
    qline=qmatch.group(1).strip() if qmatch else ''
    kind,q,reasons=risk({'qcode':n.get('selectionCode'),'text':original+'\n'+translated,'qline':qline},PREFIXES)
    if not kind:return None,'nonrisk'
    country,basis=country_for(n,refs)
    identifier=text(n.get('id'))
    if not identifier:raise SafeFailure('missing_notam_id')
    record={'id':identifier,'name':text(n.get('number') or identifier)+' / '+text(n.get('icaoLocation') or n.get('location')),
        'type':kind,'qcode':q,'qline':qline,'text':original+ ('\n\n'+translated if translated else ''),
        'notamType':n.get('type'),'validFrom':n.get('effectiveStart'),'validTo':n.get('effectiveEnd'),
        'lower':n.get('lowerLimit') or n.get('minimumFl'),'upper':n.get('upperLimit') or n.get('maximumFl'),'schedule':n.get('schedule')}
    timing_error=False
    for field in ('validFrom','validTo'):
        value=record[field]
        if value and value!='PERM':
            try:date(value)
            except (ValueError,TypeError):record[field]=None;timing_error=True
    if record['validFrom'] and record['validTo'] and record['validTo']!='PERM' and date(record['validTo'])<date(record['validFrom']):
        record['validFrom']=None;record['validTo']=None;timing_error=True
    cancel=n.get('cancelationDate')
    if n.get('type')=='C':return None,'inactive'
    if cancel:
        try:
            if date(cancel) and date(cancel)<=now:return None,'inactive'
        except (ValueError,TypeError):timing_error=True
    polygons=[];points=[];invalid=False
    for p in parts(feature.get('geometry')):
        if p.get('type') in ('Polygon','MultiPolygon'):
            try:
                g=polygon_geometry(p)
                polygons.extend([g['coordinates']] if g['type']=='Polygon' else g['coordinates'])
            except (ValueError,KeyError,TypeError):invalid=True
        elif p.get('type')=='Point':
            try:points.append(position(p['coordinates']))
            except (ValueError,KeyError,TypeError):invalid=True
        else:invalid=True
    if polygons and not invalid:
        record['geometry']={'type':'MultiPolygon','coordinates':polygons}
    text_geometry,text_warning=extract(original)
    if not text_geometry and not text_warning:text_geometry,text_warning=extract(translated)
    parsed_text=False
    if not record.get('geometry') and text_geometry:
        record.update(text_geometry);parsed_text=True
    result,missing=normalize(record,country,SOURCE,PREFIXES,now)
    if result is None and missing is None:return None,'inactive'
    props=result['properties'] if result else missing
    if parsed_text:props['accuracy']='text-boundary' if 'geometry' in text_geometry else 'text-circle'
    if text_warning:props['textGeometryWarning']=text_warning
    props.update(environment='production',countryBasis=basis,matches=reasons,
        location=text(n.get('location')),icaoLocation=text(n.get('icaoLocation')),classification=text(n.get('classification')),
        issued=text(n.get('issued')),lastUpdated=text(n.get('lastUpdated')),originalText=original,
        qline=qline,referencePoints=points,reportedCoordinates=text(n.get('coordinates')),
        reportedRadius=text(n.get('radius')),reportedRadiusUnit='not specified in provided schema',
        reportedValidFrom=text(n.get('effectiveStart')),reportedValidTo=text(n.get('effectiveEnd')))
    # Point geometry does not establish an area or a radius. Draw a pixel marker only.
    if not result and points:
        props.pop('unplottedReason',None)
        props.update(accuracy='reference-point',geometryNote='提供元の参照位置。危険区域の境界・半径を示しません。')
        result={'type':'Feature','id':country+':'+identifier,'geometry':{'type':'MultiPoint','coordinates':points},'properties':props}
    if invalid:props['geometryWarning']='未対応または不正な形状を含む。描画した位置・概略円は完全な境界ではありません。'
    if timing_error:props['timeStatus']='invalid-time';props['timeWarning']='時刻の一部を解釈できません。原文を確認してください。'
    if not result:result={'type':'Feature','id':country+':'+identifier,'geometry':None,'properties':props}
    return result,'candidate'

def build(payload,refs,now):
    if not isinstance(payload,dict) or str(payload.get('status','')).lower()!='success' or payload.get('errors'):
        raise SafeFailure('notam_response_failure')
    data=payload.get('data')
    if not isinstance(data,dict) or not isinstance(data.get('geojson'),list):raise SafeFailure('geojson_schema')
    if data.get('url'):raise SafeFailure('unexpected_pagination_or_content_url')
    groups=defaultdict(list);seen=set();stats={'received':len(data['geojson']),'riskCandidates':0,'retained':0,'excludedInactive':0,'plotted':0,'unplotted':0,'referencePoints':0,'approximateCircles':0}
    for f in data['geojson']:
        if not isinstance(f,dict) or not isinstance(f.get('properties'),dict) or not isinstance(f['properties'].get('coreNOTAMData'),dict) or not isinstance(f['properties']['coreNOTAMData'].get('notam'),dict):raise SafeFailure('notam_schema')
        item,status=candidate(f,refs,now)
        if status=='nonrisk':continue
        stats['riskCandidates']+=1
        if status=='inactive':stats['excludedInactive']+=1;continue
        if item['id'] in seen:continue
        seen.add(item['id']);groups[item['properties']['country']].append(item);stats['retained']+=1
        stats['plotted' if item['geometry'] else 'unplotted']+=1
        stats['referencePoints']+=int(item['properties'].get('accuracy')=='reference-point')
        stats['approximateCircles']+=int(item['properties'].get('accuracy')=='qline-envelope')
    return groups,stats

def publish(output, fetch=True):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);stamp=utcnow()
    index_path=output/'index.json'
    old=json.loads(index_path.read_text()) if index_path.exists() else {}
    # Never repeat a data pull within 30 minutes. A failed authentication made no
    # data request; allow an operator rerun after credential replacement, with a
    # three-minute floor. The normal schedule remains every 30 minutes.
    if old.get('environment')=='production' and old.get('lastAttempt'):
        elapsed=(date(stamp)-date(old['lastAttempt'])).total_seconds()
        auth_rejected=old.get('failurePhase')=='authentication' and old.get('error') in ('http_401','http_403') and old.get('status')=='error'
        minimum_interval=180 if auth_rejected else 1800
        if 0<=elapsed<minimum_interval:
            print('FAA_PRODUCTION_COOLDOWN: reused prior snapshot; no HTTP request')
            return int(old.get('status')=='error')
    catalog={c['code']:c for c in json.loads((ROOT/'web/countries.json').read_text())['countries']}
    catalog['ZZ']={'code':'ZZ','name':'国未特定','region':'Other','center':[0,0]}
    phase="authentication"
    try:
        token=authenticate()
        phase="notams"
        payload=request_json('/nmsapi/v1/notams?feature=AIRSPACE',{'Authorization':'Bearer '+token,'nmsResponseFormat':'GEOJSON','Accept':'application/json'})
        del token
        phase="validation"
        groups,stats=build(payload,reference_tables(),date(stamp))
        # Reuse country slots from previous snapshots so removals become explicit empty feeds.
        codes=set(groups)|{c['code'] for c in old.get('countries',[]) if c.get('code') in catalog}
        generation=hashlib.sha256((stamp+json.dumps(stats)).encode()).hexdigest()[:20]
        index={'schemaVersion':1,'demo':False,'environment':'production','source':SOURCE,'status':'ok',
            'generatedAt':stamp,'lastAttempt':stamp,'lastSuccess':stamp,'generation':generation,
            'scope':'FAA production / feature=AIRSPACE; country coverage is not guaranteed',
            'stats':stats,'countries':[]}
        if not codes.issubset(catalog):raise SafeFailure('unknown_country_code')
        for code in sorted(codes):
            records=sorted(groups.get(code,[]),key=lambda f:f['id'])
            features=[r for r in records if r['geometry']]
            unplotted=[dict(r['properties'],featureId=r['id']) for r in records if not r['geometry']]
            metadata={'country':code,'demo':False,'environment':'production','status':'ok','source':SOURCE,
                'lastAttempt':stamp,'lastSuccess':stamp,'generation':generation}
            content={'type':'FeatureCollection','features':features,'unplotted':unplotted,'metadata':metadata}
            write_json(output/(code+'.json'),content)
            index['countries'].append({'code':code,'name':catalog[code]['name'],'region':catalog[code]['region'],
                'file':code+'.json','count':len(features),'unplotted':len(unplotted),**metadata})
        write_json(index_path,index)
        print('FAA_PRODUCTION_PUBLISHED='+json.dumps(stats,sort_keys=True))
        return 0
    except Exception as error:
        # Error strings/body/headers can contain tokens: emit only controlled categories.
        category=str(error) if isinstance(error,SafeFailure) and re.fullmatch('[a-z0-9_]+',str(error)) else 'validation_or_configuration_error'
        index=old if old.get('environment')=='production' else {'schemaVersion':1,'demo':False,'countries':[],'lastSuccess':None}
        index.update(environment='production',source=SOURCE,status='error',lastAttempt=stamp,generatedAt=stamp,error=category,failurePhase=phase)
        write_json(index_path,index)
        print('FAA_PRODUCTION_FAILED='+category+'; previous snapshot retained')
        return 1

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',default=str(ROOT/'web/production'));parser.add_argument('--report',default='')
    args=parser.parse_args();errors=publish(args.output)
    if args.report:Path(args.report).write_text(str(errors))
