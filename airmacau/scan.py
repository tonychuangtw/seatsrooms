#!/usr/bin/env python3
"""澳門航空（NX）全網票價日曆掃描。

資料源（2026-09-02 打通）：
  POST https://web.airmacau.com.cn/ndc-air/api/dlxPriceCalendar
  body {"hcType":"ow","currency":"TWD","itineraries":[{"org":"TPE","dest":"MFM","date":"YYYY-MM-DD"}]}
  headers 只要 content-type + channel: PC + lang: zh-TW（帶 UA 保險）
  → 一次請求回「整個可訂區間」每天的最低價（今天 ~ 約 10 個月後），比虎航一年一段還省
  ⚠ 必須打 .cn 主機：web.airmacau.com.mo 的 /ndc-air 直接 403
  ⚠ currency 參數有效（跟星宇不同），一律要 TWD 就不用匯率換算
  ⚠ 價格是「未稅票價」：Google Flights 同日含稅價高 1,400~1,900（9/2 三航向實測），
     跟虎航 daily-prices 同型。av_search（真報價/稅金明細）有風控（406 帳號存在風險），拿不到稅
  ⚠ date 欄位隨便給一個未來日即可，回應範圍不受它影響
  ⚠ totalPrice 可能是 null（當天沒班/沒價），要過濾
  ⚠ 轉機行程也會報價（TPE-NRT 經澳門），v1 只掃 MFM⇄X 直航網

  python3 scan.py --all --json baseline.json     # 全網（MFM⇄94 機場探測，~3 分鐘）
  python3 scan.py --routes TPE-MFM,MFM-TPE
"""
import argparse, datetime, json, time, os, sys, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://web.airmacau.com.cn/ndc-air/api/dlxPriceCalendar"
AIRPORTS = "https://web.airmacau.com.cn/service-basic/airport/find"
NETWORK = os.path.join(HERE, "network.json")
HDRS = {"content-type": "application/json", "channel": "PC", "lang": "zh-TW",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"}
GAP = 0.4  # 秒；澳航沒看到 429，但別欺負人家


def post(body, timeout=25):
    req = urllib.request.Request(API, data=json.dumps(body).encode(), headers=HDRS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def calendar(org, dest, retries=2):
    """一個航向的完整日曆：[{date, amount}]，amount=未稅 TWD。"""
    anchor = (datetime.date.today() + datetime.timedelta(days=30)).isoformat()
    body = {"hcType": "ow", "currency": "TWD",
            "itineraries": [{"org": org, "dest": dest, "date": anchor}]}
    for i in range(retries + 1):
        try:
            d = post(body)
            rows = d.get("responseData") or []
            return [{"date": r["from"], "amount": r["totalPrice"]}
                    for r in rows if r.get("totalPrice")]
        except Exception as e:
            if i == retries:
                print(f"  {org}-{dest} 失敗：{str(e)[:80]}", file=sys.stderr)
                return None
            time.sleep(2 * (i + 1))


RT_API = "https://web.airmacau.com.cn/service-biz/api/price_calendar"

def rt_matrix(org, dest, retries=2):
    """來回矩陣（今天起約 30 天視窗，官網 price_calendar，固定視窗、date 參數不影響範圍）。
    回 {"出發日|回程日": 來回未稅總價}。實測來回票價比兩張單程相加便宜 8~18%（KHH⇄MFM 中位 0.82）。"""
    anchor = (datetime.date.today() + datetime.timedelta(days=7)).isoformat()
    anchor2 = (datetime.date.today() + datetime.timedelta(days=10)).isoformat()
    body = {"hcType": "rt", "currency": "TWD",
            "itineraries": [{"org": org, "dest": dest, "date": anchor},
                            {"org": dest, "dest": org, "date": anchor2}]}
    req = urllib.request.Request(RT_API, data=json.dumps(body).encode(), headers=HDRS)
    for i in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=25) as r:
                d = json.load(r)
            return {f"{x['from']}|{x['to']}": x["totalPrice"]
                    for x in (d.get("responseData") or []) if x.get("totalPrice")}
        except Exception as e:
            if i == retries:
                print(f"  rt {org}-{dest} 失敗：{str(e)[:80]}", file=sys.stderr)
                return {}
            time.sleep(2 * (i + 1))


def network(refresh=False):
    """機場中文名／國別（官網 airport API，快取 7 天）。routes 由掃描時實際有價決定。"""
    try:
        n = json.load(open(NETWORK))
        age = time.time() - n.get("fetchedAt", 0)
        if not refresh and age < 7 * 86400:
            return n
    except Exception:
        pass
    req = urllib.request.Request(AIRPORTS, headers=HDRS)
    with urllib.request.urlopen(req, timeout=25) as r:
        rows = json.load(r)["responseData"]
    names, countries = {}, {}
    for a in rows:
        code = a["par"]
        if "-" in code:      # SHA-PVG / BKK-DMK 這類城市合稱，跳過
            continue
        names[code] = a.get("shortAirportNameTw") or a.get("airPortName") or code
        countries[code] = a.get("nationalityId") or "?"
    n = {"names": names, "countries": countries, "routes": {}, "fetchedAt": time.time()}
    json.dump(n, open(NETWORK, "w"), ensure_ascii=False)
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--routes", help="逗號分隔，如 TPE-MFM,MFM-TPE")
    ap.add_argument("--all", action="store_true", help="MFM⇄全部機場探測掃描")
    ap.add_argument("--json", help="輸出 json 檔")
    ap.add_argument("--rt", action="store_true",
                    help="抓台灣⇄澳門三條的來回矩陣（30 天視窗）寫 baseline-rt.json")
    ap.add_argument("--top", type=int, default=15)
    a = ap.parse_args()

    net = network()
    if a.rt:
        rtx = {}
        for o in ("TPE", "KHH", "RMQ"):
            m = rt_matrix(o, "MFM")
            time.sleep(GAP)
            if m:
                rtx[f"{o}-MFM"] = m
        out_f = os.path.join(HERE, "baseline-rt.json")
        json.dump(rtx, open(out_f, "w"))
        print(f"來回矩陣 {', '.join(f'{k}:{len(v)}組' for k, v in rtx.items())} → {out_f}")
        if not (a.routes or a.all):
            return
    if a.routes:
        pairs = [tuple(r.split("-")) for r in a.routes.split(",")]
    elif a.all:
        # MFM⇄全部（直航網）＋台灣三場⇄全部（經澳門轉機也報價，Tony 要看轉機能去哪）
        pairs, seen = [], set()
        for org in ["MFM", "TPE", "KHH", "RMQ"]:
            for x in sorted(net["names"]):
                if x == org:
                    continue
                for p in [(org, x), (x, org)]:
                    if p not in seen:
                        seen.add(p)
                        pairs.append(p)
    else:
        pairs = [("TPE", "MFM"), ("MFM", "TPE"), ("KHH", "MFM"),
                 ("MFM", "KHH"), ("RMQ", "MFM"), ("MFM", "RMQ")]

    out, routes_found, fails = [], {}, 0
    for org, dest in pairs:
        rows = calendar(org, dest)
        time.sleep(GAP)
        if rows is None:
            fails += 1
            continue
        if not rows:
            continue
        routes_found.setdefault(org, []).append(dest)
        cc = net["countries"].get(dest if org == "MFM" else org, "?")
        for r in rows:
            out.append({"origin": org, "destination": dest, "date": r["date"],
                        "amount": r["amount"], "currency": "TWD", "twd": r["amount"],
                        "country": cc})

    # 掃出來的實際航線寫回 network.json（給產頁器分組用）
    if a.all and routes_found:
        net["routes"] = {k: sorted(v) for k, v in routes_found.items()}
        json.dump(net, open(NETWORK, "w"), ensure_ascii=False)

    dirs = {f"{r['origin']}-{r['destination']}" for r in out}
    print(f"# 航向 {len(dirs)} 條 / 有價日期 {len(out)} 筆 / 失敗 {fails}")
    best = {}
    for r in out:
        k = f"{r['origin']}-{r['destination']}"
        if k not in best or r["amount"] < best[k]["amount"]:
            best[k] = r
    print(f"\n各航向最低（未稅 TWD）")
    for k, r in sorted(best.items(), key=lambda x: x[1]["amount"])[:a.top]:
        name = f"{net['names'].get(r['origin'], r['origin'])}→{net['names'].get(r['destination'], r['destination'])}"
        print(f"  {k:12s} {name:14s} {r['amount']:>7,}  {r['date']}")

    if a.json:
        json.dump(out, open(a.json, "w"), ensure_ascii=False)
        print(f"\n→ {a.json}")


if __name__ == "__main__":
    main()
