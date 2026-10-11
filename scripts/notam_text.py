"""Conservative explicit NOTAM text geometry; ambiguous arcs are never joined."""
import re
from update_airspace import polygon_geometry, position

PAIR = re.compile(r'(?<![\d.])(\d{4}(?:\d{2})?(?:\.\d+)?)([NS])\s*[, /]?\s*(\d{5}(?:\d{2})?(?:\.\d+)?)([EW])(?![A-Z\d])')

def angle(raw, hemisphere, degrees):
    whole=raw.split('.')[0]
    if len(whole) not in (degrees+2,degrees+4):raise ValueError('coordinate format')
    d=int(raw[:degrees]); tail=raw[degrees:]
    if len(whole)==degrees+2:minutes=float(tail);seconds=0
    else:minutes=int(tail[:2]);seconds=float(tail[2:])
    if minutes>=60 or seconds>=60:raise ValueError('coordinate range')
    return (d+minutes/60+seconds/3600)*(-1 if hemisphere in 'SW' else 1)

def coord(match):
    a,b,c,d=match.groups()
    return position([angle(c,d,3),angle(a,b,2)])

def extract(value):
    text=re.sub(r'\s+',' ',str(value).upper())
    # Restrict interpretation to E) when a full ICAO message is supplied.
    section=re.search(r'(?:^|\s)E\)\s*',text)
    if section:text=re.split(r'\s+F\)',text[section.end():],maxsplit=1)[0]
    # Normalize explicit hemisphere-qualified degrees/minutes/seconds only.
    def packed(m):
        d,mi,se,h=m.groups();width=2 if h in 'NS' else 3
        return d.zfill(width)+mi.zfill(2)+(se.zfill(2) if se else '')+h
    text=re.sub(r"(?<![\d.])(\d{1,3})[°:\- ](\d{2}(?:\.\d+)?)(?:[':\- ](\d{2}(?:\.\d+)?))?[\"' ]*([NSEW])\b",packed,text)
    text=re.sub(r'\b([NS])\s*(\d{4}(?:\d{2})?(?:\.\d+)?)\s*([EW])\s*(\d{5}(?:\d{2})?(?:\.\d+)?)\b',lambda m:m[2]+m[1]+' '+m[4]+m[3],text)
    # Numbered AIRSPACE boundaries and lettered maritime areas are separate polygons.
    parts=re.split(r'\(\d+\)\s*AIRSPACE\s*:',text)
    if len(parts)>2:
        shapes=[extract(b.split('RMK:',1)[0]) for b in parts[1:]]
        if all(shape and 'geometry' in shape for shape,w in shapes):
            return {'geometry':{'type':'MultiPolygon','coordinates':[shape['geometry']['coordinates'] for shape,w in shapes]}},None
        return None,'複数空域の一部の境界を確定できません。'
    if re.search(r'\bAREAS? BOUND(?:ED)? BY\s*:',text):
        parts=re.split(r'\b[A-Z]\.\s*(?=\d{4,6}(?:\.\d+)?[NS])',text)
        if len(parts)>2:
            shapes=[extract('AREA BOUNDED BY '+b) for b in parts[1:]]
            if all(shape and 'geometry' in shape for shape,w in shapes):
                return {'geometry':{'type':'MultiPolygon','coordinates':[shape['geometry']['coordinates'] for shape,w in shapes]}},None
            return None,'複数海域の一部の境界を確定できません。'
    # Explicit AREA 1/AREA 2 chains stay separate. Never bridge disjoint zones.
    blocks=re.split(r'\b(?:AREA|ZONE)\s+[A-Z0-9]+\s*[:.)]\s*',text)
    if len(blocks)>2:
        shapes=[extract('AREA BOUNDED BY '+b) for b in blocks[1:]]
        if all(s and 'geometry' in s for s,w in shapes):
            return {'geometry':{'type':'MultiPolygon','coordinates':[s['geometry']['coordinates'] for s,w in shapes]}},None
        return None,'複数区域の一部を確定できません。原文を確認してください。'
    matches=list(PAIR.finditer(text))
    if not matches:return None,None
    try:points=[coord(m) for m in matches]
    except ValueError:return None,'本文の座標形式・値を解釈できません。'
    complex_path=re.search(r'\b(ARC|SECTOR|FAN[ -]?SHAPED|SEMICIRCLE|SEMI[ -]CIRCLE|CLOCKWISE|ANTICLOCKWISE|COUNTERCLOCKWISE|BORDER|COASTLINE|ALONG|EXCLUDING|EXCEPT)\b|\b\d{1,3}\s*(?:DEG|DEGREES)\b',text)
    if complex_path:return None,'円弧・沿岸・除外区域等を含む本文は自動で境界を確定しません。'
    # One unambiguous centre and one radius with an explicit unit.
    radius=re.search(r'\b(?:WI|WITHIN)\s+(\d+(?:\.\d+)?)\s*(NM|N M|KM|METERS?|M)\s+(?:RADIUS\s+)?(?:OF|CENT(?:ER|RE)(?:D)?\s+(?:ON|AT))\s*',text)
    if not radius:radius=re.search(r'\b(?:RADIUS\s+(?:OF\s+)?)(\d+(?:\.\d+)?)\s*(NM|N M|KM|METERS?|M)\b',text)
    if not radius:radius=re.search(r'\b(\d+(?:\.\d+)?)\s*(NM|N M|KM|METERS?|M)\s+RADIUS\s+(?:OF|CENT(?:ER|RE)(?:D)?\s+(?:ON|AT))',text)
    if radius and len(points)==1 and 0<float(radius[1])<=1000:
        unit=radius[2].replace(' ','');unit='M' if unit.startswith('METER') else unit
        return {'circle':{'center':points[0],'radius':float(radius[1]),'unit':unit}},None
    # Only a stated, straight-line boundary with a contiguous coordinate chain.
    bounded=re.search(r'\b(?:BOUNDED BY|BOUND BY|BOUNDARY DEFINED BY|AREA DEFINED BY|AREA DEFINED AS|WI AREA|WITHIN AREA|JOINING THE POINTS|FLW COORD|FOLLOWING COORDINATES)\b',text)
    if bounded and len(points)>=3:
        if any(not re.fullmatch(r'[\s,;:/\-]*(?:(?:TO|AND|PSN)\s*)?',text[a.end():b.start()]) for a,b in zip(matches,matches[1:])):
            return None,'複数の区域または接続が不明な座標列です。'
        if points[-1]!=points[0]:points.append(points[0])
        try:
            g=polygon_geometry({'type':'Polygon','coordinates':[points]})
            if abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:])))<1e-12:raise ValueError('zero area')
            # Reject self-crossings instead of creating a misleading boundary.
            def cross(a,b,c):return (b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            edges=list(zip(points,points[1:]))
            for i,(a,b) in enumerate(edges):
                for j,(c,d) in enumerate(edges):
                    if j<=i+1 or (i==0 and j==len(edges)-1):continue
                    if cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0:raise ValueError('crossing')
            return {'geometry':g},None
        except ValueError:return None,'本文の座標列から有効な単純ポリゴンを確定できません。'
    return None,'本文に座標はありますが、境界・半径を一意に確定できません。'
