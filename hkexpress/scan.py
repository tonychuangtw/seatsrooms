#!/usr/bin/env python3
"""香港快運（UO）全網票價日曆掃描。

資料源（2026-09-02 打通）：
  POST https://api.hkexpress.com/flt-booking-query/public/v1/low-fare/monthly-calendar/availability
  body {"application_code":"IBE","flights":[{"origin":"TPE","destination":"HKG",
        "begin_date":"YYYY-MM-DD","end_date":"YYYY-MM-DD"}],"currency_code":"TWD",
        "promotion_code":"","passengers":{"adult_count":1,"infant_count":0,"children_count":0}}
  純 curl 可打、免登入、無 Akamai 攔（www 首頁有 Akamai 但 API 不擋）。
  - body 格式是從 www 前端 chunk 的 webpack module 49600 直接讀出來的（e9.F transformer）
  - ⚠ 視窗上限 2 個月：begin~end 超過就回空 trip，要分段掃
  - ⚠ 幣別跟「出發地市場」走，currency_code 蓋不過去（TPE 出發回 TWD、HKG 出發回 HKD）
    → 用 ../cash-fx.json 換算台幣（跟星宇同一招）
  - ⚠ 價格是未稅票價（TPE-HKG 10/1 = 470，含稅顯然不止）；同一天會重複出現要去重
  - is_sold_out / is_no_flight 標記可用；可訂期至少到一年後
  航線表：GET https://manage.hkexpress.com/admin/public/v1/flight-route-mapping（免登入）
  45 個出發地含台灣經香港轉機的聯程目的地（TPE/KHH/RMQ 各 42 個）。

  python3 scan.py --all --json baseline.json     # HKG⇄全部 + 台灣三場⇄全部（約 20~30 分鐘）
  python3 scan.py --routes TPE-HKG,HKG-TPE
"""
import argparse, datetime, json, os, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = ("https://api.hkexpress.com/flt-booking-query/public/v1/"
       "low-fare/monthly-calendar/availability")
