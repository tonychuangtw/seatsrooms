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
// Google 登入：retry 有上限,被 ad-blocker/斷網擋掉時給明確訊息,不要無限空轉
function gsiInit(onCred){
  var tries=0;
  (function tick(){
    if(!window.google||!google.accounts){
      if(++tries>100){ var el=$("gsi-btn");
        if(el)el.innerHTML='<p class="msg err">Google 登入載入失敗——擋廣告套件或網路問題,重新整理試試</p>';
        return; }
      setTimeout(tick,200); return;
    }
    google.accounts.id.initialize({client_id:CLIENT_ID,callback:function(resp){
      try{sessionStorage.setItem(TOKEN_KEY,resp.credential);}catch(e){}
      onCred();
    }});
    google.accounts.id.renderButton($("gsi-btn"),{theme:"filled_black",size:"large",text:"signin_with"});
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
