const BASE='http://localhost:9377', USER='jxhy';
async function raw(m,p,b){const r=await fetch(BASE+p,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});return {status:r.status, txt:await r.text()};}
async function cf(m,p,b){const r=await raw(m,p,b); if(r.status>=400) throw new Error(`${m} ${p} ${r.status} ${r.txt.slice(0,160)}`); return r.txt?JSON.parse(r.txt):{};}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const c=await cf('POST','/tabs',{userId:USER,sessionKey:'hy',url:'https://www.starlux-airlines.com/zh-TW/booking/book-flight/search-a-flight'});
  const t=c.tabId; await sleep(12000);
  const ev=async e=>{try{return (await cf('POST',`/tabs/${t}/evaluate`,{userId:USER,expression:e})).result;}catch(x){return 'ERR '+String(x.message).slice(0,150)}};
  const snap=async()=>{const s=await cf('GET',`/tabs/${t}/snapshot?userId=${USER}`); return typeof s==='string'?s:(s.snapshot||'');};
  const rclick=async(re,what)=>{const s=await snap();const m=s.match(re);
    if(!m){console.log('  !!',what,'找不到');return false;}
    await cf('POST',`/tabs/${t}/click`,{userId:USER,ref:m[1]});console.log('  ✓',what,m[1]);await sleep(2600);return true;};
  const press=async k=>{ try{ await cf('POST',`/tabs/${t}/press`,{userId:USER,key:k}); console.log('  ✓ press',k);}catch(e){console.log('  !! press',k,String(e.message).slice(0,80));} await sleep(1800); };
  const jclick=re=>ev(`(()=>{const a=[...document.querySelectorAll('[role=option],li,button')].filter(x=>x.offsetParent&&${re}.test(x.textContent)&&x.textContent.trim().length<45);
    a.sort((p,q)=>p.textContent.length-q.textContent.length); if(!a.length)return 'no'; a[0].click(); return 'ok:'+a[0].textContent.trim().replace(/\s+/g,' ').slice(0,24);})()`);
  await ev(`(()=>{ window.__x=[];
    const oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return oo.apply(this,arguments);};
    XMLHttpRequest.prototype.send=function(b){ try{ if(this.__u&&/calendars|flights\\/search/.test(this.__u))
      window.__x.push({u:this.__u,b:b?String(b).slice(0,4000):null}); }catch(e){}
      return os.apply(this,arguments); }; return 'ok'; })()`);

  await rclick(/button "旅程選擇 出發地[^"]*" \[(e\d+)\]/,'開出發地');
  console.log('  JS 選 TPE:', await jclick('/^\\s*TPE\\s/')); await sleep(2500);
  console.log('  modal 還開著?', await ev(`/請選擇出發地/.test(document.body.innerText)`));
  await press('Escape');
  console.log('  modal 還開著?', await ev(`/請選擇出發地/.test(document.body.innerText)`));
  await rclick(/button "旅程選擇 目的地[^"]*" \[(e\d+)\]/,'開目的地');
  console.log('  面板標題:', await ev(`(()=>{const h=[...document.querySelectorAll('h2')].filter(x=>x.offsetParent&&/請選擇/.test(x.textContent));return h.map(x=>x.textContent.trim()).join('|')||'none';})()`));
  console.log('  JS 展開東北亞:', await jclick('/^東北亞$/')); await sleep(2500);
  console.log('  可見航點:', String(await ev(`JSON.stringify([...document.querySelectorAll('[role=option]')].filter(x=>x.offsetParent).map(x=>x.textContent.trim().replace(/\\s+/g,' ').slice(0,20)).slice(0,20))`)).slice(0,600));
  console.log('### TAB', t);
})();
