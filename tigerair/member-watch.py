#!/usr/bin/env python3
"""會員查價輪替（9/16 促銷的保險層：匿名 daily-prices 看不到會員票時就靠這支）。

讀 member-watch.json（照優先序排：濟州全期間 → 札幌雪季 → 仙台雪季），每輪：
1. 取會員 JWT（member-jwt.js，tigerclub profile 免 reCAPTCHA；快取 .member-jwt.json，
   剩 30 分鐘以上就重用 —— JWT 效期 12 小時，別每輪都開瀏覽器）
2. 排這輪要查的日期：每筆的 focus 日期每輪必查，剩下的 quota 用游標在各航向的
   日期範圍輪流推進（游標存 member-state.json 的 __cursor，跨輪接續）
3. fare-detail.js --jwt 逐日查（查價 profile 與登入身分解耦，reCAPTCHA 分數
   燒掉就換 profile 世代，跟 backfill-tax 同一招）
4. 通知規則（推 TG）：
   - 未稅票價 ≤ thresholdNet（預設 700，抓 112/512 那兩檔）→ 🔥
   - 會員價比匿名 baseline 同日便宜 5% 以上 → 🅜 會員專屬價
   - 都要配「比上次通知時更便宜」才推（教訓：只比門檻會把漲價推成好消息）

  python3 member-watch.py             # 一輪（timer 用）
  python3 member-watch.py --n 8       # 這輪最多查 8 個日期
  python3 member-watch.py --dry       # 只印不推
"""
import argparse, datetime, json, os, subprocess, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
WATCH = os.path.join(HERE, "member-watch.json")
STATE = os.path.join(HERE, "member-state.json")
JWT_CACHE = os.path.join(HERE, ".member-jwt.json")
LAST = os.path.join(HERE, ".member-last.json")
BASELINE = os.path.join(HERE, "baseline.json")
TG_ENV = os.environ.get("TG_ENV_FILE") or os.path.expanduser(
    "~/.claude/channels/telegram-seatsrooms/.env")
CHAT_ID = 711631512


def tg(text, dry=False):
    if dry:
        print("[dry] TG:\n" + text)
        return
    try:
        with open(TG_ENV) as f:
            token = next(l.split("=", 1)[1].strip() for l in f
                         if l.startswith("TELEGRAM_BOT_TOKEN="))
    except Exception:
        print("no TG token, skipped push")
        return
    body = json.dumps({"chat_id": CHAT_ID, "text": text,
                       "disable_web_page_preview": True}).encode()
    req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                 data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            print(f"TG push: HTTP {r.status}")
    except urllib.error.HTTPError as e:
        print(f"TG push failed: {e.code} {e.read()[:200]}")


def jwt_exp(tok):
    import base64
    try:
        p = tok.split(".")[1]
        p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p)).get("exp", 0)
    except Exception:
        return 0


def get_jwt():
    try:
        c = json.load(open(JWT_CACHE))
        if c.get("exp", 0) - time.time() > 30 * 60:
            return c["jwt"]
    except Exception:
        pass
    r = subprocess.run(["node", os.path.join(HERE, "member-jwt.js")],
                       cwd=HERE, timeout=90, capture_output=True, text=True)
    if r.returncode or not r.stdout.strip():
        print(f"member-jwt 失敗：{r.stderr.strip()[:200]}")
        return None
    tok = r.stdout.strip().splitlines()[-1]
    json.dump({"jwt": tok, "exp": jwt_exp(tok)}, open(JWT_CACHE, "w"))
    return tok


def date_range(since, until):
    d = datetime.date.fromisoformat(since)
    end = datetime.date.fromisoformat(until)
    today = datetime.date.today()
    if d < today:
        d = today
    out = []
    while d <= end:
        out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def baseline_map():
    """匿名日曆價（未稅），比對會員價用。沒 baseline 就空表。"""
    try:
        return {f"{r['origin']}-{r['destination']}|{r['date']}": r["amount"]
                for r in json.load(open(BASELINE)) if r.get("amount")}
    except Exception:
        return {}


