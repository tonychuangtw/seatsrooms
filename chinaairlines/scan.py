#!/usr/bin/env python3
"""華航（CI）現金票價格日曆掃描（含稅總價）。

資料源（2026-09-02，scout 08-30 先找到 farewire、brain 補上 histogram）：
  POST https://openair-california.airtrfx.com/airfare-sputnik-service/v3/ci/fares/histogram-distribution
  headers: em-api-key（flights.china-airlines.com 前端的公開 key，放 ../.env 的 CI_EM_API_KEY，不進 repo）
           ＋ origin/referer 一定要帶 flights.china-airlines.com，否則回空
  body {"faresLimit":1,"priceBuckets":{"priceStats":true},"origin":"TPE","destination":"CTS",
        "journeyType":"ONE_WAY","autoSettings":{"language":"zh-TW","market":""},
        "interval":"1d","departure":{"start":"YYYY-MM-DD","end":"YYYY-MM-DD"}}
  → histogram[] 逐日一格 {date, fares:[{priceSpecification:{totalPrice,usdTotalPrice,currencyCode},
    outboundFlight:{fareClassInput}}]}，**一次一整年**，數字與官網首頁 farewire 完全一致（同一份 datacore）
  - 價格是**含稅總價**（官網「探索最佳票價」卡片的數字），只有經濟艙最低
  - 幣別跟出發地市場走（TPE→TWD、NRT→JPY、HKG→HKD），用 ../cash-fx.json 換算台幣
  - 這是快取的最低票價（每格帶 searchDate），不是訂位引擎即時價；沒價的日子 fares:[]
  - 航線表：airTRFX 的 hangar 端點 404、sitemap 是全球聯運頁（台北出發 392 個含 Aspen），
    所以用「華航自營候選清單」逐條探測，回空就當沒這條航線（探測＝掃描）

  python3 scan.py --all --json baseline.json     # 台灣四場⇄候選網，~600 請求約 6 分鐘
  python3 scan.py --routes TPE-CTS,CTS-TPE
"""
import argparse, datetime, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = ("https://openair-california.airtrfx.com/airfare-sputnik-service/v3/ci/"
       "fares/histogram-distribution")
NETWORK = os.path.join(HERE, "network.json")
FX_FILE = os.path.join(HERE, os.pardir, "cash-fx.json")
ENV = os.path.join(HERE, os.pardir, ".env")
GAP = 0.35
TW = ["TPE", "KHH", "RMQ", "TNN"]

