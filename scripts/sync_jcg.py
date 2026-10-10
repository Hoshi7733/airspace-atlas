"""JCG official NAVAREA XI and Japan Navigational Warnings (not FAA).
Read current in-force lists for every year advertised by the official page.
Two concurrent list requests at most; warning bodies use the site's batch form.
A failed source retains its previous complete snapshot and a visible error.
"""
import json,re,time,unicodedata
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request,build_opener
from update_airspace import ROOT,NoRedirect,write_json,utcnow,date,polygon_geometry
from notam_text import extract,angle
from hazard_rules import classify,altitude
BASE='https://www1.kaiho.mlit.go.jp/TUHO/keiho/'
SOURCES={'NAVAREA11':('navarea11.html','JCG NAVAREA XI'),'JAPANNW':('japan_nw.html','JCG 日本航行警報')}
class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[]
    def handle_data(self,data):self.parts.append(data)
    def handle_starttag(self,tag,attrs):
        if tag.lower() in ('br','hr','p','strong'):self.parts.append('\n')
def plain(html):
    parser=Text();parser.feed(html);return re.sub(r'\n\s*\n+','\n',''.join(parser.parts)).strip()
def normalize(text):return unicodedata.normalize('NFKC',text).replace('−','-').replace('–','-')
def geometry(text):
    value=re.sub(r'([NSEW])(?=[^\x00-\x7F])',r'\1 ',normalize(text))
    if re.search(r'扇形|円弧|沿岸|除く|除外',value):return None,'扇形・円弧・沿岸・除外を含むため境界未確定'
    if '各線で囲まれる' in value:
        atoms=re.findall(r'(\d{2,3}-\d{2}(?:-\d{2})?(?:\.\d+)?)([NSEW])',value)
        try:
            lat=[angle(n.replace('-',''),h,2) for n,h in atoms if h in 'NS']
            lon=[angle(n.replace('-',''),h,3) for n,h in atoms if h in 'EW']
            if len(lat)==len(lon)==2 and len(set(lat))==len(set(lon))==2:
                a,b=sorted(lat);c,d=sorted(lon)
                if d-c>=180:raise ValueError('dateline')
                return {'geometry':polygon_geometry({'type':'Polygon','coordinates':[[[c,a],[d,a],[d,b],[c,b],[c,a]]]})},None
        except ValueError:pass
        return None,'緯線・経線の矩形境界を確定できません'
    if re.search(r'で囲まれる(?:海面|区域)',value):value='AREA BOUNDED BY '+value
    # Preserve declared circles; never replace a circle by an invented rectangle.
    value=re.sub(r'半径\s*(\d+(?:\.\d+)?)\s*(海里|キロメートル|メートル)',lambda m:' RADIUS '+m[1]+' '+{'海里':'NM','キロメートル':'KM','メートル':'M'}[m[2]]+' ',value)
    return extract(value)
def listings(raw):
    root=ET.fromstring(raw)
    if root.tag!='opt':raise ValueError('JCG list schema')
    result=[]
    for member in root:
        row={e.tag:e.text or '' for e in member}
        if member.tag!='Member' or not all(k in row for k in ('tana','title','categoly','number')) or not re.fullmatch(r'\d{6}',row['tana']):raise ValueError('JCG row schema')
        result.append(row)
    return result

def bodies(html):
    result={}
    for section in re.split(r'<hr\s*/?>',html,flags=re.I):
        text=plain(section)
        m=re.search(r'(?:NO\.|番号[:：])\s*(\d{2})-(\d{4})',text)
        if not m:continue
        text=text[m.start():]
        result[m[1]+m[2]]=text
    return result

