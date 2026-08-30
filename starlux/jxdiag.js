const BASE='http://localhost:9377', USER='jxdiag';
async function raw(m,p,b){const r=await fetch(BASE+p,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});return {status:r.status, txt:await r.text()};}
async function cf(m,p,b){const r=await raw(m,p,b); if(r.status>=400) throw new Error(`${m} ${p} ${r.status} ${r.txt.slice(0,160)}`); return r.txt?JSON.parse(r.txt):{};}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const c=await cf('POST','/tabs',{userId:USER,sessionKey:'dg',url:'https://www.starlux-airlines.com/zh-TW/booking/book-flight/search-a-flight'});
  const t=c.tabId; await sleep(12000);
  const ev=async e=>{try{return (await cf('POST',`/tabs/${t}/evaluate`,{userId:USER,expression:e})).result;}catch(x){return 'ERR '+String(x.message).slice(0,150)}};
  const snap=async()=>{const s=await cf('GET',`/tabs/${t}/snapshot?userId=${USER}`); return typeof s==='string'?s:(s.snapshot||'');};
  const diag=async label=>{
    console.log(label,
      '| els', await ev(`document.querySelectorAll('*').length`),
      '| role=option', await ev(`document.querySelectorAll('[role=option]').length`),
      '| iframes', await ev(`document.querySelectorAll('iframe').length`),
      '| 請選擇出發地', await ev(`/請選擇出發地/.test(document.body.innerText)`),
      '| tabs', (await cf('GET',`/tabs?userId=${USER}`)).tabs ? (await cf('GET',`/tabs?userId=${USER}`)).tabs.length : '?');
  };
  await diag('起始');
  const s=await snap(); const m=s.match(/button "旅程選擇 出發地[^"]*" \[(e\d+)\]/);
  await cf('POST',`/tabs/${t}/click`,{userId:USER,ref:m[1]}); await sleep(3000);
  await diag('真實click後');
  console.log('body 前 200 字:', String(await ev(`document.body.innerText.replace(/\\s+/g,' ').slice(0,200)`)));
})();
