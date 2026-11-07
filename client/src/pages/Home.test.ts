import { describe, expect, it } from "vitest";
import { getDataSyncStatus, isActiveTender, isDueSoonTender, mapRawTender, parseTenderPayload, readCityPreference } from "./Home";

describe("已決標案件得標對照", () => {
  it("有可比歷史時，分別保留本次與前次得標廠商", () => {
    const tender = mapRawTender({
      stage: "已決標",
      winner: "本次得標股份有限公司",
      award_price: 1200000,
      history_records: [{
        award_date: "2025-08-10",
        job_number: "114-006",
        discount_rate: 92.5,
        winner: "前次得標股份有限公司",
        relation_scope: "same_unit",
      }],
    });

    expect(tender.currentWinner).toBe("本次得標股份有限公司");
    expect(tender.previousWinner).toBe("前次得標股份有限公司");
    expect(tender.summary).toContain("本次由本次得標股份有限公司得標");
    expect(tender.summary).toContain("前次得標廠商為前次得標股份有限公司");
  });

  it("沒有歷史時，不以本次得標者回填前次得標欄位", () => {
    const tender = mapRawTender({
      stage: "已決標",
      winner: "本次得標股份有限公司",
      award_price: 1200000,
      history_records: [],
    });

    expect(tender.currentWinner).toBe("本次得標股份有限公司");
    expect(tender.previousWinner).toBe("尚無可比前次紀錄");
    expect(tender.history).toHaveLength(0);
    expect(tender.summary).toContain("尚無同機關可比的前次得標紀錄");
  });

  it("本次與前次得標者相同時，仍保留各自的資料來源角色", () => {
    const tender = mapRawTender({
      stage: "已決標",
      winner: "連續得標股份有限公司",
      history_records: [{
        award_date: "2025-08-10",
        job_number: "114-006",
        winner: "連續得標股份有限公司",
        relation_scope: "same_unit",
      }],
    });

    expect(tender.currentWinner).toBe("連續得標股份有限公司");
    expect(tender.previousWinner).toBe("連續得標股份有限公司");
    expect(tender.history[0][0]).toBe("2025-08-10");
  });

  it("歷史紀錄包含同體系不同分署時，前次得標優先判定同一機關之紀錄", () => {
    const tender = mapRawTender({
      stage: "公開徵求價單",
      unit: "海洋委員會海巡署南部分署",
      history_records: [
        {
          award_date: "2025-12-23",
          job_number: "N115-002",
          winner: "台灣佳能 (Canon)",
          source_unit: "海洋委員會海巡署北部分署",
          relation_scope: "same_parent_org",
          source_url: "https://web.pcc.gov.tw/bdm1",
        },
        {
          award_date: "2022-12-09",
          job_number: "CGS112-007G1",
          winner: "震旦 SHARP",
          source_unit: "海洋委員會海巡署南部分署",
          relation_scope: "same_unit",
          source_url: "https://web.pcc.gov.tw/bdm2",
        },
      ],
    });

    expect(tender.previousWinner).toBe("震旦 SHARP");
    expect(tender.history).toHaveLength(2);
    expect(tender.history[0][4]).toBe("https://web.pcc.gov.tw/bdm1");
    expect(tender.history[1][4]).toBe("https://web.pcc.gov.tw/bdm2");
    expect(tender.history[0][6]).toBe("海洋委員會海巡署北部分署");
    expect(tender.history[1][6]).toBe("海洋委員會海巡署南部分署");
  });
});


describe("公開資料載入", () => {
  it("合法空集合保留為空，不回退至內建案件", () => {
    const payload = parseTenderPayload({ tenders: [], review_candidates: [], forecasted_tenders: [] });
    expect(payload.tenders).toEqual([]);
    expect(payload.review_candidates).toEqual([]);
    expect(payload.forecasted_tenders).toEqual([]);
  });

  it.each([null, [], {}, { tenders: "invalid" }, { tenders: [null] }, { tenders: [], forecasted_tenders: {} }, { tenders: [{ history_records: [null] }] }, { tenders: [], last_updated: {} }])("拒絕無效資料而非顯示為零件公告：%j", (payload) => {
    expect(() => parseTenderPayload(payload)).toThrow();
  });

  it("公開預測不需要內部攻防或擴充推論欄位", () => {
    const forecast = { id: "public-1", unit: "範例機關", latest_winner: "公開得標公司", predicted_date: "2026-12-01", history_track: [] };
    expect(parseTenderPayload({ tenders: [], forecasted_tenders: [forecast] }).forecasted_tenders).toEqual([forecast]);
  });
});

