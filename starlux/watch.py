#!/usr/bin/env python3
"""星宇降價監看 —— 跌破門檻或創新低就推 Telegram。

  python3 watch.py            # 跑一輪
  python3 watch.py --dry      # 只印不推
  python3 watch.py --init     # 用目前價格當基準，不推播

watchlist.json 一筆（threshold / newLowMax 都是**含稅**價，星宇日曆本來就含稅）：
  {"route": "TPE-NRT", "since": "2026-09", "until": "2027-08",
   "threshold": 9000, "newLowMax": 12000, "note": "東京"}
"""
import argparse, json, os, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scan import month_prices, months, network  # noqa: E402

WATCHLIST = os.path.join(HERE, "watchlist.json")
STATE = os.path.join(HERE, "watch-state.json")
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--init", action="store_true")
    a = ap.parse_args()

    watches = json.load(open(WATCHLIST))
    names = network()["names"]
    try:
        state = json.load(open(STATE))
    except Exception:
        state = {}

    hits, errors = [], []
    for w in watches:
        if w.get("disabled"):
            continue
        o, d = w["route"].split("-")
        for ym in months(w["since"], w["until"]):
            try:
                rows = month_prices(o, d, ym, w.get("cabin", "eco"))
            except Exception as e:
                errors.append(f"{w['route']} {ym}: {str(e)[:70]}")
                continue
            for r in rows:
                k = f"{w['route']}|{r['date']}"
                prev = state.get(k, {}).get("low")
                # 只有比記過的更便宜才值得吵；少了這條，一個長期低於門檻的日期
                # 在漲價時也會發通知（看起來像降價，其實是漲價）
                improved = prev is None or r["amount"] < prev
                thr = w.get("threshold")
                cheap = improved and thr is not None and r["amount"] <= thr
                new_max = w.get("newLowMax")
                newlow = (improved and prev is not None and not w.get("noNewLow")
                          and (new_max is None or r["amount"] <= new_max))
                if cheap or newlow:
                    hits.append({"w": w, "date": r["date"], "amount": r["amount"],
                                 "prev": prev, "why": "門檻" if cheap else "新低"})
                if improved:
                    state[k] = {"low": r["amount"], "ts": int(time.time())}

    json.dump(state, open(STATE, "w"), indent=0)
    if errors:
        print("錯誤：" + "; ".join(errors[:5]))
    if a.init:
        print(f"基準建立完成，{len(state)} 個 (航線,日期)")
        return
    if not hits:
        print(f"沒有新的便宜票（追蹤 {len(state)} 個 (航線,日期)）")
        return

    hits.sort(key=lambda h: h["amount"])
    lines = ["✨ 星宇降價"]
    for h in hits[:25]:
        w = h["w"]
        o, d = w["route"].split("-")
        was = f"（原 {h['prev']:,}）" if h["prev"] is not None else ""
        lines.append(f"{w['route']} {h['date']}　NT${h['amount']:,} 含稅　[{h['why']}]{was}"
                     f"\n  {names.get(o, o)}→{names.get(d, d)}"
                     + (f"　{w['note']}" if w.get("note") else ""))
    if len(hits) > 25:
        lines.append(f"…另外還有 {len(hits) - 25} 筆")
    lines.append("https://www.starlux-airlines.com/zh-TW/booking/book-flight/search-a-flight")
    text = "\n".join(lines)
    print(text)
    if not a.dry:
        tg(text)


if __name__ == "__main__":
    main()
