"""Explainable military/security filter. Generic danger/restricted is insufficient."""
import re

PATTERNS = [
 ('missile/rocket',r'\b(?:MISSILE(?:S)?|ROCKET(?:S)?|SPACE\s+(?:LAUNCH|DEBRIS)|RE[ -]?ENTRY)\b'),
 ('live-fire/weapons',r'\b(?:LIVE[ -]FIR(?:E|ING)|GUNFIRE|GUNNERY|FRNG|FIRING|WEAPONS?\s+(?:EXERCISE|TRAINING|TEST)|BOMBING)\b'),
 ('military-exercise',r'\b(?:MILITARY|NAVAL|ARMED FORCES|DEFEN[CS]E)\b.{0,70}\b(?:EXERCISE|EXER|TRAINING|OPERATIONS?|ACTIVITY)\b'),
 ('security-restriction',r'\b(?:TERRORIS[MT]|ANTI[ -]?TERROR|NATIONAL SECURITY|SECURITY THREAT|HOSTILITIES|ARMED CONFLICT)\b'),
 ('jp-critical',r'ミサイル|ロケット|実弾|射撃|射爆撃|武器訓練|軍事演習|テロ警戒')
]

def classify(text,qcode=''):
    text=re.sub(r'\s+',' ',str(text)).upper()
    q=str(qcode or '').upper().strip();q=q if q.startswith('Q') else 'Q'+q
    # Closed/finished exercises must not create an active hazard.
    if re.fullmatch(r'Q[A-Z]{4}',q) and q[-2:] in ('CN','CD','CC'):return []
    if re.search(r'\b(?:FIRING|EXERCISE|MILITARY ACTIVITY)\s+(?:IS\s+)?(?:CANCELLED|CANCELED|COMPLETED)\b',text):return []
    reasons=[]
    for label,pattern in PATTERNS:
        for m in re.finditer(pattern,text):
            before=text[max(0,m.start()-12):m.start()]
            if re.search(r'\b(?:NO|NOT|WITHOUT)\s+(?:LIVE\s+)?$',before):continue
            reasons.append(label);break
    # ICAO subject WM = missile, gun or rocket firing. WXX alone is not proof.
    if re.fullmatch(r'QWM[A-Z]{2}',q):
        if not reasons and re.search(r'\b(?:RWY|TWY|LIGHT|ILS|VOR|VOLCANIC|WEATHER|THUNDERSTORM)\b',text):return []
        reasons.append('ICAO-WM')
    return sorted(set(reasons))

def altitude(text,lower=None,upper=None,qline=''):
    text=str(text).upper()
    def value(raw):
        if raw is None:return None
        raw=str(raw).strip()
        if raw in ('SFC','GND','GROUND'):return {'label':'SFC / GND','reference':'surface','value':0,'unit':'FT'}
        if raw in ('UNL','UNLIMITED'):return {'label':'UNL','reference':'unlimited'}
        m=re.fullmatch(r'FL\s*(\d{2,3})',raw)
        if m:return {'label':'FL'+m[1],'reference':'pressure','value':int(m[1]),'unit':'FL'}
        m=re.fullmatch(r'(\d+(?:\.\d+)?)\s*(FT|FEET|M)\s*(AMSL|MSL|AGL)?',raw)
        if m:return {'label':raw,'reference':m[3] or 'unspecified','value':float(m[1]),'unit':m[2]}
        return {'label':raw,'reference':'unparsed'}
    f=re.search(r'(?:^|\s)F\)\s*(.+?)(?=\s+G\)|\n|$)',text)
    g=re.search(r'(?:^|\s)G\)\s*([^\n]+)',text)
    lo=value(f[1].strip() if f else lower);hi=value(g[1].strip() if g else upper)
    basis='F/G' if f or g else 'provider'
    fields=qline.split('/')
    if len(fields)>=8:
        if lo is None and re.fullmatch(r'\d{3}',fields[-3]):lo=value('FL'+fields[-3]);basis='Q-line envelope'
        if hi is None and re.fullmatch(r'\d{3}',fields[-2]):hi=value('FL'+fields[-2]);basis='Q-line envelope'
    return {'lower':lo,'upper':hi,'basis':basis,'label':(lo or {}).get('label','未提供')+' — '+(hi or {}).get('label','未提供')}
