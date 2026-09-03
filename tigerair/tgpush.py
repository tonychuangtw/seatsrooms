#!/usr/bin/env python3
"""虎航這幾支監看程式共用的 Telegram 推播（本線 @seatsrroomsbot，不洗主頻道）。

回傳 True 代表 Telegram 真的回 200。呼叫端要拿這個結果決定 state 要不要落地：
9/3 codex review 抓到「先寫 state 再發 TG」——TG 一次沒送出去，那筆便宜票以後就
永遠不再通知。網路抖動／429 會重試，4xx（訊息格式錯）不重試直接回 False。"""
import json, os, time, urllib.error, urllib.request

TG_ENV = os.environ.get("TG_ENV_FILE") or os.path.expanduser(
    "~/.claude/channels/telegram-seatsrooms/.env")
CHAT_ID = 711631512
MAX_LEN = 4000   # Telegram 上限 4096，留一點餘裕


def _token():
    with open(TG_ENV) as f:
        return next(l.split("=", 1)[1].strip() for l in f
                    if l.startswith("TELEGRAM_BOT_TOKEN="))


def send(text, dry=False, tries=3):
    if dry:
        print("[dry] TG:\n" + text)
        return True
    try:
        token = _token()
    except Exception:
        print("no TG token, skipped push")
        return False
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 20] + "\n…（訊息過長已截斷）"
    body = json.dumps({"chat_id": CHAT_ID, "text": text,
                       "disable_web_page_preview": True}).encode()
    for i in range(tries):
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                     data=body, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                print(f"TG push: HTTP {r.status}")
                return True
        except urllib.error.HTTPError as e:
            msg = e.read()[:200]
            print(f"TG push failed ({i + 1}/{tries}): {e.code} {msg}")
            if e.code == 429:
                time.sleep(5 * (i + 1))
                continue
            if 400 <= e.code < 500:
                return False
        except Exception as e:
            print(f"TG push error ({i + 1}/{tries}): {str(e)[:120]}")
        time.sleep(3 * (i + 1))
    return False
