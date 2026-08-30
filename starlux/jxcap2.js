// 星宇：真實走完一次搜尋並錄下票價日曆 API 的 request body
// 關鍵：不要用 offsetParent 判可見 —— modal 是 position:fixed，裡面所有元素 offsetParent 都是 null
const BASE=process.env.CAMOFOX_URL||'http://localhost:9377', USER='jxcap2';
async function raw(m,p,b){const r=await fetch(BASE+p,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});return {status:r.status, txt:await r.text()};}
async function cf(m,p,b){const r=await raw(m,p,b); if(r.status>=400) throw new Error(`${m} ${p} ${r.status} ${r.txt.slice(0,160)}`); return r.txt?JSON.parse(r.txt):{};}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const VIS=`(x)=>x.getClientRects().length>0`;
(async()=>{
  const c=await cf('POST','/tabs',{userId:USER,sessionKey:'c2',url:'https://www.starlux-airlines.com/zh-TW/booking/book-flight/search-a-flight'});
  const t=c.tabId; await sleep(12000);
  const ev=async e=>{try{return (await cf('POST',`/tabs/${t}/evaluate`,{userId:USER,expression:e})).result;}catch(x){return 'ERR '+String(x.message).slice(0,150)}};
  const snap=async()=>{const s=await cf('GET',`/tabs/${t}/snapshot?userId=${USER}`); return typeof s==='string'?s:(s.snapshot||'');};
  const rclick=async(re,what)=>{const s=await snap();const m=s.match(re);
    if(!m){console.log('  !!',what,'找不到 ref');return false;}
    await cf('POST',`/tabs/${t}/click`,{userId:USER,ref:m[1]});console.log('  ✓',what);await sleep(2600);return true;};
  const jclick=(sel,re)=>ev(`(()=>{const vis=${VIS};
    const a=[...document.querySelectorAll(${JSON.stringify(sel)})].filter(x=>vis(x)&&${re}.test(x.textContent.trim()));
    a.sort((p,q)=>p.textContent.length-q.textContent.length);
    if(!a.length) return 'no('+document.querySelectorAll(${JSON.stringify(sel)}).length+' 個候選)';
    a[0].click(); return 'ok:'+a[0].textContent.trim().replace(/\\s+/g,' ').slice(0,26);})()`);
  const opts=()=>ev(`(()=>{const vis=${VIS};
    return JSON.stringify([...document.querySelectorAll('[role=option]')].filter(vis)
      .map(x=>x.textContent.trim().replace(/\\s+/g,' ').slice(0,22)).slice(0,24));})()`);

  await ev(`(()=>{ window.__x=[];
    const oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return oo.apply(this,arguments);};
    XMLHttpRequest.prototype.send=function(b){ try{ if(this.__u&&/calendars|flights\\/search/.test(this.__u))
      window.__x.push({u:this.__u,b:b?String(b).slice(0,4000):null}); }catch(e){}
      return os.apply(this,arguments); }; return 'ok'; })()`);

  await rclick(/button "旅程選擇 出發地[^"]*" \[(e\d+)\]/,'開出發地');
  console.log('  可見 options:', String(await opts()).slice(0,300));
  console.log('  選 TPE:', await jclick('[role=option]','/^TPE/')); await sleep(2600);
  console.log('  出發地鈕現在是:', String(await ev(`(()=>{const vis=${VIS};const b=[...document.querySelectorAll('button')].filter(x=>vis(x)&&/旅程出發地|旅程選擇 出發地/.test(x.textContent));return b.map(x=>x.textContent.trim().replace(/\\s+/g,' ').slice(0,30)).join('|')||'none';})()`)));
  await rclick(/button "旅程選擇 目的地[^"]*" \[(e\d+)\]/,'開目的地');
  console.log('  目的地可見 options:', String(await opts()).slice(0,300));
  console.log('  區域按鈕:', String(await ev(`(()=>{const vis=${VIS};return JSON.stringify([...document.querySelectorAll('button')].filter(x=>vis(x)&&/^(港澳|東北亞|東南亞|北美洲|歐洲|臺灣)$/.test(x.textContent.trim())).map(x=>x.textContent.trim()));})()`)));
  console.log('  展開東北亞:', await jclick('button','/^東北亞$/')); await sleep(2600);
  console.log('  展開後 options:', String(await opts()).slice(0,600));
  console.log('### TAB', t);
})();
