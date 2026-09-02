#!/usr/bin/env python3
"""把澳門航空掃描結果做成一頁「每日價格日曆」。

  python3 generate-page.py baseline.json network.json out.html

跟虎航版的差別：澳航拿不到稅金明細（av_search 有風控），全頁都是未稅票價；
機場中文名／國別來自 network.json（scan.py 從官網 airport API 抓的）。
來回＝兩張單程相加（估算；澳航是否有來回折扣未驗證，下訂前以官網為準）。
"""
import json, sys, datetime, collections

fares = json.load(open(sys.argv[1]))
NET = json.load(open(sys.argv[2]))
try:
    RTX = json.load(open(sys.argv[4] if len(sys.argv) > 4 else
                         __file__.rsplit("/", 1)[0] + "/baseline-rt.json"))
except Exception:
    RTX = {}
out_path = sys.argv[3] if len(sys.argv) > 3 else "airmacau-prices.html"

CITY = NET.get("names", {})
COUNTRY = NET.get("countries", {})
def country(code):
    return COUNTRY.get(code, "?")
# 官網 nationalityId 不是乾淨 ISO 碼（THA/MALA/kz 都有），照實列
FLAG = {"TW": "台灣", "CN": "中國大陸", "JP": "日本", "KR": "韓國", "THA": "泰國",
        "VN": "越南", "SG": "新加坡", "MALA": "馬來西亞", "PH": "菲律賓", "ID": "印尼",
        "MO": "澳門", "HK": "香港", "HUB": "澳門", "RU": "俄羅斯", "MN": "蒙古",
        "AE": "阿聯", "kz": "哈薩克"}

# ── 稅費估算（2026-09-02 用 Google Flights 同日澳航含稅價回推）────────────
# 方法：每航向取 3 個分散日期，diff = GF澳航最低含稅 − 官網日曆未稅，取「最小」
# diff 當稅（艙等錯配只會把 diff 灌高不會壓低）。校準原始數據存 scratchpad nx-calib2-out.json。
TAX_MEASURED = {
    "TPE-MFM": 2000, "KHH-MFM": 1950, "RMQ-MFM": 1800,
    "MFM-TPE": 1000, "MFM-KHH": 1150, "MFM-RMQ": 1600,
    "MFM-NRT": 1950, "MFM-ICN": 2050, "MFM-BKK": 1100, "MFM-DAD": 1250,
}
TW = {"TPE", "KHH", "RMQ", "TNN"}
def _leg_tax(o, d):
    k = f"{o}-{d}"
    if k in TAX_MEASURED:
        return TAX_MEASURED[k]
    dc = COUNTRY.get(d, "?")
    if o in TW and d == "MFM":
        return 1900
    if o == "MFM":
        if dc == "TW":
            return 1250
        if dc in ("JP", "KR"):
            return 2000
        if dc in ("THA", "VN", "PH", "ID", "SG", "MALA"):
            return 1200
    return None   # 中國大陸／回程海外出發等沒校準過的，不硬給
def est_tax(o, d):
    if o == "MFM" or d == "MFM":
        return _leg_tax(o, d)
    # 經澳門轉機（兩段）：兩段稅相加，扣掉轉機不重複收的澳門機場費（粗估 500）
    a, b = _leg_tax(o, "MFM"), _leg_tax("MFM", d)
    if a is None or b is None:
        return None
    return a + b - 500

tax = {}
routes = collections.defaultdict(dict)
for r in fares:
    routes[f"{r['origin']}-{r['destination']}"][r["date"]] = r["amount"]

data = {}
for k, days in routes.items():
    o, d = k.split("-")
    data[k] = {
        "o": o, "d": d,
        "on": CITY.get(o, o), "dn": CITY.get(d, d),
        "oc": country(o), "dc": country(d),
        "tax": est_tax(o, d),
        "days": days,
    }

all_dates = sorted({dt for v in data.values() for dt in v["days"]})
today = datetime.date.today().isoformat()
scanned = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime("%Y-%m-%d %H:%M") + " 台北"

payload = json.dumps({"routes": data, "from": all_dates[0], "to": all_dates[-1],
                      "scanned": scanned, "rtx": RTX},
                     ensure_ascii=False, separators=(",", ":"))

