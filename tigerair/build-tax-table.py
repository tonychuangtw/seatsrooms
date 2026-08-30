#!/usr/bin/env python3
"""把 fare-detail.js 的全網掃描結果整理成 tax-table.json。

  node fare-detail.js $(python3 pick-tax-dates.py) --out taxall.json
  python3 build-tax-table.py taxall.json

稅金（taxAmount）在同一航向上固定，跟日期／票價無關，所以量一次就能長期套用。
⚠ 台灣機場服務費 2026-09-01 起 500→750、2028-09-01 再到 1,000，
   調整日之後要重新量一次台灣出發的航向。
"""
import json, sys, datetime

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "tax-table.json"
routes, failed = {}, []

for item in json.load(open(src)):
    key = f"{item['origin']}-{item['destination']}"
    res = ((item.get("raw") or {}).get("result") or {}).get("data", {}).get("appFlightSearchResult")
    taxes = []
    if res:
        for jn in res.get("journeys", []):
            for leg in jn.get("legs", []):
                for al in leg.get("availabilityLegs", []):
                    for f in al.get("fares", []):
                        for pf in f.get("paxFares", []):
                            t = pf.get("ticketPrice", {}).get("taxAmount")
                            if t:
                                taxes.append(t)
    if not taxes:
        failed.append(key)
        continue
    uniq = sorted(set(taxes))
    routes[key] = {"tax": uniq[0], "sampleDate": item["date"],
                   "measuredAt": datetime.date.today().isoformat(),
                   **({"varies": uniq} if len(uniq) > 1 else {})}

json.dump({"note": "taxAmount 實測值，單位 TWD，單人單程。台灣出發 2026-09-01 起機場服務費調漲需重量。",
           "routes": routes}, open(out, "w"), ensure_ascii=False, indent=1)
print(f"{len(routes)} 條航向寫入 {out}；失敗 {len(failed)}: {' '.join(failed) if failed else '無'}")
by = {}
for k, v in routes.items():
    by.setdefault(v["tax"], []).append(k)
for t in sorted(by):
    print(f"  稅 {t:>6,}: {' '.join(sorted(by[t]))}")
