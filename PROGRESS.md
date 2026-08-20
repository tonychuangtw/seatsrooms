STATUS: in-progress
OBJECTIVE: 依 2026-08-21 Tony 核可的檢修清單，補掉 seatsrooms 線的六個弱點（掃描器靜默死亡、seats.aero 閒置、public repo 歷史、方向誤判、過期需求、死碼）
NEXT_ACTION: 見下方「進度」未勾選項，由上往下做
VALIDATION: node claude-shared/scripts/seatsrooms-monitor/*.test.js 全綠；DRY_RUN=1 跑 aggregate-airlines.js 比對 results.json 列數不變
BLOCKERS: 無
PATHS: ~/TelegramClaude/claude-shared/scripts/seatsrooms-monitor/（aggregate-airlines.js, scanner.js, scan-health-watch.js, airlines/）、~/TelegramClaude/seatsrooms/（index.html, .gitignore）
UPDATED: 2026-08-21 00:50 台北

# seatsrooms 檢修（2026-08-20 review → 08-21 施工）

Tony 08/20 問「有沒有什麼能做得更好的地方」，盤查後提六點，六點全數核可。

## 進度

- [x] 4. matchDir 方向精確比對 → 移到 `watch-directions.js`＋`watch-directions.test.js`（10 項全過）
- [x] 5. 過期需求自動下架 → `expire-watches.js`（brain，掛在 sync-seatsrooms-watchlist.sh 前面）
      ＋後端擋「日期沒改就恢復」、改完日期自動重新啟用；index/hotels 標「🗓 已過期」
- [x] 1. 掃描器停擺告警 → `scan-health-watch.js` + brain `seats-health-watch.timer`（6h 一次，已 enable）
- [ ] 2. seats.aero 對 source:'airline' 需求做交叉驗證（第二來源，官網掛掉時仍有訊號）
- [ ] 6. `airlines/` 死碼整理：刪 alaska.js/cal.js，eva.js 標知識存檔，ana/starlux 標「正本在 158」
- [ ] 3. 洗掉 seatsrooms public repo 歷史裡的 results.json（先 bundle 備份，再 force push）

## 已完成

- `.gitignore` 補 balances.json / cash-fx.json（public repo，餘額不能進 git）