ROUTES_API = "https://manage.hkexpress.com/admin/public/v1/flight-route-mapping"
NETWORK = os.path.join(HERE, "network.json")
FX_FILE = os.path.join(HERE, os.pardir, "cash-fx.json")
HDRS = {"content-type": "application/json",
        "origin": "https://www.hkexpress.com", "referer": "https://www.hkexpress.com/",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"}
GAP = 0.3
MONTHS_AHEAD = 12          # 掃到一年後
HUBS = ["HKG", "TPE", "KHH", "RMQ"]

# 官網機場名是英文（i18n 在前端），常用點自己給中文，其他顯示代碼
NAMES = {
    "HKG": "香港", "TPE": "台北桃園", "KHH": "高雄", "RMQ": "台中",
    "NRT": "東京成田", "HND": "東京羽田", "KIX": "大阪關西", "NGO": "名古屋",
    "FUK": "福岡", "OKA": "沖繩那霸", "ISG": "石垣島", "TAK": "高松", "HIJ": "廣島",
    "KMQ": "小松", "SDJ": "仙台", "TYO": "東京(市區)",
    "ICN": "首爾仁川", "PUS": "釜山", "CJU": "濟州", "TAE": "大邱",
    "BKK": "曼谷", "CNX": "清邁", "HKT": "普吉",
    "DAD": "峴港", "HAN": "河內", "PQC": "富國島",
    "MNL": "馬尼拉", "CRK": "克拉克", "PEN": "檳城", "SZB": "吉隆坡梳邦",
    "BKI": "亞庇", "PKX": "北京大興", "NGB": "寧波", "WUX": "無錫", "CZX": "常州",
    "YIW": "義烏", "SYX": "三亞", "HKM": "澳門(船)", "FYG": "蛇口(船)",
    "NSZ": "南沙(船)", "ZTI": "東莞(船)", "ZYK": "深圳福永(船)", "HZI": "惠州(巴士)",
    "ZGN": "中山(船)", "PFT": "番禺(船)",
}
COUNTRY = {
    "HKG": "HK", "TPE": "TW", "KHH": "TW", "RMQ": "TW",
    "NRT": "JP", "HND": "JP", "KIX": "JP", "NGO": "JP", "FUK": "JP", "OKA": "JP",
    "ISG": "JP", "TAK": "JP", "HIJ": "JP", "KMQ": "JP", "SDJ": "JP", "TYO": "JP",
    "ICN": "KR", "PUS": "KR", "CJU": "KR", "TAE": "KR",
    "BKK": "TH", "CNX": "TH", "HKT": "TH",
    "DAD": "VN", "HAN": "VN", "PQC": "VN",
    "MNL": "PH", "CRK": "PH", "PEN": "MY", "SZB": "MY", "BKI": "MY",
    "PKX": "CN", "NGB": "CN", "WUX": "CN", "CZX": "CN", "YIW": "CN", "SYX": "CN",
    "HKM": "MO", "FYG": "CN", "NSZ": "CN", "ZTI": "CN", "ZYK": "CN", "HZI": "CN",
    "ZGN": "CN", "PFT": "CN",
}


def fx_rates():
    try:
        return json.load(open(FX_FILE))["twdPer"]
    except Exception:
        return {"TWD": 1}


def post(body, timeout=25):
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def windows():
    """從今天起切 2 個月一段，共掃 MONTHS_AHEAD 個月。"""
    out, d = [], datetime.date.today()
    end_all = d + datetime.timedelta(days=MONTHS_AHEAD * 31)
    while d < end_all:
        e = min(d + datetime.timedelta(days=60), end_all)
        out.append((d.isoformat(), e.isoformat()))
        d = e + datetime.timedelta(days=1)
    return out


def calendar(org, dest, retries=2):
    """一個航向的完整日曆（分段掃，去重取每日最低）：{date: 原幣價}＋幣別。"""
    days, cur, empty_streak = {}, None, 0
    for b, e in windows():
        body = {"application_code": "IBE",
                "flights": [{"origin": org, "destination": dest,
                             "begin_date": b, "end_date": e}],
                "currency_code": "TWD", "promotion_code": "",
                "passengers": {"adult_count": 1, "infant_count": 0, "children_count": 0}}
        got = None
        for i in range(retries + 1):
            try:
                d = post(body)
                got = (d.get("trip") or [])
                break
            except Exception as ex:
                if i == retries:
                    print(f"  {org}-{dest} {b} 失敗：{str(ex)[:80]}", file=sys.stderr)
                time.sleep(1.5 * (i + 1))
        time.sleep(GAP)
        if not got:
            empty_streak += 1
            if empty_streak >= 2 and days:
                break        # 已有資料且連兩窗空 = 賣到頭了
            if empty_streak >= 3:
                break        # 從頭就空 = 沒這條航線
            continue
        empty_streak = 0
        for x in got[0].get("low_fare", []):
            if x.get("is_no_flight") or x.get("is_sold_out") or not x.get("price"):
                continue
            k = x["date"]
            if k not in days or x["price"] < days[k]:
                days[k] = x["price"]
                cur = x.get("currency_code") or cur
    return days, (cur or "TWD")


def route_map(refresh=False):
    try:
        n = json.load(open(NETWORK))
        if not refresh and time.time() - n.get("fetchedAt", 0) < 7 * 86400:
            return n
    except Exception:
        pass
    req = urllib.request.Request(ROUTES_API, headers={k: v for k, v in HDRS.items()
                                                      if k != "content-type"})
    with urllib.request.urlopen(req, timeout=25) as r:
        d = json.load(r)
    m = {x["origin"]: sorted(x["destination"]) for x in d.get("flight_route_mappings", [])}
    n = {"routes": m, "names": NAMES, "countries": COUNTRY, "fetchedAt": time.time()}
    json.dump(n, open(NETWORK, "w"), ensure_ascii=False)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", help="逗號分隔，如 TPE-HKG,HKG-TPE")
    ap.add_argument("--all", action="store_true", help="HKG⇄全部＋台灣三場⇄全部")
    ap.add_argument("--json", help="輸出 json 檔")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    net = route_map()
    fx = fx_rates()
    if a.routes:
        pairs = [tuple(r.split("-")) for r in a.routes.split(",")]
    elif a.all:
        pairs, seen = [], set()
        for org in HUBS:
            for x in net["routes"].get(org, []):
                for p in [(org, x), (x, org)]:
                    if p not in seen:
                        seen.add(p)
                        pairs.append(p)
    else:
        pairs = [("TPE", "HKG"), ("HKG", "TPE"), ("KHH", "HKG"),
                 ("HKG", "KHH"), ("RMQ", "HKG"), ("HKG", "RMQ")]

    out, fails = [], 0
    for org, dest in pairs:
        days, cur = calendar(org, dest)
        if not days:
            continue
        rate = fx.get(cur)
        cc = COUNTRY.get(dest if org == "HKG" else org, "?")
        for d, p in days.items():
            out.append({"origin": org, "destination": dest, "date": d,
                        "amount": p, "currency": cur,
                        "twd": round(p * rate) if rate else None, "country": cc})

    dirs = {f"{r['origin']}-{r['destination']}" for r in out}
    print(f"# 航向 {len(dirs)} 條 / 有價日期 {len(out)} 筆")
    best = {}
    for r in out:
        if r.get("twd") is None:
            continue
        k = f"{r['origin']}-{r['destination']}"
        if k not in best or r["twd"] < best[k]["twd"]:
            best[k] = r
    print("\n各航向最低（未稅，已換算台幣）")
    for k, r in sorted(best.items(), key=lambda x: x[1]["twd"])[:a.top]:
        name = f"{NAMES.get(r['origin'], r['origin'])}→{NAMES.get(r['destination'], r['destination'])}"
        orig = "" if r["currency"] == "TWD" else f"（{r['amount']:,} {r['currency']}）"
        print(f"  {k:12s} {name:16s} {r['twd']:>7,}{orig}  {r['date']}")

    if a.json:
        json.dump(out, open(a.json, "w"), ensure_ascii=False)
        print(f"\n→ {a.json}")


if __name__ == "__main__":
    main()
