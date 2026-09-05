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

var ALLOWED_DOMAINS = ["eosasc.com.tw", "gmail.com"];

function isAllowedDomain(email) {
  if (!email || email.indexOf("@") === -1) return false;
  var domain = email.split("@").pop().toLowerCase().trim();
  return ALLOWED_DOMAINS.indexOf(domain) !== -1;
}

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

    // 1. 蜜罐陷阱 (Honeypot) 偵測：若機器人填寫了隱藏欄位，直接拒絕
    if (data.hp_company_sec || data.hp_token || data.hp_code) {
      return ContentService.createTextOutput(JSON.stringify({ status: "error", message: "安全校驗未通過。" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    var action = (data.action || "").trim().toLowerCase();
    var email = (data.email || "").trim().toLowerCase();

    // 2. 取消訂閱處理 (Unsubscribe via POST)
    if (action === "unsubscribe") {
      if (!email || email.indexOf("@") === -1) {
        return ContentService.createTextOutput(JSON.stringify({ status: "error", message: "請輸入有效的 Email" }))
          .setMimeType(ContentService.MimeType.JSON);
      }
      var rows = sheet.getDataRange().getValues();
      for (var i = 1; i < rows.length; i++) {
        if (String(rows[i][0]).trim().toLowerCase() === email) {
          sheet.getRange(i + 1, 4).setValue("已停用 (使用者取消訂閱)");
          return ContentService.createTextOutput(JSON.stringify({ status: "success", message: "已成功取消訂閱！" }))
            .setMimeType(ContentService.MimeType.JSON);
        }
      }
      return ContentService.createTextOutput(JSON.stringify({ status: "error", message: "找不到該訂閱信箱" }))
        .setMimeType(ContentService.MimeType.JSON);
    }

    // 3. 網域白名單檢查：僅接受 @eosasc.com.tw 與 @gmail.com (以及 @ricoh.com.tw)
    if (!isAllowedDomain(email)) {
      return ContentService.createTextOutput(JSON.stringify({
        status: "error",
        message: "為維護內部情報安全，目前僅開放 @eosasc.com.tw 與 @gmail.com 網域訂閱。"
      })).setMimeType(ContentService.MimeType.JSON);
    }

    var cities = Array.isArray(data.cities) ? data.cities.join(", ") : (data.cities || "全部");
    var timestamp = Utilities.formatDate(new Date(), "Asia/Taipei", "yyyy-MM-dd HH:mm:ss");

    // 檢查是否已登記過，若有則更新所選縣市與時間 (UPSERT 防重複)
    var rows = sheet.getDataRange().getValues();
    var foundIndex = -1;
    var previousStatus = "";
    for (var i = 1; i < rows.length; i++) {
      if (String(rows[i][0]).trim().toLowerCase() === email) {
        foundIndex = i + 1;
        previousStatus = String(rows[i][3] || "");
        break;
      }
    }

    var isNewSubscriber = (foundIndex === -1);
    if (foundIndex > 0) {
      sheet.getRange(foundIndex, 2).setValue(cities);
      sheet.getRange(foundIndex, 3).setValue(timestamp);
      sheet.getRange(foundIndex, 4).setValue("有效 (已更新)");
    } else {
      sheet.appendRow([email, cities, timestamp, "有效"]);
    }

    // 每筆設定成功的使用者都先寄一封測試確認信，確保信箱可正常接收情報通知
    var mailSuccess = false;
    try {
      sendWelcomeTestEmail(email, cities);
      mailSuccess = true;
    } catch (mailErr) {
      Logger.log("Welcome email error: " + mailErr);
    }

    return ContentService.createTextOutput(JSON.stringify({
      status: "success",
      message: "訂閱登記成功！已寄送測試確認信至您的信箱，請查收確認。",
      mail_sent: mailSuccess
    })).setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ status: "error", message: err.toString() }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function doGet(e) {
  try {
    var sheet = SpreadsheetApp.getActiveSpreadsheet().getActiveSheet();
    var action = (e && e.parameter && e.parameter.action) ? e.parameter.action.toLowerCase() : "";
    var targetEmail = (e && e.parameter && e.parameter.email) ? e.parameter.email.trim().toLowerCase() : "";

    // 4. 一鍵取消訂閱網址點擊處理 (Web Unsubscribe Handler)
    if (action === "unsubscribe" && targetEmail) {
      var rows = sheet.getDataRange().getValues();
      var found = false;
      for (var i = 1; i < rows.length; i++) {
        if (String(rows[i][0]).trim().toLowerCase() === targetEmail) {
          sheet.getRange(i + 1, 4).setValue("已停用 (使用者取消訂閱)");
          found = true;
          break;
        }
      }

      var html = '<!DOCTYPE html><html><head><meta charset="utf-8"><title>已取消訂閱 - 互盛情報中樞</title>'
        + '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        + '<style>'
        + 'body{margin:0;padding:40px 16px;background:#eef3ed;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#202825;display:flex;justify-content:center;}'
        + '.box{background:#fbfcf8;border:1px solid #d4ded7;border-radius:12px;padding:36px;max-width:520px;text-align:center;box-shadow:0 10px 25px rgba(0,0,0,0.05);}'
        + 'h2{color:#202825;margin:12px 0 8px;font-size:20px;}'
        + 'p{color:#53605a;font-size:14px;line-height:1.6;margin:8px 0;}'
        + '.badge{display:inline-block;background:#fee2e2;color:#991b1b;padding:4px 12px;border-radius:20px;font-size:12px;font-weight:700;margin-bottom:12px;}'
        + '.btn{display:inline-block;margin-top:24px;background:#202825;color:#ffffff;text-decoration:none;font-size:13px;font-weight:700;padding:10px 24px;border-radius:6px;}'
        + '</style></head><body>'
        + '<div class="box">'
        + '<div class="badge">✕ 已取消訂閱</div>'
        + '<h2>互盛情報中樞 · 通知已停用</h2>'
        + '<p>您的信箱 <strong>' + targetEmail + '</strong> 已成功自通報名單中移除，往後將不再接收標案情報信件。</p>'
        + '<p>若日後業務需要重新開啟監控，可隨時前往首頁重新登記。</p>'
        + '<a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" class="btn">返回 互盛情報中樞 首頁 ➜</a>'
        + '</div></body></html>';

      return HtmlService.createHtmlOutput(html);
    }

    // 預設 API 查詢名單邏輯
    var rows = sheet.getDataRange().getValues();
    var subscribers = [];

    for (var i = 1; i < rows.length; i++) {
      var email = String(rows[i][0]).trim();
      var citiesRaw = String(rows[i][1]).trim();
      var status = String(rows[i][3] || "有效").trim();

      if (email && isAllowedDomain(email) && status.indexOf("停用") === -1 && status.indexOf("退訂") === -1) {
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

/**
 * 發送設定成功測試信件 (Neo-Editorial 風格)
 */
function sendWelcomeTestEmail(toEmail, citiesStr) {
  var subject = "【互盛情報中樞】通知設定成功測試信 · 標案監控已啟動";
  var unsubLink = "https://gyuyu2002-jeff.github.io/ricoh-intel-hub/?action=unsubscribe&email=" + encodeURIComponent(toEmail);
  var htmlBody = '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
    + '<body style="margin:0; padding:24px 12px; background:#eef3ed; font-family:\'Noto Sans TC\', -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif; color:#202825;">'
    + '<div style="max-width:640px; margin:0 auto; background:#fbfcf8; border:1px solid #d4ded7; border-radius:12px; overflow:hidden; box-shadow:0 8px 30px rgba(38,61,52,0.06);">'
    + '<div style="background:#202825; color:#ffffff; padding:24px 28px; border-bottom:3px solid #c92d3f;">'
    + '<div style="font-size:10px; font-weight:700; letter-spacing:0.12em; color:#a3b2a8; text-transform:uppercase;">RICOH INTERNAL BUSINESS INTELLIGENCE</div>'
    + '<h1 style="margin:6px 0 4px; font-size:22px; font-weight:700;">互盛情報中樞 · 通知設定成功</h1>'
    + '<div style="font-size:12px; color:#cdd8d1;">收信功能驗證測試 · 標案雷達已正式啟動</div>'
    + '</div>'
    + '<div style="padding:24px 28px;">'
    + '<div style="background:#eaf2eb; border-left:4px solid #2f5146; border-radius:4px; padding:14px 16px; margin-bottom:20px;">'
    + '<div style="font-size:14px; font-weight:700; color:#2f5146; margin-bottom:4px;">🎉 信箱連通測試成功！</div>'
    + '<div style="font-size:12px; color:#3a584c; line-height:1.6;">收到此信代表您的信箱已順利與「互盛情報中樞」完成對接。往後每日比對到符合您關注縣市的影印機/事務機新標案或公開徵求時，系統將主動發送通報信給您。</div>'
    + '</div>'
    + '<div style="background:#ffffff; border:1px solid #e2ece4; border-radius:8px; padding:18px 20px; margin-bottom:16px;">'
    + '<div style="font-size:13px; font-weight:700; color:#202825; margin-bottom:12px; border-bottom:1px solid #edf2ee; padding-bottom:8px;">📌 您的訂閱監控設定</div>'
    + '<table style="width:100%; font-size:12px; line-height:1.8; color:#4a5851;">'
    + '<tr><td style="width:90px; font-weight:700; color:#6b7c73;">通知信箱：</td><td><code style="background:#f4f7f4; padding:2px 6px; border-radius:4px; color:#202825;">' + toEmail + '</code></td></tr>'
    + '<tr><td style="font-weight:700; color:#6b7c73;">關注地區：</td><td><strong>' + (citiesStr || "全台所有縣市") + '</strong></td></tr>'
    + '<tr><td style="font-weight:700; color:#6b7c73;">監控標的：</td><td>影印機、多功能複合機、耗材採購、租賃案、公開徵求</td></tr>'
    + '<tr><td style="font-weight:700; color:#6b7c73;">通報頻率：</td><td>每日自動排程多次巡檢比對，有新案即彙整通知（具指紋防重複機制）</td></tr>'
    + '<tr><td style="font-weight:700; color:#6b7c73;">發信來源：</td><td><code>huxen.ricoh@gmail.com</code></td></tr>'
    + '</table>'
    + '</div>'
    + '<div style="background:#fcfbf6; border:1px solid #f1e9d2; border-radius:6px; padding:12px 16px; margin-top:16px; font-size:11px; color:#7d6b38; line-height:1.6;">'
    + '💡 <strong>防漏信提醒：</strong>若此信件位於「促銷內容」或「垃圾郵件」匣，請務必點選「非垃圾郵件」並將 <code>huxen.ricoh@gmail.com</code> 新增至通訊錄，以確保往後商機第一時間不漏接。'
    + '</div>'
    + '<div style="text-align:center; margin-top:24px; padding-top:16px; border-top:1px dashed #d4ded7;">'
    + '<a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" target="_blank" style="display:inline-block; background:#202825; color:#ffffff; font-size:13px; font-weight:700; padding:10px 24px; border-radius:6px; text-decoration:none;">前往 互盛情報中樞 完整看板 ➜</a>'
    + '</div>'
    + '</div>'
    + '<div style="background:#f4f7f4; padding:16px 28px; font-size:11px; color:#849289; text-align:center; border-top:1px solid #e1e9e2; line-height:1.7;">'
    + '發件信箱：huxen.ricoh@gmail.com · 此為互盛內部業務情報系統自動發送之設定確認信<br>'
    + '若欲修改通知縣市，請前往 <a href="https://gyuyu2002-jeff.github.io/ricoh-intel-hub/" style="color:#2f5146; text-decoration:none; font-weight:700;">互盛情報中樞</a> 更新設定。<br>'
    + '若不想再收到此情報信，請點擊 <a href="' + unsubLink + '" style="color:#c92d3f; text-decoration:underline;">[立即取消訂閱]</a>。'
    + '</div></div></body></html>';

  MailApp.sendEmail({
    to: toEmail,
    subject: subject,
    htmlBody: htmlBody,
    name: "互盛情報中樞"
  });
}

