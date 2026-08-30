#!/usr/bin/env node
// 台灣虎航「含稅總價」查詢：daily-prices 只給未稅票價，含稅明細要走訂位引擎的
// appFlightSearchResult（有 fareAmount / taxAmount / totalAmount / remainingSeat）。
// 建立 session 需要 reCAPTCHA v3 token，所以在 camofox 頁面內執行整套 fetch。
//
//   node fare-detail.js KHH CTS 2026-10-30 [KHH CJU 2026-10-05 ...]
//
// 輸出 JSON 到 stdout；--out <file> 可另存。camofox 不在就直接失敗（非靜默）。
const BASE = 'http://localhost:9377';
// camofox session 名帶 PID：兩個查詢同時跑時不會互相 DELETE 掉對方的 session
const USER = process.env.TIGERAIR_CF_USER || `tigerair-${process.pid}`;
const SITEKEY = '6LeAFC4hAAAAANDlMutLdP9CLqWaUKYxEUMPb5L2';

async function cf(method, p, body) {
  const res = await fetch(BASE + p, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  const json = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(`camofox ${method} ${p} -> HTTP ${res.status} ${JSON.stringify(json).slice(0, 200)}`);
  return json;
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

// 在頁面內跑的函式：走完 waiting-room → recaptcha → create session → flight search result
const IN_PAGE = args => `(async () => {
  const { origin, destination, date, sitekey, adult } = ${JSON.stringify(args)};
  const deviceId = crypto.randomUUID();
  const H = {
    'Content-Type': 'application/json',
    'x-language': 'zh-TW',
    'x-device-id': deviceId,
    'x-requested-with': 'XMLHttpRequest',
  };
  const j = async (url, opt) => {
    const r = await fetch(url, opt);
    const t = await r.text();
    try { return JSON.parse(t); } catch { return { __status: r.status, __body: t.slice(0, 300) }; }
  };

  // 1. 排隊系統拿 token（平時秒過，促銷時就是真的在排隊）
  const WRH = { 'Content-Type': 'application/json', 'x-device-id': deviceId };
  const aq = await j('https://api-wr.tigerairtw.com/assign_queue_num',
    { method: 'POST', headers: WRH, body: JSON.stringify({ event_id: 'normal' }) });
  if (!aq.api_request_id) return { error: 'assign_queue_num failed', detail: aq };
  const gt = await j('https://api-wr.tigerairtw.com/generate_token',
    { method: 'POST', headers: WRH,
      body: JSON.stringify({ request_id: aq.api_request_id, event_id: 'normal' }) });
  if (!gt.access_token) return { error: 'generate_token failed', detail: gt };

  // 2. reCAPTCHA v3（action 跟官網搜尋鈕一致）
  // 官網自己載的是 render=explicit，grecaptcha.ready 不會為我們的 key 觸發，
  // 所以另外掛一支 render=<sitekey> 的 loader（同一個 key，同一頁）。
  if (!document.querySelector('script[data-tgrc]')) {
    await new Promise((res, rej) => {
      const s = document.createElement('script');
      s.dataset.tgrc = '1';
      s.src = 'https://www.google.com/recaptcha/api.js?render=' + sitekey;
      s.onload = res; s.onerror = () => rej(new Error('recaptcha loader failed'));
      document.head.appendChild(s);
    });
    await new Promise(r => setTimeout(r, 2500));
  }
  let rc2 = await new Promise((res, rej) => {
    grecaptcha.ready(() => grecaptcha.execute(sitekey, { action: 'submit' }).then(res, e => rej(new Error(String(e)))));
  });

  // 3. 建立航班搜尋 session
  let create, sid;
  for (let attempt = 0; attempt < 3 && !sid; attempt++) {
    if (attempt) {
      await new Promise(r => setTimeout(r, 1500));
      rc2 = await new Promise((res, rej) => {
        grecaptcha.ready(() => grecaptcha.execute(sitekey, { action: 'submit' }).then(res, e => rej(new Error(String(e)))));
      });
    }
  create = await j('https://api-book.tigerairtw.com/graphql', { method: 'POST', headers: H, body: JSON.stringify({
    query: \`mutation a($input: CreateFlightSearchSessionInput!) {
      appCreateFlightSearchSession(input: $input) { __typename ... on FlightSearchSession { id } }
    }\`,
    variables: { input: {
      adultCount: adult, childCount: 0, infantCount: 0,
      departureDate: date, stationPairs: [{ origin, destination }],
      userCurrency: 'TWD', flightType: 'oneWay',
      waitingRoomToken: gt.access_token, recaptchaTokenV3: rc2,
    } },
  }) });
    sid = create?.data?.appCreateFlightSearchSession?.id;
  }
  if (!sid) return { error: 'create session failed', detail: create };

  // 4. 取結果（含稅金明細與剩餘座位）
  const out = await j('https://api-book.tigerairtw.com/graphql', { method: 'POST', headers: H, body: JSON.stringify({
    query: \`query r($id: String!) {
      appFlightSearchResult(id: $id) {
        id
        journeys { legs { origin destination departureDate availabilityLegs {
          origin destination legSellKey duration
          availabilitySegments { origin destination departureTime arrivalTime carrierCode flightNumber
            availabilitySegmentDetails { remainingSeat totalSeat soldSeat } }
          fares { sellable availableCount productClass fareSellKey
            paxFares { paxType ticketPrice {
              userCurrency fareAmount taxAmount productClassAmount
              promotionDiscountAmount discountedFareAmount
              totalAmountWithoutTax discountedTotalAmountWithoutTax
              totalAmount discountedTotalAmount } } }
        } } }
      }
    }\`,
    variables: { id: sid },
  }) });
  return { sessionId: sid, result: out };
})()`;

async function main() {
  const args = process.argv.slice(2);
  const outIdx = args.indexOf('--out');
  let outFile = null;
  if (outIdx >= 0) { outFile = args[outIdx + 1]; args.splice(outIdx, 2); }
  const delayIdx = args.indexOf('--delay');
  let delay = 9000;
  if (delayIdx >= 0) { delay = parseInt(args[delayIdx + 1], 10) * 1000; args.splice(delayIdx, 2); }
  const adultIdx = args.indexOf('--adult');
  let adult = 1;
  if (adultIdx >= 0) { adult = parseInt(args[adultIdx + 1], 10); args.splice(adultIdx, 2); }
  if (args.length < 3 || args.length % 3) {
    console.error('用法: node fare-detail.js <ORIG> <DEST> <YYYY-MM-DD> [...] [--adult N] [--delay 秒] [--out file]');
    process.exit(1);
  }
  const jobs = [];
  for (let i = 0; i < args.length; i += 3) {
    jobs.push({ origin: args[i].toUpperCase(), destination: args[i + 1].toUpperCase(), date: args[i + 2] });
  }

  const results = [];
  let tabId = null;
  const openTab = async () => {
    const created = await cf('POST', '/tabs', {
      userId: USER, sessionKey: 'tg', url: 'https://booking.tigerairtw.com/zh-TW',
    });
    tabId = created.tabId;
    await sleep(7000);   // 等 grecaptcha 載入
  };
  try {
    await openTab();
    for (let i = 0; i < jobs.length; i++) {
      const job = jobs[i];
      if (i) {
        // 每筆都重新載入頁面：連續在同一個頁面 context 建 session，
        // reCAPTCHA v3 的分數會一路掉，大約第 10 筆之後就開始被判定失敗。
        try {
          await cf('POST', `/tabs/${tabId}/navigate`, { userId: USER, url: 'https://booking.tigerairtw.com/zh-TW' });
          await sleep(delay);
        } catch { await cf('DELETE', `/sessions/${USER}`).catch(() => {}); await openTab(); }
      }
      let r;
      try {
        const res = await cf('POST', `/tabs/${tabId}/evaluate`, {
          userId: USER, expression: IN_PAGE({ ...job, sitekey: SITEKEY, adult }),
        });
        r = res.result;
      } catch (e) { r = { error: String(e.message).slice(0, 200) }; }
      // reCAPTCHA 被判失敗時，整個 session 重開再試一次（換 IP 沒辦法，至少換 context）
      if (r && r.error && JSON.stringify(r.detail || '').includes('ecaptcha')) {
        await cf('DELETE', `/sessions/${USER}`).catch(() => {});
        await sleep(20000);
        await openTab();
        try {
          const res = await cf('POST', `/tabs/${tabId}/evaluate`, {
            userId: USER, expression: IN_PAGE({ ...job, sitekey: SITEKEY, adult }),
          });
          r = res.result;
        } catch (e) { r = { error: String(e.message).slice(0, 200) }; }
      }
      results.push({ ...job, raw: r });
      console.error(`[${i + 1}/${jobs.length}] ${job.origin}-${job.destination} ${job.date} `
        + (r && r.error ? `FAIL ${r.error}` : 'ok'));
      if (outFile) require('fs').writeFileSync(outFile, JSON.stringify(results, null, 1));
    }
  } finally {
    if (tabId) { try { await cf('DELETE', `/sessions/${USER}`); } catch {} }
  }
  const text = JSON.stringify(results, null, 1);
  if (outFile) require('fs').writeFileSync(outFile, text);
  console.log(text);
}
main().catch(e => { console.error(e); process.exit(1); });
