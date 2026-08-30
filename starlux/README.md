# 星宇票價日曆 —— 探路中（2026-08-30）

目標：做出跟 `../tigerair/` 一樣的全網現金票價格日曆。

## 已確認
`POST https://ecapi.starlux-airlines.com/searchFlight/v2/flights/calendars/monthly`
header 只要 `jx-lang: zh-TW`，不用登入、沒有 Akamai。

payload 共 6 個必填（來源：`_nuxt/ed1a30d.js` 的 `mHandleShowMonthPicker`）：
`{cabin, itineraries, travelers, goFareFamilyCode, promotion, corporateCode}`

已對出來的 3 個：
```json
{"cabin":"eco",
 "itineraries":[{"departure":"TPE","arrival":"NRT","departureDate":"2026-10-15"}],
 "travelers":{"adult":1,"child":0,"infant":0}}
```
→ 回 `validation.required (and 2 more errors)`（剩 3 個沒對出來）

**爬山訊號**：錯誤訊息裡的數字就是還缺幾個欄位。`{}` 是 6 個，每滿足一個少一個。

## 這三支腳本
- `jxcapture.js` 全程用 camofox 真實 click（snapshot ref）——選單打得開，但這狀態下 `[role=option]` 抓不到
- `jxgo5.js` 全程用頁面內 JS `.click()`——選得到 TPE，但 modal 關不掉、區域手風琴不展開
- `jxhybrid.js` 兩者混用——同上

## 兩個踩過的誤判（別再踩）
1. `/請選擇出發地/.test(document.body.innerText)` **不能**拿來判斷選單開了沒——
   那是按鈕自己的標籤，頁面一載入就是 true
2. camofox 的真實 click（`POST /tabs/:id/click`）在這個站沒作用（點完 DOM 完全沒變）；
   要用頁面內 JS `.click()`

## 目前唯一卡住的點
目的地面板的區域手風琴（臺灣／港澳／東北亞／…）點不開，`aria-expanded` 一直是 false。
NRT 其實已經在 innerHTML 裡，內容有 render 只是收合著。
建議改到 scout（192.168.1.158）跑——星宇的 UI 自動化在那台早就打通過。

下一步詳見 `../PROGRESS.md`（本機檔案，不在 repo）。
