import fs from "node:fs";
import path from "node:path";

const root = "/home/ubuntu/ricoh-work";
const data = JSON.parse(fs.readFileSync(path.join(root, "client/src/data/brand_spec_comparison.json"), "utf8"));
const output = "/home/ubuntu/ricoh-competitor-audit/second_layer_gap_matrix.md";
const notListed = "官方來源未列";

const labels = {
  scan_speed_simplex: "單面掃描速度",
  scan_speed_duplex: "雙面掃描速度",
  adf_capacity: "ADF／SPDF 容量",
  scan_resolution: "掃描解析度",
  duplex_print_and_first_output: "雙面列印／首張輸出",
  paper_capacity_and_max_size: "紙張容量／最大紙張",
  monthly_volume: "月印量／建議印量",
  print_languages: "列印語言",
  security_features: "資安功能",
  cloud_scan_features: "雲端掃描功能",
};

const fields = Object.keys(labels);
const rows = data.records.map((record) => {
  const missing = fields.filter((field) => record[field] === notListed);
  return {
    brand: record.brand,
    model: record.model,
    region: record.source_market,
    source: record.source_url,
    type: record.type,
    speed: record.actual_ppm_a4,
    missing,
    verified: fields.length - missing.length,
  };
}).sort((a, b) => b.missing.length - a.missing.length || a.brand.localeCompare(b.brand) || a.model.localeCompare(b.model));

const byBrand = [...new Set(rows.map((row) => row.brand))].map((brand) => {
  const items = rows.filter((row) => row.brand === brand);
  return {
    brand,
    machines: items.length,
    missing: items.reduce((sum, item) => sum + item.missing.length, 0),
    verified: items.reduce((sum, item) => sum + item.verified, 0),
  };
});

const lines = [
  "# 34 筆機型第二層規格缺口矩陣",
  "",
  `產生日期：${new Date().toISOString().slice(0, 10)}`,
  "",
  "本清單只將值為「官方來源未列」的第二層欄位視為待補；並不以同系列、經銷商或推測值填補。",
  "",
  "## 品牌缺口總覽",
  "",
  "| 品牌 | 機型數 | 已核對欄位 | 待補欄位 |",
  "| --- | ---: | ---: | ---: |",
  ...byBrand.map((item) => `| ${item.brand} | ${item.machines} | ${item.verified} | ${item.missing} |`),
  "",
  "## 逐筆缺口與優先研究來源",
  "",
  "| 品牌／機型 | 類型／速度 | 來源市場 | 已核對 | 待補欄位 | 官方來源 |",
  "| --- | --- | --- | ---: | --- | --- |",
  ...rows.map((row) => `| ${row.brand}／${row.model} | ${row.type}／${row.speed} | ${row.region} | ${row.verified}/${fields.length} | ${row.missing.length ? row.missing.map((field) => labels[field]).join("、") : "無"} | [來源](${row.source}) |`),
  "",
  "## 欄位定義",
  "",
  ...Object.entries(labels).map(([field, label]) => "- `" + field + "`：" + label),
  "",
];

fs.writeFileSync(output, lines.join("\n"));
console.log(`Wrote ${rows.length} machine gaps to ${output}`);
