#!/usr/bin/env python3
"""台灣虎航票價掃描器 — 走官網公開的 daily-prices API（無需登入）。

顯示兩個價格：官網查到的「單人未稅單程票價」，以及加上該航向實測稅金後的
含稅總價（tigerLight 陽春艙，行李／選位／餐另計）。

用法:
  python3 scan.py --routes KHH-CJU,KHH-CTS --since 2026-09-01 --until 2026-12-31
  python3 scan.py --all --since 2026-09-01 --until 2027-03-31 --top 30
"""
import argparse, datetime, json, os, sys, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))

API = "https://api-book.tigerairtw.com/api"
PRICE_API = "https://api-cms.tigerairtw.com/api/app/book/daily-prices"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
HDR = {"User-Agent": UA, "Origin": "https://www.tigerairtw.com",
       "Referer": "https://www.tigerairtw.com/", "X-LANGUAGE": "zh-TW",
       "Accept": "application/json"}
TW_ORIGINS = ["TPE", "RMQ", "KHH", "TNN"]
TAX_FILE = os.path.join(HERE, "tax-table.json")   # 絕對路徑：從別的目錄 import 也找得到


def load_tax():
    """各航向的稅金＋機場費（fare-detail.js 實測，build-tax-table.py 產生）。"""
    try:
        with open(TAX_FILE) as f:
            return {k: v["tax"] for k, v in json.load(f)["routes"].items()}
    except Exception:
        return {}


_throttle = threading.Semaphore(1)
_last = [0.0]
MIN_GAP = 0.35   # 秒；官網 API 會 429，不要打太快


def get(url, tries=6):
    for i in range(tries):
        try:
            with _throttle:
                gap = MIN_GAP - (time.monotonic() - _last[0])
                if gap > 0:
                    time.sleep(gap)
                _last[0] = time.monotonic()
            req = urllib.request.Request(url, headers=HDR)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429 and i < tries - 1:
                time.sleep(3 * (i + 1))
                continue
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def destinations(origin):
    q = urllib.parse.urlencode({"locale": "zh-TW", "origin": origin})
    d = get(f"{API}/general/available-destinations?{q}")
    out = []
    for c in d["data"]["appAvailableDestinations"]:
        cc = c["country"]["code2"]
        for m in c["stationMenus"]:
            if m.get("station"):
                out.append((cc, m["station"]["stationCode"]))
    return out


def all_routes():
    rs = []
    for o in TW_ORIGINS:
        for cc, d in destinations(o):
            rs.append((o, d, cc))
    return rs


def daily_prices(origin, dest, since, until, currency="TWD"):
    q = urllib.parse.urlencode({"origin": origin, "destination": dest,
                                "userCurrency": currency, "pricingCurrency": currency,
                                "since": since, "until": until})
    d = get(f"{PRICE_API}?{q}")
    return [r for r in d.get("data", []) if r.get("amount")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", help="逗號分隔，如 KHH-CJU,KHH-CTS")
    ap.add_argument("--all", action="store_true", help="掃全部台灣出發航線")
    ap.add_argument("--since", required=True)
    ap.add_argument("--until", required=True)
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--rt", action="store_true", help="同時抓回程")
    ap.add_argument("--json", help="輸出 json 檔")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--alert", action="store_true",
                    help="有航線失敗就推 TG（排程用）")
    ap.add_argument("--critical", default="KHH-CJU,CJU-KHH,KHH-CTS,CTS-KHH",
                    help="這些航向失敗要用 🔴 告警（逗號分隔）")
    a = ap.parse_args()

    if a.all:
        routes = all_routes()
    elif a.routes:
        routes = []
        for p in a.routes.split(","):
            o, d = p.strip().upper().split("-")
            routes.append((o, d, "?"))
    else:
        sys.exit("需要 --routes 或 --all")

    if a.rt:
        routes = routes + [(d, o, cc) for o, d, cc in routes]

    rows, failed = [], []
    def work(r):
        o, d, cc = r
        try:
            return r, [dict(x, origin=o, destination=d, country=cc)
                       for x in daily_prices(o, d, a.since, a.until)], None
        except Exception as e:
            print(f"  !! {o}-{d} 失敗: {e}", file=sys.stderr)
            return r, [], str(e)[:120]

    with ThreadPoolExecutor(max_workers=a.workers) as ex:
        for r, res, err in ex.map(work, routes):
            if err:
                failed.append((r, err))
            rows.extend(res)

    tax = load_tax()
    for r in rows:
        t = tax.get(f"{r['origin']}-{r['destination']}")
        r["tax"] = t
        r["total"] = (r["amount"] + t) if t is not None else None
    rows.sort(key=lambda r: r["total"] if r["total"] is not None else r["amount"])
    print(f"# 航線 {len(routes)} 條 / 有價日期 {len(rows)} 筆 "
          f"({a.since} ~ {a.until})\n")
    if not tax:
        print("（沒有 tax-table.json，只顯示未稅價；跑 build-tax-table.py 產生）\n")
    print(f"{'排名':<4}{'航線':<10}{'日期':<12}{'未稅':>9}{'+稅':>7}{'含稅總價':>10}  標籤")
    for i, r in enumerate(rows[:a.top], 1):
        lbl = ",".join(x.get("name", "") if isinstance(x, dict) else str(x)
                       for x in r.get("fareLabels", []))
        tt = f"{r['tax']:>7,}" if r["tax"] is not None else "      ?"
        tot = f"{r['total']:>10,}" if r["total"] is not None else "         ?"
        print(f"{i:<4}{r['origin']}-{r['destination']:<6}{r['date']:<12}"
              f"{r['amount']:>9,}{tt}{tot}  {lbl}")

    # 每條航線的最低價
    best = {}
    for r in rows:
        k = f"{r['origin']}-{r['destination']}"
        if k not in best or r["amount"] < best[k]["amount"]:
            best[k] = r
    print(f"\n# 各航線最低價（{len(best)} 條有票）  未稅 / 含稅")
    for k, r in sorted(best.items(),
                       key=lambda kv: kv[1]["total"] or kv[1]["amount"]):
        tot = f"{r['total']:>8,}" if r["total"] is not None else "       ?"
        print(f"  {k:<10}{r['amount']:>8,} /{tot}  {r['date']}")

    if a.json:
        sys.path.insert(0, os.path.dirname(HERE))
        from scanmeta import finish
        rc = finish(a.json, rows, [(o, d) for o, d, _ in routes],
                    [{"route": f"{r[0]}-{r[1]}", "error": err} for r, err in failed],
                    since=a.since, until=a.until, airline="虎航", alert=a.alert,
                    critical=a.critical.split(",") if a.critical else ())
        json.dump(rows, open(a.json, "w"), ensure_ascii=False, indent=1)
        print(f"\n→ {a.json}")
        sys.exit(rc)


if __name__ == "__main__":
    main()
