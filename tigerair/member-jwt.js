#!/usr/bin/env node
// 取 TigerClub 會員 JWT（book_ibe_app_jwt，12 小時效期）。
// tigerclub profile 是信任裝置＋membership session 常駐，載入訂位頁就會自動換新 JWT，
// 不經過 reCAPTCHA。拿到的 token 給 fare-detail.js --jwt 用（查價 profile 自由輪替）。
//
//   node member-jwt.js            # 印 JWT 到 stdout（exp 資訊到 stderr）
const BASE = process.env.CAMOFOX_URL || 'http://localhost:9377';
const USER = 'tigerclub';
async function cf(m, p, b) {
  const r = await fetch(BASE + p, { method: m, headers: { 'content-type': 'application/json' },
    body: b ? JSON.stringify(b) : undefined });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`camofox ${m} ${p} -> ${r.status}`);
  return j;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));
(async () => {
  const { tabId } = await cf('POST', '/tabs', {
    userId: USER, sessionKey: 'jwt', url: 'https://booking.tigerairtw.com/zh-TW' });
  let jwt = null;
  for (let i = 0; i < 6 && !jwt; i++) {
    await sleep(4000);
    const r = await cf('POST', `/tabs/${tabId}/evaluate`, { userId: USER,
      expression: `(document.cookie.match(/book_ibe_app_jwt=([^;]+)/)||[])[1]||''` });
    jwt = r.result || null;
  }
  await cf('DELETE', `/sessions/${USER}`).catch(() => {});
  if (!jwt) { console.error('沒拿到 JWT：tigerclub profile 可能沒登入了（重跑 tigerclub-login）'); process.exit(1); }
  jwt = decodeURIComponent(jwt);
  try {
    const p = JSON.parse(Buffer.from(jwt.split('.')[1], 'base64url').toString());
    console.error(`memberNo ${p.memberNo}，效期到 ${new Date(p.exp * 1000).toLocaleString('zh-TW', { timeZone: 'Asia/Taipei' })} 台北`);
  } catch {}
  console.log(jwt);
})().catch(e => { console.error('FAILED:', e.message); process.exit(1); });
