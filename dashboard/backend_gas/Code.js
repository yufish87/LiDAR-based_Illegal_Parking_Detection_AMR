/**
 * Google Apps Script - 科技執法違停偵測系統後端 API
 */

// 請將此常數替換為您實際的 Google Drive 資料夾 ID（真實數值請參閱 docs/website_code_security.md）
const DRIVE_FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID_HERE";


/**
 * 1. doPost(e) - 邊緣設備上傳 API
 * 接收邊緣端設備傳來的 JSON Payload，並將圖片與資料存入 Google 服務。
 */
function doPost(e) {
  let output = {};

  try {
    if (!e || !e.postData || !e.postData.contents) {
      throw new Error("Empty request payload");
    }

    // 1. 解析 Payload
    const data = JSON.parse(e.postData.contents);
    const action = data.action || "create";

    // ── 路由：更新審核狀態 ──────────────────────────────────────────
    if (action === "update_status") {
      const eventId = data.event_id;
      const newStatus = data.status;
      if (!eventId || !newStatus) throw new Error("Missing event_id or status");

      const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
      const dataRange = sheet.getDataRange();
      const values = dataRange.getValues();

      for (let i = 1; i < values.length; i++) {
        if (String(values[i][0]) === String(eventId)) {
          sheet.getRange(i + 1, 7).setValue(newStatus); // G 欄
          break;
        }
      }

      return ContentService.createTextOutput(
        JSON.stringify({ status: "success", message: "狀態更新成功", event_id: eventId })
      ).setMimeType(ContentService.MimeType.JSON);
    }

    // ── 路由：新增違停事件 (預設 create) ───────────────────────────

    const eventId = data.event_id || "";
    const timestamp = data.timestamp || "";
    const zoneName = data.zone_name || "";
    const mapsUrl = data.maps_url || "";
    const address = data.address || "";
    const imgFilename = data.image_filename || `photo_${Date.now()}.jpg`;
    const imgBase64 = data.image_base64 || "";

    let photoUrl = "";

    // 3. 用 Drive REST API 上傳圖片 (繞過 DriveApp 在 Web App 的授權問題)
    if (imgBase64) {
      try {
        const oauthToken = ScriptApp.getOAuthToken();
        const boundary = "-------GAS_BOUNDARY_314159265";
        const delimiter = "\r\n--" + boundary + "\r\n";
        const closeDelimiter = "\r\n--" + boundary + "--";

        const metadata = JSON.stringify({
          name: imgFilename,
          parents: [DRIVE_FOLDER_ID]
        });

        const multipartBody =
          delimiter +
          "Content-Type: application/json\r\n\r\n" +
          metadata +
          delimiter +
          "Content-Type: image/jpeg\r\n" +
          "Content-Transfer-Encoding: base64\r\n\r\n" +
          imgBase64 +
          closeDelimiter;

        // 上傳檔案
        const uploadResp = UrlFetchApp.fetch(
          "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
          {
            method: "POST",
            contentType: 'multipart/related; boundary="' + boundary + '"',
            headers: { Authorization: "Bearer " + oauthToken },
            payload: multipartBody,
            muteHttpExceptions: true
          }
        );
        const fileData = JSON.parse(uploadResp.getContentText());
        const fileId = fileData.id;

        if (!fileId) throw new Error("Upload failed: " + uploadResp.getContentText());

        // 設定公開可讀
        UrlFetchApp.fetch(
          "https://www.googleapis.com/drive/v3/files/" + fileId + "/permissions",
          {
            method: "POST",
            contentType: "application/json",
            headers: { Authorization: "Bearer " + oauthToken },
            payload: JSON.stringify({ role: "reader", type: "anyone" }),
            muteHttpExceptions: true
          }
        );

        // 4. 直連網址
        photoUrl = "https://drive.google.com/uc?id=" + fileId;
      } catch (fileErr) {
        photoUrl = "Error uploading image: " + fileErr.toString();
      }
    }

    // 5. 將資料寫入試算表
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    sheet.appendRow([
      eventId,
      timestamp,
      zoneName,
      mapsUrl,
      address,
      photoUrl,
      "", // G: 審核狀態 (預設留空)
      ""  // H: 備註 (預設留空)
    ]);

    output = {
      status: "success",
      message: "Record and photo added successfully",
      event_id: eventId,
      photo_url: photoUrl
    };

  } catch (error) {
    output = {
      status: "error",
      message: error.toString()
    };
  }

  // 6. 回傳 JSON 格式狀態
  return ContentService.createTextOutput(JSON.stringify(output))
    .setMimeType(ContentService.MimeType.JSON);
}

/**
 * 2. doGet(e) - Next.js Dashboard 讀取 API
 * 讀取試算表資料，並將 Google Drive 圖片網址轉換為直連網址供前端渲染。
 */
function doGet(e) {
  let output = [];

  try {
    const sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    const dataRange = sheet.getDataRange();
    const values = dataRange.getValues();

    // 1. 若除了標題列外有資料
    if (values.length > 1) {
      const rows = values.slice(1); // 跳過第一行的標題列

      // 2. 整理成 JSON Object 陣列
      output = rows.map(row => {
        let imageUrl = row[5] ? row[5].toString() : "";

        // 3. 圖片直連轉換邏輯
        if (imageUrl.includes("drive.google.com")) {
          // 利用 Regex 擷取出檔案 ID (通常是 25 字元以上的英數字與連字號)
          const match = imageUrl.match(/[-\w]{25,}/);
          if (match && match[0]) {
            const fileId = match[0];
            // 替換為直連格式
            imageUrl = `https://drive.google.com/uc?id=${fileId}`;
          }
        }

        return {
          id: row[0] ? row[0].toString() : "",
          timestamp: row[1] ? row[1].toString() : "",
          zone: row[2] ? row[2].toString() : "",
          maps_url: row[3] ? row[3].toString() : "",
          address: row[4] ? row[4].toString() : "",
          image_url: imageUrl,
          status: row[6] ? row[6].toString() : "",
          notes: row[7] ? row[7].toString() : ""
        };
      });
    }
  } catch (error) {
    return ContentService.createTextOutput(JSON.stringify({
      status: "error",
      message: error.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }

  // 4. 回傳格式化後的 JSON 陣列
  return ContentService.createTextOutput(JSON.stringify(output))
    .setMimeType(ContentService.MimeType.JSON);
}
