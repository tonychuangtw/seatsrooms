#!/usr/bin/env python3
"""華航現金票降價監看 —— 跌破門檻或創新低就推 Telegram。

  python3 watch.py            # 跑一輪
  python3 watch.py --dry      # 只印不推
  python3 watch.py --init     # 用目前價格當基準，不推播

watchlist.json 一筆（價格是**含稅** TWD，海外出發已換匯）：
  {"route": "KHH-CTS", "since": "2027-01-20", "until": "2027-01-26",
   "threshold": 15000, "newLowMax": 18000, "note": "高雄→札幌 1/23 前後"}
通知規則跟虎航同款：低於門檻「而且比上次通知更便宜」才推（防止漲價被推成好消息）；
創新低要低於 newLowMax 才推，noNewLow 可整個關掉。
"""
import argparse, datetime, json, os, sys, urllib.error, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scan import calendar, fx_rates  # noqa: E402

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
    try:
        st = json.load(open(STATE))
    except Exception:
        st = {}
    today = datetime.date.today().isoformat()

    lines, cal_cache = [], {}
    for w in watches:
        rt = w["route"]
        if rt not in cal_cache:
            o, d = rt.split("-")
            days = calendar(o, d) or {}
            fx = fx_rates()
            cal_cache[rt] = {dd: round(p * fx.get(cur, 1)) for dd, (p, cur, usd, fc) in days.items()}
        days = {d: p for d, p in cal_cache[rt].items()
                if w.get("since", "") <= d <= w.get("until", "9999") and d >= today}
        if not days:
            continue
        lowkey = f"low|{rt}|{w.get('since','')}"
        prev_low = st.get(lowkey)
        cur_low = min(days.values())
        for d, p in sorted(days.items()):
            k = f"{rt}|{d}"
            prev = st.get(k)
            thr = w.get("threshold")
            hit = None
            if thr and p <= thr and (prev is None or p < prev):
                hit = f"💰 {rt} {d} 含稅 {p:,}（門檻 {thr:,}）"
            elif (not w.get("noNewLow") and prev_low is not None and p < prev_low
                  and p <= w.get("newLowMax", 0)):
                hit = f"📉 {rt} {d} 含稅 {p:,} 創新低（原低點 {prev_low:,}）"
            if hit and not a.init:
                lines.append(hit + (f"｜{w['note']}" if w.get("note") else ""))
            if hit or prev is None or p != prev:
                st[k] = p
        st[lowkey] = cur_low if prev_low is None else min(prev_low, cur_low)

    json.dump(st, open(STATE, "w"))
    if lines:
        msg = "🇹🇼 華航現金票降價\n" + "\n".join(lines[:20])
        if len(lines) > 20:
            msg += f"\n…共 {len(lines)} 筆"
        if a.dry:
            print("[dry]\n" + msg)
        else:
            tg(msg)
    print(f"監看 {len(watches)} 筆、通知 {len(lines)}")


if __name__ == "__main__":
    main()
