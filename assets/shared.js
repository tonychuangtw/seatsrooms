/* seatsrooms 共用前端邏輯 — index/hotels 兩頁通用。
   全部掛在全域(非 module),頁面的 IIFE 直接取用。
   頁面要先呼叫 onAuthFail(signOut) 註冊 401 時的登出行為。 */
"use strict";
var CLIENT_ID="481860179039-gb37qsdogd4vgnn2g5umh73jen02avj4.apps.googleusercontent.com";
var API="https://claudebot500.tailfcf67f.ts.net", TOKEN_KEY="seatsrooms.token", SESS_KEY="seatsrooms.sess";
function $(id){return document.getElementById(id);}
function esc(s){return String(s==null?"":s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;").replace(/'/g,"&#39;");}
// API 給的 URL 只放行 https,避免壞資料直接塞進 href
function safeUrl(u){return (typeof u==="string"&&/^https:\/\//i.test(u))?esc(u):null;}
function token(){try{return localStorage.getItem(SESS_KEY)||sessionStorage.getItem(TOKEN_KEY);}catch(e){return null;}}
// 長效 session（2026-08-12）：Google ID token 一小時就過期，登入後拿它換一顆
// 後端簽的 30 天 token 存 localStorage；之後每次開頁再換新（滾動續期），不用一直重登。
function refreshSession(){ if(!token())return;
  api("POST","/api/session",{},function(e,d){ if(e||!d||!d.token)return;
    try{localStorage.setItem(SESS_KEY,d.token);sessionStorage.removeItem(TOKEN_KEY);}catch(x){} }); }
function fmtTime(ms){if(!ms)return "—";var d=new Date(ms);return (d.getMonth()+1)+"/"+d.getDate()+" "+d.getHours()+":"+String(d.getMinutes()).padStart(2,"0");}
function fmtAge(ms){var h=Math.floor(ms/3600e3);if(h<1)return Math.max(1,Math.round(ms/60e3))+" 分前";if(h<48)return h+" 小時前";return Math.floor(h/24)+" 天前";}
var AUTH_FAIL_CB=null;
function onAuthFail(cb){AUTH_FAIL_CB=cb;}
function api(method,path,body,cb){
  var x=new XMLHttpRequest(); x.open(method,API+path);
  x.setRequestHeader("Authorization","Bearer "+token());
  if(body)x.setRequestHeader("Content-Type","application/json"); x.timeout=20000;
  x.onload=function(){var d=null;try{d=JSON.parse(x.responseText);}catch(e){}
    // 401 也要先 callback 再登出,不然按鈕會永遠卡在「送出中…」的 disabled 狀態
    if(x.status===401){cb("登入逾期,請重新登入",null);if(AUTH_FAIL_CB)AUTH_FAIL_CB();return;}
    cb(x.status>=200&&x.status<300?null:((d&&d.error)||("HTTP "+x.status)),d);};
  x.onerror=function(){cb("連線失敗(500 主機可能離線)");}; x.ontimeout=function(){cb("連線逾時");};
  x.send(body?JSON.stringify(body):null);
}
// 掃描健康燈：names={key:顯示名}, h={key:{last}}; 門檻(小時)可依掃描節奏調
function healthHtml(h,names,greenH,yellowH){
  if(!h)return "";
  var now=Date.now(),html="";
  Object.keys(names).forEach(function(p){
    if(!(p in h)||!h[p])return;
    var last=h[p].last, age=last!=null?now-last:null;
    var cls=age==null?"r":(age<(greenH||14)*3600e3?"g":(age<(yellowH||28)*3600e3?"y":"r"));
    html+='<span><i class="'+cls+'"></i>'+names[p]+" "+(age!=null?fmtAge(age):"沒掃到")+"</span>";
  });
  return html?'<span style="border:none;background:none;padding:3px 0">掃描健康：</span>'+html:"";
}
// 近14天狀態時間軸：history 只記變化點,這裡展開成逐日格子;某日之前完全沒紀錄=未知(空格)
function timelineHtml(history,tlCls,statusLabel){
  var h=history||[]; if(!h.length)return "";
  var out='<div class="tl" aria-label="近14天狀態"><span class="tl-l">14天</span>',now=new Date();
  for(var i=13;i>=0;i--){
    var d=new Date(now.getFullYear(),now.getMonth(),now.getDate()-i);
    var dayEnd=d.getTime()+86399999,st=null;
    for(var j=h.length-1;j>=0;j--){ if(h[j].t<=dayEnd){st=h[j].status;break;} }
    var lbl=(d.getMonth()+1)+"/"+d.getDate();
    out+='<i class="'+(st?(tlCls[st]||"t-un"):"t-un")+'" title="'+lbl+" "+esc(st?(statusLabel[st]||st):"無紀錄")+'"></i>';
  }
  return out+"</div>";
}
/* ---- 站內彈窗 / 提示（2026-08-15 全線指示:不准用原生 alert/confirm/prompt）----
   原生框會顯示「tonychuangtw.github.io 顯示：…」,跟深色站完全不搭。
   樣式用 JS 注入,rules.html 這種沒載 shared.css 的頁也能用。 */
(function(){
  var css=
  '.mdl-back{position:fixed;inset:0;background:rgba(0,0,0,.66);display:flex;align-items:center;'
  +'justify-content:center;padding:18px;z-index:9999;opacity:0;transition:opacity .15s}'
  +'.mdl-back.in{opacity:1}'
  +'.mdl{background:var(--card,#17171c);border:1px solid var(--border,#2a2a33);border-radius:14px;'
  +'padding:18px;max-width:400px;width:100%;color:var(--text,#ececf1);box-shadow:0 18px 44px rgba(0,0,0,.5);'
  +'transform:translateY(8px) scale(.98);transition:transform .15s;'
  +'font-family:-apple-system,"PingFang TC","Noto Sans TC",sans-serif}'
  +'.mdl-back.in .mdl{transform:none}'
  +'.mdl h3{margin:0 0 8px;font-size:1.02rem}'
  +'.mdl .mdl-b{margin:0;font-size:0.9rem;color:var(--text2,#9a9aa8);line-height:1.6;white-space:pre-line}'
  +'.mdl .mdl-b b{color:var(--text,#ececf1)}'
  +'.mdl-btns{display:flex;gap:8px;margin-top:16px;justify-content:flex-end;flex-wrap:wrap}'
  +'.mdl-btns button{border:none;border-radius:9px;padding:10px 16px;font-size:0.9rem;font-weight:600;'
  +'cursor:pointer;font-family:inherit}'
  +'.mdl-btns .mdl-c{background:transparent;color:var(--text2,#9a9aa8);border:1px solid var(--border,#2a2a33)}'
  +'.mdl-btns .mdl-o{background:var(--accent,#6aa8ff);color:#06131c}'
  +'.mdl-btns .mdl-o.danger{background:var(--bad,#e5484d);color:#fff}'
  +'.mdl-url{width:100%;margin-top:12px;padding:9px;border-radius:8px;border:1px solid var(--border,#2a2a33);'
  +'background:var(--bg,#0d0d10);color:var(--text2,#9a9aa8);font-size:0.8rem;font-family:inherit}'
  +'.tst-wrap{position:fixed;left:0;right:0;bottom:16px;z-index:10000;display:flex;flex-direction:column;'
  +'align-items:center;gap:8px;pointer-events:none;padding:0 14px}'
  +'.tst{background:var(--card,#17171c);border:1px solid var(--border,#2a2a33);border-radius:11px;'
  +'padding:11px 16px;font-size:0.88rem;color:var(--text,#ececf1);max-width:400px;'
  +'box-shadow:0 10px 28px rgba(0,0,0,.5);opacity:0;transform:translateY(10px);transition:opacity .18s,transform .18s;'
  +'font-family:-apple-system,"PingFang TC","Noto Sans TC",sans-serif;line-height:1.45}'
  +'.tst.in{opacity:1;transform:none}'
  +'.tst.err{border-color:var(--bad,#e5484d);color:var(--bad,#e5484d)}'
  +'.tst.ok{border-color:var(--ok,#4cc38a);color:var(--ok,#4cc38a)}'
  +'.gbtn{display:flex;align-items:center;justify-content:center;gap:9px;width:100%;max-width:260px;'
  +'background:#131316;color:#e3e3e3;border:1px solid #3c4043;border-radius:9px;padding:11px 16px;'
  +'font-size:0.93rem;font-weight:600;cursor:pointer;font-family:inherit}'
  +'.gbtn svg{width:17px;height:17px;flex:none}';
  var h=document.head||document.documentElement;   // 測試 shim 沒有 head,別在那邊炸掉
  if(!h||!h.appendChild)return;
  var s=document.createElement("style"); s.textContent=css; h.appendChild(s);
})();

// 站內 toast：一次性提示(成功/失敗),不擋操作。kind: "err" | "ok" | ""
function toast(msg,kind){
  var wrap=document.querySelector(".tst-wrap");
  if(!wrap){wrap=document.createElement("div");wrap.className="tst-wrap";document.body.appendChild(wrap);}
  var t=document.createElement("div");
  t.className="tst"+(kind?" "+kind:""); t.setAttribute("role","status"); t.textContent=msg;
  wrap.appendChild(t);
  requestAnimationFrame(function(){t.classList.add("in");});
  setTimeout(function(){ t.classList.remove("in");
    setTimeout(function(){ if(t.parentNode)t.parentNode.removeChild(t); },220);
  }, kind==="err"?5000:3200);
}

/* 站內 modal。opts:{title,body,okText,cancelText,danger,extraHtml,onOk,onCancel}
   cancelText 給 null = 單鈕告知框(取代 alert);有 cancelText = 兩段式確認(取代 confirm) */
function modal(opts){
  opts=opts||{};
  var back=document.createElement("div"); back.className="mdl-back";
  back.setAttribute("role","dialog"); back.setAttribute("aria-modal","true");
  var hasCancel=opts.cancelText!==null;
  back.innerHTML='<div class="mdl">'
    +(opts.title?'<h3>'+esc(opts.title)+'</h3>':"")
    +'<p class="mdl-b">'+esc(opts.body||"")+'</p>'
    +(opts.extraHtml||"")
    +'<div class="mdl-btns">'
    +(hasCancel?'<button type="button" class="mdl-c">'+esc(opts.cancelText||"取消")+'</button>':"")
    +'<button type="button" class="mdl-o'+(opts.danger?" danger":"")+'">'+esc(opts.okText||(hasCancel?"確定":"知道了"))+'</button>'
    +'</div></div>';
  var prev=document.activeElement;
  function close(cb){
    document.removeEventListener("keydown",onKey);
    back.classList.remove("in");
    setTimeout(function(){ if(back.parentNode)back.parentNode.removeChild(back);
      try{if(prev&&prev.focus)prev.focus();}catch(e){} if(cb)cb(); },170);
  }
  function onKey(ev){
    if(ev.key==="Escape"){ev.preventDefault();close(opts.onCancel);}
    // 焦點鎖在框內,不然背景的表單還按得到
    else if(ev.key==="Tab"){
      var f=back.querySelectorAll("button,input,a[href]"); if(!f.length)return;
      var first=f[0],last=f[f.length-1];
      if(ev.shiftKey&&document.activeElement===first){ev.preventDefault();last.focus();}
      else if(!ev.shiftKey&&document.activeElement===last){ev.preventDefault();first.focus();}
    }
  }
  back.querySelector(".mdl-o").addEventListener("click",function(){close(opts.onOk);});
  var c=back.querySelector(".mdl-c");
  if(c)c.addEventListener("click",function(){close(opts.onCancel);});
  // 點背景=取消(等同按取消,不會誤觸執行)
  back.addEventListener("click",function(ev){ if(ev.target===back)close(opts.onCancel); });
  document.addEventListener("keydown",onKey);
  document.body.appendChild(back);
  requestAnimationFrame(function(){ back.classList.add("in");
    var o=back.querySelector(hasCancel?".mdl-c":".mdl-o"); if(o)o.focus(); });
  return back;
}
// 兩段式確認：確定才跑 onOk（取代 confirm()）
function confirmDlg(msg,onOk,opts){
  opts=opts||{};
  modal({title:opts.title||"確認",body:msg,okText:opts.okText||"確定",
    cancelText:opts.cancelText||"取消",danger:opts.danger!==false,onOk:onOk});
}
// 單鈕告知框（取代要求「看到才繼續」的 alert()；一般錯誤請用 toast）
function alertDlg(msg,title){ modal({title:title||"提示",body:msg,cancelText:null}); }

// App 內建瀏覽器（LINE / Telegram / FB / IG / 微信 / Android webview）
function isInAppBrowser(){
  var ua=navigator.userAgent||"";
  if(/\bLine\/|FBAN|FBAV|FB_IAB|Instagram|MicroMessenger|Telegram/i.test(ua))return true;
  if(/\bwv\b|; wv\)/i.test(ua))return true;                    // Android WebView
  // iOS：內建瀏覽器沒有 Safari 標記
  return /iPhone|iPad|iPod/i.test(ua)&&!/Safari/i.test(ua);
}
// 引導改用外部瀏覽器（GSI 被 webview 擋掉時的出路）
function showOpenExternalHelp(){
  var url=location.href;
  modal({title:"請用外部瀏覽器開啟",
    body:isInAppBrowser()
      ?"你現在是在 App 的內建瀏覽器裡（LINE / Telegram / FB 等），它會擋掉 Google 登入，所以登入按鈕按不動。\n\n請點右上角「⋯」或「⋮」選「用預設瀏覽器開啟」（Safari / Chrome），再登入一次。"
      :"Google 登入元件載不進來（可能是擋廣告套件、公司網路，或這是 App 的內建瀏覽器）。\n\n請改用 Safari / Chrome 開啟本站再登入；已經是的話關掉擋廣告套件重新整理試試。",
    extraHtml:'<input class="mdl-url" readonly value="'+esc(url)+'" aria-label="本站網址">',
    okText:"複製網址",cancelText:"關閉",
    onOk:function(){
      var done=function(){toast("網址已複製,貼到瀏覽器開啟","ok");};
      if(navigator.clipboard&&navigator.clipboard.writeText){
        navigator.clipboard.writeText(url).then(done,function(){toast("複製失敗,請長按網址手動複製","err");});
      }else{ toast("請長按上面的網址手動複製","err"); }
    }});
}
// Google 登入：先畫自己的鈕,再等 GSI 換上真的那顆。
// App 內建瀏覽器常擋 accounts.google.com,「等 GSI 載好才畫」會讓登入鈕整個不見,
// 看起來像這站沒有登入功能（2026-08-15 Tony 全線指示）。
function gsiInit(onCred){
  var el=$("gsi-btn"); if(!el)return;
  el.innerHTML="";
  var fb=document.createElement("button");
  fb.type="button"; fb.className="gbtn";
  fb.innerHTML='<svg viewBox="0 0 48 48" aria-hidden="true">'
    +'<path fill="#4285F4" d="M45.1 24.5c0-1.6-.1-3.1-.4-4.5H24v8.5h11.8c-.5 2.7-2.1 5-4.4 6.6v5.5h7.1c4.2-3.8 6.6-9.5 6.6-16.1z"/>'
    +'<path fill="#34A853" d="M24 46c6 0 11-2 14.5-5.4l-7.1-5.5c-2 1.3-4.5 2.1-7.4 2.1-5.7 0-10.6-3.9-12.3-9.1H4.3v5.7C7.8 41 15.3 46 24 46z"/>'
    +'<path fill="#FBBC05" d="M11.7 28.1c-.4-1.3-.7-2.7-.7-4.1s.2-2.8.7-4.1v-5.7H4.3C2.8 17.1 2 20.4 2 24s.8 6.9 2.3 9.8l7.4-5.7z"/>'
    +'<path fill="#EA4335" d="M24 10.8c3.2 0 6.1 1.1 8.4 3.3l6.3-6.3C34.9 4.2 30 2 24 2 15.3 2 7.8 7 4.3 14.2l7.4 5.7c1.7-5.2 6.6-9.1 12.3-9.1z"/>'
    +'</svg>使用 Google 登入';
  fb.addEventListener("click",showOpenExternalHelp);
  el.appendChild(fb);
  var tries=0;
  (function tick(){
    if(!window.google||!google.accounts||!google.accounts.id){
      // 10 秒還沒來就當它被擋了:fallback 鈕留著,補一行說明,不要無限空轉
      if(++tries>50){ if(!el.querySelector(".gsi-note")){
          var p=document.createElement("p"); p.className="msg gsi-note"; p.style.marginTop="8px";
          p.textContent=isInAppBrowser()
            ?"偵測到 App 內建瀏覽器,Google 登入被擋——點上面按鈕看怎麼用外部瀏覽器開"
            :"Google 登入元件載不進來(擋廣告套件或網路問題),點上面按鈕看解法";
          el.appendChild(p); } return; }
      setTimeout(tick,200); return;
    }
    google.accounts.id.initialize({client_id:CLIENT_ID,callback:function(resp){
      try{sessionStorage.setItem(TOKEN_KEY,resp.credential);}catch(e){}
      onCred();
    }});
    el.innerHTML="";  // GSI 到了,換上真的那顆
    google.accounts.id.renderButton(el,{theme:"filled_black",size:"large",text:"signin_with"});
  })();
}
// 下拉選單灌數字選項
function fillNum(sel,from,to,def,suffix){
  if(!sel)return;
  for(var i=from;i<=to;i++){ var o=document.createElement("option");
    o.value=i; o.textContent=i+(suffix||""); if(i===def)o.selected=true; sel.appendChild(o); }
}
// PWA 加到主畫面後是全螢幕,沒有瀏覽器的重新整理鈕(2026-08-14 Tony 反映):
// 1) 頁尾補一顆「↻ 重新載入頁面」 2) 切回 app 且頁面已載入超過 6 小時就自動整頁重載拿新版
var PAGE_LOADED_AT=Date.now();
document.addEventListener("visibilitychange",function(){
  if(!document.hidden&&Date.now()-PAGE_LOADED_AT>6*3600e3)location.reload();
});
document.addEventListener("DOMContentLoaded",function(){
  var f=document.querySelector(".foot");
  if(!f)return;
  var a=document.createElement("a");
  a.href="#"; a.textContent="↻ 重新載入頁面";
  a.style.cssText="color:var(--accent);text-decoration:none;margin-left:6px";
  a.addEventListener("click",function(ev){ev.preventDefault();location.reload();});
  f.appendChild(document.createTextNode(" · "));
  f.appendChild(a);
});