# 華航＋華信自營／常態航點候選（2026），探測回空就自動剔除
CAND = {
    # 日本
    "NRT": ("東京成田", "JP"), "HND": ("東京羽田", "JP"), "KIX": ("大阪關西", "JP"),
    "NGO": ("名古屋", "JP"), "FUK": ("福岡", "JP"), "CTS": ("札幌新千歲", "JP"),
    "OKA": ("沖繩那霸", "JP"), "HIJ": ("廣島", "JP"), "KMQ": ("小松", "JP"),
    "TAK": ("高松", "JP"), "KOJ": ("鹿兒島", "JP"), "KMJ": ("熊本", "JP"),
    "MYJ": ("松山", "JP"), "OKJ": ("岡山", "JP"), "SDJ": ("仙台", "JP"),
    "AOJ": ("青森", "JP"), "HKD": ("函館", "JP"), "ISG": ("石垣", "JP"),
    "MMY": ("宮古", "JP"), "SHI": ("下地島", "JP"), "KIJ": ("新潟", "JP"),
    "TOY": ("富山", "JP"), "NGS": ("長崎", "JP"), "OIT": ("大分", "JP"),
    # 韓國
    "ICN": ("首爾仁川", "KR"), "GMP": ("首爾金浦", "KR"), "PUS": ("釜山", "KR"),
    "CJU": ("濟州", "KR"),
    # 港澳中國
    "HKG": ("香港", "HK"), "MFM": ("澳門", "MO"),
    "PEK": ("北京首都", "CN"), "PKX": ("北京大興", "CN"), "PVG": ("上海浦東", "CN"),
    "SHA": ("上海虹橋", "CN"), "CAN": ("廣州", "CN"), "SZX": ("深圳", "CN"),
    "XMN": ("廈門", "CN"), "HGH": ("杭州", "CN"), "NKG": ("南京", "CN"),
    "CTU": ("成都雙流", "CN"), "TFU": ("成都天府", "CN"), "CKG": ("重慶", "CN"),
    "WUH": ("武漢", "CN"), "CSX": ("長沙", "CN"), "FOC": ("福州", "CN"),
    "NGB": ("寧波", "CN"), "WUX": ("無錫", "CN"), "TSN": ("天津", "CN"),
    "XIY": ("西安", "CN"), "KMG": ("昆明", "CN"), "HAK": ("海口", "CN"),
    "CGO": ("鄭州", "CN"), "TAO": ("青島", "CN"), "DLC": ("大連", "CN"),
    "SHE": ("瀋陽", "CN"), "HRB": ("哈爾濱", "CN"), "NNG": ("南寧", "CN"),
    "WNZ": ("溫州", "CN"), "HFE": ("合肥", "CN"), "YNT": ("煙台", "CN"),
    # 東南亞／南亞
    "BKK": ("曼谷", "TH"), "CNX": ("清邁", "TH"), "HKT": ("普吉", "TH"),
    "SGN": ("胡志明", "VN"), "HAN": ("河內", "VN"), "DAD": ("峴港", "VN"),
    "PNH": ("金邊", "KH"), "SIN": ("新加坡", "SG"), "KUL": ("吉隆坡", "MY"),
    "PEN": ("檳城", "MY"), "MNL": ("馬尼拉", "PH"), "CEB": ("宿霧", "PH"),
    "CGK": ("雅加達", "ID"), "DPS": ("峇里島", "ID"), "SUB": ("泗水", "ID"),
    "RGN": ("仰光", "MM"), "DEL": ("德里", "IN"), "BOM": ("孟買", "IN"),
    "KTM": ("加德滿都", "NP"),
    # 大洋洲
    "SYD": ("雪梨", "AU"), "MEL": ("墨爾本", "AU"), "BNE": ("布里斯本", "AU"),
    "AKL": ("奧克蘭", "NZ"), "GUM": ("關島", "GU"), "ROR": ("帛琉", "PW"),
    # 北美
    "LAX": ("洛杉磯", "US"), "SFO": ("舊金山", "US"), "JFK": ("紐約", "US"),
    "SEA": ("西雅圖", "US"), "ONT": ("安大略", "US"), "YVR": ("溫哥華", "CA"),
    "HNL": ("檀香山", "US"),
    # 歐洲
    "FRA": ("法蘭克福", "DE"), "AMS": ("阿姆斯特丹", "NL"), "LHR": ("倫敦", "GB"),
    "CDG": ("巴黎", "FR"), "VIE": ("維也納", "AT"), "PRG": ("布拉格", "CZ"),
    "FCO": ("羅馬", "IT"),
}
NAMES = {k: v[0] for k, v in CAND.items()}
NAMES.update({"TPE": "台北桃園", "KHH": "高雄", "RMQ": "台中", "TNN": "台南"})
COUNTRY = {k: v[1] for k, v in CAND.items()}
COUNTRY.update({"TPE": "TW", "KHH": "TW", "RMQ": "TW", "TNN": "TW"})


def api_key():
    k = os.environ.get("CI_EM_API_KEY")
    if k:
        return k
    try:
        for l in open(ENV):
            if l.startswith("CI_EM_API_KEY="):
                return l.split("=", 1)[1].strip().strip('"\'')
    except Exception:
        pass
    sys.exit("缺 CI_EM_API_KEY（../.env）")


