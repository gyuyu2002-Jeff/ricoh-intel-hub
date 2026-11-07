import { describe, expect, it } from "vitest";
import data from "../data/brand_spec_comparison.json";
import {
  compareMemory,
  compareNumbers,
  compareResolution,
  compareScanSpeeds,
  compareStorage,
  compareTextQuantity,
  parseScanSpeed,
} from "./spec-comparison";

describe("掃描速度與測試條件", () => {
  it("不把 IM C2010 的 300 dpi 當速度或錯判比 C251i 快", () => {
    const ricoh = data.records.find((r) => r.model === "IM C2010")!;
    const konica = data.records.find((r) => r.model === "bizhub C251i")!;
    expect(parseScanSpeed(ricoh.scan_speed_simplex)?.value).toBe(80);
    expect(compareScanSpeeds(ricoh.scan_speed_simplex, konica.scan_speed_simplex)).toBe(0);
  });

  it("僅比較相同明確條件的單一速度值", () => {
    expect(compareScanSpeeds("單面 80 ipm（A4、300 dpi）", "單面 100 ipm（A4、300 dpi）")).toBe(2);
    expect(compareScanSpeeds("單面 80 ipm（A4、200 dpi）", "單面 100 ipm（A4、300 dpi）")).toBe(0);
    expect(compareScanSpeeds("單面 80 ipm", "單面 100 ipm")).toBe(0);
    expect(compareScanSpeeds("雙面 100 ppm（A4、300 dpi）", "雙面 150 ipm（A4、300 dpi）")).toBe(0);
  });

  it.each([
    "150 ppm（200 dpi）／120 ppm（300 dpi；SPDF）",
    "黑白／彩色 80 ppm（單次雙面 160 ipm）",
    "標準 ARDF：80 ipm；選配 SPDF：120 ipm（200 dpi）",
    "黑白／彩色最高 100／100 ipm",
    "300 dpi",
    "官方來源未列",
  ])("不把混合條件或缺失資訊 %s 簡化成最高速度", (value) => {
    expect(parseScanSpeed(value)).toBeNull();
    expect(compareScanSpeeds(value, "單面 80 ipm（A4、300 dpi）")).toBe(0);
  });
});

describe("缺失值與不同規格條件", () => {
  it("資料不明不代表較差", () => {
    for (const value of [undefined, null, 0, Number.NaN, Number.POSITIVE_INFINITY]) {
      expect(compareNumbers(100, value)).toBe(0);
      expect(compareNumbers(value, 100)).toBe(0);
    }
    expect(compareMemory("8 GB", "Not separately stated")).toBe(0);
    expect(compareTextQuantity("首張黑白輸出：4.5 秒", "官方來源未列", "秒")).toBe(0);
  });

  it("容量換算一致但不混入選配或主機與面板拆分", () => {
    expect(compareMemory("8,192 MB (8 GB)", "8 GB")).toBe(0);
    expect(compareMemory("8 GB", "6 GB")).toBe(1);
    expect(compareMemory("6 GB（選購可擴充至 8 GB）", "8 GB")).toBe(0);
    expect(compareMemory("6 GB（主機 2 GB + 面板 4 GB）", "8 GB")).toBe(0);
  });

  it("SSD 沒有任意加分，僅比較同介質的容量", () => {
    expect(compareStorage("256 GB SSD", "500 GB HDD")).toBe(0);
    expect(compareStorage("256 GB SSD", "512 GB SSD")).toBe(2);
    expect(compareStorage("1 TB SSD", "512 GB SSD")).toBe(1);
    expect(compareStorage("未列 SSD 容量", "256 GB SSD")).toBe(0);
    expect(compareStorage("At least 500 GB HDD", "512 GB HDD")).toBe(0);
  });

  it("不以解析度乘積混淆不同方向、等效解析度或紙張限制", () => {
    expect(compareResolution("600 x 2,400 dpi", "1,200 x 1,200 dpi")).toBe(0);
    expect(compareResolution("1,200 x 1,200 dpi", "600 x 600 dpi")).toBe(1);
    expect(compareResolution("最大 1,200 x 1,200 dpi", "600 x 600 dpi")).toBe(1);
    expect(compareResolution("9,600 equivalent x 600 dpi", "1,200 x 1,200 dpi")).toBe(0);
    expect(compareResolution("100–1,200 dpi；1,200 dpi 僅 A5 或更小", "600 x 600 dpi")).toBe(0);
  });

  it("不選出黑白與彩色混合的最快首張時間", () => {
    expect(compareTextQuantity("首張列印：黑白 4.5 秒／彩色 7.0 秒", "首張黑白輸出：5.2 秒", "秒")).toBe(0);
    expect(compareTextQuantity("首張輸出：黑白／彩色 5.2／6.9 秒", "首張黑白輸出：4.5 秒", "秒")).toBe(0);
    expect(compareTextQuantity("首張黑白輸出：4.5 秒", "首張黑白輸出：5.2 秒", "秒")).toBe(1);
    expect(compareTextQuantity("首張黑白輸出：4.5 秒", "首張彩色輸出：5.2 秒", "秒")).toBe(0);
  });

  it("不混用標配、選配、建議與最大容量", () => {
    expect(compareTextQuantity("ARDF 100 張（標準）", "ARDF 150 張（標準）", "張")).toBe(2);
    expect(compareTextQuantity("ARDF 100 張（標準）", "選配 SPDF 220 張", "張")).toBe(0);
    expect(compareTextQuantity("標準 1,200／最大 4,700 張", "標準 1,150／最大 6,650 張", "張")).toBe(0);
    expect(compareTextQuantity("標準 1,200／最大 4,700 張", "標準 1,200／最大 6,650 張", "張")).toBe(0);
    expect(compareTextQuantity("建議 16,000 頁／最高 130,000 頁", "最高 150,000 頁", "頁")).toBe(0);
  });
});
