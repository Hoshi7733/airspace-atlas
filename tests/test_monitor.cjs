const assert=require('node:assert/strict');const m=require('../web/monitor-core.js');
assert.equal(m.countryRegion({code:'US',region:'Americas'}),'NorthAmerica');assert.equal(m.countryRegion({code:'BR',region:'Americas'}),'SouthAmerica');
assert.deepEqual(m.coordinate('35.5','-140'),[35.5,-140]);for(const p of [['','0'],['91','0'],['0','181'],['x','0']])assert.throws(()=>m.coordinate(...p));
const f=(id,x,y)=>({id,geometry:{type:'Point',coordinates:[x,y]},properties:{radius_m:1852}}),a=f('old',140,35),b=f('new',141,35),c=f('off',0,0),all=new Map([a,b,c].map(f=>[f.id,f]));
assert.deepEqual(m.additions(null,all,[a,b,c],[30,130,40,150]),[]);assert.deepEqual(m.additions(new Set(['old']),all,[a,b,c],[30,130,40,150]).map(f=>f.id),['new']);assert(m.inBox(f('wrapped',-170,20),[10,180,30,200]));
console.log('monitor: region mapping, valid coordinates, initial suppression, new visible alerts and world wrap passed');

assert.equal(m.countryRegion({code:'IR',region:'Asia'}),'MiddleEast');
assert.deepEqual(m.coordinateText('3530N13945E'),[35.5,139.75]);
assert.deepEqual(m.coordinateText('353000N1394500E'),[35.5,139.75]);
assert.deepEqual(m.coordinateText('3530S0030W'),[-35.5,-.5]);
assert.deepEqual(m.coordinateText('35.5,139.75'),[35.5,139.75]);
for(const s of ['3560N13945E','9100N13945E','3530N18100E','3530N1394560E','hello'])assert.throws(()=>m.coordinateText(s));
