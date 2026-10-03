const assert=require('node:assert/strict');
const Controller=require('../web/refresh-controller.js');
(async()=>{
 let now=0,calls=0,resolve,pending=false,fail=false,last;const timers=new Map();let id=0;
 const c=new Controller({now:()=>now,every:(f,ms)=>{timers.set(++id,{f,ms});return id},cancel:i=>timers.delete(i),onState:s=>last=s,load:async()=>{calls++;if(pending)await new Promise(r=>resolve=r);if(fail)throw Error('offline');return 'success'}});
 await c.start();assert.equal(calls,1);assert.equal(last.nextAt,1800000);
 now=10000;await c.manual();assert.equal(last.nextAt,1810000);assert.equal(timers.size,2);
 now=1800000;await c.due();assert.equal(calls,2);
 pending=true;now=1810000;const task=c.due();await c.manual();await c.due();assert.equal(calls,3);resolve();await task;pending=false;
 fail=true;now=2000000;await c.manual();assert.equal(last.status,'error');assert.equal(last.lastSuccess,1810000);
 fail=false;now=10000000;await c.due();assert.equal(calls,5);assert.equal(last.nextAt,11800000);await c.due();assert.equal(calls,5);
 c.stop();assert.equal(timers.size,0);console.log('refresh controller: reset / single-flight / failure / resume passed');
})();
