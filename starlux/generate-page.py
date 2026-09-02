#!/usr/bin/env python3
"""把星宇掃描結果做成一頁「每日價格日曆」。

  python3 generate-page.py baseline.json network.json out.html

跟虎航版的差別：星宇日曆給的就是含稅總價，所以沒有稅金欄位；
機場中文名與航線圖都來自 network.json（scan.py 從官網 airports API 抓的）。
"""
import json, sys, datetime, collections

fares = json.load(open(sys.argv[1]))
NET = json.load(open(sys.argv[2]))
CITY = NET.get("names", {})
COUNTRY = NET.get("countries", {})
out_path = sys.argv[3] if len(sys.argv) > 3 else "starlux-prices.html"
try:
    RT = json.load(open(sys.argv[4] if len(sys.argv) > 4 else "baseline-rt.json"))["routes"]
except Exception:
    RT = {}

TW = ("TPE", "RMQ", "KHH", "TNN")

routes = collections.defaultdict(dict)
for r in fares:
    routes[f"{r['origin']}-{r['destination']}"][r["date"]] = r.get("twd") or r["amount"]

data = {}
for k, days in routes.items():
    o, d = k.split("-")
    data[k] = {"o": o, "d": d,
               "on": CITY.get(o, o), "dn": CITY.get(d, d),
               "oc": "TW" if o in TW else "OTHER",
               "dc": COUNTRY.get(d, "其他"),
               "tax": None, "days": days}

all_dates = sorted({dt for v in data.values() for dt in v["days"]})
scanned = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") + " 台北"
CARRIERS = ['JX']
# 機型表（aircraft/aircraft-map.json，GF 抽樣）：只取本航空的班號
AC = {}
try:
    _acm = json.load(open(__file__.rsplit("/", 1)[0] + "/../aircraft/aircraft-map.json"))
    for _k, _v in _acm.items():
        _rows = [{"fn": fn, "aircraft": x["aircraft"], "pitch": x.get("pitch"), "seen": x.get("lastSeen")}
                 for fn, x in _v.items() if not fn.startswith("__") and fn[:2] in CARRIERS]
        if _rows:
            AC[_k] = sorted(_rows, key=lambda r: r["fn"])
except Exception:
    pass
payload = json.dumps({"routes": data, "from": all_dates[0], "to": all_dates[-1],
                      "scanned": scanned, "ac": AC,
                      "rt": {k: {"go": v["go"], "ret": v["ret"]} for k, v in RT.items()}},
                     ensure_ascii=False, separators=(",", ":"))