def build(rows,texts,kind,stamp):
    features=[];unplotted=[]
    for row in rows:
        text=texts[row['tana']]
        reasons=classify(normalize(row['title']+' '+text))
        if not reasons and row['categoly']=='訓練試験' and re.search(r'危険な訓練|爆撃|飛しょう体|飛翔体',row['title']):reasons=['JCG-military-training']
        if not reasons:continue
        ident='JCG:'+kind+':'+row['tana'];shape,warning=geometry(text)
        props=dict(id=ident,featureId=ident,name=row['title']+' / '+row['tana'],country='ZZ',countryBasis='海域警報。発行機関の国と海域の帰属を区別',layer='NAVWARN',type='Danger',source=SOURCES[kind][1],authority='Japan Coast Guard',sourceURL=BASE+'cgi/disp_warnings.cgi?'+urlencode(dict(TYPE=kind,TANA=row['tana'],LANG='JP')),text=text,originalText=text,criticalReasons=reasons,altitude=altitude(''),validFrom=None,validTo=None,timeStatus='source-listed-schedule-unparsed',schedule='JCGの現行一覧掲載。実施日・時間帯は原文参照（現在実施中を意味しません）',fetchedAt=stamp)
        g=None
        if shape and 'geometry' in shape:g=shape['geometry'];props['accuracy']='text-boundary'
        elif shape and 'circle' in shape:
            c=shape['circle'];g={'type':'Point','coordinates':c['center']};props.update(accuracy='text-circle',radius_m=c['radius']*{'NM':1852,'KM':1000,'M':1}[c['unit']])
        if g:features.append(dict(type='Feature',id=ident,geometry=g,properties=props))
        else:unplotted.append(dict(props,unplottedReason=warning or '本文から境界を確定できません'))
    return dict(type='FeatureCollection',features=features,unplotted=unplotted,metadata=dict(status='ok',source=SOURCES[kind][1],sourceURL=BASE+SOURCES[kind][0],lastAttempt=stamp,lastSuccess=stamp,retained=len(features)+len(unplotted),plotted=len(features),unplotted=len(unplotted),coverage='海上保安庁の現行一覧に掲載された警報。全世界の網羅ではありません。'))

def fetch(url,form=None):
    time.sleep(.5)
    req=Request(url,data=urlencode(form).encode() if form else None,headers={'User-Agent':'ALTA-SYSTEM-Research/3.0','Accept':'text/html,application/xml','Content-Type':'application/x-www-form-urlencoded; charset=UTF-8'})
    with build_opener(NoRedirect()).open(req,timeout=25) as response:
        raw=response.read(5_000_001)
        if len(raw)>5_000_000:raise ValueError('JCG response size')
    return raw.decode('utf-8-sig')

def sync(kind,path):
    path=Path(path);stamp=utcnow();old=json.loads(path.read_text()) if path.exists() else None
    if old and old['metadata'].get('lastAttempt') and (date(stamp)-date(old['metadata']['lastAttempt'])).total_seconds()<1800:return int(old['metadata']['status']!='ok')
    try:
        page=fetch(BASE+SOURCES[kind][0]);years=sorted(set(re.findall(r'id="yearlylist_(\d{4})"',page)),reverse=True)
        if not 1<=len(years)<=20:raise ValueError('JCG year list')
        def year_rows(year):return listings(fetch(BASE+'cgi//warnings.cgi',dict(YEAR=year,TYPE=kind,LANG='JP')))
        with ThreadPoolExecutor(max_workers=2) as pool:rows=[r for group in pool.map(year_rows,years) for r in group]
        rows=list({r['tana']:r for r in rows}.values())
        chosen=[r for r in rows if r['categoly']=='訓練試験' or classify(normalize(r['title']))]
        texts={}
        for i in range(0,len(chosen),80):
            batch=chosen[i:i+80];texts.update(bodies(fetch(BASE+'cgi/disp_warnings.cgi',dict(TYPE=kind,TANA=':'.join(r['tana'] for r in batch)+':',LANG='JP'))))
        if any(r['tana'] not in texts for r in chosen):raise ValueError('incomplete warning bodies')
        result=build(chosen,texts,kind,stamp);result['metadata'].update(received=len(rows),years=years)
        write_json(path,result);print(kind+'_PUBLISHED='+str(result['metadata']['retained']));return 0
    except Exception as e:
        old=old or dict(type='FeatureCollection',features=[],unplotted=[],metadata={})
        old['metadata'].update(status='error',source=SOURCES[kind][1],sourceURL=BASE+SOURCES[kind][0],lastAttempt=stamp,error='JCG公式一覧・本文の取得検証に失敗。前回分を保持。')
        write_json(path,old);print(kind+'_FAILED='+type(e).__name__);return 1
