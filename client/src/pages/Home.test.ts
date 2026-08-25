import { describe, expect, it } from "vitest";
import { mapRawTender } from "./Home";

describe("已決標案件得標對照", () => {
  it("有可比歷史時，分別保留本次與前次得標廠商", () => {
    const tender = mapRawTender({
      stage: "已決標",
      main_competitor: "本次得標股份有限公司",
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
      main_competitor: "本次得標股份有限公司",
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
      main_competitor: "連續得標股份有限公司",
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
});
