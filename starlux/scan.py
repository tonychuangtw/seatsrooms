#!/usr/bin/env python3
"""星宇航空票價掃描器 —— 走官網公開的月票價日曆 API（無需登入、無 Akamai）。

  python3 scan.py --routes TPE-NRT,TPE-CTS --since 2026-09 --until 2027-03
  python3 scan.py --all --since 2026-09 --until 2027-08 --top 30 --json baseline.json

⚠ 跟虎航不一樣：星宇日曆給的就是**含稅總價**（實測 TPE-NRT 2026-10-15 日曆 8,574
   ＝ /flights/search 的 base 6,170 ＋ totalTaxes 2,404），所以這裡不需要稅金表。
   amount 會隨旅客人數放大（adt=2 就是兩人份），預設 adt=1 即單人含稅價。
"""
import argparse, calendar, datetime, json, os, re, sys, threading, time
import urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
API = "https://ecapi.starlux-airlines.com"
CAL = f"{API}/searchFlight/v2/flights/calendars/monthly"
SEARCH = f"{API}/searchFlight/v2/flights/search"
FF_CACHE = os.path.join(HERE, "fare-families.json")
AIRPORTS = f"{API}/utilities/v2/airports"
NET_CACHE = os.path.join(HERE, "network.json")
FX_FILE = os.path.join(HERE, os.pardir, "cash-fx.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
HDR = {"User-Agent": UA, "Content-Type": "application/json",
       "Accept": "application/json", "jx-lang": "zh-TW",
       "Origin": "https://www.starlux-airlines.com",
       "Referer": "https://www.starlux-airlines.com/"}
CABINS = ("eco", "ecoPremium", "business", "first")

def fx_rates():
    """台幣匯率表（seatsrooms 既有的 cash-fx.json，twdPer[幣別] = 1 單位換多少台幣）。

    ⚠ 星宇的報價幣別是**由出發地決定的**，改 payload 或 header 都無法指定：
    台灣出發回 TWD，澳門出發回 MOP，日本出發回 JPY……。把它們當成同一個幣別排序
    會得到完全錯誤的結論（例：MFM→TPE 913 MOP 其實是 3,578 台幣，不是 913 台幣）。
    """
    try:
        with open(FX_FILE) as f:
            return json.load(f)["twdPer"]
    except Exception:
        return {"TWD": 1}


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
    routes, names, countries = {}, {}, {}
    for region in d["regions"]:
        for country in region["countries"]:
            cname = country.get("locName") or country.get("engName")
            for city in country["cities"]:
                for ap in city["airports"]:
                    names[ap["code"]] = city.get("locName") or city.get("engName")
                    countries[ap["code"]] = cname
                    if not ap.get("isOperatedByJX"):
                        continue
                    dests = sorted({a["waypoint"] for a in ap.get("available", [])
                                    if a.get("carrierCode") == "JX"
                                    and a.get("isRoundTripOrOneWay")
                                    and a.get("isSegmentExist")})
                    if dests:
                        routes[ap["code"]] = dests
    net = {"routes": routes, "names": names, "countries": countries,
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


_FX = None


def to_twd(amount, currency):
    global _FX
    if _FX is None:
        _FX = fx_rates()
    rate = _FX.get(currency)
    return round(amount * rate) if rate else None


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
            cur = p.get("currencyCode", "TWD")
            out.append({"origin": origin, "destination": dest,
                        "date": c["departureDate"], "amount": p["amount"],
                        "currency": cur, "twd": to_twd(p["amount"], cur),
                        "status": c.get("status")})
    return out


# ── 來回票 ──────────────────────────────────────────────────────────────────
# 實測（TPE-MFM、TPE-NRT 各一組，跟官網 airOffer.totalPrices.total 對過）：
#   來回總價(去 D, 回 R) = 去程RT月曆[D] + 回程RT月曆[R]
# 去程RT月曆：itineraries 帶兩段、不帶 goFareFamilyCode，回「去程日期」的月曆，價格跟回程日無關。
# 回程RT月曆：帶 goFareFamilyCode（該航線任一個**經濟艙**家族代碼，頭等代碼會給另一組價），
#   回「回程日期」的月曆，價格跟去程日期無關（只有去程之前的日子被遮成 unavailable）。
# 所以一條航線一個月只要兩次請求，任何天數的來回都能算出來。


def load_ff():
    try:
        return json.load(open(FF_CACHE))
    except Exception:
        return {}


def fare_families(origin, dest, ym, cabin="eco", cache=None, months_to_try=None):
    """這條航線該艙等的家族代碼，**由便宜到貴**排（Y4, Y3, Y2, Y1）。一條航線查一次，存檔。

    代碼格式是「艙等字母＋桶號＋市場」（例 Y3TWNEA），桶號越大越便宜。
    """
    cache = cache if cache is not None else load_ff()
    key = f"{origin}-{dest}|{cabin}"
    if key in cache:
        return cache[key]
    prefix = {"eco": "Y", "ecoPremium": "W", "business": "J", "first": "F"}[cabin]
    # 季節性航線（例：台中—札幌只飛冬季）第一個月可能沒班，往後幾個月找
    tries = [(m, day) for m in (months_to_try or [ym])[:6] for day in (15, 22, 8)]
    for m_, day in tries:
        go = f"{m_}-{day:02d}"
        ret = (datetime.date.fromisoformat(go) + datetime.timedelta(days=4)).isoformat()
        payload = {"cabin": cabin,
                   "itineraries": [{"departure": origin, "arrival": dest, "departureDate": go},
                                   {"departure": dest, "arrival": origin, "departureDate": ret}],
                   "travelers": {"adt": 1, "chd": 0, "inf": 0}}
        try:
            d = call(SEARCH, payload)
        except OutOfHorizon:
            return []
        except Exception:
            continue
        codes = {o["fareFamilyCode"] for f in (d.get("data") or {}).get("flights", [])
                 for o in f.get("airOffers", []) if o.get("fareFamilyCode", "").startswith(prefix)}
        if codes:
            def bucket(c):
                m = re.match(r"[A-Z](\d+)", c)
                return int(m.group(1)) if m else 0
            ordered = sorted(codes, key=bucket, reverse=True)
            cache[key] = ordered
            json.dump(cache, open(FF_CACHE, "w"), indent=1)
            return ordered
    return []


def _cal_map(payload):
    try:
        d = call(CAL, payload)
    except OutOfHorizon:
        return {}
    if not d.get("success"):
        raise RuntimeError(d.get("message", {}).get("content", "unknown error"))
    m = {}
    for c in d["data"]["calendars"] or []:
        p = c.get("price") or {}
        if p.get("amount"):
            m[c["departureDate"]] = to_twd(p["amount"], p.get("currencyCode", "TWD")) or p["amount"]
    return m


def go_calendar_rt(origin, dest, ym, cabin="eco", adt=1):
    """去程RT月曆 {date: twd}：itineraries 帶兩段、不帶家族代碼。價格跟回程日無關。"""
    mid = f"{ym}-15"
    ret_mid = (datetime.date.fromisoformat(mid) + datetime.timedelta(days=4)).isoformat()
    return _cal_map({"cabin": cabin, "travelers": {"adt": adt, "chd": 0, "inf": 0},
                     "itineraries": [{"departure": origin, "arrival": dest, "departureDate": mid},
                                     {"departure": dest, "arrival": origin, "departureDate": ret_mid}]})


def ret_calendar_rt(origin, dest, ym, ff, anchor_go, cabin="eco", adt=1):
    """回程RT月曆 {date: twd}：帶 goFareFamilyCode。

    ⚠ 家族代碼必須在 anchor_go 那天**真的有位**，否則整個月回空白（不是錯誤）。
    ⚠ 回程價會跟家族走（東京線 Y3→7,401、Y1→8,032），跟去程日期無關。
    """
    return _cal_map({"cabin": cabin, "travelers": {"adt": adt, "chd": 0, "inf": 0},
                     "goFareFamilyCode": ff,
                     "itineraries": [{"departure": origin, "arrival": dest, "departureDate": anchor_go},
                                     {"departure": dest, "arrival": origin, "departureDate": f"{ym}-15"}]})


def rt_totals(go, ret, nights):
    """把兩張月曆合成「那天出發、N 晚後回」的總價表 {date: (total, goPrice, retPrice)}。"""
    res = {}
    for d, g in go.items():
        r_date = (datetime.date.fromisoformat(d) + datetime.timedelta(days=nights)).isoformat()
        r = ret.get(r_date)
        if r:
            res[d] = (g + r, g, r)
    return res


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
    ap.add_argument("--rt", action="store_true",
                    help="來回模式：每航線每月抓去程RT月曆＋回程RT月曆（多一個月給跨月的回程）")
    ap.add_argument("--nights", type=int, default=3, help="--rt 時列表用幾晚（3天2夜=2）")
    ap.add_argument("--tw-only", action="store_true", help="只掃台灣出發的航向")
    ap.add_argument("--alert", action="store_true", help="有航向失敗就推 TG（排程用）")
    a = ap.parse_args()

    net = network(a.refresh_network)
    names = net["names"]
    if a.all:
        pairs = [(o, d) for o, ds in net["routes"].items() for d in ds]
    elif a.routes:
        pairs = [tuple(p.strip().upper().split("-")) for p in a.routes.split(",")]
    else:
        sys.exit("需要 --routes 或 --all")

    if a.tw_only:
        pairs = [p for p in pairs if p[0] in ("TPE", "RMQ", "KHH", "TNN")]
    ms = months(a.since, a.until)
    if a.rt:
        return main_rt(a, pairs, ms, names)
    print(f"# {len(pairs)} 個航向 × {len(ms)} 個月 = {len(pairs) * len(ms)} 次請求"
          f"（{a.cabin}，{a.adt} 位大人，含稅）", file=sys.stderr)

    rows, errors, route_err = [], [], {}
    for i, (o, d) in enumerate(pairs, 1):
        for ym in ms:
            try:
                rows.extend(month_prices(o, d, ym, a.cabin, a.adt))
            except Exception as e:
                errors.append(f"{o}-{d} {ym}: {str(e)[:80]}")
                route_err.setdefault(f"{o}-{d}", []).append(f"{ym} {str(e)[:60]}")
        if i % 10 == 0:
            print(f"  …{i}/{len(pairs)}", file=sys.stderr)

    rows.sort(key=lambda r: r["twd"] or r["amount"])
    print(f"# 有價日期 {len(rows)} 筆（{a.since} ~ {a.until}）"
          + (f"／失敗 {len(errors)} 次" if errors else "") + "\n")
    print(f"{'排名':<4}{'航線':<10}{'日期':<12}{'含稅 TWD':>10}  原幣")
    for i, r in enumerate(rows[:a.top], 1):
        orig = "" if r["currency"] == "TWD" else f"  {r['amount']:,} {r['currency']}"
        print(f"{i:<4}{r['origin']}-{r['destination']:<6}{r['date']:<12}"
              f"{(r['twd'] or 0):>10,}{orig}")

    best = {}
    for r in rows:
        k = f"{r['origin']}-{r['destination']}"
        if k not in best or (r["twd"] or r["amount"]) < (best[k]["twd"] or best[k]["amount"]):
            best[k] = r
    print(f"\n# 各航向最低含稅價（{len(best)} 條有票）")
    for k, r in sorted(best.items(), key=lambda kv: kv[1]["twd"] or kv[1]["amount"]):
        o, d = k.split("-")
        label = f"{names.get(o, o)}→{names.get(d, d)}"
        orig = "" if r["currency"] == "TWD" else f"（{r['amount']:,} {r['currency']}）"
        print(f"  {k:<9}{(r['twd'] or 0):>8,}  {r['date']}  {label}{orig}")

    if errors:
        print(f"\n# 失敗 {len(errors)} 次", file=sys.stderr)
        for e in errors[:10]:
            print("  " + e, file=sys.stderr)
    if a.json:
        sys.path.insert(0, os.path.dirname(HERE))
        from scanmeta import finish
        failed = [{"route": k, "error": f"{len(v)} 個月失敗：" + "；".join(v[:2])}
                  for k, v in route_err.items()]
        rc = finish(a.json, rows, pairs, failed, since=a.since, until=a.until, airline="星宇",
                    alert=a.alert, critical=("TPE-NRT", "NRT-TPE", "TPE-CTS", "CTS-TPE"))
        json.dump(rows, open(a.json, "w"), ensure_ascii=False, indent=1)
        print(f"\n→ {a.json}")
        sys.exit(rc)


def main_rt(a, pairs, ms, names):
    # 回程可能跨到下個月，回程月曆多抓一個月
    y, m = map(int, ms[-1].split("-"))
    m += 1
    if m > 12:
        m, y = 1, y + 1
    ret_ms = ms + [f"{y:04d}-{m:02d}"]
    print(f"# 來回：{len(pairs)} 個航向 × ({len(ms)} 去程月 + {len(ret_ms)} 回程月 + 1 次代碼查詢)"
          f" ≈ {len(pairs) * (len(ms) + len(ret_ms) + 1)} 次請求", file=sys.stderr)
    ff_cache = load_ff()
    data, errors = {}, []
    for i, (o, d) in enumerate(pairs, 1):
        fams = fare_families(o, d, ms[0], a.cabin, ff_cache, months_to_try=ms)
        if not fams:
            errors.append(f"{o}-{d}: 找不到 {a.cabin} 艙等家族代碼")
            continue
        go_all = {}
        for ym in ms:
            try:
                go_all.update(go_calendar_rt(o, d, ym, a.cabin, a.adt))
            except Exception as e:
                errors.append(f"{o}-{d} go {ym}: {str(e)[:80]}")
        if not go_all:
            continue
        # 錨定日 = 去程最便宜的那天（最便宜的家族在那天一定有位）；同價取最早
        anchor = min(go_all, key=lambda k: (go_all[k], k))
        ret_all, used = {}, None
        for ff in fams:                       # 便宜→貴，空的就退到下一個家族
            ret_all = {}
            for ym in ret_ms:
                try:
                    ret_all.update(ret_calendar_rt(o, d, ym, ff, anchor, a.cabin, a.adt))
                except Exception as e:
                    errors.append(f"{o}-{d} ret {ym}: {str(e)[:80]}")
            if ret_all:
                used = ff
                break
        data[f"{o}-{d}"] = {"origin": o, "destination": d, "ff": used, "anchor": anchor,
                            "go": go_all, "ret": ret_all}
        if i % 10 == 0:
            print(f"  …{i}/{len(pairs)}", file=sys.stderr)

    n = a.nights
    print(f"# 來回 {n} 晚（{n + 1} 天 {n} 夜）各航向最便宜出發日，含稅台幣（{len(data)} 條）\n")
    best = []
    for k, v in data.items():
        t = rt_totals(v["go"], v["ret"], n)
        if t:
            d0 = min(t, key=lambda x: t[x][0])
            best.append((t[d0][0], k, d0, t[d0][1], t[d0][2]))
    for tot, k, d0, g, r in sorted(best)[:a.top]:
        o, d = k.split("-")
        print(f"  {k:<9}{tot:>8,}  {d0} 出發（去 {g:,} ＋ 回 {r:,}）  {names.get(o, o)}⇄{names.get(d, d)}")
    if errors:
        print(f"\n# 失敗 {len(errors)} 次", file=sys.stderr)
        for e in errors[:10]:
            print("  " + e, file=sys.stderr)
    if a.json:
        json.dump({"scanned": datetime.datetime.now().isoformat(timespec="minutes"),
                   "cabin": a.cabin, "routes": data}, open(a.json, "w"), ensure_ascii=False)
        print(f"\n→ {a.json}")


if __name__ == "__main__":
    main()