HTML = """<title>星宇價格日曆</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>
:root{
  --paper:#E9ECEF; --card:#FFFFFF; --sunk:#F3F5F7;
  --ink:#13181D; --muted:#5A646F; --faint:#8A939D;
  --rule:#D3D9DF; --rule-soft:#E3E8EC;
  --amber:#C86A10; --amber-soft:#F3E2CC;
  --cheap:#0C5F58; --cheap-bg:#CFE6E1;
  --mid-bg:#E6E9EC;
  --dear:#9B3524; --dear-bg:#F0D6CF;
  --shadow:0 1px 2px rgba(19,24,29,.06),0 8px 24px -12px rgba(19,24,29,.18);
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#0D1114; --card:#151A1F; --sunk:#11161A;
    --ink:#E3E8EC; --muted:#8B959F; --faint:#68737D;
    --rule:#242B32; --rule-soft:#1D242A;
    --amber:#E59A47; --amber-soft:#3A2A15;
    --cheap:#6FCBBC; --cheap-bg:#123832;
    --mid-bg:#1D242A;
    --dear:#E08A76; --dear-bg:#3A1F19;
    --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.7);
  }
}
:root[data-theme="dark"]{
  --paper:#0D1114; --card:#151A1F; --sunk:#11161A;
  --ink:#E3E8EC; --muted:#8B959F; --faint:#68737D;
  --rule:#242B32; --rule-soft:#1D242A;
  --amber:#E59A47; --amber-soft:#3A2A15;
  --cheap:#6FCBBC; --cheap-bg:#123832;
  --mid-bg:#1D242A;
  --dear:#E08A76; --dear-bg:#3A1F19;
  --shadow:0 1px 2px rgba(0,0,0,.4),0 8px 24px -12px rgba(0,0,0,.7);
}
*{box-sizing:border-box}
body{
  margin:0; background:var(--paper); color:var(--ink);
  font-family:"IBM Plex Sans",system-ui,"Noto Sans TC",sans-serif;
  font-size:15px; line-height:1.55; -webkit-font-smoothing:antialiased;
}
.wrap{max-width:1180px; margin:0 auto; padding:0 20px 72px}

/* ── 出境看板式頁首 ─────────────────────── */
header{
  border-bottom:2px solid var(--ink);
  padding:34px 0 18px; margin-bottom:26px;
}
.kicker{
  font-family:"Barlow Condensed",system-ui,sans-serif;
  font-size:14px; font-weight:600; letter-spacing:.18em;
  text-transform:uppercase; color:var(--amber); margin:0 0 4px;
}
h1{
  font-family:"Barlow Condensed",system-ui,"Noto Sans TC",sans-serif;
  font-weight:700; font-size:clamp(38px,7vw,62px); line-height:.95;
  letter-spacing:-.005em; margin:0; text-wrap:balance;
}
.sub{color:var(--muted); margin:10px 0 0; max-width:62ch; font-size:14.5px}
.meta{
  display:flex; flex-wrap:wrap; gap:8px 22px; margin-top:16px;
  font-family:"IBM Plex Mono",ui-monospace,monospace;
  font-size:12px; color:var(--faint); letter-spacing:.02em;
}
.meta b{color:var(--muted); font-weight:500}

/* ── 航線選擇 ────────────────────────────── */
.picker{
  background:var(--card); border:1px solid var(--rule); border-radius:3px;
  box-shadow:var(--shadow); padding:16px 18px 18px; margin-bottom:26px;
}
.picker h2, .board h2, .allroutes h2{
  font-family:"Barlow Condensed",system-ui,sans-serif;
  font-size:13px; font-weight:600; letter-spacing:.16em; text-transform:uppercase;
  color:var(--muted); margin:0 0 12px;
}
.grp{display:flex; align-items:flex-start; gap:12px; padding:7px 0; border-top:1px solid var(--rule-soft)}
.grp:first-of-type{border-top:0}
.grp-label{
  flex:0 0 74px; font-family:"IBM Plex Mono",monospace; font-size:11.5px;
  color:var(--faint); letter-spacing:.06em; padding-top:5px;
}
.chips{display:flex; flex-wrap:wrap; gap:5px}
button.chip{
  font:inherit; font-size:13px; cursor:pointer;
  background:var(--sunk); color:var(--ink);
  border:1px solid var(--rule); border-radius:2px;
  padding:4px 9px; display:inline-flex; align-items:baseline; gap:5px;
  transition:background .12s,border-color .12s,color .12s;
}
button.chip .code{font-family:"IBM Plex Mono",monospace; font-size:11px; color:var(--faint); letter-spacing:.04em}
button.chip:hover{border-color:var(--amber)}
button.chip:focus-visible{outline:2px solid var(--amber); outline-offset:2px}
button.chip[aria-pressed="true"]{background:var(--ink); color:var(--paper); border-color:var(--ink)}
button.chip[aria-pressed="true"] .code{color:var(--paper); opacity:.62}
.dirtoggle{display:flex; gap:5px; margin-top:14px; padding-top:12px; border-top:1px solid var(--rule-soft)}

/* ── 摘要條 ─────────────────────────────── */
.summary{
  display:flex; flex-wrap:wrap; gap:0; margin-bottom:22px;
  background:var(--card); border:1px solid var(--rule); border-radius:3px;
  box-shadow:var(--shadow); overflow:hidden;
}
.stat{flex:1 1 150px; padding:14px 18px; border-left:1px solid var(--rule-soft)}
.stat:first-child{border-left:0}
.stat .lab{
  font-family:"Barlow Condensed",sans-serif; font-size:12px; font-weight:600;
  letter-spacing:.14em; text-transform:uppercase; color:var(--faint);
}
.stat .val{
  font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums;
  font-size:25px; font-weight:600; line-height:1.25; margin-top:2px;
}
.stat .note{font-size:12px; color:var(--muted); margin-top:1px}
.stat.hi .val{color:var(--cheap)}

/* ── 月曆 ───────────────────────────────── */
.cals{display:grid; grid-template-columns:repeat(auto-fill,minmax(310px,1fr)); gap:16px}
.cal{background:var(--card); border:1px solid var(--rule); border-radius:3px; box-shadow:var(--shadow); padding:14px 14px 16px}
.cal h3{
  font-family:"Barlow Condensed",sans-serif; font-size:17px; font-weight:600;
  letter-spacing:.06em; margin:0 0 10px; display:flex; justify-content:space-between; align-items:baseline;
}
.cal h3 span{font-family:"IBM Plex Mono",monospace; font-size:11px; color:var(--faint); font-weight:400; letter-spacing:0}
.dow{display:grid; grid-template-columns:repeat(7,1fr); gap:3px; margin-bottom:3px}
.dow div{
  text-align:center; font-family:"IBM Plex Mono",monospace; font-size:10px;
  color:var(--faint); letter-spacing:.05em; padding-bottom:2px;
}
.dow div.we{color:var(--amber)}
.days{display:grid; grid-template-columns:repeat(7,1fr); gap:3px}
.day{
  aspect-ratio:1/.92; border-radius:2px; background:var(--sunk);
  display:flex; flex-direction:column; align-items:center; justify-content:center;
  gap:1px; padding:2px; border:1px solid transparent;
}
.day.empty{background:transparent}
.day .dnum{font-family:"IBM Plex Mono",monospace; font-size:10px; color:var(--faint); line-height:1}
.day .p{
  font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums;
  font-size:12px; font-weight:600; line-height:1.1;
}
.day .p small{font-size:9.5px; font-weight:400; opacity:.72; display:block}
.day.none .p{color:var(--faint); font-weight:400; font-size:11px}
.day.q1{background:var(--cheap-bg)} .day.q1 .p{color:var(--cheap)}
.day.q2{background:var(--mid-bg)}
.day.q3{background:var(--dear-bg)} .day.q3 .p{color:var(--dear)}
.day.best{border-color:var(--cheap); box-shadow:inset 0 0 0 1px var(--cheap)}

/* ── 最便宜看板 ─────────────────────────── */
.board,.allroutes{
  background:var(--card); border:1px solid var(--rule); border-radius:3px;
  box-shadow:var(--shadow); padding:16px 18px 18px; margin:26px 0;
}
.tblwrap{overflow-x:auto}
table{border-collapse:collapse; width:100%; font-size:13.5px}
th,td{text-align:right; padding:6px 10px; border-bottom:1px solid var(--rule-soft); white-space:nowrap}
th{
  font-family:"Barlow Condensed",sans-serif; font-size:12px; font-weight:600;
  letter-spacing:.12em; text-transform:uppercase; color:var(--faint);
  border-bottom:1px solid var(--rule);
}
th:first-child,td:first-child,th.l,td.l{text-align:left}
td.num{font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums}
td.tot{font-weight:600}
tbody tr:hover td{background:var(--sunk)}
.dow-tag{font-family:"IBM Plex Mono",monospace; font-size:11px; color:var(--faint)}
.dow-tag.we{color:var(--amber)}
.rt-name{font-size:12px; color:var(--muted); margin-left:6px}

.legend{display:flex; flex-wrap:wrap; gap:14px; margin-top:12px; font-size:12px; color:var(--muted)}
.legend i{display:inline-block; width:11px; height:11px; border-radius:2px; margin-right:5px; vertical-align:-1px}
footer{margin-top:34px; padding-top:16px; border-top:1px solid var(--rule); font-size:12.5px; color:var(--faint)}
footer p{margin:0 0 6px; max-width:78ch}
@media (max-width:640px){
  .grp{flex-direction:column; gap:4px}
  .grp-label{flex:none; padding-top:0}
  .stat{flex:1 1 50%}
}
</style>

<div class="wrap">
<header>
  <p class="kicker">STARLUX · 自營航線每日最低價</p>
  <h1>星宇價格日曆</h1>
  <p class="sub">星宇官網的月票價日曆給的就是<b>含稅總價</b>（實測 TPE→NRT 日曆 8,574
     ＝ 票價 6,170 ＋ 稅 2,404），所以這頁不用再加稅。海外出發航段官網以當地幣別報價
     （澳門幣、日圓、美元…），這裡一律換算成台幣。經濟艙、單人、單程；行李與選位另計。</p>
  <div class="meta">
    <span><b>掃描時間</b> __SCANNED__</span>
    <span><b>涵蓋</b> __FROM__ → __TO__</span>
    <span><b>航向</b> __NROUTES__ 條</span>
    <span><b>有票日期</b> __NDAYS__ 筆</span>
    <span><b>稅金已量</b> __NTAX__ / __NROUTES__ 條航向</span>
  </div>
</header>

<section class="picker">
  <h2>選航線</h2>
  <div id="groups"></div>
  <div class="dirtoggle" id="dirtoggle">
    <button class="chip" id="btn-out" aria-pressed="true">去程</button>
    <button class="chip" id="btn-ret" aria-pressed="false">回程</button>
  </div>
  <div class="dirtoggle" id="modechips" style="flex-wrap:wrap;align-items:center">
    <button class="chip" data-n="0" aria-pressed="true">單程</button>
    <button class="chip" data-n="2">來回 3天2夜</button>
    <button class="chip" data-n="3">來回 4天3夜</button>
    <button class="chip" data-n="4">來回 5天4夜</button>
    <button class="chip" data-n="5">來回 6天5夜</button>
    <label class="chip" style="gap:6px">自訂 <input id="nights-in" type="number" min="1" max="60" value="7" style="width:54px;font:inherit;padding:1px 4px"> 晚</label>
  </div>
  <p class="sub" id="rtnote" style="display:none;font-size:12.5px;margin-top:10px">來回總價 = 去程段 ＋ 回程段（已用官網全程總價驗證）。回程段依「最便宜去程艙等桶」估算：便宜的出發日算得準，貴的出發日可能略微樂觀幾百元；下訂前以官網為準。來回只掃台灣出發的航線。</p>
</section>

<section class="board" id="combo-card" style="display:none">
  <h2>找最便宜的去回組合</h2>
  <div class="chips" style="align-items:center;gap:10px">
    <label>最少 <input id="c-min" type="number" min="1" max="60" value="2" style="width:54px;font:inherit"> 晚</label>
    <label>最多 <input id="c-max" type="number" min="1" max="60" value="6" style="width:54px;font:inherit"> 晚</label>
    <label>出發月 <input id="c-month" type="month" style="font:inherit"></label>
    <button class="chip" id="c-go">找</button>
  </div>
  <div class="tblwrap" style="margin-top:12px"><table id="combo">
    <thead><tr><th class="l">出發</th><th class="l">回程</th><th>晚數</th><th>去程</th><th>回程</th><th>來回總價</th></tr></thead>
    <tbody></tbody>
  </table></div>
</section>

<div class="summary" id="summary"></div>
<div class="cals" id="cals"></div>

<section class="board">
  <h2>這條航線最便宜的 20 天</h2>
  <div class="tblwrap"><table id="best">
    <thead id="best-head"><tr><th class="l">日期</th><th class="l">星期</th><th>含稅總價</th></tr></thead>
    <tbody></tbody>
  </table></div>
</section>

<section class="allroutes">
  <h2>全航線最低價一覽</h2>
  <div class="tblwrap"><table id="all">
    <thead><tr><th class="l">航線</th><th>含稅總價</th><th class="l">最便宜那天</th></tr></thead>
    <tbody></tbody>
  </table></div>
  <div class="legend">
    <span><i style="background:var(--cheap-bg)"></i>該航線最便宜的三分之一</span>
    <span><i style="background:var(--mid-bg)"></i>中間</span>
    <span><i style="background:var(--dear-bg)"></i>最貴的三分之一</span>
    <span><i style="background:var(--sunk)"></i>當天沒班機</span>
  </div>
</section>

<footer>
  <p>資料來源：星宇航空官網的月票價日曆（公開查詢，無需登入）。價格已含稅費，
     以經濟艙、一位大人、單程計；行李與選位另計。</p>
  <p>可訂期間約未來 12 個月，超出的月份官網會直接擋掉。價格隨時可能變動，
     實際以官網下訂當下為準。</p>
</footer>
</div>

<script>
const DATA = __PAYLOAD__;
const R = DATA.routes;
const fmt = n => n.toLocaleString('en-US');
const WD = ['日','一','二','三','四','五','六'];
const first = Object.keys(R).filter(k=>R[k].oc==='TW').sort((a,b)=>Object.keys(R[b].days).length-Object.keys(R[a].days).length)[0].split('-');
const state = { origin:first[0], dest:first[1], dir:'out', nights:0 };
const AC = DATA.ac || {};   // 航線→[{fn,aircraft,pitch,seen}]，GF 抽樣（aircraft/sample.js）
function acHtml(k){ const a=AC[k]; if(!a||!a.length) return '';
  const seen=a.map(x=>x.seen).sort().pop();
  const items=a.map(x=>'<b>'+x.fn+'</b> '+x.aircraft+(x.pitch?'<small style="opacity:.7">（座距 '+x.pitch+'cm）</small>':'')).join(' · ');
  return '<div class="stat" style="flex:1 1 100%"><div class="lab">執飛機型 · GF 抽樣 '+(seen||'').slice(5).replace('-','/')+'</div><div class="val" style="font-size:15px;line-height:1.5;font-family:inherit">'+items+'</div><div class="note">機型跟航線班號綁定，換季才會變；抽樣日沒飛的班次不會列出</div></div>'; }
const RT = DATA.rt || {};
const addDays = (iso,n) => { const d=new Date(iso+'T00:00:00Z'); d.setUTCDate(d.getUTCDate()+n); return d.toISOString().slice(0,10); };
function rtDays(k,n){ const v=RT[k]; if(!v) return null; const out={}; let any=false;
  for(const d of Object.keys(v.go)){ const rd=addDays(d,n), r=v.ret[rd]; if(r){ out[d]={t:v.go[d]+r,g:v.go[d],r:r,rd:rd}; any=true; } }
  return any?out:null; }
function curDays(){ const k=key();
  if(state.nights>0){ const m=rtDays(k,state.nights); if(!m) return null;
    const days={}; for(const d of Object.keys(m)) days[d]=m[d].t; return {days, rt:m}; }
  return R[k] ? {days:R[k].days, rt:null} : null; }

function key(){ return state.dir==='out' ? state.origin+'-'+state.dest : state.dest+'-'+state.origin; }

function buildGroups(){
  const box = document.getElementById('groups');
  const origins = ['TPE','RMQ','KHH','TNN'].filter(o=>Object.values(R).some(v=>v.o===o));
  const oRow = document.createElement('div');
  oRow.className = 'grp';
  oRow.innerHTML = '<div class="grp-label">台灣</div>';
  const oChips = document.createElement('div'); oChips.className='chips';
  origins.forEach(o=>{
    const b=document.createElement('button'); b.className='chip'; b.dataset.o=o;
    const any = Object.values(R).find(v=>v.o===o);
    b.innerHTML = (any?any.on:o)+' <span class="code">'+o+'</span>';
    b.onclick=()=>{ state.origin=o; const ds=dests(o); if(!ds.includes(state.dest)) state.dest=ds[0]; render(); };
    oChips.appendChild(b);
  });
  oRow.appendChild(oChips); box.appendChild(oRow);
  box.appendChild(Object.assign(document.createElement('div'),{id:'destbox'}));
}

function dests(o){
  return Object.values(R).filter(v=>v.o===o).map(v=>v.d)
    .filter((v,i,a)=>a.indexOf(v)===i);
}

function buildDests(){
  const box = document.getElementById('destbox');
  box.innerHTML='';
  const byC = {};
  dests(state.origin).forEach(d=>{
    const v = R[state.origin+'-'+d];
    (byC[v.dc] = byC[v.dc] || []).push(d);
  });
  Object.keys(byC).sort((a,b)=>byC[b].length-byC[a].length||a.localeCompare(b)).forEach(c=>{
    const row=document.createElement('div'); row.className='grp';
    row.innerHTML='<div class="grp-label">'+c+'</div>';
    const chips=document.createElement('div'); chips.className='chips';
    byC[c].forEach(d=>{
      const v=R[state.origin+'-'+d];
      const b=document.createElement('button'); b.className='chip';
      b.setAttribute('aria-pressed', d===state.dest);
      b.innerHTML = v.dn+' <span class="code">'+d+'</span>';
      b.onclick=()=>{ state.dest=d; render(); };
      chips.appendChild(b);
    });
    row.appendChild(chips); box.appendChild(row);
  });
}

function render(){
  document.querySelectorAll('#groups > .grp:first-child .chip')
    .forEach(b=>b.setAttribute('aria-pressed', b.dataset.o===state.origin));
  buildDests();
  document.getElementById('btn-out').setAttribute('aria-pressed', state.dir==='out');
  document.getElementById('btn-ret').setAttribute('aria-pressed', state.dir==='ret');

  const rt = state.nights>0;
  if(rt) state.dir='out';
  document.getElementById('dirtoggle').style.display = rt?'none':'';
  document.getElementById('rtnote').style.display = rt?'':'none';
  document.getElementById('combo-card').style.display = rt?'':'none';
  document.querySelectorAll('#modechips .chip[data-n]').forEach(b=>b.setAttribute('aria-pressed', +b.dataset.n===state.nights));
  document.getElementById('best-head').innerHTML = rt
    ? '<tr><th class="l">出發</th><th class="l">星期</th><th class="l">回程</th><th>去程</th><th>回程</th><th>來回總價</th></tr>'
    : '<tr><th class="l">日期</th><th class="l">星期</th><th>含稅總價</th></tr>';
  const k = key(), curD = curDays(), v = curD;
  const cals = document.getElementById('cals');
  const sum = document.getElementById('summary');
  const bestBody = document.querySelector('#best tbody');
  if(!v){
    sum.innerHTML='<div class="stat"><div class="lab">這個方向</div><div class="val">—</div><div class="note">'+(rt?'這條航線沒有來回資料':'沒有掃到票價')+'</div></div>';
    cals.innerHTML=''; bestBody.innerHTML=''; return;
  }
  const days = v.days, tax = null;
  const prices = Object.values(days).sort((a,b)=>a-b);
  const lo = prices[0], hi = prices[prices.length-1];
  const q1 = prices[Math.floor(prices.length/3)], q2 = prices[Math.floor(prices.length*2/3)];
  const med = prices[Math.floor(prices.length/2)];
  const T = n => tax==null ? null : n+tax;

  sum.innerHTML = [
    ['最低價', lo, rt?('含稅來回 '+(state.nights+1)+'天'+state.nights+'夜'):'含稅 · 單人單程', true],
    ['中位數', (T(med)??med), '一半的日子比這便宜', false],
    ['最高價', (T(hi)??hi), '整段期間最貴的一天', false],
    ['有票天數', Object.keys(days).length, DATA.from+' → '+DATA.to, false],
  ].map(([lab,val,note,hi2])=>
    '<div class="stat'+(hi2?' hi':'')+'"><div class="lab">'+lab+'</div><div class="val">'+
    (lab==='有票天數'? val : fmt(val))+'</div><div class="note">'+note+'</div></div>').join('');
  sum.insertAdjacentHTML('beforeend', acHtml(key()));

  // 月曆
  const months = [...new Set(Object.keys(days).map(d=>d.slice(0,7)))].sort();
  const allMonths = [];
  let cur = DATA.from.slice(0,7), end = DATA.to.slice(0,7);
  while(cur <= end){ allMonths.push(cur);
    let [y,m]=cur.split('-').map(Number); m++; if(m>12){m=1;y++;}
    cur = y+'-'+String(m).padStart(2,'0'); }

  cals.innerHTML = allMonths.map(ym=>{
    const [y,m]=ym.split('-').map(Number);
    const first=new Date(Date.UTC(y,m-1,1)).getUTCDay();
    const ndays=new Date(Date.UTC(y,m,0)).getUTCDate();
    const inMonth = Object.entries(days).filter(([d])=>d.startsWith(ym));
    const mLo = inMonth.length? Math.min(...inMonth.map(x=>x[1])) : null;
    let cells='';
    for(let i=0;i<first;i++) cells+='<div class="day empty"></div>';
    for(let d=1; d<=ndays; d++){
      const iso = ym+'-'+String(d).padStart(2,'0');
      const p = days[iso];
      if(p===undefined){
        cells+='<div class="day none"><div class="dnum">'+d+'</div><div class="p">–</div></div>';
      } else {
        const cls = p<=q1?'q1':(p>=q2?'q3':'q2');
        const best = (p===mLo && p<=q1) ? ' best':'';
        const tot = T(p);
        cells+='<div class="day '+cls+best+'"><div class="dnum">'+d+'</div><div class="p">'+
               fmt(p)+'</div></div>';
      }
    }
    const label = y+'年'+m+'月';
    return '<div class="cal"><h3>'+label+'<span>'+(mLo!=null? '最低 '+fmt(T(mLo)??mLo) : '無班機')+'</span></h3>'+
      '<div class="dow"><div class="we">日</div><div>一</div><div>二</div><div>三</div><div>四</div><div>五</div><div class="we">六</div></div>'+
      '<div class="days">'+cells+'</div></div>';
  }).join('');

  // 最便宜 20 天
  bestBody.innerHTML = Object.entries(days).sort((a,b)=>a[1]-b[1]).slice(0,20).map(([d,p])=>{
    const wd = new Date(d+'T00:00:00Z').getUTCDay();
    const we = (wd===0||wd===6)?' we':'';
    if(rt){ const x=curD.rt[d];
      return '<tr><td class="l num">'+d+'</td><td class="l dow-tag'+we+'">'+WD[wd]+'</td><td class="l num">'+x.rd+'</td>'+
        '<td class="num">'+fmt(x.g)+'</td><td class="num">'+fmt(x.r)+'</td><td class="num tot">'+fmt(x.t)+'</td></tr>'; }
    return '<tr><td class="l num">'+d+'</td><td class="l dow-tag'+we+'">'+WD[wd]+'</td>'+
      '<td class="num tot">'+fmt(p)+'</td></tr>';
  }).join('');
}

function findCombos(){
  const v=RT[key()], body=document.querySelector('#combo tbody');
  if(!v){ body.innerHTML='<tr><td colspan="6" class="l">這條航線沒有來回資料</td></tr>'; return; }
  const mn=Math.max(1,+document.getElementById('c-min').value||1), mx=Math.max(mn,+document.getElementById('c-max').value||mn);
  const ym=document.getElementById('c-month').value; const out=[];
  for(const d of Object.keys(v.go)){ if(ym && !d.startsWith(ym)) continue;
    for(let n=mn;n<=mx;n++){ const rd=addDays(d,n), r=v.ret[rd]; if(r) out.push({d,rd,n,g:v.go[d],r,t:v.go[d]+r}); } }
  out.sort((a,b)=>a.t-b.t||a.d.localeCompare(b.d));
  body.innerHTML = out.length ? out.slice(0,15).map(x=>{ const wd=new Date(x.d+'T00:00:00Z').getUTCDay();
    return '<tr><td class="l num">'+x.d+'（'+WD[wd]+'）</td><td class="l num">'+x.rd+'</td><td class="num">'+x.n+'</td>'+
      '<td class="num">'+fmt(x.g)+'</td><td class="num">'+fmt(x.r)+'</td><td class="num tot">'+fmt(x.t)+'</td></tr>'; }).join('')
    : '<tr><td colspan="6" class="l">這個範圍沒有可組合的日期</td></tr>';
}

function buildAll(){
  const rt = state.nights>0;
  const entries = rt
    ? Object.keys(RT).map(k=>{ const m=rtDays(k,state.nights); if(!m||!R[k]) return null; const days={}; for(const d of Object.keys(m)) days[d]=m[d].t; return [k,{...R[k],days}]; }).filter(Boolean)
    : Object.entries(R);
  const rows = entries.map(([k,v])=>{
    const e = Object.entries(v.days).sort((a,b)=>a[1]-b[1])[0];
    return {k, v, date:e[0], p:e[1], tot: null};
  }).sort((a,b)=> (a.tot??a.p)-(b.tot??b.p));
  document.querySelector('#all tbody').innerHTML = rows.map(r=>
    '<tr><td class="l"><b>'+r.k+'</b><span class="rt-name">'+r.v.on+' → '+r.v.dn+'</span></td>'+
    '<td class="num tot">'+fmt(r.p)+'</td>'+
    '<td class="l num">'+r.date+'</td></tr>').join('');
}

document.getElementById('btn-out').onclick=()=>{ state.dir='out'; render(); };
document.getElementById('btn-ret').onclick=()=>{ state.dir='ret'; render(); };
document.querySelectorAll('#modechips .chip[data-n]').forEach(b=>{ b.onclick=()=>{ state.nights=+b.dataset.n; buildAll(); render(); }; });
document.getElementById('nights-in').onchange=function(){ const n=+this.value; if(n>0){ state.nights=n; buildAll(); render(); } };
document.getElementById('c-go').onclick=findCombos;
buildGroups(); buildAll(); render();
</script>
"""

html = (HTML
        .replace("__PAYLOAD__", payload)
        .replace("__SCANNED__", scanned)
        .replace("__FROM__", all_dates[0])
        .replace("__TO__", all_dates[-1])
        .replace("__NROUTES__", str(len(data)))
        .replace("__NDAYS__", f"{len(fares):,}")
)
open(out_path, "w").write(html)
print(f"{out_path}  {len(html)/1024:.0f} KB  {len(data)} 航向 / {len(fares):,} 筆")
