#!/usr/bin/env python3
"""每日掃描後把 baseline 存一份壓縮快照到 history/，給價格趨勢用。

  python3 history-snapshot.py <baseline.json> <history-dir> [字尾]

檔名用台北日期（可加字尾區分 rt）；同一天重跑就覆蓋（以最後一次為準）。"""
import gzip, shutil, sys, datetime, os
src, hdir = sys.argv[1], sys.argv[2]
suffix = ("-" + sys.argv[3]) if len(sys.argv) > 3 else ""
tpe = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
dst = os.path.join(hdir, tpe.strftime("%Y%m%d") + suffix + ".json.gz")
with open(src, "rb") as f, gzip.open(dst, "wb") as g:
    shutil.copyfileobj(f, g)
print(f"{dst}  {os.path.getsize(dst)//1024} KB")
