// 星宇：真實走完一次搜尋，把票價日曆 API 的 request body 抓下來
const BASE='http://localhost:9377', USER='jxcap';
async function raw(m,p,b){const r=await fetch(BASE+p,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});return {status:r.status, txt:await r.text()};}
async function cf(m,p,b){const r=await raw(m,p,b); if(r.status>=400) throw new Error(`${m} ${p} ${r.status} ${r.txt.slice(0,200)}`); return r.txt?JSON.parse(r.txt):{};}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const c=await cf('POST','/tabs',{userId:USER,sessionKey:'cap',url:'https://www.starlux-airlines.com/zh-TW/booking/book-flight/search-a-flight'});
  const t=c.tabId; await sleep(12000);
  const ev=async e=>{try{return (await cf('POST',`/tabs/${t}/evaluate`,{userId:USER,expression:e})).result;}catch(x){return 'ERR '+String(x.message).slice(0,150)}};
  const snap=async()=>{const s=await cf('GET',`/tabs/${t}/snapshot?userId=${USER}`); return typeof s==='string'?s:(s.snapshot||'');};
  const click=async (re,what)=>{
    const s=await snap(); const m=s.match(re);
    if(!m){ console.log('  !! 找不到', what); return false; }
    await cf('POST',`/tabs/${t}/click`,{userId:USER,ref:m[1]});
    console.log('  ✓', what, m[1]); await sleep(2600); return true;
  };
  await ev(`(()=>{ window.__x=[];
    const oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return oo.apply(this,arguments);};
    XMLHttpRequest.prototype.send=function(b){ try{ if(this.__u&&/calendars|flights\\/search/.test(this.__u))
      window.__x.push({u:this.__u,b:b?String(b).slice(0,4000):null}); }catch(e){}
      return os.apply(this,arguments); }; return 'ok'; })()`);

  await click(/button "旅程選擇 出發地[^"]*" \[(e\d+)\]/, '開出發地');
  {const sx=await snap();
   console.log('  snapshot len', sx.length, '| 有請選擇出發地:', /請選擇出發地/.test(sx),
     '| option 數:', (sx.match(/option "/g)||[]).length,
     '| 前三個 option:', (sx.match(/option "[^"]{0,26}/g)||[]).slice(0,3).join(' / '));}
  await click(/option "TPE [^"]*" \[(e\d+)\]/, '選 TPE');
  await click(/button "旅程選擇 目的地[^"]*" \[(e\d+)\]/, '開目的地');
  let s=await snap();
  console.log('  面板:', (s.match(/heading "請選擇[^"]*"/)||['?'])[0],
              '| 區域:', (s.match(/button "(?:港澳|東北亞|東南亞|北美洲|歐洲)" \[e\d+\]/g)||[]).join(' '));
  await click(/button "東北亞" \[(e\d+)\]/, '展開東北亞');
  s=await snap();
  console.log('  東北亞航點:', (s.match(/option "[A-Z]{3} [^"]{0,22}/g)||[]).slice(0,12).join(' / '));
  await click(/option "NRT [^"]*" \[(e\d+)\]/, '選 NRT');
  s=await snap();
  console.log('  目前:', (s.match(/button "旅程[^"]*"/g)||[]).join(' | ').slice(0,160));
  console.log('### TAB', t, 'USER', USER);
})();
