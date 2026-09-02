#!/usr/bin/env node
// 機型抽樣器：對每條航線用 Google Flights 查一個日期、展開全部航班詳情，
// 把「班號 → 機型／座椅間距」寫進 aircraft-map.json（可續跑、可定期重抽）。
//
//   node sample.js                 # 跑 routes.json 的 priority 段，30 天內抽過的跳過
//   node sample.js --all           # priority + rest
//   node sample.js --routes TPE-CTS,KHH-CJU --date 2026-11-01
//   node sample.js --max 50        # 這輪最多查幾條（timer 分批用）
//
// 資料形狀：{ "TPE-CTS": { "CI130": {airline, aircraft, pitch, cabin, dates:[…], lastSeen}, … }, … }
// 機型跟航線／班號綁定、久久才換（Tony 9/2），所以抽樣一次夠用一個月；GF 一次查詢就同時
// 拿到該航線所有航空的每一班（華航／星宇／虎航一起收），比各家 API 逐一問省太多。
'use strict';
const fs = require('fs'), path = require('path');
const { parse } = require('./parse');
const HERE = __dirname;
const MAP = path.join(HERE, 'aircraft-map.json');
const ROUTES = path.join(HERE, 'routes.json');
const BASE = process.env.CAMOFOX_URL || 'http://localhost:9377';
const USER = 'gfplane';
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 ? args[i + 1] : d; };
const MAX = +opt('--max', 400), FRESH_DAYS = +opt('--fresh', 30);
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function cf(m, p, b) {
  const r = await fetch(BASE + p, { method: m, headers: { 'content-type': 'application/json' }, body: b ? JSON.stringify(b) : undefined });
  const t = await r.text(); if (!r.ok) throw new Error(`${m} ${p} ${r.status}`); return t ? JSON.parse(t) : {};
}
function sampleDate() {
  // 預設：4 週後最近的星期三（避開週末尖峰班表差異）；--date 可指定
  const d = new Date(); d.setDate(d.getDate() + 28);
  while (d.getDay() !== 3) d.setDate(d.getDate() + 1);
  return d.toISOString().slice(0, 10);
}
(async () => {
  const map = fs.existsSync(MAP) ? JSON.parse(fs.readFileSync(MAP, 'utf8')) : {};
  const rj = JSON.parse(fs.readFileSync(ROUTES, 'utf8'));
  let routes = opt('--routes') ? opt('--routes').split(',') : rj.priority.concat(args.includes('--all') ? rj.rest : []);
  const date = opt('--date', sampleDate());
  const cutoff = Date.now() - FRESH_DAYS * 86400e3;
  routes = routes.filter(k => !(map[k] && map[k].__sampledAt && map[k].__sampledAt > cutoff));
  routes = routes.slice(0, MAX);
  console.log(`抽樣 ${routes.length} 條，日期 ${date}`);
  let tabId = null, n = 0;
  const open = async () => { const c = await cf('POST', '/tabs', { userId: USER, sessionKey: 'gf', url: 'https://www.google.com/travel/flights?hl=zh-TW&curr=TWD' }); tabId = c.tabId; await sleep(5000); };
  await open();
  for (const k of routes) {
    const [o, d] = k.split('-');
    try {
      await cf('POST', `/tabs/${tabId}/navigate`, { userId: USER, url: 'https://www.google.com/travel/flights?q=' + encodeURIComponent(`one way flights to ${d} from ${o} on ${date}`) + '&hl=zh-TW&curr=TWD' });
      await sleep(12000);
      // 先展開「顯示更多航班」（GF 預設只列部分），再把每班的詳細資料點開
      await cf('POST', `/tabs/${tabId}/evaluate`, { userId: USER, expression: `(()=>{const more=[...document.querySelectorAll('button')].filter(b=>/更多航班|顯示更多|其他航班/.test((b.getAttribute('aria-label')||'')+b.textContent)); more.forEach(b=>b.click()); return more.length;})()` }).catch(()=>{});
      await sleep(3000);
      await cf('POST', `/tabs/${tabId}/evaluate`, { userId: USER, expression: `(()=>{const bs=[...document.querySelectorAll('button[aria-label^="航班詳細資料"]')]; bs.forEach(b=>{ if(b.getAttribute('aria-expanded')!=='true') b.click(); }); return bs.length;})()` });
      await sleep(4000);
      const s = await cf('GET', `/tabs/${tabId}/snapshot?userId=${USER}`);
      const txt = typeof s === 'string' ? s : (s.snapshot || '');
      const segs = parse(txt).filter(x => x.dep === o && x.arr === d);   // 只收直飛這條航段
      const entry = map[k] || {};
      for (const x of segs) {
        const fn = x.code + x.num;
        const e = entry[fn] || { airline: x.airline, aircraft: x.aircraft, pitch: x.pitch, cabin: x.cabin, dates: [] };
        e.aircraft = x.aircraft; e.pitch = x.pitch ?? e.pitch; e.airline = x.airline;
        if (!e.dates.includes(date)) e.dates.push(date);
        e.lastSeen = date; entry[fn] = e;
      }
      entry.__sampledAt = Date.now();
      map[k] = entry;
      fs.writeFileSync(MAP, JSON.stringify(map, null, 1));
      const uniq = [...new Set(segs.map(x => x.code + x.num + ' ' + x.aircraft))];
      console.log(`${k}: ${segs.length} 班 → ${uniq.slice(0, 6).join(' | ')}${uniq.length > 6 ? ' …' : ''}`);
    } catch (e) {
      console.log(`${k}: ERR ${String(e.message).slice(0, 80)}`);
      try { await cf('DELETE', `/sessions/${USER}`); } catch {}
      await sleep(8000); await open();
    }
    if (++n % 25 === 0) { try { await cf('DELETE', `/sessions/${USER}`); } catch {} await sleep(20000); await open(); }
    await sleep(2500);
  }
  try { await cf('DELETE', `/sessions/${USER}`); } catch {}
  console.log('done', n);
})().catch(e => { console.error('FAILED', e.message); process.exit(1); });
