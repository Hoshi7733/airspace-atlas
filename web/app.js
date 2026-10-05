/* ALTA SYSTEM: multi-country selection, independent region browsing, local PDF export. */
'use strict';
const $=s=>document.querySelector(s);
const params=new URLSearchParams(location.search),demoMode=params.get('demo')==='1',dataRoot=demoMode?'demo/':'production/';
const regions={Asia:'アジア',Americas:'南北アメリカ',Europe:'ヨーロッパ',Oceania:'オセアニア',Africa:'アフリカ',Antarctic:'南極',Other:'国未特定'};
let region=params.get('region')||'all',index=null,catalog=[],feeds=new Map(),visible=[],layers=new Map(),loading=false,failures=[];
let selectedCountries=new Set((params.get('countries')??params.get('country')??(demoMode?'JP,KR,US,GB,AU':'')).toUpperCase().split(',').filter(c=>/^[A-Z]{2}$/.test(c)));
const selectedAlerts=new Set();
let reportURL=null,pdfBusy=false,initialCountries=!params.has('countries')&&!params.has('country')&&!demoMode;
const node=(tag,text,cls)=>{const n=document.createElement(tag);if(text!=null)n.textContent=text;if(cls)n.className=cls;return n};
const time=v=>v?new Date(v).toLocaleString('ja-JP',{timeZone:'UTC'})+' UTC':'未取得';
const accuracy={'provider-boundary':'提供元の境界','provider-circle':'提供元の円','qline-envelope':'Q行の概略円（正確な境界ではありません）','text-boundary':'本文の直線境界から抽出','text-circle':'本文の中心・半径から抽出','reference-point':'参照点のみ・危険区域の境界や半径は不明'};
const expired=p=>p.validTo&&p.validTo!=='PERM'&&Date.parse(p.validTo)<=Date.now();
const countryName=c=>catalog.find(x=>x.code===c)?.name||c;
const map=typeof L!=='undefined'?L.map('map',{worldCopyJump:false,zoomControl:false}).setView([28,125],3):null;
let group=null;
if(map){L.control.zoom({position:'bottomright'}).addTo(map);L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png',{maxZoom:18,attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}).addTo(map);group=L.featureGroup().addTo(map);}
$('#mode-link').href=demoMode?'./':'?demo=1';$('#mode-link').textContent=demoMode?'FAA本番データへ':'架空デモを見る';
function syncURL(){const p=new URLSearchParams(location.search);p.delete('country');p.set('countries',[...selectedCountries].sort().join(','));region==='all'?p.delete('region'):p.set('region',region);history.replaceState(null,'',location.pathname+'?'+p.toString());}
function allFeatures(){const m=new Map();for(const data of feeds.values()){
 for(const f of data.features||[])if(!expired(f.properties))m.set(f.id,f);
 for(const p of data.unplotted||[])if(!expired(p)){const id=p.featureId||p.country+':'+p.id;m.set(id,{type:'Feature',id,geometry:null,properties:p});}
}return m;}
function reportSelection(){const all=allFeatures();return [...selectedAlerts].map(id=>all.get(id)).filter(Boolean);}
function pruneSelection(){const all=allFeatures();for(const id of selectedAlerts)if(!all.has(id))selectedAlerts.delete(id);}
function updateReportUI(){const selected=reportSelection();$('#pdf-button').disabled=pdfBusy||!selected.length;$('#pdf-count').textContent=`選択 ${selected.length}件（表示条件に隠れた選択も含む）`;document.querySelectorAll('[data-alert-id]').forEach(n=>n.checked=selectedAlerts.has(n.dataset.alertId));for(const [id,l] of layers)l.setStyle({color:selectedAlerts.has(id)?'#f59e0b':'#ef4444',weight:selectedAlerts.has(id)?4:2});}
function toggleAlert(id,checked){checked?selectedAlerts.add(id):selectedAlerts.delete(id);updateReportUI();}
function alertCheck(f){const label=node('label',null,'report-check');const c=node('input');c.type='checkbox';c.dataset.alertId=f.id;c.checked=selectedAlerts.has(f.id);c.setAttribute('aria-label',f.properties.name+'をPDFに選択');c.onchange=()=>toggleAlert(f.id,c.checked);label.append(c,node('span','PDFに選択'));return label;}
function details(f){const p=f.properties,el=node('article',null,'popup');el.append(node('small',p.type+' / '+countryName(p.country)),node('h3',p.name),alertCheck(f));const dl=node('dl');for(const [k,v] of [['識別子',p.id],['Qコード',p.qcode||'未提供'],['区域情報',accuracy[p.accuracy]||'未描画'],['国の分類根拠',p.countryBasis||'デモ'],['所在地コード',p.icaoLocation||p.location||'未提供'],['形状の注意',[p.geometryWarning,p.geometryNote,p.textGeometryWarning].filter(Boolean).join(' / ')||'—'],['時刻の注意',p.timeWarning||'—'],['高度',`${p.lower??'未提供'} — ${p.upper??'未提供'}`],['開始',p.validFrom||'未提供'],['終了',p.validTo||'未提供'],['時間条件',p.schedule||p.timeStatus],['出典',p.source]])dl.append(node('dt',k),node('dd',v));el.append(dl,node('p',p.text||''));return el;}
function positions(g){if(g.type==='Point')return [g.coordinates];if(g.type==='MultiPoint')return g.coordinates;return g.type==='Polygon'?g.coordinates.flat():g.coordinates.flat(2);}
// The largest empty longitude gap places JP + US around the Pacific, avoiding an unnecessary world-wide view.
function longitudeAnchor(fs){const xs=fs.flatMap(f=>positions(f.geometry).map(p=>(p[0]+360)%360)).sort((a,b)=>a-b);if(!xs.length)return 0;let gap=-1,start=xs[0];for(let i=0;i<xs.length;i++){const next=i+1<xs.length?xs[i+1]:xs[0]+360;if(next-xs[i]>gap){gap=next-xs[i];start=next%360;}}return start;}
function shiftedGeometry(g,anchor){const pts=positions(g),center=pts.reduce((s,p)=>s+p[0],0)/pts.length;let target=(center+360)%360;if(target<anchor)target+=360;const offset=360*Math.round((target-center)/360);const shift=p=>[p[0]+offset,p[1]];return {type:g.type,coordinates:g.type==='Point'?shift(g.coordinates):g.type==='MultiPoint'?g.coordinates.map(shift):g.type==='Polygon'?g.coordinates.map(r=>r.map(shift)):g.coordinates.map(poly=>poly.map(r=>r.map(shift)))};}
function draw(f,anchor){const p=f.properties,g=shiftedGeometry(f.geometry,anchor),selected=selectedAlerts.has(f.id);const style={color:selected?'#f59e0b':'#ef4444',weight:selected?4:2,fillColor:'#ef4444',fillOpacity:.14,dashArray:p.accuracy==='qline-envelope'?'6 5':undefined};let l;if(g.type==='Point'){if(!Number.isFinite(p.radius_m)||p.radius_m<=0)return;const [lon,lat]=g.coordinates;l=L.circle([lat,lon],{...style,radius:p.radius_m});}else l=L.geoJSON({...f,geometry:g},{style,pointToLayer:(_,latlng)=>L.circleMarker(latlng,{...style,radius:6,fillOpacity:.5,dashArray:'2 3'})});l.bindPopup(()=>details(f),{maxWidth:340});l.on('click',()=>toggleAlert(f.id,!selectedAlerts.has(f.id)));group.addLayer(l);layers.set(f.id,l);return l;}
function fitVisible(){if(!map)return;if(group.getLayers().length){map.fitBounds(group.getBounds(),{padding:[50,50],maxZoom:8,animate:false});}else{const chosen=catalog.filter(c=>selectedCountries.has(c.code));if(chosen.length===1)map.setView(chosen[0].center,4,{animate:false});else if(chosen.length){const a=longitudeAnchor(chosen.map(c=>({geometry:{type:'Point',coordinates:[c.center[1],c.center[0]]}})));map.fitBounds(chosen.map(c=>{let lon=(c.center[1]+360)%360;if(lon<a)lon+=360;return [c.center[0],lon]}),{padding:[50,50],maxZoom:5,animate:false});}else map.setView([25,20],2);}}
function jumpCountry(code){if(!map)return;const ls=visible.filter(f=>f.properties.country===code).map(f=>layers.get(f.id)).filter(Boolean);if(ls.length)map.fitBounds(L.featureGroup(ls).getBounds(),{padding:[45,45],maxZoom:8,animate:false});else{const c=catalog.find(c=>c.code===code);if(c)map.setView(c.center,4,{animate:false});}}
function countryStatus(code){const c=index?.countries.find(c=>c.code===code);if(!c)return demoMode?'デモなし':'今回の取得範囲にデータなし';const m=feeds.get(code)?.metadata;if(failures.includes(code))return '再読込失敗';if(m?.status==='unconfigured')return 'API未接続';return demoMode?'架空デモ':(index?.status==='error'||m?.status==='error')?'取得失敗':m?.lastSuccess?`${c.count+c.unplotted}件`:'未取得';}
function updateChoices(){const query=$('#country-search').value.trim().toLowerCase();const list=catalog.filter(c=>(region==='all'||c.region===region)&&(!query||`${c.name} ${c.english} ${c.code}`.toLowerCase().includes(query)));const groups=[];for(const [r,title]of Object.entries(regions)){const members=list.filter(c=>c.region===r);if(!members.length)continue;const section=node('section',null,'country-region');section.append(node('h3',title));for(const c of members){const row=node('div',null,'country-row'),check=node('input'),jump=node('button',c.name+' / '+c.code);check.type='checkbox';check.checked=selectedCountries.has(c.code);check.setAttribute('aria-label',c.name+'を表示');check.onchange=()=>{check.checked?selectedCountries.add(c.code):selectedCountries.delete(c.code);syncURL();render(true);updateChoices();};jump.type='button';jump.title='地図を'+c.name+'へ移動';jump.setAttribute('aria-label',c.name+'へ移動');jump.onclick=()=>jumpCountry(c.code);row.append(check,jump,node('small',countryStatus(c.code)));section.append(row);}groups.push(section);}$('#country-list').replaceChildren(...groups);$('#country-count').textContent=`選択 ${selectedCountries.size} / 250 国・地域＋国未特定`;document.querySelectorAll('#tabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.region===region)));}
function render(fit=false){group?.clearLayers();layers.clear();visible=[];const rows=[],missing=[];const kinds=new Set([...document.querySelectorAll('[data-kind]:checked')].map(x=>x.dataset.kind));const query=$('#search').value.trim().toLowerCase();const chosen=catalog.filter(c=>selectedCountries.has(c.code));const matches=p=>!expired(p)&&($('#include-future').checked||!p.validFrom||Date.parse(p.validFrom)<=Date.now())&&kinds.has(p.type)&&(!query||`${p.id} ${p.name} ${p.text} ${p.qcode}`.toLowerCase().includes(query));for(const c of chosen){const data=feeds.get(c.code);if(!data)continue;for(const f of data.features){const p=f.properties;if(!matches(p)||(!$('#approx').checked&&p.accuracy==='qline-envelope'))continue;visible.push(f);}for(const p of data.unplotted||[])if(matches(p)){const f={type:'Feature',id:p.featureId||p.country+':'+p.id,geometry:null,properties:p};const el=node('details',null,'unplotted-item');el.append(node('summary',`${c.code} / ${p.name} — 範囲・位置を描画できません`),details(f));missing.push(el);}}const anchor=longitudeAnchor(visible);for(const f of visible){const p=f.properties,l=map?draw(f,anchor):null,row=node('div',null,'area');const b=node('button',null,'area-detail');b.append(node('span',p.country+' / '+p.type,'area-type'),node('strong',p.name),node('small',p.id+(p.timeStatus==='future'?' · 開始前':'')+(p.accuracy==='qline-envelope'?' · 概略円':p.accuracy==='reference-point'?' · 参照点／範囲不明':'')));b.onclick=()=>{if(l){map.fitBounds(l.getBounds(),{padding:[45,45],maxZoom:8,animate:false});l.openPopup();}};row.append(b,alertCheck(f));rows.push(row);}$('#count').textContent=String(visible.length).padStart(2,'0');$('#areas').replaceChildren(...(rows.length?rows:[node('p','表示対象はありません。未描画の警報・取得範囲・選択条件もご確認ください。','empty')]));$('#unplotted-count').textContent=`未描画の警報 ${missing.length}件`;$('#unplotted-list').replaceChildren(...missing);$('#map-title').textContent=chosen.length===1?chosen[0].name+'の航空警報':`${chosen.length} 国・地域の航空警報`;
const stale=index.status==='error'||failures.length>0||(!demoMode&&(!index.lastSuccess||Date.now()-Date.parse(index.lastSuccess)>3600000));
const note=[];if(demoMode)note.push('DEMO：すべて架空');else note.push(index.lastSuccess?'FAA本番環境・定期取得':'FAA本番環境・取得未完了');
if(!demoMode&&index.status==='error')note.push(index.error==='http_401'||index.error==='http_403'?'本番の認証・アクセス権を確認してください':`取得エラー：${index.error||'unknown'}`);
if(!demoMode&&index.coverage&&!index.coverageComplete)note.push('初回取得の一部が未完了');
if(index.coverageGap)note.push('同期の空白期間あり・再取得待ち');
if(stale)note.push(index.lastSuccess?'取得失敗または古いデータ：前回の成功分を表示':'本番データは未取得です');
if(!selectedCountries.size)note.push('対象国をチェックしてください');if(!map)note.push('地図ライブラリの読込失敗');
$('#notice').textContent=note.join(' / ');$('#notice').classList.toggle('warning',Boolean(stale));
$('#mode').textContent=demoMode?'DEMO DATA':index.lastSuccess?'FAA PRODUCTION':'FAA PRODUCTION / 未取得';
$('#updated').textContent=demoMode?'架空データ・API未使用':'FAA取得成功：'+time(index.lastSuccess);
const st=index.stats;$('#feed-summary').textContent=demoMode?'架空データの操作デモ':st?`今回受信 ${st.received}件 / 保存中の対象警報 ${st.retained}件 / 本文形状 ${st.textShapes||0}件 / ${index.countries.filter(c=>c.count+c.unplotted>0).length}国・地域に分類。FAA配信範囲内。`:'本番データはまだ取得できていません。取得状態をご確認ください。';
pruneSelection();updateReportUI();if(fit)fitVisible();}
async function json(url){const r=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(25000)});if(!r.ok)throw Error('HTTP '+r.status);return r.json();}
async function refresh(first=false){
 if(loading)return;loading=true;$('#refresh').disabled=true;
 try{
  const [next,countries]=await Promise.all([json(dataRoot+'index.json'),catalog.length?Promise.resolve(null):json('countries.json')]);
  if(next.schemaVersion!==1||!Array.isArray(next.countries)||(!demoMode&&next.environment!=='production'))throw Error('schema');
  if(countries)catalog=[...countries.countries,{code:'ZZ',name:'国未特定',english:'Unassigned',region:'Other',center:[0,0]}].sort((a,b)=>a.name.localeCompare(b.name,'ja'));
  const nextFeeds=new Map();failures=[];
  for(let i=0;i<next.countries.length;i+=8){await Promise.all(next.countries.slice(i,i+8).map(async c=>{
   try{
    if(!/^[A-Z]{2}$/.test(c.code)||c.file!==c.code+'.json')throw Error('path');
    const data=await json(dataRoot+c.file+(next.generation?'?v='+encodeURIComponent(next.generation):''));
    if(!Array.isArray(data.features)||!Array.isArray(data.unplotted)||data.metadata.country!==c.code||data.metadata.demo!==next.demo||(!demoMode&&(data.metadata.environment!=='production'||data.metadata.generation!==next.generation)))throw Error('snapshot');
    nextFeeds.set(c.code,data);
   }catch{failures.push(c.code);}
  }));}
  // Commit all feeds together: a partial network failure must not mix snapshot generations.
  if(failures.length){$('#notice').textContent='国別JSONの同期失敗。前回の表示を保持しています。';return 'partial';}
  index=next;feeds=nextFeeds;
  if(initialCountries){selectedCountries=new Set(next.countries.filter(c=>c.count+c.unplotted>0).map(c=>c.code));initialCountries=false;}
  selectedCountries=new Set([...selectedCountries].filter(c=>catalog.some(x=>x.code===c)));
  updateChoices();syncURL();render(first);return 'success';
 }catch{$('#notice').textContent='一覧の同期失敗。前回の表示を保持しています。';throw Error('JSON synchronization failed');}
 finally{loading=false;$('#refresh').disabled=false;}
}
$('#tabs').onclick=e=>{const b=e.target.closest('[data-region]');if(!b)return;region=b.dataset.region;for(const c of catalog)if(region==='all'||c.region===region)selectedCountries.add(c.code);updateChoices();syncURL();if(index)render(true);};$('#country-search').oninput=updateChoices;
$('#countries-clear').onclick=()=>{selectedCountries.clear();syncURL();updateChoices();render(true);};$('#countries-all').onclick=()=>{const q=$('#country-search').value.trim().toLowerCase();for(const c of catalog)if((region==='all'||c.region===region)&&(!q||`${c.name} ${c.english} ${c.code}`.toLowerCase().includes(q)))selectedCountries.add(c.code);syncURL();updateChoices();render(true);};
$('#search').oninput=()=>render();document.querySelectorAll('[data-kind],#approx,#include-future').forEach(el=>el.onchange=()=>render());$('#refresh').onclick=()=>refresher.manual();$('#fit').onclick=fitVisible;$('#pdf-clear').onclick=()=>{selectedAlerts.clear();updateReportUI();};
$('#pdf-button').onclick=async()=>{const button=$('#pdf-button');pdfBusy=true;button.disabled=true;$('#pdf-status').textContent='PDFを作成中…';try{const records=structuredClone(reportSelection());if(!records.length)throw Error('警報を選択してください。');const result=await AltaReport.download(records,{demo:demoMode,staging:false,countryName,feeds});if(reportURL)URL.revokeObjectURL(reportURL);reportURL=URL.createObjectURL(result.blob);const save=node('a','PDFを保存');save.href=reportURL;save.download=result.filename;save.className='pdf-save';$('#pdf-status').replaceChildren(node('span',`${records.length}件のPDFを作成しました。自動保存が始まらない場合はこちら： `),save);save.click();}catch(e){$('#pdf-status').textContent='PDF作成失敗：'+e.message;}finally{pdfBusy=false;updateReportUI();}};
if(region!=='all'&&!regions[region])region='all';
let firstRefresh=true;
const refresher=new AltaRefreshController({load:async()=>{const result=await refresh(firstRefresh);firstRefresh=false;return result;},onState:s=>{
 const stamp=v=>v==null?'未同期':new Date(v).toLocaleTimeString('ja-JP',{hour12:false,hour:'2-digit',minute:'2-digit',second:'2-digit'});
 $('#sync-time').textContent=stamp(s.lastSuccess);
 const seconds=Math.ceil(s.remaining/1000);$('#sync-countdown').textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}分${String(seconds%60).padStart(2,'0')}秒`;
 $('#sync-result').textContent=({idle:'待機中',loading:'公開JSONを同期中…',success:'同期成功',partial:'一部の同期に失敗・前回データを保持',error:'通信失敗・前回の表示を保持'})[s.status];
 $('#sync-panel').dataset.state=s.status;
 $('#sync-attempt').textContent=s.lastAttempt==null?'—':stamp(s.lastAttempt);
 $('#refresh').disabled=s.busy;
}});
refresher.start();
setInterval(()=>{if(index&&!loading)render();},60000);
// Background tabs and sleeping devices may throttle timers. Catch up once when overdue.
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresher.due();});
window.addEventListener('online',()=>refresher.due());
