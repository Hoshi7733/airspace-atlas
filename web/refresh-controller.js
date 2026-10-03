/* Published JSON only. Single flight; manual refresh restarts the 30-minute interval. */
'use strict';
class AltaRefreshController {
 constructor({load,onState=()=>{},period=1800000,now=()=>Date.now(),every=(fn,ms)=>setInterval(fn,ms),cancel=id=>clearInterval(id)}){Object.assign(this,{load,onState,period,now,every,cancel});this.state={nextAt:null,lastAttempt:null,lastSuccess:null,status:'idle'};this.busy=false;}
 emit(){this.onState({...this.state,busy:this.busy,remaining:Math.max(0,(this.state.nextAt??this.now())-this.now())});}
 reset(){if(this.timer!=null)this.cancel(this.timer);this.state.nextAt=this.now()+this.period;this.timer=this.every(()=>this.due(),this.period);this.emit();}
 start(){this.reset();this.ticker=this.every(()=>this.emit(),1000);return this.run();}
 async run(){if(this.busy)return;this.busy=true;this.state.lastAttempt=this.now();this.state.status='loading';this.emit();try{const result=await this.load();this.state.status=result==='partial'?'partial':'success';if(this.state.status==='success')this.state.lastSuccess=this.now();}catch{this.state.status='error';}finally{this.busy=false;this.emit();}}
 manual(){if(this.busy)return;this.reset();return this.run();}
 due(){if(this.now()<this.state.nextAt)return;this.reset();return this.run();}
 stop(){this.cancel(this.timer);this.cancel(this.ticker);}
}
if(typeof module!=='undefined')module.exports=AltaRefreshController;
