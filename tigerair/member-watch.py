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
import argparse, datetime, json, os, subprocess, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from tgpush import send as tg  # noqa: E402
WATCH = os.path.join(HERE, "member-watch.json")
STATE = os.path.join(HERE, "member-state.json")
JWT_CACHE = os.path.join(HERE, ".member-jwt.json")
LAST = os.path.join(HERE, ".member-last.json")
BASELINE = os.path.join(HERE, "baseline.json")


def tpe_now():
    return (datetime.datetime.now(datetime.timezone.utc)
            + datetime.timedelta(hours=8)).strftime("%m/%d %H:%M")


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


def date_range(since, until, flight_days=None):
    """區間內每一天；有 baseline 就只留「日曆上真的有班機」的日子（9/3 gemini：
    高雄濟州一週只飛幾天，盲掃沒班機的日子一樣開瀏覽器等 20 秒、燒 reCAPTCHA 分數）。"""
    d = datetime.date.fromisoformat(since)
    end = datetime.date.fromisoformat(until)
    today = datetime.date.today()
    if d < today:
        d = today
    out = []
    while d <= end:
        if flight_days is None or d.isoformat() in flight_days:
            out.append(d.isoformat())
        d += datetime.timedelta(days=1)
    return out


def flight_days_map():
    """baseline.json → {航向: {有班機的日期}}；沒 baseline 回 {}（呼叫端就不過濾）。"""
    out = {}
    try:
        for r in json.load(open(BASELINE)):
            if r.get("amount"):
                out.setdefault(f"{r['origin']}-{r['destination']}", set()).add(r["date"])
    except Exception:
        pass
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
    ap.add_argument("--wr-wait", type=int, default=90, help="排隊室最多等幾秒（促銷當天可拉到 180）")
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
            return False
        seen.add(k)
        jobs.append({"route": route, "date": date, "w": w})
        return True

    for w in watches:
        for d in w.get("focus", []):
            add(w["route"], d, w)
    quota = a.n
    fdays = flight_days_map()
    ranges = {w["route"]: date_range(w["since"], w["until"], fdays.get(w["route"]))
              for w in watches}
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
            if add(r, ds[i], w):    # 已在 focus 裡的日期不占 quota（9/3 gemini）
                quota -= 1
            cur[r] = i + 1
            progressed = True
        if not progressed:
            break

    if not jobs:
        print("沒有要查的日期")
        return

    jwt = get_jwt()
    if not jwt:
        # 每 12 分鐘一輪，掉登入時只在第一次與之後每 6 小時吵一次
        last = st.get("__jwtAlertAt", 0)
        if time.time() - last > 6 * 3600:
            if tg("⚠️ 虎航會員查價：拿不到 JWT，tigerclub profile 可能掉登入了，"
                  "要重跑 tigerclub-login（Gmail 收 6 碼 → --code）", a.dry) and not a.dry:
                st["__jwtAlertAt"] = int(time.time())
                json.dump(st, open(STATE, "w"), indent=1, ensure_ascii=False)
        else:
            print("拿不到 JWT（已告警過，6 小時內不重複）")
        sys.exit(1)
    exp = jwt_exp(jwt)
    exp_tpe = (datetime.datetime.fromtimestamp(exp, datetime.timezone.utc)
               + datetime.timedelta(hours=8)).strftime("%m/%d %H:%M") if exp else "?"

    gen = st.get("__profileGen", 0)
    profile = "tigerair-member" if gen <= 1 else f"tigerair-member{gen}"
    args = []
    for j in jobs:
        o, d = j["route"].split("-")
        args += [o, d, j["date"]]
    print(f"這輪查 {len(jobs)} 筆（profile {profile}）："
          + " ".join(f"{j['route']}@{j['date']}" for j in jobs))
    fd_err = None
    try:
        # 促銷擁擠時排隊室最多等 --wr-wait 秒，timeout 要跟著放大
        r = subprocess.run(["node", os.path.join(HERE, "fare-detail.js"), *args,
                            "--jwt", jwt, "--delay", "20", "--wr-wait", str(a.wr_wait),
                            "--out", LAST],
                           cwd=HERE, timeout=120 + (110 + a.wr_wait) * len(jobs), check=True,
                           capture_output=True, text=True,
                           env={**os.environ, "TIGERAIR_CF_USER": profile})
        for line in r.stderr.splitlines():
            if "排隊" in line:
                print(line)       # 留下排隊室的實際回應長相，9/16 當天要看
        detail = json.load(open(LAST))
    except Exception as e:
        fd_err = str(e)[:200]
        print(f"fare-detail 失敗：{fd_err}")
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
            hits.append((j, best, reasons, k))

    # 整輪失敗的處理（9/3 codex：以前 fare-detail 整個炸掉 detail=[]，換 profile 的條件
    # 反而不成立，而且只印 log 沒人知道）：連續失敗計數，第 1 次告警、之後每 2 次換一個
    # 查價 profile 世代（reCAPTCHA 分數判死只能換身分；JWT 到期則靠 get_jwt 換新）
    fail = st.get("__fail", 0)
    st["__profileGen"] = gen
    if ok == 0:
        fail += 1
        why = fd_err or next((str((d.get("raw") or {}).get("error"))[:100] for d in detail
                              if (d.get("raw") or {}).get("error")), "全部無報價")
        if fail == 1:
            tg(f"⚠️ 虎航會員查價整輪失敗（{len(jobs)} 筆 0 成功）：{why}\n"
               f"profile {profile}，JWT 到期 {exp_tpe}；連續兩輪失敗會自動換查價 profile", a.dry)
        elif fail % 2 == 0:
            st["__profileGen"] = gen + 1 if gen else 2
            tg(f"⚠️ 虎航會員查價連續 {fail} 輪失敗：{why}\n"
               f"下輪換查價 profile 世代 {st['__profileGen']}（JWT 到期 {exp_tpe}）", a.dry)
        else:
            print(f"連續失敗 {fail} 輪：{why}")
    else:
        if fail:
            print(f"恢復成功（之前連續失敗 {fail} 輪）")
        fail = 0
    st["__fail"] = fail
    st["__health"] = {"lastRun": tpe_now(), "ok": ok, "jobs": len(jobs), "profile": profile,
                      "jwtExp": exp_tpe, "fail": fail,
                      "lastSuccess": tpe_now() if ok else (st.get("__health") or {}).get("lastSuccess")}

    sent = False
    if hits:
        lines = ["🐯 虎航會員查價（TigerClub 尊榮虎）"]
        for j, best, reasons, k in hits:
            tot, fare, tax, seats, cnt, flight = best
            o, d = j["route"].split("-")
            lines.append(f"{o}→{d} {j['date']} {flight}：未稅 {fare:,}＋稅 {tax:,}"
                         f"＝{tot:,}，剩 {seats} 位／此價 {cnt} 張")
            lines += ["  " + r for r in reasons]
            if j["w"].get("note"):
                lines.append(f"  （{j['w']['note']}）")
        sent = tg("\n".join(lines), a.dry)
        # TG 真的送出去才記 notified（9/3 codex：以前先記再送，送失敗就永遠不再通知）
        if sent and not a.dry:
            for j, best, reasons, k in hits:
                st[k]["notified"] = best[1]
        elif not sent:
            print("TG 沒送出去，notified 不記，下輪重推")
    json.dump(st, open(STATE, "w"), indent=1, ensure_ascii=False)
    print(f"查 {len(jobs)} 筆、成功 {ok}、通知 {len(hits)}" + ("" if sent or not hits else "（未送出）"))
    if hits and not sent and not a.dry:
        sys.exit(1)


if __name__ == "__main__":
    main()
