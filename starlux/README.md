# 星宇票價日曆

官網有一支公開的月票價日曆 API：不用登入、沒有 Akamai、curl 直接打得到，
**一次請求 = 一條航線一整個日曆月**。

```
POST https://ecapi.starlux-airlines.com/searchFlight/v2/flights/calendars/monthly
header: Content-Type: application/json, jx-lang: zh-TW
body:   {"cabin":"eco",
         "itineraries":[{"departure":"TPE","arrival":"NRT","departureDate":"2026-10-15"}],
         "travelers":{"adt":1,"chd":0,"inf":0}}
```

兩個卡最久的欄位名（正解在 `_nuxt/ed1a30d.js` 的 `getTravelersAndCabin`）：
- `travelers` 是 **adt / chd / inf**，不是 adult/child/infant
- `itineraries` 是 **departure / arrival**，不是 origin/destination

其他重點：
- cabin 只吃 `eco` / `ecoPremium` / `business` / `first`
- 必填只有 cabin / itineraries / travelers 三個，其餘選填
- **回的價格就是含稅總價**（TPE-NRT 日曆 8,574 ＝ 票價 6,170 ＋ 稅 2,404，
  跟 `/flights/search` 對得上），所以這條線不需要稅金表
- `amount` 隨旅客人數放大，要單人價就 `adt: 1`
- 可訂期間約未來 12 個月，超出回 HTTP 422（scan.py 當空月份處理）
- 航線圖：`GET .../utilities/v2/airports`，取 `isOperatedByJX` 的機場與
  `available[].carrierCode == "JX"` 的 waypoint → 37 個出發機場 / 94 個航向

## 用法
```bash
python3 scan.py --routes TPE-NRT,TPE-CTS --since 2026-09 --until 2027-03
python3 scan.py --all --since 2026-09 --until 2027-08 --json baseline.json   # 約 20 分鐘
python3 watch.py --init      # 建立基準
python3 watch.py             # 跌破門檻／創新低就推 TG
python3 generate-page.py baseline.json network.json out.html
```

## 死路存證（別再走一次）
- deeplink 猜 query 參數（`/booking/search-result?from=..&to=..`）不會觸發搜尋
- camofox 的真實 click 在 starlux.com 沒作用（點完 DOM 完全沒變）
- 頁面內 JS `.click()` 開得了機場選單、選得到出發地，但目的地的區域手風琴不展開
- `/請選擇出發地/.test(document.body.innerText)` 不能當「選單開了沒」的判斷 —— 那是按鈕自己的標籤

最後是直接讀前端 bundle 看出欄位名，不是靠錄封包。`jx*.js` 那幾支探路腳本留著當紀錄。
