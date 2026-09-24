# 校園違停監控中心 — 前端儀表板 (Frontend Dashboard)

基於 Next.js 16 (App Router)、React 19 與 Leaflet GIS 打造的科技執法監控中心介面。

---

## 技術棧 (Tech Stack)

* 核心框架：Next.js 16 (Turbopack) + React 19
* 程式語言：TypeScript 5
* 樣式系統：Tailwind CSS 4 + 自訂深色科技感主題 (Dark Theme)
* GIS 地圖引擎：Leaflet 1.9 + React-Leaflet 5 (OpenStreetMap 圖資)

---

## 元件架構說明 (Component Architecture)

* `app/page.tsx`：伺服器端渲染 (SSR) 頁面入口，負責向後端 GAS API 抓取最新違規事件並反向排序。
* `app/components/DashboardClient.tsx`：客戶端主狀態控制器，管理事件清單選取狀態、手動重新整理與輪詢更新。
* `app/components/MapView.tsx`：Leaflet 地圖整合元件，將事件經緯度繪製為標記點，支援地圖點位飛越 (Fly-to) 與 Popup 彈窗。
* `app/components/EventCard.tsx`：違停卡片，包含相片預覽、違規時間地點、審核按鈕（「確認違停」與「誤判剔除」）及即時狀態更新。
* `app/types.ts`：資料結構定義 (ViolationEvent)。

---

## 環境設定與啟動 (Getting Started)

### 1. 安裝依賴
```bash
npm install
```

### 2. 環境變數設定
複製 `.env.example` 為 `.env.local`：
```bash
cp .env.example .env.local
```
在 `.env.local` 中填入你的 Google Apps Script Web App 部署網址：
```env
NEXT_PUBLIC_GAS_API_URL=https://script.google.com/macros/s/YOUR_GAS_DEPLOYMENT_ID/exec
```

### 3. 開發伺服器啟動
```bash
npm run dev
```
瀏覽器訪問 `http://localhost:3000`。

### 4. 正式版本打包建置
```bash
npm run build
npm run start
```