HDRS = None
def hdrs():
    global HDRS
    if HDRS is None:
        HDRS = {"content-type": "application/json", "em-api-key": api_key(),
                "origin": "https://flights.china-airlines.com",
                "referer": "https://flights.china-airlines.com/",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"}
    return HDRS


def fx_rates():
    try:
        return json.load(open(FX_FILE))["twdPer"]
    except Exception:
        return {"TWD": 1}


def calendar(org, dest, retries=2):
    """一個航向整年日曆：{date: (local_price, currency, usd, fareClass)}。"""
    today = datetime.date.today()
    body = {"faresLimit": 1, "priceBuckets": {"priceStats": True},
            "origin": org, "destination": dest, "journeyType": "ONE_WAY",
            "autoSettings": {"language": "zh-TW", "market": ""}, "interval": "1d",
            "departure": {"start": today.isoformat(),
                          "end": (today + datetime.timedelta(days=364)).isoformat()}}
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers=hdrs())
    for i in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            out = {}
            for cell in d.get("histogram") or []:
                fares = cell.get("fares") or []
                if not fares:
                    continue
                ps = fares[0].get("priceSpecification") or {}
                if not ps.get("totalPrice"):
                    continue
                out[cell["date"]] = (ps["totalPrice"], ps.get("currencyCode") or "TWD",
                                     ps.get("usdTotalPrice"),
                                     (fares[0].get("outboundFlight") or {}).get("fareClassInput"))
            return out
        except Exception as e:
            if i == retries:
                print(f"  {org}-{dest} 失敗：{str(e)[:80]}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", help="逗號分隔，如 TPE-CTS,CTS-TPE")
    ap.add_argument("--all", action="store_true", help="台灣四場⇄候選網探測掃描")
    ap.add_argument("--json", help="輸出 json 檔")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()
    fx = fx_rates()

    if a.routes:
        pairs = [tuple(r.split("-")) for r in a.routes.split(",")]
    elif a.all:
        pairs = []
        for o in TW:
            for x in CAND:
                pairs += [(o, x), (x, o)]
    else:
        pairs = [("TPE", "CTS"), ("CTS", "TPE"), ("KHH", "CTS"), ("CTS", "KHH")]

    out, routes_found, fails = [], {}, 0
    for org, dest in pairs:
        days = calendar(org, dest)
        time.sleep(GAP)
        if days is None:
            fails += 1
            continue
        if not days:
            continue
        routes_found.setdefault(org, []).append(dest)
        cc = COUNTRY.get(dest if org in TW else org, "?")
        for dt, (p, cur, usd, fc) in days.items():
            rate = fx.get(cur)
            twd = round(p * rate) if rate else (round(usd * fx.get("USD", 31.7)) if usd else None)
            out.append({"origin": org, "destination": dest, "date": dt,
                        "amount": p, "currency": cur, "twd": twd, "fareClass": fc,
                        "country": cc})

    if a.all and routes_found:
        json.dump({"routes": {k: sorted(v) for k, v in routes_found.items()},
                   "names": NAMES, "countries": COUNTRY, "fetchedAt": time.time()},
                  open(NETWORK, "w"), ensure_ascii=False)

    dirs = {f"{r['origin']}-{r['destination']}" for r in out}
    print(f"# 航向 {len(dirs)} 條 / 有價日期 {len(out)} 筆 / 失敗 {fails}")
    best = {}
    for r in out:
        if r["twd"] is None:
            continue
        k = f"{r['origin']}-{r['destination']}"
        if k not in best or r["twd"] < best[k]["twd"]:
            best[k] = r
    print("\n各航向最低（含稅，已換算台幣）")
    for k, r in sorted(best.items(), key=lambda x: x[1]["twd"])[:a.top]:
        name = f"{NAMES.get(r['origin'], r['origin'])}→{NAMES.get(r['destination'], r['destination'])}"
        orig = "" if r["currency"] == "TWD" else f"（{r['amount']:,.0f} {r['currency']}）"
        print(f"  {k:12s} {name:16s} {r['twd']:>8,}{orig}  {r['date']}")
    if a.json:
        json.dump(out, open(a.json, "w"), ensure_ascii=False)
        print(f"\n→ {a.json}")


if __name__ == "__main__":
    main()
