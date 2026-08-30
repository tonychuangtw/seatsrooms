#!/usr/bin/env python3
"""星宇航空票價掃描器 —— 走官網公開的月票價日曆 API（無需登入、無 Akamai）。

  python3 scan.py --routes TPE-NRT,TPE-CTS --since 2026-09 --until 2027-03
  python3 scan.py --all --since 2026-09 --until 2027-08 --top 30 --json baseline.json

⚠ 跟虎航不一樣：星宇日曆給的就是**含稅總價**（實測 TPE-NRT 2026-10-15 日曆 8,574
   ＝ /flights/search 的 base 6,170 ＋ totalTaxes 2,404），所以這裡不需要稅金表。
   amount 會隨旅客人數放大（adt=2 就是兩人份），預設 adt=1 即單人含稅價。
"""
import argparse, calendar, datetime, json, os, sys, threading, time
import urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://ecapi.starlux-airlines.com"
CAL = f"{API}/searchFlight/v2/flights/calendars/monthly"
AIRPORTS = f"{API}/utilities/v2/airports"
NET_CACHE = os.path.join(HERE, "network.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
HDR = {"User-Agent": UA, "Content-Type": "application/json",
       "Accept": "application/json", "jx-lang": "zh-TW",
       "Origin": "https://www.starlux-airlines.com",
       "Referer": "https://www.starlux-airlines.com/"}
CABINS = ("eco", "ecoPremium", "business", "first")

class OutOfHorizon(Exception):
    """超出可訂期間（API 回 422）。"""


_gate = threading.Semaphore(1)
_last = [0.0]
MIN_GAP = 0.4


def call(url, payload=None, tries=6):
    body = json.dumps(payload).encode() if payload is not None else None
    for i in range(tries):
        try:
            with _gate:
                gap = MIN_GAP - (time.monotonic() - _last[0])
                if gap > 0:
                    time.sleep(gap)
                _last[0] = time.monotonic()
            req = urllib.request.Request(url, data=body, headers=HDR)
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            # 422 = 超出可訂期間（目前約 12 個月），不是錯誤，往上回報成空月份
            if e.code == 422:
                raise OutOfHorizon()
            if e.code in (429, 502, 503) and i < tries - 1:
                # 429 要退夠久才有用；掃描與監看同時跑的時候特別容易撞到
                time.sleep(5 * (i + 1))
                continue
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def network(refresh=False):
    """星宇自營航線圖。utilities/v2/airports 一包約 1MB，快取起來別每次抓。"""
    if not refresh and os.path.exists(NET_CACHE):
        age = time.time() - os.path.getmtime(NET_CACHE)
        if age < 7 * 86400:
            return json.load(open(NET_CACHE))
    d = call(AIRPORTS)["data"]
    routes, names = {}, {}
    for region in d["regions"]:
        for country in region["countries"]:
            for city in country["cities"]:
                for ap in city["airports"]:
                    names[ap["code"]] = city.get("locName") or city.get("engName")
                    if not ap.get("isOperatedByJX"):
                        continue
                    dests = sorted({a["waypoint"] for a in ap.get("available", [])
                                    if a.get("carrierCode") == "JX"
                                    and a.get("isRoundTripOrOneWay")
                                    and a.get("isSegmentExist")})
                    if dests:
                        routes[ap["code"]] = dests
    net = {"routes": routes, "names": names,
           "fetchedAt": datetime.date.today().isoformat()}
    json.dump(net, open(NET_CACHE, "w"), ensure_ascii=False, indent=1)
    return net


def months(since, until):
    y, m = map(int, since.split("-"))
    ey, em = map(int, until.split("-"))
    out = []
    while (y, m) <= (ey, em):
        out.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def month_prices(origin, dest, ym, cabin="eco", adt=1):
    """一次請求拿一整個日曆月。departureDate 給哪天不重要，回的是那個月。"""
    payload = {"cabin": cabin,
               "itineraries": [{"departure": origin, "arrival": dest,
                                "departureDate": f"{ym}-15"}],
               "travelers": {"adt": adt, "chd": 0, "inf": 0}}
    try:
        d = call(CAL, payload)
    except OutOfHorizon:
        return []
    if not d.get("success"):
        raise RuntimeError(d.get("message", {}).get("content", "unknown error"))
    out = []
    for c in d["data"]["calendars"] or []:
        p = c.get("price") or {}
        if p.get("amount"):
            out.append({"origin": origin, "destination": dest,
                        "date": c["departureDate"], "amount": p["amount"],
                        "currency": p.get("currencyCode", "TWD"),
                        "status": c.get("status")})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", help="逗號分隔，如 TPE-NRT,TPE-CTS")
    ap.add_argument("--all", action="store_true", help="掃全部星宇自營航向")
    ap.add_argument("--since", required=True, help="YYYY-MM")
    ap.add_argument("--until", required=True, help="YYYY-MM")
    ap.add_argument("--cabin", default="eco", choices=CABINS)
    ap.add_argument("--adt", type=int, default=1)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--json")
    ap.add_argument("--refresh-network", action="store_true")
    a = ap.parse_args()

    net = network(a.refresh_network)
    names = net["names"]
    if a.all:
        pairs = [(o, d) for o, ds in net["routes"].items() for d in ds]
    elif a.routes:
        pairs = [tuple(p.strip().upper().split("-")) for p in a.routes.split(",")]
    else:
        sys.exit("需要 --routes 或 --all")

    ms = months(a.since, a.until)
    print(f"# {len(pairs)} 個航向 × {len(ms)} 個月 = {len(pairs) * len(ms)} 次請求"
          f"（{a.cabin}，{a.adt} 位大人，含稅）", file=sys.stderr)

    rows, errors = [], []
    for i, (o, d) in enumerate(pairs, 1):
        for ym in ms:
            try:
                rows.extend(month_prices(o, d, ym, a.cabin, a.adt))
            except Exception as e:
                errors.append(f"{o}-{d} {ym}: {str(e)[:80]}")
        if i % 10 == 0:
            print(f"  …{i}/{len(pairs)}", file=sys.stderr)

    rows.sort(key=lambda r: r["amount"])
    print(f"# 有價日期 {len(rows)} 筆（{a.since} ~ {a.until}）"
          + (f"／失敗 {len(errors)} 次" if errors else "") + "\n")
    print(f"{'排名':<4}{'航線':<10}{'日期':<12}{'含稅 TWD':>10}  ")
    for i, r in enumerate(rows[:a.top], 1):
        print(f"{i:<4}{r['origin']}-{r['destination']:<6}{r['date']:<12}{r['amount']:>10,}")

    best = {}
    for r in rows:
        k = f"{r['origin']}-{r['destination']}"
        if k not in best or r["amount"] < best[k]["amount"]:
            best[k] = r
    print(f"\n# 各航向最低含稅價（{len(best)} 條有票）")
    for k, r in sorted(best.items(), key=lambda kv: kv[1]["amount"]):
        o, d = k.split("-")
        label = f"{names.get(o, o)}→{names.get(d, d)}"
        print(f"  {k:<9}{r['amount']:>8,}  {r['date']}  {label}")

    if errors:
        print(f"\n# 失敗 {len(errors)} 次", file=sys.stderr)
        for e in errors[:10]:
            print("  " + e, file=sys.stderr)
    if a.json:
        json.dump(rows, open(a.json, "w"), ensure_ascii=False, indent=1)
        print(f"\n→ {a.json}")


if __name__ == "__main__":
    main()
