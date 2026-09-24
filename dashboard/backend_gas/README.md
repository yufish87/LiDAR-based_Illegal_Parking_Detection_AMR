# 違停取證雲端無伺服器後端 (Google Apps Script Backend)

本目錄包含系統後端微服務原始碼，運行於 Google Apps Script (GAS) 雲端環境。

---

## 功能與職責

1. `doPost(e)` (自走車上傳與審核更新)：
   * 事件上傳：接收邊緣端自走車透過 HTTP POST 傳入的 Base64 照片與事件資訊，透過 Google Drive REST API 直接將照片存入指定的 Google Drive 資料夾，並設定公開直連權限。
   * 試算表記錄：將事件編號、時間戳記、違規區域、GPS 連結、真實地址與相片直連網址寫入 Google Sheets 違規資料庫。
   * 狀態更新 (`update_status`)：接收前端儀表板送出的審核指令，依 `event_id` 更新指定事件的審核狀態（例如「已確認」或「誤判」）。

2. `doGet(e)` (前端即時資料查詢)：
   * 讀取 Google Sheets 內所有紀錄，整理成格式化 JSON 陣列回傳給前端儀表板渲染。

---

## 部署指南

### 方式一：透過 Google 試算表介面手動部署
1. 建立一個 Google Sheets (https://sheets.new)，點選上方選單 擴充功能 > Apps Script。
2. 將 `Code.js` 與 `appsscript.json` 複製貼上至編輯器中。
3. 將 `Code.js` 中的 `DRIVE_FOLDER_ID` 改為你 Google Drive 中用於儲存照片的資料夾 ID。
4. 點擊 部署 > 新部署：
   * 類型選擇 網頁應用程式 (Web App)
   * 執行身分：我 (Me)
   * 存取權限：所有人 (Anyone)
5. 複製生成的 Web App URL 提供給前端 `.env.local` 與自走車節點使用。

### 方式二：使用 Google clasp CLI 部署
1. 安裝 clasp：
   ```bash
   npm install -g @google/clasp
   clasp login
   ```
2. 將 `.clasp.json` 中的 `scriptId` 填入你的 Apps Script 專案 ID。
3. 推送程式碼：
   ```bash
   clasp push
   ```
