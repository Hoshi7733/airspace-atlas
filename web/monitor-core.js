/* Pure helpers shared by rendering and regression tests. */
(function(root){
const regions={Asia:{name:'アジア',view:[32,110,3],box:[-12,25,82,180]},NorthAmerica:{name:'北米',view:[38,-105,3],box:[5,-180,85,-30]},Europe:{name:'ヨーロッパ',view:[51,17,4],box:[34,-25,72,65]},Oceania:{name:'オセアニア',view:[-23,145,3],box:[-55,110,10,240]},Africa:{name:'アフリカ',view:[2,20,3],box:[-36,-20,38,55]},SouthAmerica:{name:'南米',view:[-20,-62,3],box:[-60,-90,14,-30]}};
const south=new Set('AR BO BR CL CO EC FK GF GY PY PE SR UY VE'.split(' '));
function countryRegion(c){return c.region==='Americas'?(south.has(c.code)?'SouthAmerica':'NorthAmerica'):c.region;}
function points(g){if(!g)return [];if(g.type==='Point')return [g.coordinates];if(g.type==='MultiPoint')return g.coordinates;return g.type==='Polygon'?g.coordinates.flat():g.coordinates.flat(2);}
function inBox(f,box){const ps=points(f.geometry);if(!ps.length)return false;let [s,w,n,e]=box;const radius=(f.properties.radius_m||0)/111000;return [-360,0,360].some(shift=>{const xs=ps.map(p=>p[0]+shift),ys=ps.map(p=>p[1]);const lat=(Math.min(...ys)+Math.max(...ys))/2;const lonRadius=radius/Math.max(.05,Math.cos(lat*Math.PI/180));return Math.max(...xs)+lonRadius>=w&&Math.min(...xs)-lonRadius<=e&&Math.max(...ys)+radius>=s&&Math.min(...ys)-radius<=n;});}
function coordinate(lat,lon){if(String(lat).trim()===''||String(lon).trim()==='')throw Error('緯度と経度を入力してください');const a=Number(lat),b=Number(lon);if(!Number.isFinite(a)||!Number.isFinite(b)||Math.abs(a)>90||Math.abs(b)>180)throw Error('緯度 −90〜90、経度 −180〜180で入力してください');return [a,b];}
function additions(previous,all,visible,box){if(previous===null)return [];return visible.filter(f=>!previous.has(f.id)&&inBox(f,box));}
const api={regions,countryRegion,points,inBox,coordinate,additions};if(typeof module!=='undefined')module.exports=api;root.AltaMonitor=api;
})(typeof window==='undefined'?globalThis:window);
