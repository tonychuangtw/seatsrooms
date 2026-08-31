#!/usr/bin/env python3
"""虎航降價監看 —— 掃 watchlist 裡的航線，跌破門檻或創新低就推 Telegram。

  python3 watch.py                 # 跑一輪
  python3 watch.py --dry           # 只印不推播
  python3 watch.py --init          # 用目前價格當基準，不推播

watchlist.json 一筆長這樣（threshold 比含稅總價、thresholdNet 比官網未稅價，
兩個都省略就只看創新低；"allRoutes": true 會展開成全部台灣進出的航向）：
  {"route": "KHH-CJU", "since": "2026-09-16", "until": "2027-03-27",
   "threshold": 3000, "note": "濟州，時間都可看"}

state 檔記住每個 (航線,日期) 看過的最低價，同一個價格不會重複吵。
"""
import argparse, json, os, subprocess, sys, time, urllib.request, urllib.error

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scan import all_routes, daily_prices, load_tax  # noqa: E402

WATCHLIST = os.path.join(HERE, "watchlist.json")
STATE = os.path.join(HERE, "watch-state.json")
VERIFY_STAMP = os.path.join(HERE, ".verify-stamp")
VERIFY_COOLDOWN = 8 * 60   # 秒
TG_ENV = os.environ.get("TG_ENV_FILE") or os.path.expanduser(
    "~/.claude/channels/telegram-seatsrooms/.env")
CHAT_ID = 711631512


def tg(text):
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