HTML = """<title>澳門航空價格日曆</title>
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
  <p class="kicker">Air Macau · 全航線每日最低價</p>
  <h1>澳門航空價格日曆</h1>
  <p class="sub">官網價格日曆是「單人未稅單程」最低價，本頁的<b>含稅總價是估算值</b>（用 Google Flights 同日澳航含稅價校準，誤差約 ±數百元）。台灣出發到澳門以外的目的地＝<b>經澳門轉機</b>的行程。
     艙等以最陽春的 tigerLight 計；行李、選位、餐點另外加。</p>
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
  <p class="sub" id="rtnote" style="display:none;font-size:12.5px;margin-top:10px"><b>澳航來回票比兩張單程相加便宜 8~18%</b>（9/2 實測，KHH⇄MFM 中位數 −18%）。台灣⇄澳門且出發日在近 30 天內的格子用的是<b>官網來回日曆的真實來回價</b>（標 ✓）；其餘（遠期／轉機航線）仍是兩張單程相加的<b>上限估</b>，實際訂可能更便宜。含稅一律為估算，下訂前以官網為準。</p>
</section>

<section class="board" id="combo-card" style="display:none">
  <h2>找最便宜的去回組合</h2>
  <div class="dirtoggle" style="flex-wrap:wrap;align-items:flex-end;border-top:0;margin-top:0;padding-top:0;gap:10px">
    <label style="font-size:12.5px;color:var(--muted)">最少幾晚<br><input id="c-min" type="number" min="1" max="60" value="2" style="width:64px;font:inherit;padding:3px 6px"></label>
    <label style="font-size:12.5px;color:var(--muted)">最多幾晚<br><input id="c-max" type="number" min="1" max="60" value="6" style="width:64px;font:inherit;padding:3px 6px"></label>
    <label style="font-size:12.5px;color:var(--muted)">出發月份（留空＝全部）<br><input id="c-month" type="month" style="font:inherit;padding:3px 6px"></label>
    <button class="chip" id="c-go" type="button">找</button>
  </div>
  <div class="tblwrap" style="margin-top:12px"><table id="combo">
    <thead><tr><th class="l">出發</th><th class="l">回程</th><th>晚數</th><th>去程</th><th>回程</th><th>來回未稅</th><th>含稅總價(估)</th></tr></thead>
    <tbody></tbody>
  </table></div>
</section>

<div class="summary" id="summary"></div>
<div class="cals" id="cals"></div>

<section class="board">
  <h2>這條航線最便宜的 20 天</h2>
  <div class="tblwrap"><table id="best">
    <thead id="best-head"><tr><th class="l">日期</th><th class="l">星期</th><th>未稅票價</th><th>＋稅(估)</th><th>含稅總價(估)</th></tr></thead>
    <tbody></tbody>
  </table></div>
</section>

<section class="allroutes">
  <h2>全航線最低價一覽</h2>
  <div class="tblwrap"><table id="all">
    <thead><tr><th class="l">航線</th><th>未稅</th><th>＋稅(估)</th><th>含稅總價(估)</th><th class="l">最便宜那天</th></tr></thead>
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
  <p>資料來源：澳門航空官網價格日曆（公開查詢，無需登入）。稅費為估算值：用 Google Flights
     同日澳航含稅價回推（每航向取多日期的最小差值），台灣出發約 +1,800～2,000、澳門→台灣約
     +1,000～1,600、澳門→日韓約 +2,000、澳門→東南亞約 +1,100～1,250；經澳門轉機＝兩段相加再扣
     轉機不重複的機場費。中國大陸航線與海外→澳門方向未校準，顯示未稅。</p>
  <p>台灣出發到澳門以外的目的地都是<b>經澳門轉機</b>的行程（澳航官網直接賣聯程票）。
     官網日曆是快取值；實際下訂前請以官網即時查詢為準。</p>
</footer>
</div>

<script>
const DATA = __PAYLOAD__;
const R = DATA.routes;
const fmt = n => n.toLocaleString('en-US');
const WD = ['日','一','二','三','四','五','六'];
const RTX = DATA.rtx || {};   // 官網來回矩陣（近30天，真·來回價，比單程相加便宜 8~18%）
const state = { origin:'MFM', dest:'TPE', dir:'out', nights:0 };

function key(){ return state.dir==='out' ? state.origin+'-'+state.dest : state.dest+'-'+state.origin; }
function addDays(iso,n){ const d=new Date(iso+'T00:00:00Z'); d.setUTCDate(d.getUTCDate()+n); return d.toISOString().slice(0,10); }
function retKey(k){ const p=k.split('-'); return p[1]+'-'+p[0]; }
// 來回＝兩張單程相加（實測無折扣）
function rtView(k,n){
  const go=R[k], back=R[retKey(k)];
  if(!go||!back) return null;
  const days={}, det={}; let any=false;
  for(const d of Object.keys(go.days)){ const rd=addDays(d,n), r=back.days[rd];
    const ex = RTX[k] ? RTX[k][d+'|'+rd] : undefined;
    if(ex!==undefined){ days[d]=ex; det[d]={g:go.days[d],r:(r===undefined?null:r),rd,ex:true}; any=true; }
    else if(r!==undefined){ days[d]=go.days[d]+r; det[d]={g:go.days[d],r,rd}; any=true; } }
  if(!any) return null;
  return {days, rt:det, tax:(go.tax!=null&&back.tax!=null)?go.tax+back.tax:null};
}
function curView(){ const k=key();
  if(state.nights>0) return rtView(k,state.nights);
  return R[k] ? {days:R[k].days, rt:null, tax:R[k].tax} : null; }

function buildGroups(){
  const box = document.getElementById('groups');
  const origins = ['MFM','TPE','KHH','RMQ'];
  const oRow = document.createElement('div');
  oRow.className = 'grp';
  oRow.innerHTML = '<div class="grp-label">出發地</div>';
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
  const names = {TW:'台灣',CN:'中國大陸',JP:'日本',KR:'韓國',THA:'泰國',VN:'越南',SG:'新加坡',MALA:'馬來西亞',PH:'菲律賓',ID:'印尼',MO:'澳門',HK:'香港',RU:'俄羅斯',MN:'蒙古',AE:'阿聯',kz:'哈薩克',FR:'法國',IT:'義大利',ES:'西班牙',DE:'德國',GB:'英國',PT:'葡萄牙',BE:'比利時',EG:'埃及',TR:'土耳其'};
  Object.keys(byC).sort((a,b)=>byC[b].length-byC[a].length||String(a).localeCompare(b)).forEach(c=>{
    const row=document.createElement('div'); row.className='grp';
    row.innerHTML='<div class="grp-label">'+(names[c]||'其他')+'</div>';
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
  const rt = state.nights>0;
  if(rt) state.dir='out';
  document.getElementById('dirtoggle').style.display = rt?'none':'';
  document.getElementById('rtnote').style.display = rt?'':'none';
  document.getElementById('combo-card').style.display = rt?'':'none';
  document.querySelectorAll('#modechips .chip[data-n]').forEach(b=>b.setAttribute('aria-pressed', +b.dataset.n===state.nights));
  document.getElementById('btn-out').setAttribute('aria-pressed', state.dir==='out');
  document.getElementById('btn-ret').setAttribute('aria-pressed', state.dir==='ret');
  document.getElementById('best-head').innerHTML = rt
    ? '<tr><th class="l">出發</th><th class="l">星期</th><th class="l">回程</th><th>去程</th><th>回程</th><th>＋稅(估)</th><th>含稅總價(估)</th></tr>'
    : '<tr><th class="l">日期</th><th class="l">星期</th><th>未稅票價</th><th>＋稅(估)</th><th>含稅總價(估)</th></tr>';

  const k = key(), v = curView();
  const cals = document.getElementById('cals');
  const sum = document.getElementById('summary');
  const bestBody = document.querySelector('#best tbody');
  if(!v){
    sum.innerHTML='<div class="stat"><div class="lab">這個方向</div><div class="val">—</div><div class="note">'+
      (rt?'這個天數組不出來回（回程日都沒班機）':'沒有掃到票價')+'</div></div>';
    cals.innerHTML=''; bestBody.innerHTML=''; return;
  }
  const days = v.days, tax = v.tax;
  const prices = Object.values(days).sort((a,b)=>a-b);
  const lo = prices[0], hi = prices[prices.length-1];
  const q1 = prices[Math.floor(prices.length/3)], q2 = prices[Math.floor(prices.length*2/3)];
  const med = prices[Math.floor(prices.length/2)];
  const T = n => tax==null ? null : n+tax;

  const rtlab = rt ? ('來回'+(state.nights+1)+'天'+state.nights+'夜 · ') : '';
  sum.innerHTML = [
    ['最低價', (T(lo)??lo), rtlab+(tax==null?'未稅 ':'含稅(估) ')+fmt(lo)+(tax==null?'':' ＋稅 '+fmt(tax)), true],
    ['中位數', (T(med)??med), '一半的日子比這便宜', false],
    ['最高價', (T(hi)??hi), '整段期間最貴的一天', false],
    ['有票天數', Object.keys(days).length, DATA.from+' → '+DATA.to, false],
  ].map(([lab,val,note,hi2])=>
    '<div class="stat'+(hi2?' hi':'')+'"><div class="lab">'+lab+'</div><div class="val">'+
    (lab==='有票天數'? val : fmt(val))+'</div><div class="note">'+note+'</div></div>').join('');

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
               (tot!=null? fmt(tot) : fmt(p))+
               (tot!=null? '<small>'+fmt(p)+'</small>' : '<small>未稅</small>')+'</div></div>';
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
    if(rt){ const x=v.rt[d];
      return '<tr><td class="l num">'+d+'</td><td class="l dow-tag'+we+'">'+WD[wd]+'</td>'+
        '<td class="l num">'+x.rd+'</td>'+
        (x.ex? '<td class="num" colspan="2">官網來回價 ✓</td>'
             : '<td class="num">'+fmt(x.g)+'</td><td class="num">'+fmt(x.r)+'</td>')+
        '<td class="num">'+(tax==null?'未量':fmt(tax))+'</td>'+
        '<td class="num tot">'+(tax==null?'—':fmt(p+tax))+'</td></tr>'; }
    return '<tr><td class="l num">'+d+'</td><td class="l dow-tag'+we+'">'+WD[wd]+'</td>'+
      '<td class="num">'+fmt(p)+'</td><td class="num">'+(tax==null?'未量':fmt(tax))+'</td>'+
      '<td class="num tot">'+(tax==null?'—':fmt(p+tax))+'</td></tr>';
  }).join('');
}

// 找最便宜的去回組合：給晚數範圍（＋可選出發月），列前 15 組
function findCombos(){
  const body = document.querySelector('#combo tbody');
  const mn=Math.max(1,+document.getElementById('c-min').value||1);
  const mx=Math.max(mn,+document.getElementById('c-max').value||mn);
  const ym=document.getElementById('c-month').value;
  const k=key(), go=R[k], back=R[retKey(k)];
  if(!go||!back){ body.innerHTML='<tr><td colspan="7" class="l">這條航線缺其中一個方向的資料</td></tr>'; return; }
  const tax=(go.tax!=null&&back.tax!=null)?go.tax+back.tax:null;
  const out=[];
  for(const d of Object.keys(go.days)){ if(ym && !d.startsWith(ym)) continue;
    for(let n=mn;n<=mx;n++){ const rd=addDays(d,n), r=back.days[rd];
      const ex = RTX[k] ? RTX[k][d+'|'+rd] : undefined;
      if(ex!==undefined) out.push({d,rd,n,g:null,r:null,t:ex,ex:true});
      else if(r!==undefined) out.push({d,rd,n,g:go.days[d],r,t:go.days[d]+r}); } }
  out.sort((a,b)=>a.t-b.t||a.d.localeCompare(b.d));
  body.innerHTML = out.length ? out.slice(0,15).map(x=>{
    const wd=new Date(x.d+'T00:00:00Z').getUTCDay(), we=(wd===0||wd===6)?' we':'';
    return '<tr><td class="l num'+we+'">'+x.d+'（'+WD[wd]+'）</td><td class="l num">'+x.rd+'</td>'+
      '<td class="num">'+x.n+'</td>'+
      (x.ex? '<td class="num" colspan="2">官網來回價 ✓</td>'
           : '<td class="num">'+fmt(x.g)+'</td><td class="num">'+fmt(x.r)+'</td>')+
      '<td class="num">'+fmt(x.t)+'</td><td class="num tot">'+(tax==null?'—':fmt(x.t+tax))+'</td></tr>';
  }).join('') : '<tr><td colspan="7" class="l">這個範圍沒有可組合的日期</td></tr>';
}

function buildAll(){
  const rt = state.nights>0;
  let entries = Object.entries(R);
  if(rt) entries = entries.filter(([k,v])=>['MFM','TPE','KHH','RMQ'].includes(v.o));
  const rows = entries.map(([k,v])=>{
    const view = rt ? rtView(k,state.nights) : v;
    if(!view) return null;
    const e = Object.entries(view.days).sort((a,b)=>a[1]-b[1])[0];
    return {k, v, tax:view.tax, date:e[0], p:e[1], tot: view.tax==null? null : e[1]+view.tax};
  }).filter(Boolean).sort((a,b)=> (a.tot??a.p)-(b.tot??b.p));
  document.querySelector('#all tbody').innerHTML = rows.map(r=>
    '<tr><td class="l"><b>'+r.k+(rt?' 來回':'')+'</b><span class="rt-name">'+r.v.on+(rt?' ⇄ ':' → ')+r.v.dn+'</span></td>'+
    '<td class="num">'+fmt(r.p)+'</td><td class="num">'+(r.tax==null?'未量':fmt(r.tax))+'</td>'+
    '<td class="num tot">'+(r.tot==null?'—':fmt(r.tot))+'</td>'+
    '<td class="l num">'+r.date+'</td></tr>').join('');
}

document.getElementById('btn-out').onclick=()=>{ state.dir='out'; render(); };
document.getElementById('btn-ret').onclick=()=>{ state.dir='ret'; render(); };
document.querySelectorAll('#modechips .chip[data-n]').forEach(b=>
  b.addEventListener('click',()=>{ state.nights=+b.dataset.n; buildAll(); render(); }));
document.getElementById('nights-in').addEventListener('change',function(){
  const n=+this.value; if(n>0){ state.nights=n; buildAll(); render(); } });
document.getElementById('c-go').addEventListener('click',findCombos);
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
        .replace("__NTAX__", str(sum(1 for v in data.values() if v["tax"] is not None))))
open(out_path, "w").write(html)
print(f"{out_path}  {len(html)/1024:.0f} KB  {len(data)} 航向 / {len(fares):,} 筆")
