/* Plain JavaScript + Leaflet. Relative URLs support /repository-name/ on GitHub Pages. */
'use strict';
const $=s=>document.querySelector(s);
const params=new URLSearchParams(location.search);
const demoMode=params.get('demo')==='1';
const dataRoot=demoMode?'demo/':'data/';
$('#mode-link').href=demoMode?'./':'?demo=1';$('#mode-link').textContent=demoMode?'実データへ':'デモを見る';
const allowed=new Set((params.get('countries')||'').toUpperCase().split(',').filter(c=>/^[A-Z]{2}$/.test(c)));
let region=params.get('region')||'all',country=params.get('country')?.toUpperCase()||'all';
let index=null,feeds=new Map(),visible=[],layers=new Map(),loading=false;
let failures=[];
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n};
const time=v=>v?new Date(v).toLocaleString('ja-JP',{timeZone:'UTC'})+' UTC':'未取得';
const accuracy={'provider-boundary':'提供元の境界','provider-circle':'提供元の円','qline-envelope':'Q行の概略円（正確な境界ではありません）'};
const map=typeof L!=='undefined'?L.map('map',{worldCopyJump:true,zoomControl:false}).setView([28,125],3):null;
let group=null;
if(map){
 L.control.zoom({position:'bottomright'}).addTo(map);
 L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);
 group=L.featureGroup().addTo(map);
}else{$('#notice').textContent='地図ライブラリを取得できません。ネットワーク接続をご確認ください。'}
function syncURL(){const p=new URLSearchParams(location.search);region==='all'?p.delete('region'):p.set('region',region);country==='all'?p.delete('country'):p.set('country',country);history.replaceState(null,'',location.pathname+(p.size?'?'+p.toString():''));}
function countries(){return (index?.countries||[]).filter(c=>(!allowed.size||allowed.has(c.code))&&(region==='all'||region===c.region));}
function updateChoices(){const list=countries();if(!list.some(c=>c.code===country))country='all';$('#country').replaceChildren(new Option('選択した国すべて','all'),...list.map(c=>new Option(c.name+' / '+c.code,c.code)));$('#country').value=country;document.querySelectorAll('#tabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.region===region)));syncURL();}
function details(f){const p=f.properties;const el=node('article',null,'popup');el.append(node('small',p.type+' / '+p.country),node('h3',p.name));const dl=node('dl');for(const [k,v] of [['識別子',p.id],['Qコード',p.qcode||'未提供'],['区域情報',accuracy[p.accuracy]],['高度',`${p.lower||'未提供'} — ${p.upper||'未提供'}`],['開始',p.validFrom||'未提供'],['終了',p.validTo||'未提供'],['時間条件',p.schedule||p.timeStatus],['出典',p.source]]){dl.append(node('dt',k),node('dd',v))}el.append(dl,node('p',p.text||''));return el;}
function draw(f){const p=f.properties;const style={color:'#ef4444',weight:2,fillColor:'#ef4444',fillOpacity:.14,dashArray:p.accuracy==='qline-envelope'?'6 5':undefined};let layer;if(f.geometry.type==='Point'){if(!Number.isFinite(p.radius_m)||p.radius_m<=0)return;const [lon,lat]=f.geometry.coordinates;layer=L.circle([lat,lon],{...style,radius:p.radius_m});}else{layer=L.geoJSON(f,{style});}layer.bindPopup(details(f),{maxWidth:320});group.addLayer(layer);layers.set(f.id,layer);return layer;}
function expired(p){return p.validTo&&p.validTo!=='PERM'&&Date.parse(p.validTo)<=Date.now();}
function render(){
 group?.clearLayers();layers.clear();visible=[];const rows=[];const missing=[];
 const kinds=new Set([...document.querySelectorAll('[data-kind]:checked')].map(x=>x.dataset.kind));const query=$('#search').value.trim().toLowerCase();
 const chosen=countries().filter(c=>country==='all'||country===c.code);
 for(const c of chosen){const data=feeds.get(c.code);if(!data)continue;for(const f of data.features){const p=f.properties;if(expired(p)||!kinds.has(p.type)||(!$('#approx').checked&&p.accuracy==='qline-envelope'))continue;if(query&&!`${p.id} ${p.name} ${p.text} ${p.qcode}`.toLowerCase().includes(query))continue;visible.push(f);const layer=map?draw(f):null;const b=node('button',null,'area');b.append(node('span',c.code+' / '+p.type,'area-type'),node('strong',p.name),node('small',p.id+(p.timeStatus==='future'?' · 開始前':'')+(p.accuracy==='qline-envelope'?' · 概略':'')));b.onclick=()=>{if(layer){map.fitBounds(layer.getBounds(),{padding:[45,45],maxZoom:8});layer.openPopup()}};rows.push(b);}for(const p of data.unplotted||[]){if(!expired(p)&&kinds.has(p.type)&&(!query||`${p.name} ${p.id} ${p.text} ${p.qcode}`.toLowerCase().includes(query)))missing.push(node('p',`${c.code} / ${p.name} — ${p.unplottedReason}`));}}
 $('#count').textContent=String(visible.length).padStart(2,'0');$('#areas').replaceChildren(...(rows.length?rows:[node('p','表示対象はありません。国・レイヤー・検索条件をご確認ください。','empty')]));$('#unplotted-count').textContent=`未描画の警報 ${missing.length}件`;$('#unplotted-list').replaceChildren(...missing);
 $('#map-title').textContent=country==='all'?'世界の航空警報':(chosen[0]?.name||country)+'の航空警報';
 const bad=chosen.filter(c=>{const m=feeds.get(c.code)?.metadata;return !m||m.status==='error'||(!m.demo&&(!m.lastSuccess||Date.now()-Date.parse(m.lastSuccess)>3600000))});
 const note=[];if(index?.demo)note.push('デモ：すべて架空の区域です');const pending=chosen.filter(c=>feeds.get(c.code)?.metadata.status==='unconfigured');if(pending.length)note.push('NOTAM API接続待ち：'+pending.map(c=>c.code).join(', ')+' · 接続設定をご確認ください');if(bad.length&&!pending.length)note.push('未取得・更新失敗・古いデータ：'+bad.map(c=>c.code).join(', '));if(failures.length)note.push('再読込失敗：'+failures.join(', '));if(!map)note.push('地図ライブラリの読み込みに失敗');if(!chosen.length)note.push('この地域には設定された国がありません');
 $('#notice').textContent=note.join(' / ')||'取得済みスナップショットを表示 · 有効化条件は警報詳細を確認';$('#notice').classList.toggle('warning',bad.length>0||failures.length>0);
 $('#mode').textContent=index?.demo?'DEMO DATA':chosen.some(c=>feeds.get(c.code)?.metadata.status==='unconfigured')?'NOTAM 未接続':'NOTAM SNAPSHOT';
 $('#updated').textContent=index?.demo?'デモ・実API未接続':chosen.map(c=>c.code+': '+time(feeds.get(c.code)?.metadata.lastSuccess)).join(' / ');
}
async function json(url){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(25000)});if(!r.ok)throw Error('HTTP '+r.status);return r.json();}
async function refresh(){if(loading)return;loading=true;$('#refresh').disabled=true;$('#refresh').textContent='更新中…';try{const next=await json(dataRoot+'index.json');if(next.schemaVersion!==1||!Array.isArray(next.countries))throw Error('schema');index=next;failures=[];await Promise.all(index.countries.filter(c=>!allowed.size||allowed.has(c.code)).map(async c=>{try{if(!/^[A-Z]{2}$/.test(c.code)||c.file!==c.code+'.json')throw Error('invalid path');const data=await json(dataRoot+c.file);if(data.type!=='FeatureCollection'||!Array.isArray(data.features)||data.metadata.country!==c.code||data.metadata.demo!==index.demo)throw Error('invalid snapshot');feeds.set(c.code,data);}catch{failures.push(c.code);if(feeds.get(c.code)?.metadata.demo!==index.demo)feeds.delete(c.code)}}));updateChoices();render();}catch{$('#notice').textContent='データ一覧の更新に失敗しました。前回の表示を保持しています。';$('#notice').classList.add('warning');}finally{loading=false;$('#refresh').disabled=false;$('#refresh').textContent='↻ 今すぐ再読込';}}
$('#tabs').onclick=e=>{const b=e.target.closest('button[data-region]');if(!b)return;region=b.dataset.region;updateChoices();render()};$('#country').onchange=e=>{country=e.target.value;syncURL();render()};$('#search').oninput=render;document.querySelectorAll('input[type=checkbox]').forEach(el=>el.onchange=render);$('#refresh').onclick=refresh;$('#fit').onclick=()=>{if(group?.getLayers().length)map.fitBounds(group.getBounds(),{padding:[35,35],maxZoom:8});else map?.setView([25,20],2)};
if(![...document.querySelectorAll('#tabs button')].some(b=>b.dataset.region===region))region='all';
refresh();setInterval(refresh,30*60*1000);setInterval(()=>{if(index&&!loading)render()},60*1000);document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
