#!/usr/bin/env python3
"""把 fare-detail.js 的輸出整理成一行一個艙等的表。"""
import json, sys

for item in json.load(open(sys.argv[1])):
    raw = item.get("raw") or {}
    res = (raw.get("result") or {}).get("data", {}).get("appFlightSearchResult")
    if not res:
        print(f"{item['origin']}-{item['destination']} {item['date']}  失敗: "
              f"{json.dumps(raw, ensure_ascii=False)[:160]}")
        continue
    for jn in res.get("journeys", []):
        for leg in jn.get("legs", []):
            for al in leg.get("availabilityLegs", []):
                seg = (al.get("availabilitySegments") or [{}])[0]
                det = (seg.get("availabilitySegmentDetails") or [{}])[0]
                flt = f"{seg.get('carrierCode','')}{seg.get('flightNumber','')}"
                dep = (seg.get("departureTime") or "")[11:16]
                for f in al.get("fares", []):
                    tp = (f.get("paxFares") or [{}])[0].get("ticketPrice", {})
                    print(f"{item['origin']}-{item['destination']} {item['date']} {flt} {dep} "
                          f"{f.get('productClass',''):<12} "
                          f"票價 {tp.get('fareAmount',0):>7,} "
                          f"稅 {tp.get('taxAmount',0):>5,} "
                          f"艙等加價 {tp.get('productClassAmount',0):>5,} "
                          f"= 總計 {tp.get('totalAmount',0):>7,}  "
                          f"剩 {det.get('remainingSeat','?')}/{det.get('totalSeat','?')} "
                          f"該價可訂 {f.get('availableCount','?')}")
