/* Pure helpers shared by rendering and regression tests. */
(function(root){
const regions={Asia:{name:'アジア',view:[32,110,3],box:[-12,25,82,180]},MiddleEast:{name:'中東',view:[28,45,4],box:[12,25,43,64]},NorthAmerica:{name:'北米',view:[38,-105,3],box:[5,-180,85,-30]},Europe:{name:'ヨーロッパ',view:[51,17,4],box:[34,-25,72,65]},Oceania:{name:'オセアニア',view:[-23,145,3],box:[-55,110,10,240]},Africa:{name:'アフリカ',view:[2,20,3],box:[-36,-20,38,55]},SouthAmerica:{name:'南米',view:[-20,-62,3],box:[-60,-90,14,-30]}};
const south=new Set('AR BO BR CL CO EC FK GF GY PY PE SR UY VE'.split(' '));
const middleEast=new Set('AE BH CY EG IL IQ IR JO KW LB OM PS QA SA SY TR YE'.split(' '));
function countryRegion(c){if(middleEast.has(c.code))return 'MiddleEast';return c.region==='Americas'?(south.has(c.code)?'SouthAmerica':'NorthAmerica'):c.region;}
function points(g){if(!g)return [];if(g.type==='Point')return [g.coordinates];if(g.type==='MultiPoint')return g.coordinates;return g.type==='Polygon'?g.coordinates.flat():g.coordinates.flat(2);}
function inBox(f,box){const ps=points(f.geometry);if(!ps.length)return false;let [s,w,n,e]=box;const radius=(f.properties.radius_m||0)/111000;return [-360,0,360].some(shift=>{const xs=ps.map(p=>p[0]+shift),ys=ps.map(p=>p[1]);const lat=(Math.min(...ys)+Math.max(...ys))/2;const lonRadius=radius/Math.max(.05,Math.cos(lat*Math.PI/180));return Math.max(...xs)+lonRadius>=w&&Math.min(...xs)-lonRadius<=e&&Math.max(...ys)+radius>=s&&Math.min(...ys)-radius<=n;});}
function coordinate(lat,lon){if(String(lat).trim()===''||String(lon).trim()==='')throw Error('緯度と経度を入力してください');const a=Number(lat),b=Number(lon);if(!Number.isFinite(a)||!Number.isFinite(b)||Math.abs(a)>90||Math.abs(b)>180)throw Error('緯度 −90〜90、経度 −180〜180で入力してください');return [a,b];}
function coordinateText(value){
 const text=String(value).trim().toUpperCase();
 const decimal=text.match(/^([+-]?\d+(?:\.\d+)?)\s*[, ]\s*([+-]?\d+(?:\.\d+)?)$/);
 if(decimal)return coordinate(decimal[1],decimal[2]);
 const m=text.match(/^(\d+(?:\.\d+)?)\s*([NS])\s*[, /]?\s*(\d+(?:\.\d+)?)\s*([EW])$/);
 if(!m)throw Error('例：3530N13945E ／ 353000N1394500E ／ 35.5,139.75');
 function angle(raw,hem,lat){
  const n=raw.split('.')[0].length;let d,mi=0,se=0;
  if(lat?(n===4||n===6):(n===4||n===5||n===6||n===7)){
   const seconds=lat?n===6:n>=6;const width=n-(seconds?4:2);
   d=Number(raw.slice(0,width));mi=Number(raw.slice(width,seconds?width+2:undefined));
   if(seconds)se=Number(raw.slice(width+2));
  }else if(n<=(lat?2:3))d=Number(raw);else throw Error('座標の桁数を確認してください');
  if(mi>=60||se>=60)throw Error('分・秒は60未満で入力してください');
  return (d+mi/60+se/3600)*(/[SW]/.test(hem)?-1:1);
 }
 return coordinate(angle(m[1],m[2],true),angle(m[3],m[4],false));
}
function additions(previous,all,visible,box){if(previous===null)return [];return visible.filter(f=>!previous.has(f.id)&&inBox(f,box));}
const api={regions,countryRegion,points,inBox,coordinate,coordinateText,additions};if(typeof module!=='undefined')module.exports=api;root.AltaMonitor=api;
})(typeof window==='undefined'?globalThis:window);
