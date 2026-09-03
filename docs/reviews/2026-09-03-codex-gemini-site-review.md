# 網站現況第二意見（2026-09-03 台北 15:01）

Tony 要求 codex 與 gemini（agy）各看一次 seatsrooms 網站原始碼。以下為原文，brain 驗證註記見末段。

## codex（GPT）
## 1. 一句話評價

功能已相當完整、資料呈現也比一般比價站透明，但目前「展示」成熟度高於「搶票戰備」：9/16 最關鍵的虎航會員監控、通知可靠性與失敗告警仍有明顯缺口。

## 2. 建議（依重要性排序）

1. **`tigerair/watch.py`、`member-watch.py`、`watchlist-promo.json`：先把 9/16 排程真正落地並做演練。**  
   runner 上目前找不到對應的 systemd timer/service，也沒有 `watch-state`、`member-state`、JWT cache 等執行痕跡；程式存在不等於當天會跑。應建立並啟用促銷專用 timer，匿名全網價約每分鐘掃一次、會員價輪替查詢；9/15 做一次完整演練，確認 TG 實際收到通知。9/16 開賣前先登入 TigerClub、暖好 camofox、確認 JWT 能續發，並避免當天自動重啟瀏覽器。

2. **`tigerair/watch.py`、`member-watch.py`：通知成功後才能寫入「已通知／最低價」狀態。**  
   現在先更新 state、後送 Telegram；若 TG timeout、斷網或回 429，該價格仍會被記成已看過，下一輪不再通知。應改成「候選命中 → 送 TG → 確認 HTTP 200 → 原子寫 state」，失敗則保留待重試，另加 message id 或事件鍵避免重複。

3. **`tigerair/member-watch.py`：會員查價失敗必須告警並確實換 profile。**  
   `fare-detail.js` 整體失敗時被轉成空陣列，但現有換 profile 條件不會成立，因此可能一直使用壞掉的 profile，且只在 log 留一句話。應記錄連續失敗次數、空結果也算失敗，首次推警告、連續兩三次自動換 profile，並產生包含 `lastSuccess`、JWT 到期時間、成功筆數的 health state。

4. **`tigerair.html`：做一個「9/16 搶票模式」。**  
   首屏固定顯示 KHH→CJU、CJU→KHH、KHH→CTS、CTS→KHH 四條，列出未稅、稅金、含稅、剩餘座位、資料時間與「前往虎航訂票」。目前靜態資料中 KHH→CJU 最低未稅 1,599、KHH→CTS 5,099，兩條去程都沒有 9/16 航班資料；這些資訊不應藏在航線選擇器與長日曆裡。促銷當天還應讓 112／512／700 以下結果置頂，而不是只按含稅最低價排序。

5. **五個票價站內頁：顯示資料新鮮度與掃描完整度。**  
   `/api/<airline>/prices` 載入後目前只畫價格，沒有把掃描時間、成功航線數、失敗航線數放在頁面顯眼處。應在標題下顯示「最後成功掃描（台北時間）／成功 X、失敗 Y」，超過預定週期就整頁顯示黃色或紅色警告。現在靜態分享頁最後資料時間是 9/2 23:08～23:53 台北，使用者從站內頁無法快速判斷是否過期。

6. **五家 `scan.py`：部分失敗不能仍視為成功並發布。**  
   虎航掃描器把單一路線例外轉成空結果，最後仍正常結束；排程很容易發布一份缺航線但看似正常的新資料。其他家也應統一輸出 manifest：預期航線、成功、空結果、失敗、開始／完成時間；關鍵航線 KHH-CJU、KHH-CTS 任一失敗時非零退出，保留上一份完整資料，不覆蓋正式頁。

7. **`index.html`、五家票價頁與 `hotels.html`：手機導覽改為任務導向。**  
   現在每頁頂部有六七顆航空公司導覽鈕，價格表仍以橫向捲動為主。建議主導覽只留「機位、現金票、飯店、規則」，現金票頁內再切航空公司；窄螢幕把「最低 20 天」改成日期／含稅總價卡片，次要欄位展開才看。這會比繼續塞橫向表格更適合單手搶票。

8. **`airmacau.html`、`hkexpress.html`：估算價與真實價在視覺上分級。**  
   目前「含稅估算」、轉機拼接價、官網真實含稅價都出現在相近欄位，快速掃視容易當成同等可信。建議每筆加 `實價／估價／上限估` badge，排序預設優先實價；未校準稅金的航線不要和含稅結果混排。

