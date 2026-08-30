const BASE='http://localhost:9377', USER='jxgo5';
async function cf(m,p,b){const r=await fetch(BASE+p,{method:m,headers:{'Content-Type':'application/json'},body:b?JSON.stringify(b):undefined});const j=await r.json().catch(()=>({}));if(!r.ok)throw new Error(`${m} ${p} ${r.status}`);return j;}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  const c=await cf('POST','/tabs',{userId:USER,sessionKey:'go5',url:'https://www.starlux-airlines.com/zh-TW/booking/book-flight/search-a-flight'});
  const t=c.tabId; await sleep(12000);
  const ev=async e=>{try{return (await cf('POST',`/tabs/${t}/evaluate`,{userId:USER,expression:e})).result;}catch(x){return 'ERR '+String(x.message).slice(0,130)}};
  await ev(`(()=>{ window.__x=[];
    const oo=XMLHttpRequest.prototype.open, os=XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.open=function(m,u){this.__u=u;return oo.apply(this,arguments);};
    XMLHttpRequest.prototype.send=function(b){ try{ if(this.__u&&/calendars|flights\\/search/.test(this.__u))
      window.__x.push({u:this.__u,b:b?String(b).slice(0,3000):null}); }catch(e){}
      return os.apply(this,arguments); }; return 'ok'; })()`);
  // Vue 的手風琴常掛在 pointerdown/mousedown，光 .click() 不會展開，補完整事件序列
  const fire = `(el)=>{ const o={bubbles:true,cancelable:true,composed:true,view:window,button:0};
    ['pointerover','pointerenter','pointerdown','mousedown','pointerup','mouseup','click']
      .forEach(n=>{ const E = n.startsWith('pointer') ? PointerEvent : MouseEvent;
        try{ el.dispatchEvent(new E(n,o)); }catch(e){ el.dispatchEvent(new MouseEvent(n.replace('pointer','mouse'),o)); } }); }`;
  const btnByText = re => ev(`(()=>{const fire=${fire};
    const b=[...document.querySelectorAll('button')].find(x=>x.offsetParent&&${re}.test(x.textContent.trim()));
    if(!b)return 'no'; b.focus&&b.focus(); fire(b); return 'ok';})()`);
  const opt = re => ev(`(()=>{const a=[...document.querySelectorAll('[role=option]')].filter(x=>x.offsetParent&&${re}.test(x.textContent));
    if(!a.length) return 'no options; total='+document.querySelectorAll('[role=option]').length;
    a[0].click(); return 'ok:'+a[0].textContent.trim().replace(/\\s+/g,' ').slice(0,26);})()`);
  const listOpts = () => ev(`JSON.stringify([...document.querySelectorAll('[role=option]')].filter(x=>x.offsetParent).map(x=>x.textContent.trim().replace(/\\s+/g,' ').slice(0,24)).slice(0,30))`);

  console.log('出發地:', await btnByText('/出發地/')); await sleep(2200);
  console.log('選 TPE:', await opt('/^\\s*TPE/')); await sleep(2500);
  // 選完出發地後 modal 可能還開著，蓋住目的地按鈕 → 先 Esc 關掉
  console.log('關 modal:', await ev(`(()=>{document.dispatchEvent(new KeyboardEvent('keydown',{key:'Escape',keyCode:27,bubbles:true}));
    document.body.dispatchEvent(new KeyboardEvent('keyup',{key:'Escape',keyCode:27,bubbles:true}));
    return 'esc';})()`)); await sleep(1800);
  console.log('modal 還在嗎:', String(await ev(`(()=>{const h=[...document.querySelectorAll('h2,[role=heading]')].filter(x=>x.offsetParent&&/請選擇(出發地|目的地)/.test(x.textContent));return h.map(x=>x.textContent.trim()).join('|')||'none';})()`)));
  console.log('目的地:', await btnByText('/目的地/')); await sleep(2500);
  console.log('面板標題:', String(await ev(`(()=>{const h=[...document.querySelectorAll('h2,[role=heading]')].filter(x=>x.offsetParent&&/請選擇/.test(x.textContent));return h.map(x=>x.textContent.trim()).join('|')||'none';})()`)));
  console.log('目的地 options:', String(await listOpts()).slice(0,400));
  console.log('東北亞:', await btnByText('/^東北亞$/')); await sleep(2500);
  console.log('展開後 options:', String(await listOpts()).slice(0,700));
  console.log('選 NRT:', await opt('/NRT|成田/')); await sleep(2500);
  console.log('狀態:', String(await ev(`JSON.stringify([...document.querySelectorAll('button')].filter(b=>b.offsetParent&&/旅程/.test(b.textContent)).map(b=>b.textContent.trim().replace(/\\s+/g,' ').slice(0,34)))`)));
  console.log('### TAB', t);
})();
