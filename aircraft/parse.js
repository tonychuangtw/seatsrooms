// 解析 Google Flights 展開後的 snapshot：每段航程一行
//   「下午6:15·臺灣桃園國際機場 (TPE) 路程時間：… 晚上9:45·關西國際機場 (KIX) 捷星日本航空 · 經濟艙 · Airbus A320 · GK 54」
// 後面的 listitem 可能有「腿部活動空間較窄 (74 公分)」。回 [{dep,arr,airline,cabin,aircraft,code,num,pitch}]
'use strict';
function parse(txt){
  const lines = txt.split('\n');
  const out = [];
  // 每段：「(TPE) 路程時間：… (CTS) 中華航空 · 經濟艙 · Boeing 777 · CI 130」，轉機時一行多段
  const segRe = /\(([A-Z]{3})\) 路程時間：.*?\(([A-Z]{3})\) ([^·\n]+?) · ([^·\n]+?) · ([^·\n]+?) · ([A-Z0-9]{2}) (\d{1,4})/g;
  for (let i = 0; i < lines.length; i++) {
    const l = lines[i];
    if (!/- text: /.test(l)) continue;
    let m; segRe.lastIndex = 0;
    const segs = [];
    while ((m = segRe.exec(l))) segs.push(m);
    if (!segs.length) continue;
    // 座椅間距：接下來的 listitem（多段時只能配到最後一段，前段給 null）
    let pitch = null;
    for (let j = i + 1; j < Math.min(i + 8, lines.length); j++) {
      const pm = lines[j].match(/腿部活動空間[^\(]*\((\d+) 公分\)/);
      if (pm) { pitch = +pm[1]; break; }
      if (/- text: /.test(lines[j])) break;
    }
    segs.forEach((m, idx) => out.push({ dep: m[1], arr: m[2], airline: m[3].trim(), cabin: m[4].trim(),
      aircraft: m[5].trim(), code: m[6], num: m[7], pitch: idx === segs.length - 1 ? pitch : null }));
  }
  return out;
}
module.exports = { parse };
if (require.main === module) {
  const txt = require('fs').readFileSync(process.argv[2], 'utf8');
  const segs = parse(txt);
  console.log(segs.length, 'segments');
  for (const s of segs) console.log(`${s.dep}-${s.arr} ${s.code}${s.num} ${s.airline} ${s.aircraft} ${s.pitch ? s.pitch + 'cm' : ''}`);
}