## 3. 明確 bug

- [`tigerair/watch.py:224`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/watch.py:224)：在 Telegram 發送前便更新最低價 state；[`tigerair/watch.py:228`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/watch.py:228) 又先寫檔，TG 發送失敗會永久漏掉該次便宜票。

- [`tigerair/member-watch.py:229`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.py:229)：先設定 `notified`；[`tigerair/member-watch.py:238`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.py:238) 先落盤，直到 [`tigerair/member-watch.py:250`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.py:250) 才送 TG，同樣會在發送失敗後壓掉重試。

- [`tigerair/member-watch.py:199`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.py:199)：整批查價失敗時將 `detail=[]`；但 [`tigerair/member-watch.py:235`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.py:235) 只有 `detail` 非空才換 profile，因此最需要換 profile 的整批失敗反而不會換。

- [`tigerair/scan.py:122`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/scan.py:122)：航線掃描例外被轉成空陣列，主程式仍以成功碼結束；排程可能把缺航線資料當作完整掃描發布。

- [`tigerair.html:372`](/home/tonychuangtw/TelegramClaude/seatsrooms/tigerair.html:372)：API 回空資料時仍直接取 `all[0]` 與 `all[all.length-1]`，不像星宇／華航頁有空資料保護；之後渲染會以未定義日期範圍運作。相同問題也存在 [`airmacau.html:390`](/home/tonychuangtw/TelegramClaude/seatsrooms/airmacau.html:390) 與 [`hkexpress.html:388`](/home/tonychuangtw/TelegramClaude/seatsrooms/hkexpress.html:388)。

## gemini（agy）
### 1. 網站現況一句話評價

「核心爬取與日曆分析架構極為扎實（打通五家航空公司私有 API 與含稅還原），但各航司前端頁面缺乏統一元件抽象且未針對手機做專屬優化；9/16 搶票最大死穴在於會員查價排隊系統未做輪詢容錯、且查價速度追不上開賣秒殺節奏。」

---

### 2. 具體建議（按重要性排序）

#### 建議一：【9/16 搶票最關鍵】分離「極速日曆監控」與「會員查價」，並為高雄濟州／札幌建立高頻專屬通道
* **哪個檔／功能**：[tigerair/watch.py](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/watch.py)、[tigerair/member-watch.json](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.json)、[tigerair/watchlist-promo.json](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/watchlist-promo.json)
* **問題**：
  1. `watchlist-promo.json` 目前只有一行 `allRoutes: true`，會把全網 60 多條航線混在一起，並只取前 25 筆推播，Tony 最重視的高雄濟州（KHH-CJU）與高雄札幌（KHH-CTS）極容易被淹沒。
  2. `member-watch.py` 依賴瀏覽器跑 reCAPTCHA，每查 6 個日期要耗時 4～5 分鐘；且 `member-watch.json` 裡的 `KHH-CJU` 完全沒有設 `focus`（只寫「濟州去程，全期間」），輪替盲掃 100 多天根本來不及抓秒殺票。
* **怎麼改**：
  1. 在 `watchlist-promo.json` 頂部把目標航線獨立拉出來（設 `thresholdNet: 512` 或 `112`），其餘全網航線設較嚴苛門檻或放在下方。
  2. 9/16 當天 09:55 起，主攻 [tigerair/watch.py](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/watch.py) 每 1～2 分鐘跑一輪（`daily-prices` API 回應僅 300ms，無 reCAPTCHA、無排隊系統阻擋），這支抓全員促銷（512 元）最穩。
  3. [tigerair/member-watch.json](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.json) 必須事前補上 Tony 預計出發的濟州候選日期（填入 `focus` 陣列，例如指定 10 月、11 月特定的週五去週日回），不要全區間盲掃。

