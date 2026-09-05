/**
 * Google Apps Script - 互盛情報中樞 訂閱登記與名單 API
 * 
 * 部署步驟（只需 1 分鐘）：
 * 1. 在 Google Drive 開新 Google 試算表，命名為「互盛情報中樞_訂閱名單」。
 * 2. 第一列設定表頭：A1: Email, B1: 關注縣市, C1: 登記時間, D1: 狀態
 * 3. 點選選單「擴充功能」->「Apps Script」。
 * 4. 清空內容，貼上此腳本所有程式碼並按「儲存 (Ctrl+S)」。
 * 5. 點右上角「部署」->「新建部署」：
 *    - 種類選擇：「網頁應用程式 (Web App)」
 *    - 執行身分：「我 (您的帳號)」
 *    - 誰可以存取：「所有人 (Anyone)」
 * 6. 點選「部署」並授權，複製產生的「網頁應用程式網址 (Web App URL)」。
 * 7. 將該網址填入 GitHub 倉庫 Secrets 中的 `SUBSCRIBERS_URL`，同時填入前端設定。
 */

function doPost(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var data = {};
    if (e.postData && e.postData.contents) {
      try {
        data = JSON.parse(e.postData.contents);
      } catch (err) {
        data = e.parameter;
      }
    } else {
      data = e.parameter;
    }

    var email = (data.email || "").trim().toLowerCase();
    var cities = Array.isArray(data.cities) ? data.cities.join(", ") : (data.cities || "全部");
    var timestamp = Utilities.formatDate(new Date(), "Asia/Taipei", "yyyy-MM-dd HH:mm:ss");

    if (!email || email.indexOf("@") === -1) {
      return ContentService.createTextOutput(JSON.stringify({ status: "error", message: "請輸入有效的 Email" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // 檢查是否已登記過，若有則更新所選縣市與時間
    var rows = sheet.getDataRange().getValues();
    var foundIndex = -1;
    for (var i = 1; i < rows.length; i++) {
      if (String(rows[i][0]).trim().toLowerCase() === email) {
        foundIndex = i + 1;
        break;
      }
    }

    if (foundIndex > 0) {
      sheet.getRange(foundIndex, 2).setValue(cities);
      sheet.getRange(foundIndex, 3).setValue(timestamp);
      sheet.getRange(foundIndex, 4).setValue("有效 (已更新)");
    } else {
      sheet.appendRow([email, cities, timestamp, "有效"]);
    }

    return ContentService.createTextOutput(JSON.stringify({ status: "success", message: "訂閱登記成功！" }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var rows = sheet.getDataRange().getValues();
    var subscribers = [];

    // 從第二列開始讀取資料 (跳過標題列)
    for (var i = 1; i < rows.length; i++) {
      var email = String(rows[i][0]).trim();
      var citiesRaw = String(rows[i][1]).trim();
      var status = String(rows[i][3] || "有效").trim();

      if (email && email.indexOf("@") !== -1 && status.indexOf("停用") === -1) {
        var citiesList = citiesRaw ? citiesRaw.split(",").map(function(c) { return c.trim(); }) : ["全部"];
        subscribers.push({
          email: email,
          cities: citiesList,
          created_at: rows[i][2]
        });
      }
    }

    return ContentService.createTextOutput(JSON.stringify({ status: "success", subscribers: subscribers }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString(), subscribers: [] }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}
