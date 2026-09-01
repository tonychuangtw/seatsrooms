#!/usr/bin/env node
// TigerClub 會員登入（camofox profile `tigerclub`，brain :9377）。
// 帳密讀 ../.env 的 TIGERAIR_USER / TIGERAIR_PASS，本檔不含任何敏感資料。
//
// 兩段式（MFA 驗證碼寄 Tony 的 Gmail，要靠 Claude 的 Gmail MCP 收，腳本自己收不了）：
//   node tigerclub-login.js               # 填帳密送出。直接進會員首頁就完成；
//                                         # 跳 MFA 就停在驗證頁（tab 存 .tclogin-tab）
//   node tigerclub-login.js --code 123456 # 第二段：填驗證碼＋勾「信任此裝置」→ 確認
//
// 完成後驗證：node member-jwt.js 能印出 JWT 就是活的。
// 教訓（2026-09-02）：membership session 大約 1~2 天就掉，「信任此裝置」也不一定保住
// 下次免 MFA —— 促銷日（9/16）早上一定要先跑一次 member-jwt.js 驗活，掉了就重登。
const fs = require('fs'), path = require('path');
const BASE = process.env.CAMOFOX_URL || 'http://localhost:9377';
const USER = 'tigerclub';
const TABF = path.join(__dirname, '.tclogin-tab');

const ci = process.argv.indexOf('--code');
const CODE = ci >= 0 ? process.argv[ci + 1] : null;

async function cf(m, p, b) {
  const r = await fetch(BASE + p, { method: m, headers: { 'content-type': 'application/json' },
    body: b ? JSON.stringify(b) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`camofox ${m} ${p} -> ${r.status} ${JSON.stringify(j).slice(0, 150)}`);
  return j;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function phase1() {
  const env = fs.readFileSync(path.join(__dirname, '..', '.env'), 'utf8');
  const get = k => { const m = env.match(new RegExp('^' + k + "=(?:'([^']*)'|\"([^\"]*)\"|(.*))$", 'm'));
    return m ? (m[1] ?? m[2] ?? m[3]).trim() : null; };
  const u = get('TIGERAIR_USER'), p = get('TIGERAIR_PASS');
  if (!u || !p) throw new Error('.env 沒有 TIGERAIR_USER/PASS');
  await cf('DELETE', '/sessions/' + USER).catch(() => {});
  const { tabId } = await cf('POST', '/tabs', { userId: USER, sessionKey: 'login',
    url: 'https://membership.tigerairtw.com/login?language=zh-TW&targetOrigin=https://booking.tigerairtw.com' });
  fs.writeFileSync(TABF, tabId);
  await sleep(9000);
  const ev = async e => (await cf('POST', `/tabs/${tabId}/evaluate`, { userId: USER, expression: e })).result;
  const filled = await ev(`(()=>{
    const set=(el,v)=>{const d=Object.getOwnPropertyDescriptor(el.constructor.prototype,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
    const email=document.querySelector('input[type=email]'), pass=document.querySelector('input[type=password]');
    if(!email&&pass){ set(pass,${JSON.stringify('PASS')}); return 'pass-only'; }
    if(!email||!pass) return 'no-form';
    set(email,${JSON.stringify('USER')}); set(pass,${JSON.stringify('PASS')}); return 'ok';
  })()`.replace('"USER"', JSON.stringify(u)).replaceAll('"PASS"', JSON.stringify(p)));
  console.log('fill:', filled);
  if (filled === 'no-form') { console.log('沒看到登入表單（可能已登入？）'); }
  await sleep(1200);
  console.log('click:', await ev(`(()=>{const b=[...document.querySelectorAll('button')].filter(x=>x.offsetParent&&x.textContent.trim()==='登入')[0];if(!b)return 'no-button';b.click();return 'ok';})()`));
  await sleep(9000);
  const url = await ev('location.href');
  console.log('url:', url);
  if (/mfa-verify/.test(url)) {
    console.log('→ 跳 MFA：去 Gmail 收 from:tigerairtw.com 最新驗證碼（10 分鐘效期，多封取最新），'
      + '再跑 node tigerclub-login.js --code <6碼>');
  } else if (/index/.test(url)) {
    console.log('→ 直接進會員首頁，完成（session 保留，跑 member-jwt.js 驗證）');
  } else {
    console.log('page:', String(await ev(`document.body.innerText.replace(/\\s+/g,' ').slice(0,300)`)));
  }
}

async function phase2() {
  const tabId = fs.readFileSync(TABF, 'utf8').trim();
  const ev = async e => (await cf('POST', `/tabs/${tabId}/evaluate`, { userId: USER, expression: e })).result;
  const r2 = await ev(`(()=>{
    const set=(el,v)=>{const d=Object.getOwnPropertyDescriptor(el.constructor.prototype,'value');d.set.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));};
    const digits=[...document.querySelectorAll('input[type=number]')];
    if(digits.length<6) return 'no-digit-boxes:'+digits.length;
    const code=${JSON.stringify(CODE)};
    for(let i=0;i<6;i++) set(digits[i], code[i]);
    const cb=document.querySelector('input[type=checkbox]');
    if(cb && !cb.checked) cb.click();   // 信任此裝置
    return 'filled';
  })()`);
  console.log('fill:', r2);
  await sleep(800);
  console.log('confirm:', await ev(`(()=>{const b=[...document.querySelectorAll('button')].filter(x=>x.offsetParent&&/確認/.test(x.textContent))[0];if(!b)return 'no-button';b.click();return 'ok';})()`));
  await sleep(9000);
  const url = await ev('location.href');
  console.log('url:', url);
  if (/index/.test(url)) console.log('→ 登入完成（跑 member-jwt.js 驗證）');
  else console.log('page:', String(await ev(`document.body.innerText.replace(/\\s+/g,' ').slice(0,300)`)));
}

(CODE ? phase2() : phase1()).catch(e => { console.error('FAILED:', e.message); process.exit(1); });