#### 建議二：【9/16 搶票準備】fare-detail.js 排隊系統容錯與 TG 直接訂票連結（Deep Link）
* **哪個檔／功能**：[tigerair/fare-detail.js](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/fare-detail.js#L58-L66)、[tigerair/watch.py](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/watch.py#L268)
* **問題**：
  1. `fare-detail.js` 在打 `generate_token` 時只打一次，若 9/16 促銷當天虎航啟用排隊室（Waiting Room），該 API 回傳等待狀態而非 `access_token`，腳本會立即以 `generate_token failed` 崩潰（見 Bug 6）。
  2. TG 降價通知最後只給首頁 `https://booking.tigerairtw.com/`，Tony 在手機上收到通知還得手動選出發地、目的地、日期、單程，選完票早就被搶光。
* **怎麼改**：
  1. 在 `fare-detail.js` 的 `generate_token` 加入輪詢等待（每 3 秒重試一次，最多等 60 秒），不要直接報錯。
  2. TG 推播訊息中附上預填參數的直接連結，例如：
     `https://booking.tigerairtw.com/zh-TW?origin=KHH&destination=CJU&departureDate=2026-10-15`，手機點擊可直接跳入搜尋結果頁。

#### 建議三：【掃描效率】member-watch.py 過濾無航班日期，查價速度直接翻倍
* **哪個檔／功能**：[tigerair/member-watch.py:82-93](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.py#L82-L93) 的 `date_range`
* **問題**：
  `date_range` 盲目產生區間內每一天。但虎航很多二線航線（如高雄濟州）一週僅飛特定幾天（如一三五日）。查到沒飛的日子一樣得開瀏覽器等待 20 秒 delay 並燒掉 reCAPTCHA 分數，白白浪費了 40%～50% 的會員查詢配額與寶貴時間。
* **怎麼改**：
  從 `baseline.json`（或日曆掃描結果）提取該航線「實際有航班」的日期集合，`date_range` 只挑歷史上有航班的星期或日期進行輪替，排除沒班機的日子。

#### 建議四：【手機版 UX】導航列改為橫向滑動與標註當前頁面
* **哪個檔／功能**：[assets/shared.css:15-17](file:///home/tonychuangtw/TelegramClaude/seatsrooms/assets/shared.css#L15-L17)、各頁面的 `<div class="nav">`
* **問題**：
  站內共有 7 個主要頁籤，在手機寬度（375px~390px）下折成 3～4 行，佔據畫面頂部將近 1/3 的垂直高度，且沒有高亮「當前頁面」。
* **怎麼改**：
  在 [assets/shared.css](file:///home/tonychuangtw/TelegramClaude/seatsrooms/assets/shared.css) 中將 `.nav` 設為單行橫向滾動：
  ```css
  .nav { display:flex; gap:8px; flex-wrap:nowrap; overflow-x:auto; -webkit-overflow-scrolling:touch; padding-bottom:4px; margin:6px 0 12px; }
  .nav a { flex-shrink:0; }
  .nav a.active { background:var(--accent); color:#06131c; border-color:var(--accent); }
  ```
  並在各 HTML 頁將自己的連結加上 `class="active"`。

#### 建議五：【手機版 UX】日曆格子小螢幕防擠壓與價格標註
* **哪個檔／功能**：[tigerair.html:40-50](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair.html#L40-L50)、[tigerair.html:295-298](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair.html#L295-L298)
* **問題**：
  手機寬度扣除內距後，每週 7 格每格僅約 40px。遇到 5 位數票價（如旺季 14,999）時，字體若無保護會換行或破版；且格內上下疊放兩個數字，未標明哪一個是含稅、哪一個是未稅，初次看易困惑。
* **怎麼改**：
  1. `.cell .p` 加上 `white-space: nowrap; font-size: clamp(0.62rem, 2.5vw, 0.72rem);`。
  2. 仿照 [tigerair/generate-page.py](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/generate-page.py#L474-L476) 的好做法：上方大字顯示含稅總價，下方 `<small>` 明確顯示 `未 1,399`，有稅金時標注「未」，無稅金時標注「未稅」。

#### 建議六：【UX & 資訊架構】去回組合查詢自動觸發與補齊回程星期
* **哪個檔／功能**：[tigerair.html:321-338](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair.html#L321-L338) 的 `findCombos`
* **問題**：
  1. 切換至「來回」時，「找最便宜的去回組合」卡片預設是空的，使用者必須手動找到並點擊「找」按鈕才會算出結果。
  2. 結果表格裡，出發日有標星期（如 `2026-10-15（四）`），但回程日只給冷冰冰的 `2026-10-19`，使用者無法一眼看出回程是週日還是週一。
* **怎麼改**：
  1. 切換票種至來回或切換航線時，於 `render()` 自動呼叫一次 `findCombos()`。
  2. 回程日期格式改為 `esc(x.rd) + "（" + WD[retWd] + "）"`。

#### 建議七：【快取與穩定性】統一 HTML 引用 shared.css 版本號
* **哪個檔／功能**：[tigerair.html:11](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair.html#L11)、[starlux.html:11](file:///home/tonychuangtw/TelegramClaude/seatsrooms/starlux.html#L11)、[chinaairlines.html:11](file:///home/tonychuangtw/TelegramClaude/seatsrooms/chinaairlines.html#L11)、[airmacau.html:11](file:///home/tonychuangtw/TelegramClaude/seatsrooms/airmacau.html#L11)、[hkexpress.html:11](file:///home/tonychuangtw/TelegramClaude/seatsrooms/hkexpress.html#L11)
* **問題**：
  `assets/shared.css` 在 2026-09-02 修復了手機版按鈕排版問題，[index.html:11](file:///home/tonychuangtw/TelegramClaude/seatsrooms/index.html#L11) 與 [hotels.html:11](file:///home/tonychuangtw/TelegramClaude/seatsrooms/hotels.html#L11) 已經是 `?v=20260902`，但五家航空的頁面全部停留在舊的 `?v=20260815`。在手機瀏覽器強快取下，手機版排版修正無法在票價頁生效。
* **怎麼改**：
  將五個 HTML 檔的 CSS 引用版本號統一更新為 `shared.css?v=20260902`。

---

### 3. 明確發現的 Bug（檔名與行號）

#### Bug 1：虎航來回新低價通知永遠不會開火
* **檔名與行號**：[tigerair/watch.py:183-185](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/watch.py#L183-L185)
* **錯誤代碼**：
  ```python
  newlow = (not w.get("noNewLow") and prev is not None and net < prev
            and net <= w.get("newLowMax", 0))
  ```
* **原因**：
  如果 watchlist 項目沒有特別設定 `newLowMax`，`w.get("newLowMax", 0)` 會回傳 `0`。機票價格 `net` 都是幾千元，`net <= 0` 永遠為 `False`，導致來回機票的「創新低」推播永遠被靜默吞掉。
* **修正**：
  參考單程模式（第 218 行）的做法，改為 `and (new_max is None or net <= new_max)`。

#### Bug 2：五家航空的 watch.py 預設讀取的 watchlist.json 均不存在
* **檔名與行號**：
  * [tigerair/watch.py:21](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/watch.py#L21)
  * [starlux/watch.py:20](file:///home/tonychuangtw/TelegramClaude/seatsrooms/starlux/watch.py#L20)
  * [chinaairlines/watch.py:20](file:///home/tonychuangtw/TelegramClaude/seatsrooms/chinaairlines/watch.py#L20)
  * [hkexpress/watch.py:20](file:///home/tonychuangtw/TelegramClaude/seatsrooms/hkexpress/watch.py#L20)
  * [airmacau/watch.py:20](file:///home/tonychuangtw/TelegramClaude/seatsrooms/airmacau/watch.py#L20)
* **錯誤代碼**：
  ```python
  WATCHLIST = os.path.join(HERE, "watchlist.json")
  watches = json.load(open(a.list))
  ```
* **原因**：
  這五個目錄底下全都沒有 `watchlist.json`（tigerair 底下只有 `watchlist-promo.json` 和 `member-watch.json`）。若直接執行文檔寫的 `python3 watch.py`，會直接拋出 `FileNotFoundError` 崩潰。
* **修正**：
  在各目錄提供範本 `watchlist.json`，或在 `tigerair/watch.py` 預設為 `watchlist-promo.json`。

#### Bug 3：tigerair/scan.py 使用相對路徑載入 tax-table.json
* **檔名與行號**：[tigerair/scan.py:22](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/scan.py#L22)、[tigerair/scan.py:28](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/scan.py#L28)
* **錯誤代碼**：
  ```python
  TAX_FILE = "tax-table.json"
  def load_tax():
      try:
          with open(TAX_FILE) as f:
  ```
* **原因**：
  使用相對路徑 `"tax-table.json"`。若在專案根目錄執行 `python3 tigerair/watch.py` 或由其他排程腳本匯入時，找不到該檔案會進入 `except: return {}`，導致稅金表完全失效變為空字典，所有含稅價失準。
* **修正**：
  改為基於腳本路徑的絕對路徑：
  `TAX_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tax-table.json")`。

#### Bug 4：chinaairlines.html 缺少來回模式切換按鈕
* **檔名與行號**：[chinaairlines.html:89-92](file:///home/tonychuangtw/TelegramClaude/seatsrooms/chinaairlines.html#L89-L92)
* **錯誤代碼**：
  ```html
  <div class="chips" id="modechips">
    <button class="chip" data-n="0" aria-pressed="true">單程</button>
  </div>
  ```
* **原因**：
  底層 JavaScript（第 156、294、310 行）具備完整的 `RT`、`rtDays` 和 `combo` 來回計算邏輯，但 HTML 卻只放了一顆「單程」按鈕，缺少 `data-n="2"`、`data-n="3"` 等來回晶片與晚數輸入框，導致使用者在前端無法切換至來回模式，`#combo-card` 也永遠無法展示。
* **修正**：
  補上與其他航司相同的 3天2夜、4天3夜、自訂晚數等來回按鈕。

#### Bug 5：tigerair/member-watch.py 的 focus 去重導致 quota 無效消耗
* **檔名與行號**：[tigerair/member-watch.py:166-170](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/member-watch.py#L166-L170)
* **錯誤代碼**：
  ```python
  add(r, ds[i], w)
  cur[r] = i + 1
  quota -= 1
  ```
* **原因**：
  如果游標輪到的 `ds[i]` 已經在稍早的 `focus` 清單中被加入過，`add()` 函式會因為 `k in seen` 提早返回而不加入任務，但外部的 `quota -= 1` 仍然執行。這導致該輪實際查詢的日期數量少於使用者設定的 `--n`。
* **修正**：
  將 `quota -= 1` 移入 `add()` 成功加入時才扣減，或先檢查 `if k not in seen:` 再扣減配額。

#### Bug 6：tigerair/fare-detail.js 排隊室（Waiting Room）未做排隊等待
* **檔名與行號**：[tigerair/fare-detail.js:63-66](file:///home/tonychuangtw/TelegramClaude/seatsrooms/tigerair/fare-detail.js#L63-L66)
* **錯誤代碼**：
  ```javascript
  const gt = await j('https://api-wr.tigerairtw.com/generate_token',
    { method: 'POST', headers: WRH,
      body: JSON.stringify({ request_id: aq.api_request_id, event_id: 'normal' }) });
  if (!gt.access_token) return { error: 'generate_token failed', detail: gt };
  ```
* **原因**：
  平時沒有排隊時 `generate_token` 會直接給 `access_token`。但在 9/16 促銷開賣擁擠時，排隊系統會回傳等待狀態與排隊序號，不會第一時間給 token。腳本一次沒拿到 token 就判定失敗退出，促銷當下會員查價將全面癱瘓。
* **修正**：
  加入 `while` 輪詢邏輯等待排隊通過再繼續進行後續 GraphQL 查詢。

## brain 驗證註記

**屬實（兩家共同或已對照程式碼）**
- watch.py / member-watch.py 都是「先寫 state、後發 TG」，TG 發送失敗該筆就永遠不再通知（codex）
- member-watch.py 整批查價失敗時 detail=[]，換 profile 的條件反而不成立，且只印 log 不告警（codex）
- scan.py 單條航線失敗轉成空陣列、exit 0，排程會把缺航線的資料當完整版發布（codex）
- tigerair / airmacau / hkexpress 站內頁沒有空資料保護，starlux / chinaairlines 有（codex）
- fare-detail.js 的 generate_token 只打一次，促銷排隊室回等待狀態就直接報錯（gemini，9/16 高風險）
- watch.py 來回模式的 newLowMax 預設 0，來回創新低永遠不會推（gemini）
- member-watch.py 輪替時 add() 去重但 quota 照扣，實際查的筆數少於 --n（gemini，小）
- 五家票價頁 shared.css 版本號停在 20260815，9/2 手機版修正在票價頁可能被快取擋住（gemini）
- watchlist-promo.json 一輪只列前 25 筆，KHH-CJU / KHH-CTS 可能被其他航線淹沒；但 tigerair-promo.timer 另外每分鐘跑 watchlist.json（Tony 那 5 筆），主要目標有獨立通道（gemini，部分成立）

**誤判**
- codex 說「runner 上找不到 timer」：排程都在 brain，runner 本來就沒有
- gemini 說「五家 watchlist.json 不存在」：檔案是 gitignored，brain 上都在
- gemini 說「chinaairlines.html 缺來回按鈕」：華航掃描器只做單程，前端只放單程是刻意的
- gemini 說 scan.py 的 tax-table.json 用相對路徑會失效：systemd 有設 WorkingDirectory，實際不會出事，但改成絕對路徑更穩