describe("案件狀態與截止日", () => {
  const now = new Date("2026-11-07T01:00:00Z");
  it.each(["無法決標", "已決標", "已取消", "待確認"])("%s 不算進行中或三日內", (stage) => {
    const tender = { stage, deadline: "2026-11-08", deadline_confidence: "verified" };
    expect(isActiveTender(tender, now)).toBe(false);
    expect(isDueSoonTender(tender, now)).toBe(false);
  });
  it("公開徵求與有效招標納入，已逾期案排除", () => {
    expect(isActiveTender({ stage: "公開徵求價單", deadline: "2026-11-07" }, now)).toBe(true);
    expect(isActiveTender({ stage: "正式開標", deadline: "2026-11-06" }, now)).toBe(false);
  });
  it("三日內使用台北日曆與已核實期限，不使用業務評分", () => {
    const make = (deadline: string) => ({ stage: "正式開標", deadline, deadline_confidence: "verified" });
    expect(isDueSoonTender(make("2026-11-10"), now)).toBe(true);
    expect(isDueSoonTender(make("2026-11-11"), now)).toBe(false);
    expect(isDueSoonTender({ ...make("2026-11-08"), deadline_confidence: "inferred" }, now)).toBe(false);
    expect(isDueSoonTender(make("2026-11-07"), new Date("2026-11-07T16:00:00Z"))).toBe(false);
  });
  it("指定機關採購保持獨立分類", () => {
    const tender = mapRawTender({ title: "數位看板", relevance: { category: "target_agency_procurement", confidence: "high" } });
    expect(tender.category).toBe("target_agency_procurement");
    expect(tender.terms).toEqual(["機關專案採購"]);
  });
});

describe("同步狀態", () => {
  const now = new Date("2026-11-07T09:00:00+08:00");
  it("維護寫檔不會掩蓋最近抓取失敗", () => {
    expect(getDataSyncStatus({ last_updated: "2026-11-07 08:48", collection_status: { status: "complete", latest_attempt_status: "failed" } }, now)).toBe("warning");
  });
  it("過期與未知時間不顯示已更新", () => {
    expect(getDataSyncStatus({ last_updated: "2026-11-05 18:37", collection_status: { status: "complete", latest_attempt_at: "2026-11-05 18:37" } }, now)).toBe("warning");
    expect(getDataSyncStatus({ last_updated: "invalid", collection_status: { status: "complete" } }, now)).toBe("unknown");
    expect(getDataSyncStatus({ last_updated: "2026-11-07 08:48", collection_status: { latest_attempt_status: "complete", latest_attempt_at: "2026-11-07 08:30" } }, now)).toBe("complete");
  });
  it("維護寫檔不會讓過期的抓取結果顯示已更新", () => {
    expect(getDataSyncStatus({ last_updated: "2026-11-07 08:48", collection_status: { latest_attempt_status: "complete", latest_attempt_at: "2026-11-05 18:37" } }, now)).toBe("warning");
    expect(getDataSyncStatus({ last_updated: "2026-11-07 08:48", collection_status: { latest_attempt_status: "complete" } }, now)).toBe("unknown");
  });
});

describe("本機偏好隱私", () => {
  it("清除舊信箱及遠端URL設定，只讀取公開縣市偏好", () => {
    const values = new Map([
      ["ricoh_subscriber_info", JSON.stringify({ email: "test@example.com", cities: ["桃園市"] })],
      ["SUBSCRIBERS_URL", "https://example.com/private"],
      ["ricoh_public_preferences", JSON.stringify({ city: "桃園市" })],
    ]);
    const storage = { getItem: (key: string) => values.get(key) ?? null, removeItem: (key: string) => { values.delete(key); } };
    expect(readCityPreference(storage)).toBe("桃園市");
    expect(values.has("ricoh_subscriber_info")).toBe(false);
    expect(values.has("SUBSCRIBERS_URL")).toBe(false);
  });
  it("不採用未知縣市或損壞偏好", () => {
    const storage = { getItem: () => JSON.stringify({ city: "未知" }), removeItem: () => {} };
    expect(readCityPreference(storage)).toBe("全部縣市");
  });
});
