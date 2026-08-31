#!/usr/bin/env python3
"""慢慢把 tax-table.json 補齊（每輪只量幾條）。

reCAPTCHA v3 是分數制：同一個 IP／瀏覽器 profile 連續建 session，大概第 10 筆之後
分數就掉到會被判 verify failed，而且要隔一段時間才回得來。所以稅金不能一次掃完，
用 timer 每 20 分鐘補 2 條，一天內就會補滿，也不會把分數燒掉。

  python3 backfill-tax.py            # 補 2 條
  python3 backfill-tax.py --n 3
  python3 backfill-tax.py --stale 90 # 順便重量超過 90 天沒更新的
"""
import argparse, collections, datetime, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
TABLE = os.path.join(HERE, "tax-table.json")
BASELINE = os.path.join(HERE, "baseline.json")
FALLBACK_BASELINE = os.path.join(HERE, "baseline-20260830.json")
TMP = os.path.join(HERE, ".backfill-last.json")
STATE = os.path.join(HERE, ".backfill-state.json")


def load_table():
    try:
        return json.load(open(TABLE))
    except Exception:
        return {"note": "taxAmount 實測值，單位 TWD，單人單程。", "routes": {}}


def sample_dates():
    """每個航向挑一個有票的日期（取中間那天，避開頭尾邊界）。"""
    src = BASELINE if os.path.exists(BASELINE) else FALLBACK_BASELINE
    by = collections.defaultdict(list)
    for r in json.load(open(src)):
        by[f"{r['origin']}-{r['destination']}"].append(r["date"])
    return {k: sorted(v)[len(v) // 2] for k, v in by.items()}


def load_state():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"fails": 0, "nextTry": None}


def profile_name(gen):
    # gen 0/1 = 最初的 tigerair-tax；之後 tigerair-tax2、tigerair-tax3…
    return "tigerair-tax" if gen <= 1 else f"tigerair-tax{gen}"


def save_state(st):
    json.dump(st, open(STATE, "w"), indent=0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=2, help="這輪最多量幾條")
    ap.add_argument("--stale", type=int, default=0, help="超過幾天沒量就重量（0=不重量）")
    ap.add_argument("--now", action="store_true", help="忽略退避時間,立刻試一輪")
    a = ap.parse_args()

    # 失敗就退避：reCAPTCHA 被判低分之後繼續猛打只會讓分數更難回來，
    # 每失敗一次把下次嘗試往後推一倍（30 分 → 1 小時 → 2 小時，上限 4 小時）。
    st = load_state()
    now = datetime.datetime.now()
    if not a.now and st.get("nextTry"):
        try:
            nxt = datetime.datetime.fromisoformat(st["nextTry"])
            if now < nxt:
                print(f"退避中（連續失敗 {st.get('fails', 0)} 次），"
                      f"{nxt.strftime('%m-%d %H:%M')} 之後再試")
                return
        except ValueError:
            pass

    table = load_table()
    dates = sample_dates()
    today = datetime.date.today()

    todo = [k for k in dates if k not in table["routes"]]
    if a.stale:
        cutoff = (today - datetime.timedelta(days=a.stale)).isoformat()
        todo += [k for k, v in table["routes"].items()
                 if k in dates and v.get("measuredAt", "") < cutoff]
    if not todo:
        print(f"稅金表已完整（{len(table['routes'])} 條航向），沒有要補的")
        return

    # 連續失敗時把佇列輪轉，避免固定卡在同樣的前幾條
    off = st.get("fails", 0) * a.n % len(todo)
    todo = todo[off:] + todo[:off]
    batch = todo[:a.n]
    args = []
    for k in batch:
        o, d = k.split("-")
        args += [o, d, dates[k]]
    print(f"待補 {len(todo)} 條，這輪量：{' '.join(batch)}")

    try:
        subprocess.run(["node", os.path.join(HERE, "fare-detail.js"), *args,
                        "--delay", "25", "--out", TMP],
                       cwd=HERE, timeout=120 + 90 * len(batch), check=True,
                       capture_output=True,
                       env={**os.environ,
                            "TIGERAIR_CF_USER": profile_name(st.get("profileGen", 0))})
    except subprocess.TimeoutExpired:
        print("fare-detail 逾時，這輪放棄")
    except subprocess.CalledProcessError as e:
        print(f"fare-detail 失敗：{e.stderr.decode()[:200] if e.stderr else e}")
    if not os.path.exists(TMP):
        return

    added, failed = [], []
    for item in json.load(open(TMP)):
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
        entry = {"tax": uniq[0], "sampleDate": item["date"],
                 "measuredAt": today.isoformat()}
        if len(uniq) > 1:
            entry["varies"] = uniq
        table["routes"][key] = entry
        added.append(f"{key}={uniq[0]}")

    json.dump(table, open(TABLE, "w"), ensure_ascii=False, indent=1)
    print(f"寫入 {len(table['routes'])}/{len(dates)} 條。"
          f"新增 {', '.join(added) if added else '無'}；"
          f"失敗 {', '.join(failed) if failed else '無'}")

    gen = st.get("profileGen", 0)
    if added:
        save_state({"fails": 0, "nextTry": None, "profileGen": gen})
    else:
        # 整輪失敗幾乎都是 reCAPTCHA 分數燒掉，而且實測燒掉的 profile 隔一天也
        # 回不來（08-31：tigerair-tax 退避到 4 小時仍連續失敗，換全新 profile 一次就過）
        # → 直接換下一個 profile，退避只留短的
        fails = st.get("fails", 0) + 1
        wait = min(60, 30 * (2 ** (fails - 1)))
        nxt = now + datetime.timedelta(minutes=wait)
        save_state({"fails": fails, "nextTry": nxt.isoformat(timespec="seconds"),
                    "profileGen": gen + 1})
        print(f"整輪都失敗（第 {fails} 次），退避 {wait} 分鐘到 {nxt.strftime('%m-%d %H:%M')}，"
              f"下輪換 profile {profile_name(gen + 1)}")


if __name__ == "__main__":
    main()