def cheapest(item):
    """從 fare-detail 一筆結果取最便宜艙等：(total, fare, tax, seats, count, flight)。"""
    res = ((item.get("raw") or {}).get("result") or {}).get("data", {}) \
        .get("appFlightSearchResult")
    if not res:
        return None
    best = None
    for jn in res.get("journeys", []):
        for leg in jn.get("legs", []):
            for al in leg.get("availabilityLegs", []):
                det = ((al.get("availabilitySegments") or [{}])[0]
                       .get("availabilitySegmentDetails") or [{}])[0]
                for f in al.get("fares", []):
                    tp = (f.get("paxFares") or [{}])[0].get("ticketPrice", {})
                    tot = tp.get("totalAmount")
                    if tot and (best is None or tot < best[0]):
                        seg = (al.get("availabilitySegments") or [{}])[0]
                        best = (tot, tp.get("fareAmount"), tp.get("taxAmount"),
                                det.get("remainingSeat"), f.get("availableCount"),
                                f"{seg.get('carrierCode', '')}{seg.get('flightNumber', '')}")
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=6, help="這輪最多查幾個日期（focus 不占額外 quota）")
    ap.add_argument("--dry", action="store_true", help="只印不推播")
    a = ap.parse_args()

    watches = json.load(open(WATCH))
    try:
        st = json.load(open(STATE))
    except Exception:
        st = {}
    cur = st.setdefault("__cursor", {})
    today = datetime.date.today().isoformat()

    # 排隊：focus 日期每輪必查（去重），剩下 quota 由游標在各航向輪流推進
    jobs, seen = [], set()

    def add(route, date, w):
        k = f"{route}|{date}"
        if k in seen or date < today:
            return
        seen.add(k)
        jobs.append({"route": route, "date": date, "w": w})

    for w in watches:
        for d in w.get("focus", []):
            add(w["route"], d, w)
    quota = a.n
    ranges = {w["route"]: date_range(w["since"], w["until"]) for w in watches}
    # round-robin：每次從游標處取下一個日期，輪完一圈折返起點
    while quota > 0:
        progressed = False
        for w in watches:
            if quota <= 0:
                break
            r = w["route"]
            ds = ranges[r]
            if not ds:
                continue
            i = cur.get(r, 0) % len(ds)
            add(r, ds[i], w)
            cur[r] = i + 1
            quota -= 1
            progressed = True
        if not progressed:
            break

    if not jobs:
        print("沒有要查的日期")
        return

    jwt = get_jwt()
    if not jwt:
        tg("⚠️ 虎航會員查價：拿不到 JWT，tigerclub profile 可能掉登入了，要重跑 tigerclub-login",
           a.dry)
        sys.exit(1)

    gen = st.get("__profileGen", 0)
    profile = "tigerair-member" if gen <= 1 else f"tigerair-member{gen}"
    args = []
    for j in jobs:
        o, d = j["route"].split("-")
        args += [o, d, j["date"]]
    print(f"這輪查 {len(jobs)} 筆（profile {profile}）："
          + " ".join(f"{j['route']}@{j['date']}" for j in jobs))
    try:
        subprocess.run(["node", os.path.join(HERE, "fare-detail.js"), *args,
                        "--jwt", jwt, "--delay", "20", "--out", LAST],
                       cwd=HERE, timeout=120 + 90 * len(jobs), check=True,
                       capture_output=True,
                       env={**os.environ, "TIGERAIR_CF_USER": profile})
        detail = json.load(open(LAST))
    except Exception as e:
        print(f"fare-detail 失敗：{str(e)[:200]}")
        detail = []

    base = baseline_map()
    hits, ok = [], 0
    for j, item in zip(jobs, detail):
        best = cheapest(item)
        k = f"{j['route']}|{j['date']}"
        if not best:
            st[k] = {**st.get(k, {}), "err": (item.get("error") or "no fare")[:80],
                     "at": today}
            continue
        ok += 1
        tot, fare, tax, seats, cnt, flight = best
        prev = st.get(k, {})
        st[k] = {"fare": fare, "tax": tax, "total": tot, "seats": seats,
                 "flight": flight, "at": today,
                 "notified": prev.get("notified")}
        thr = j["w"].get("thresholdNet", 700)
        anon = base.get(k)
        reasons = []
        if fare is not None and fare <= thr:
            reasons.append(f"🔥 未稅 {fare:,} ≤ 門檻 {thr}")
        if fare is not None and anon and fare < anon * 0.95:
            note = ""
            if not j["route"].split("-")[0] in ("TPE", "KHH", "RMQ", "TNN"):
                note = "（海外出發日曆是快取值，可能是快取落差非會員折扣）"
            reasons.append(f"🅜 會員價 {fare:,} < 匿名日曆 {anon:,}{note}")
        # 「比上次通知時更便宜」才推：漲價不推、同價不重複推
        if reasons and (prev.get("notified") is None or fare < prev["notified"]):
            if not a.dry:
                st[k]["notified"] = fare
            hits.append((j, best, reasons))

    st["__profileGen"] = gen  # 預留：整輪全掛時下輪換世代
    if ok == 0 and detail:
        st["__profileGen"] = gen + 1 if gen else 2
        print(f"整輪沒拿到任何報價，下輪換 profile 世代 {st['__profileGen']}")
    json.dump(st, open(STATE, "w"), indent=1, ensure_ascii=False)

    if hits:
        lines = ["🐯 虎航會員查價（TigerClub 尊榮虎）"]
        for j, best, reasons in hits:
            tot, fare, tax, seats, cnt, flight = best
            o, d = j["route"].split("-")
            lines.append(f"{o}→{d} {j['date']} {flight}：未稅 {fare:,}＋稅 {tax:,}"
                         f"＝{tot:,}，剩 {seats} 位／此價 {cnt} 張")
            lines += ["  " + r for r in reasons]
            if j["w"].get("note"):
                lines.append(f"  （{j['w']['note']}）")
        tg("\n".join(lines), a.dry)
    print(f"查 {len(jobs)} 筆、成功 {ok}、通知 {len(hits)}")


if __name__ == "__main__":
    main()
