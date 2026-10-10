/* Prototype entrance only. Public static assets and JSON remain publicly readable. */
'use strict';
window.altaAccessReady=(async()=>{
 const panel=document.querySelector('#access-panel'),form=document.querySelector('#access-form'),message=document.querySelector('#access-message');
 let config;try{const r=await fetch('access-config.json',{cache:'no-store'});if(!r.ok)throw Error();config=await r.json();}catch{message.textContent='入口設定を読み込めません。再読み込みしてください。';return new Promise(()=>{});}
 if(!config.enabled){document.querySelector('#access-state').textContent='公開試作 · 簡易認証は設定待ち';panel.hidden=true;return;}
 const saved=sessionStorage.getItem('alta-gate');if(saved===config.hash){panel.hidden=true;return;}
 await new Promise(resolve=>{form.onsubmit=async e=>{e.preventDefault();const input=document.querySelector('#access-password');const bytes=new TextEncoder();try{const key=await crypto.subtle.importKey('raw',bytes.encode(input.value),'PBKDF2',false,['deriveBits']);input.value='';const bits=await crypto.subtle.deriveBits({name:'PBKDF2',salt:bytes.encode(config.salt),iterations:config.iterations,hash:'SHA-256'},key,256);const hash=[...new Uint8Array(bits)].map(x=>x.toString(16).padStart(2,'0')).join('');if(hash!==config.hash){message.textContent='パスワードが一致しません。';return;}sessionStorage.setItem('alta-gate',hash);panel.hidden=true;resolve();}catch{message.textContent='認証処理を利用できません。HTTPS接続をご確認ください。';}};});
 document.querySelector('#access-state').textContent='簡易認証済み';
})();