def verify(hits):
    """票價日曆是快取值，可能跟即時報價對不上。對最便宜的幾筆做即時查詢，
    順便把剩餘座位帶回來（要 camofox :9377；沒有就靜默略過）。

    促銷期間 watch 每分鐘跑一輪，每輪都開瀏覽器過 reCAPTCHA 會把分數打爆、
    而且一輪就跑掉一分多鐘。所以加冷卻：8 分鐘內驗過就不再驗，價格照推。"""
    if not hits:
        return
    try:
        if time.time() - os.path.getmtime(VERIFY_STAMP) < VERIFY_COOLDOWN:
            print("即時覆核冷卻中，這輪只推快取價")
            return
    except OSError:
        pass
    open(VERIFY_STAMP, "w").write(str(int(time.time())))
    args = []
    for h in hits:
        o, d = h["w"]["route"].split("-")
        args += [o, d, h["date"]]
    out = os.path.join(HERE, "verify-last.json")
    try:
        subprocess.run(["node", os.path.join(HERE, "fare-detail.js"), *args, "--out", out],
                       cwd=HERE, timeout=240, capture_output=True, check=True,
                       env={**os.environ, "TIGERAIR_CF_USER": "tigerair-watch"})
        detail = json.load(open(out))
    except Exception as e:
        print(f"即時覆核跳過：{str(e)[:120]}")
        return
    for h, item in zip(hits, detail):
        res = ((item.get("raw") or {}).get("result") or {}).get("data", {}).get("appFlightSearchResult")
        if not res:
            h["live"] = "即時查詢失敗"
            continue
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
                                    f"{seg.get('carrierCode','')}{seg.get('flightNumber','')}")
        if best:
            h["live"] = (f"官網即時報價：{best[5]} 含稅 NT${best[0]:,}"
                         f"（票價 {best[1]:,}＋稅 {best[2]:,}）剩 {best[3]} 位／此價 {best[4]} 張")
            # 海外出發的日曆價是快取＋匯率換算，常跟即時報價對不上；差超過 1% 就標出來
            if best[1] and h.get("amount") and abs(best[1] - h["amount"]) > h["amount"] * 0.01:
                h["live"] += f"\n  ⚠ 日曆價 {h['amount']:,} 是快取值已過時，以即時報價為準"
        else:
            h["live"] = "即時查詢無可售艙位"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="只印不推播")
    ap.add_argument("--init", action="store_true", help="建立基準，不推播")
    ap.add_argument("--verify", type=int, default=3, metavar="N",
                    help="用即時查詢覆核前 N 筆（含剩餘座位）；0 = 關閉")
    ap.add_argument("--list", default=WATCHLIST, metavar="FILE",
                    help="要跑哪份 watchlist（預設 watchlist.json）")
    ap.add_argument("--state", default=STATE, metavar="FILE", help="狀態檔")
    a = ap.parse_args()

    watches = json.load(open(a.list))
    # allRoutes: true 的項目展開成全部台灣進出的航向（促銷期間全網撿便宜用）
    expanded = []
    for w in watches:
        if not w.get("allRoutes"):
            expanded.append(w)
            continue
        for o, d, _ in all_routes():
            expanded.append({**w, "route": f"{o}-{d}"})
            expanded.append({**w, "route": f"{d}-{o}"})
    watches = expanded

    tax = load_tax()
    try:
        state = json.load(open(a.state))
    except Exception:
        state = {}

    hits, errors = [], []
    for w in watches:
        if w.get("disabled"):
            continue
        o, d = w["route"].split("-")
        t = tax.get(w["route"])
        try:
            rows = daily_prices(o, d, w["since"], w["until"])
        except Exception as e:
            errors.append(f"{w['route']}: {e}")
            continue
        for r in rows:
            k = f"{w['route']}|{r['date']}"
            prev = state.get(k, {}).get("low")
            total = r["amount"] + t if t is not None else None
            # 只有「這個 (航線,日期) 比我們記過的還便宜」才值得吵。少了這個條件，
            # 一個一直低於門檻的日期會在價格往上跳的時候也發通知（原 1,999 → 現 2,399
            # 照樣推「門檻」），看起來像降價其實是漲價。
            improved = prev is None or r["amount"] < prev

            # threshold 比的是含稅總價；thresholdNet 直接比官網的未稅價
            # （促銷文案講的「112 元起」「512 元起」都是未稅數字，用這個才對得上）
            thr, thr_net = w.get("threshold"), w.get("thresholdNet")
            cheap = thr_net is not None and r["amount"] <= thr_net
            if not cheap and thr is not None:
                # 稅金表還沒建好時退回用未稅價比門檻，寧可多吵一次也不要靜默失效
                cheap = (total if total is not None else r["amount"]) <= thr
            cheap = cheap and improved

            # 創新低這條規則會對任何跌幅開火。全網掃描用 noNewLow 整個關掉；
            # 一般需求用 newLowMax 設一個「還在射程內才通知」的未稅價上限，
            # 免得春節那種兩萬起跳的線每降一千就吵一次。
            new_max = w.get("newLowMax")
            newlow = (not w.get("noNewLow")) and improved and prev is not None \
                and (new_max is None or r["amount"] <= new_max)

            if cheap or newlow:
                hits.append({"w": w, "date": r["date"], "amount": r["amount"],
                             "total": total, "tax": t, "prev": prev,
                             "why": "門檻" if cheap else "新低"})
            if prev is None or r["amount"] < prev:
                state[k] = {"low": r["amount"], "ts": int(time.time())}
        time.sleep(0.3)

    json.dump(state, open(a.state, "w"), indent=0)

    if errors:
        print("錯誤：" + "; ".join(errors))
    if a.init:
        print(f"基準建立完成，{len(state)} 個 (航線,日期)")
        return
    if not hits:
        print(f"沒有新的便宜票（追蹤 {len(state)} 個 (航線,日期)）")
        return

    hits.sort(key=lambda h: h["total"] if h["total"] is not None else h["amount"])
    # 單一 watchlist 條目一輪最多列 5 筆：新條目第一輪沒有基準，整條航線幾十個日期
    # 會同時觸發（08-31 CTS-KHH 一口氣 26 筆洗版），只推最便宜的幾筆＋一行總數
    shown, kept, extra = {}, [], {}
    for h in hits:
        kid = id(h["w"])
        shown[kid] = shown.get(kid, 0) + 1
        if shown[kid] <= 5:
            kept.append(h)
        else:
            extra[h["w"]["route"]] = extra.get(h["w"]["route"], 0) + 1
    hits = kept
    if a.verify:
        verify(hits[:a.verify])
    lines = ["🐯 虎航降價"]
    for h in hits[:25]:
        w = h["w"]
        price = (f"{h['total']:,} 含稅" if h["total"] is not None
                 else f"{h['amount']:,} 未稅")
        was = f"（原 {h['prev']:,} 未稅）" if h["prev"] is not None else ""
        lines.append(f"{w['route']} {h['date']}　NT${price}　[{h['why']}]{was}"
                     + (f"\n  {h['live']}" if h.get("live") else "")
                     + (f"\n  {w['note']}" if w.get("note") else ""))
    if len(hits) > 25:
        lines.append(f"…另外還有 {len(hits) - 25} 筆")
    for rt, n in extra.items():
        lines.append(f"…{rt} 另有 {n} 個日期低於門檻（只列最便宜 5 筆）")
    lines.append("https://booking.tigerairtw.com/")
    text = "\n".join(lines)
    print(text)
    if not a.dry:
        tg(text)


if __name__ == "__main__":
    main()
