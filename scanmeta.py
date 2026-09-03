#!/usr/bin/env python3
"""五家票價掃描器共用的收尾：失敗航向補舊資料、寫 meta、必要時推 TG（2026-09-03 codex review）。

以前單一航向失敗就靜默變空、程式照樣 exit 0，排程會把「缺一條航線」的資料當完整版發布，
頁面也看不出來。現在每支 scan.py 在寫 --json 之後呼叫 finish()：

  1. failed 裡的航向若這輪一筆都沒有 → 從上一份 json 撈同航向（date >= since）補回來，標 stale: true
  2. 寫 <json 去副檔名>.meta.json：scannedAt／routes／ok／failed／staleFilled／missing／rows，
     後端 /api/<airline>/prices 帶給票價頁畫「最後掃描／失敗幾條」
  3. alert=True 且有失敗 → 推 TG（本線 bot）；關鍵航向失敗用 🔴
  4. 回傳 exit code：補不到（missing）或關鍵航向失敗 → 1，其餘 0

rows 會被就地 extend（stale 列補在後面），呼叫端要在 finish() 之後才 json.dump。
"""
import datetime, json, os, sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def finish(json_path, rows, pairs, failed, *, since=None, until=None, airline="",
           alert=False, critical=()):
    routes = [f"{o}-{d}" for o, d in pairs]
    have = {f"{r['origin']}-{r['destination']}" for r in rows}
    stale_filled, missing = [], []
    if failed:
        try:
            prev = json.load(open(json_path))
            if not isinstance(prev, list):
                prev = []
        except Exception:
            prev = []
        prev_by = {}
        for x in prev:
            prev_by.setdefault(f"{x['origin']}-{x['destination']}", []).append(x)
        for f in failed:
            k = f["route"]
            if k in have:
                continue            # 部分月份失敗但還有資料：記在 meta 就好，不補
            old = [x for x in prev_by.get(k, [])
                   if not since or x.get("date", "") >= since]
            if old:
                rows.extend({**x, "stale": True} for x in old)
                stale_filled.append(k)
            else:
                missing.append(k)

    now = datetime.datetime.now(datetime.timezone.utc)
    failed_routes = {f["route"] for f in failed}
    meta = {"airline": airline,
            "scannedAt": now.isoformat(timespec="seconds"),
            "scannedAtTaipei": (now + datetime.timedelta(hours=8)).strftime("%Y-%m-%d %H:%M"),
            "since": since, "until": until,
            "routes": len(routes), "ok": len(routes) - len(failed_routes),
            "failed": failed, "staleFilled": stale_filled, "missing": missing,
            "rows": len(rows)}
    json.dump(meta, open(os.path.splitext(json_path)[0] + ".meta.json", "w"),
              ensure_ascii=False, indent=1)

    rc = 0
    if failed:
        crit = set(critical or ())
        bad_crit = [f["route"] for f in failed if f["route"] in crit]
        msg = (f"{'🔴' if bad_crit else '⚠️'} {airline}掃描 {len(routes)} 航向有 {len(failed_routes)} 條失敗"
               + (f"（關鍵航線：{'、'.join(bad_crit)}）" if bad_crit else "")
               + (f"\n用上一份補回：{'、'.join(stale_filled)}" if stale_filled else "")
               + (f"\n沒有舊資料可補、頁面會缺：{'、'.join(missing)}" if missing else "")
               + "\n" + "；".join(f"{f['route']} {str(f['error'])[:60]}" for f in failed[:8]))
        print(msg, file=sys.stderr)
        if alert:
            sys.path.insert(0, ROOT)
            from tgpush import send
            send(msg)
        if missing or bad_crit:
            rc = 1
    return rc
