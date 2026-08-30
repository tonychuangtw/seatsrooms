const BASE='http://localhost:9377', USER='jxacc';
async function raw(m,p,b){const r=await fetch(BASE+p,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});return {status:r.status, txt:await r.text()};}
async function cf(m,p,b){const r=await raw(m,p,b); if(r.status>=400) throw new Error(`${m} ${p} ${r.status} ${r.txt.slice(0,160)}`); return r.txt?JSON.parse(r.txt):{};}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const c=await cf('POST','/tabs',{userId:USER,sessionKey:'ac',url:'https://www.starlux-airlines.com/zh-TW/booking/book-flight/search-a-flight'});
  const t=c.tabId; await sleep(12000);
  const ev=async e=>{try{return (await cf('POST',`/tabs/${t}/evaluate`,{userId:USER,expression:e})).result;}catch(x){return 'ERR '+String(x.message).slice(0,150)}};
  const j=re=>ev(`(()=>{const a=[...document.querySelectorAll('button')].filter(x=>${re}.test(x.textContent.trim()));if(!a.length)return 'no';a[0].click();return 'ok';})()`);
  console.log('開出發地:', await j('/出發地/')); await sleep(2500);
  console.log('選TPE:', await ev(`(()=>{const o=[...document.querySelectorAll('[role=option]')].filter(x=>/^TPE/.test(x.textContent.trim()));if(!o.length)return 'no';o[0].click();return 'ok';})()`)); await sleep(2500);
  console.log('modal 在嗎(用 role=dialog 判):', await ev(`document.querySelectorAll('[role=dialog],dialog,[aria-modal=true]').length`));
  console.log('開目的地:', await j('/目的地/')); await sleep(2500);
  console.log('accordion 狀態:', String(await ev(`(()=>{const b=[...document.querySelectorAll('button')].filter(x=>/^(臺灣|港澳|東北亞|東南亞|北美洲|歐洲)$/.test(x.textContent.trim()));
    return JSON.stringify(b.map(x=>({t:x.textContent.trim(),exp:x.getAttribute('aria-expanded'),dis:x.disabled,tag:x.tagName,cls:(x.className||'').slice(0,40)})));})()`)).slice(0,700));
  console.log('點東北亞(font-bold 那顆):', await ev(`(()=>{const a=[...document.querySelectorAll('button')].filter(x=>x.textContent.trim()==='東北亞');
    if(a.length<2) return 'only '+a.length; a[1].click(); return 'clicked idx1';})()`)); await sleep(2500);
  console.log('  → aria-expanded:', String(await ev(`(()=>{const a=[...document.querySelectorAll('button')].filter(x=>x.textContent.trim()==='東北亞');return JSON.stringify(a.map(x=>x.getAttribute('aria-expanded')));})()`)));
  console.log('  → option 數:', await ev(`document.querySelectorAll('[role=option]').length`));
  console.log('點東北亞(accordion 那顆再試一次):', await j('/^東北亞$/')); await sleep(2500);
  console.log('點完狀態:', String(await ev(`(()=>{const b=[...document.querySelectorAll('button')].filter(x=>/^(臺灣|東北亞)$/.test(x.textContent.trim()));
    return JSON.stringify(b.map(x=>({t:x.textContent.trim(),exp:x.getAttribute('aria-expanded')})));})()`)));
  console.log('option 數:', await ev(`document.querySelectorAll('[role=option]').length`));
  console.log('NRT 在不在 DOM:', await ev(`/NRT/.test(document.body.innerHTML)`));
})();
