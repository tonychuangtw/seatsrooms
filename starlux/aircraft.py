#!/usr/bin/env python3
"""星宇機型細分：GF 只寫「Airbus A350」，星宇自家 /flights/search 會給 aircraftCode
（351=A350-1000、359=A350-900、339=A330-900neo、321=A321neo），把 ../aircraft/aircraft-map.json
裡 JX 班號的機型換成細分名稱。一條航向查一次（約 4 秒一次，星宇 search 有 429 限流）。

  python3 aircraft.py            # 台灣出發＋回程所有 JX 航向
"""
import datetime, json, os, sys, time
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from scan import SEARCH, call, network  # noqa: E402
MAP = os.path.join(HERE, os.pardir, "aircraft", "aircraft-map.json")
TW = ("TPE", "RMQ", "KHH", "TNN")

def pretty(name):
    n = (name or "").upper().replace("PASSENGER", "").strip()
    n = n.replace("AIRBUS ", "Airbus ").replace("BOEING ", "Boeing ")
    return n.replace("NEO", "neo")

def search(o, d):
    base = datetime.date.today() + datetime.timedelta(days=28)
    for add in (0, 3, 30, 60, 90):
        day = (base + datetime.timedelta(days=add)).isoformat()
        payload = {"cabin": "eco",
                   "itineraries": [{"departure": o, "arrival": d, "departureDate": day}],
                   "travelers": {"adt": 1, "chd": 0, "inf": 0}}
        try:
            r = call(SEARCH, payload)
        except Exception as e:
            time.sleep(6)
            continue
        flights = (r.get("data") or {}).get("flights") or []
        if flights:
            names = {a["code"]: a.get("aircraft") for a in (r.get("meta") or {}).get("aircraft", [])}
            out = {}
            for f in flights:
                for fd in f.get("flightDetails") or []:
                    fn = fd.get("marketingFlightNumber") or fd.get("flightNumber")
                    code = fd.get("aircraftCode")
                    if fn and code:
                        out[f"JX{fn}"] = pretty(names.get(code, code))
            return out, day
    return {}, None

def main():
    net = network()
    routes = []
    for o, ds in (net.get("routes") or {}).items():
        if o in TW:
            for d in ds:
                routes += [(o, d), (d, o)]
    m = json.load(open(MAP)) if os.path.exists(MAP) else {}
    changed = 0
    for o, d in routes:
        fl, day = search(o, d)
        time.sleep(4)
        k = f"{o}-{d}"
        entry = m.setdefault(k, {})
        for fn, ac in fl.items():
            e = entry.get(fn) or {"airline": "星宇航空", "pitch": None, "cabin": "經濟艙", "dates": []}
            types = [t for t in (e.get("types") or ([e["aircraft"]] if e.get("aircraft") else [])) if not t.startswith("Airbus A350") and not t.startswith("Airbus A330")]
            if ac not in types:
                types.append(ac)
            e["types"] = types; e["aircraft"] = " / ".join(types)
            e["jxSampled"] = day; entry[fn] = e; changed += 1
        print(f"{k}: {len(fl)} 班 {', '.join(f'{a}={b}' for a, b in list(fl.items())[:4])}")
    json.dump(m, open(MAP, "w"), ensure_ascii=False, indent=1)
    print("updated", changed)

if __name__ == "__main__":
    main()
