/*
 * Design system reminder: Specification dossier / Swiss archive.
 * This page prioritizes source traceability, actual ppm and configuration caveats.
 * Keep the warm-paper palette, signal-red index markers, mono technical data and low-radius surfaces.
 * The brand comparator supports both manual model self-selection and auto-matching by speed tier.
 */
import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  Award,
  CheckCircle2,
  ChevronDown,
  Clock,
  FilterX,
  GitCompareArrows,
  Info,
  Search,
  SlidersHorizontal,
  Zap,
} from "lucide-react";
import sourceData from "@/data/brand_spec_comparison.json";

type SpecRecord = {
  brand: string;
  model: string;
  source_market: string;
  type: string;
  actual_ppm_a4: number;
  comparison_tier: string;
  print_resolution: string;
  ram_standard: string;
  ram_max: string;
  storage_standard: string;
  storage_optional: string;
  source_confidence: string;
  source_url: string;
  notes: string;
  scan_speed_simplex: string;
  scan_speed_duplex: string;
  adf_spdf: string;
  scan_resolution: string;
  duplex_print: string;
  first_output: string;
  paper_input: string;
  max_paper_size: string;
  monthly_volume: string;
  print_language: string;
  security_features: string;
  cloud_scan_features: string;
  extended_source_url: string;
  extended_source_note: string;
};

type SpecPayload = {
  title: string;
  checked_date: string;
  version?: string;
  records: SpecRecord[];
};

const payload = sourceData as unknown as SpecPayload;
const allRecords = payload.records;
const allBrands = Array.from(new Set(allRecords.map((record) => record.brand)));

function machineKind(record: SpecRecord) {
  return record.type.toLowerCase().includes("monochrome") ? "黑白" : "彩色";
}

function isVerifiedConfidence(value?: string): boolean {
  if (!value) return true;
  return !value.includes("待確認") && !value.includes("待核對");
}

function confidenceText(value?: string): string {
  if (!value) return "官方已核對";
  if (value.includes("互盛") || value.includes("理光")) return "互盛官方";
  if (value.includes("金儀")) return "金儀官方";
  if (value.includes("震旦") || value.includes("夏普")) return "震旦官方";
  if (value.includes("富士")) return "台灣富士";
  if (value.includes("佳能")) return "台灣佳能";
  if (value.includes("愛普生")) return "愛普生官方";
  if (value.includes("HP")) return "HP 官方";
  return "官方已核對";
}

function pickComparisonRecord(brand: string, output: string, speedTier: string) {
  const requestedPpm = Number(speedTier);
  return allRecords
    .filter((record) => record.brand === brand && machineKind(record) === output && record.comparison_tier.includes(`${speedTier} ppm`))
    .sort((a, b) => Math.abs(a.actual_ppm_a4 - requestedPpm) - Math.abs(b.actual_ppm_a4 - requestedPpm))[0] ?? null;
}

function IndexMark() {
  return (
    <span className="spec-index-mark" aria-hidden="true">
      <img src={`${import.meta.env.BASE_URL}spec-assets/ricoh-intel-index-mark.png`} alt="" />
    </span>
  );
}

// Spec comparison helpers: returns 1 if A is better, 2 if B is better, 0 if equal or indeterminate
function parseRamValue(s?: string): number {
  if (!s) return 0;
  const clean = s.replace(/,/g, "");
  const gb = clean.match(/(\d+(?:\.\d+)?)\s*GB/i);
  if (gb) return parseFloat(gb[1]) * 1024;
  const mb = clean.match(/([\d]+)\s*MB/i);
  if (mb) return parseFloat(mb[1]);
  return 0;
}

function parseStorageValue(s?: string): number {
  if (!s) return 0;
  const clean = s.replace(/,/g, "");
  const tb = clean.match(/(\d+(?:\.\d+)?)\s*TB/i);
  const gb = clean.match(/(\d+(?:\.\d+)?)\s*GB/i);
  let score = 0;
  if (tb) score = parseFloat(tb[1]) * 1024;
  else if (gb) score = parseFloat(gb[1]);
  if (/SSD/i.test(clean)) score += 500;
  return score;
}

function parseScanIpm(s?: string): number {
  if (!s) return 0;
  const matches = s.match(/\b(\d{2,3})\b/g);
  if (matches) {
    const nums = matches.map((m) => parseInt(m, 10)).filter((n) => n <= 400);
    if (nums.length) return Math.max(...nums);
  }
  return 0;
}

function parseAdfSheets(s?: string): number {
  if (!s) return 0;
  const matches = s.match(/(\d+)\s*張/g);
  if (matches) {
    const nums = matches.map((m) => parseInt(m.replace(/\D/g, ""), 10));
    if (nums.length) return Math.max(...nums);
  }
  return 0;
}

function parseFirstOutputSec(s?: string): number {
  if (!s) return 999;
  const matches = s.match(/(\d+(?:\.\d+)?)\s*秒/g);
  if (matches) {
    const nums = matches.map((m) => parseFloat(m.replace(/[^\d.]/g, "")));
    if (nums.length) return Math.min(...nums);
  }
  return 999;
}

function parsePaperInput(s?: string): number {
  if (!s) return 0;
  const matches = s.match(/([\d,]+)\s*張/g);
  if (matches) {
    const nums = matches.map((m) => parseInt(m.replace(/[^\d]/g, ""), 10));
    if (nums.length) return Math.max(...nums);
  }
  return 0;
}

function parseMonthlyVolume(s?: string): number {
  if (!s) return 0;
  const matches = s.match(/([\d,]+)\s*頁/g);
  if (matches) {
    const nums = matches.map((m) => parseInt(m.replace(/[^\d]/g, ""), 10));
    if (nums.length) return Math.max(...nums);
  }
  return 0;
}

function parseResolutionDpi(s?: string): number {
  if (!s) return 0;
  const clean = s.replace(/,/g, "");
  const m = clean.match(/(\d{3,4})\s*[x×*]\s*(\d{3,4})/i);
  if (m) {
    return parseInt(m[1], 10) * parseInt(m[2], 10);
  }
  const single = clean.match(/(\d{3,4})\s*dpi/i);
  if (single) return parseInt(single[1], 10) * parseInt(single[1], 10);
  return 0;
}

function cmpHigher(valA: number, valB: number): 0 | 1 | 2 {
  if (valA > 0 && valB > 0) {
    if (valA > valB) return 1;
    if (valB > valA) return 2;
  } else if (valA > 0 && valB <= 0) {
    return 1;
  } else if (valB > 0 && valA <= 0) {
    return 2;
  }
  return 0;
}

function cmpLower(valA: number, valB: number): 0 | 1 | 2 {
  if (valA > 0 && valB > 0 && valA < 900 && valB < 900) {
    if (valA < valB) return 1;
    if (valB < valA) return 2;
  } else if (valA > 0 && valA < 900 && (valB <= 0 || valB >= 900)) {
    return 1;
  } else if (valB > 0 && valB < 900 && (valA <= 0 || valA >= 900)) {
    return 2;
  }
  return 0;
}

interface SpecDiffMap {
  ppm: 0 | 1 | 2;
  resolution: 0 | 1 | 2;
  ram: 0 | 1 | 2;
  ramMax: 0 | 1 | 2;
  storage: 0 | 1 | 2;
  scanSimplex: 0 | 1 | 2;
  scanDuplex: 0 | 1 | 2;
  adf: 0 | 1 | 2;
  scanRes: 0 | 1 | 2;
  firstOutput: 0 | 1 | 2;
  paper: 0 | 1 | 2;
  monthly: 0 | 1 | 2;
}

function CompareCard({
  side,
  record,
  allSideModels,
  onModelChange,
  specDiff,
  advantageCount,
}: {
  side: "A" | "B";
  record: SpecRecord | null;
  allSideModels: SpecRecord[];
  onModelChange: (model: string) => void;
  specDiff: SpecDiffMap;
  advantageCount: number;
}) {
  if (!record) {
    return (
      <article className="brand-compare-card brand-compare-empty">
        <Info size={22} />
        <h3>尚未選定機型 {side}</h3>
        <p>請於選單中選取機型。</p>
      </article>
    );
  }
  const isBetter = (key: keyof SpecDiffMap) => (side === "A" ? specDiff[key] === 1 : specDiff[key] === 2);

  return (
    <article className="brand-compare-card" key={`${side}-${record.brand}-${record.model}`}>
      <div className="brand-compare-card-head">
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span className="spec-brand-code">{record.brand}</span>
          <span className={`spec-badge-slot ${side === "B" ? "spec-badge-slot-b" : ""}`}>
            設備 {side}
          </span>
          {advantageCount > 0 && (
            <span className="spec-advantage-counter" title={`在此組比較中，設備 ${side} 在 ${advantageCount} 個規格項目中勝出`}>
              ★ {advantageCount} 項優勢
            </span>
          )}
        </div>
        <span className={`spec-status ${isVerifiedConfidence(record.source_confidence) ? "is-verified" : "is-caveat"}`}>
          <CheckCircle2 size={13} />{confidenceText(record.source_confidence)}
        </span>
      </div>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", flexWrap: "wrap", gap: "8px" }}>
        <h3>{record.model}</h3>
        <select
          className="spec-card-inline-select"
          value={record.model}
          onChange={(e) => onModelChange(e.target.value)}
          title="直接更換此卡片機型"
        >
          {allSideModels.map((m) => (
            <option key={m.model} value={m.model}>
              切換：{m.model} ({machineKind(m)} · {m.actual_ppm_a4} ppm)
            </option>
          ))}
        </select>
      </div>
      <p>
        {machineKind(record)} ·{" "}
        <span className={isBetter("ppm") ? "spec-val-better" : ""}>
          實際 {record.actual_ppm_a4} ppm
          {isBetter("ppm") && <span className="spec-val-better-badge">較快</span>}
        </span>{" "}
        · {record.comparison_tier}
      </p>
      <dl className="brand-compare-fields">
        <div>
          <dt>列印解析度</dt>
          <dd className={isBetter("resolution") ? "spec-val-better" : ""}>
            {record.print_resolution}
            {isBetter("resolution") && <span className="spec-val-better-badge">優勢</span>}
          </dd>
        </div>
        <div>
          <dt>記憶體</dt>
          <dd className={isBetter("ram") ? "spec-val-better" : ""}>
            {record.ram_standard}
            {isBetter("ram") && <span className="spec-val-better-badge">容量大</span>}
            {record.ram_max && record.ram_max !== "-" && !record.ram_max.includes("未另標示") && !record.ram_max.includes("Not") && (
              <small className={isBetter("ramMax") ? "spec-val-better" : ""}>
                最大：{record.ram_max}
                {isBetter("ramMax") && <span className="spec-val-better-badge">優勢</span>}
              </small>
            )}
          </dd>
        </div>
        <div>
          <dt>標準儲存</dt>
          <dd className={isBetter("storage") ? "spec-val-better" : ""}>
            {record.storage_standard}
            {isBetter("storage") && <span className="spec-val-better-badge">優勢</span>}
            {record.storage_optional && record.storage_optional !== "無" && record.storage_optional !== "-" && <small>選配：{record.storage_optional.replace(/^選配\s*/, "")}</small>}
          </dd>
        </div>
      </dl>
      <details className="brand-compare-extended">
        <summary>展開掃描、紙張與資安／雲端規格</summary>
        <dl>
          <div>
            <dt>單面掃描</dt>
            <dd className={isBetter("scanSimplex") ? "spec-val-better" : ""}>
              {record.scan_speed_simplex}
              {isBetter("scanSimplex") && <span className="spec-val-better-badge">較快</span>}
            </dd>
          </div>
          <div>
            <dt>雙面掃描</dt>
            <dd className={isBetter("scanDuplex") ? "spec-val-better" : ""}>
              {record.scan_speed_duplex}
              {isBetter("scanDuplex") && <span className="spec-val-better-badge">較快</span>}
            </dd>
          </div>
          <div>
            <dt>ADF／SPDF</dt>
            <dd className={isBetter("adf") ? "spec-val-better" : ""}>
              {record.adf_spdf}
              {isBetter("adf") && <span className="spec-val-better-badge">容量大</span>}
            </dd>
          </div>
          <div>
            <dt>掃描解析度</dt>
            <dd className={isBetter("scanRes") ? "spec-val-better" : ""}>
              {record.scan_resolution}
              {isBetter("scanRes") && <span className="spec-val-better-badge">優勢</span>}
            </dd>
          </div>
          <div>
            <dt>雙面列印／首張輸出</dt>
            <dd>
              {record.duplex_print}
              <small className={isBetter("firstOutput") ? "spec-val-better" : ""}>
                {record.first_output}
                {isBetter("firstOutput") && <span className="spec-val-better-badge">出紙快</span>}
              </small>
            </dd>
          </div>
          <div>
            <dt>進紙／最大紙張</dt>
            <dd className={isBetter("paper") ? "spec-val-better" : ""}>
              {record.paper_input}
              {isBetter("paper") && <span className="spec-val-better-badge">進紙多</span>}
              <small>{record.max_paper_size}</small>
            </dd>
          </div>
          <div>
            <dt>月印量</dt>
            <dd className={isBetter("monthly") ? "spec-val-better" : ""}>
              {record.monthly_volume}
              {isBetter("monthly") && <span className="spec-val-better-badge">負載高</span>}
            </dd>
          </div>
          <div><dt>列印語言</dt><dd>{record.print_language}</dd></div>
          <div><dt>資安與雲端掃描</dt><dd>{record.security_features}<small>{record.cloud_scan_features}</small></dd></div>
        </dl>
      </details>
      <div className="brand-compare-card-foot">
        <span>{record.source_market}</span>
        <div className="brand-compare-source-links">
          <a href={record.source_url} target="_blank" rel="noreferrer">原始規格 <ArrowUpRight size={14} /></a>
          {record.extended_source_url && record.extended_source_url !== record.source_url ? (
            <a href={record.extended_source_url} target="_blank" rel="noreferrer">第二層來源 <ArrowUpRight size={14} /></a>
          ) : null}
        </div>
      </div>
    </article>
  );
}

export default function SpecComparison() {
  const [brand, setBrand] = useState("all");
  const [kind, setKind] = useState("all");
  const [tier, setTier] = useState("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<SpecRecord | null>(allRecords[0] ?? null);

  // Side-by-side comparison states with full model self-selection
  const [compareBrandA, setCompareBrandA] = useState("RICOH");
  const [compareModelA, setCompareModelA] = useState("IM C3010");

  const [compareBrandB, setCompareBrandB] = useState("Konica Minolta");
  const [compareModelB, setCompareModelB] = useState("bizhub C251i");

  const [compareOutput, setCompareOutput] = useState("彩色");
  const [compareTier, setCompareTier] = useState("30");

  // Models available for Side A and Side B based on chosen brands
  const brandAModels = useMemo(() => {
    return allRecords.filter((r) => r.brand === compareBrandA);
  }, [compareBrandA]);

  const brandBModels = useMemo(() => {
    return allRecords.filter((r) => r.brand === compareBrandB);
  }, [compareBrandB]);

  // Handle Brand A change with auto-select
  const handleBrandAChange = (newBrand: string) => {
    setCompareBrandA(newBrand);
    const matched = pickComparisonRecord(newBrand, compareOutput, compareTier);
    const fallback = allRecords.find((r) => r.brand === newBrand);
    setCompareModelA(matched?.model ?? fallback?.model ?? "");
  };

  // Handle Brand B change with auto-select
  const handleBrandBChange = (newBrand: string) => {
    setCompareBrandB(newBrand);
    const matched = pickComparisonRecord(newBrand, compareOutput, compareTier);
    const fallback = allRecords.find((r) => r.brand === newBrand);
    setCompareModelB(matched?.model ?? fallback?.model ?? "");
  };

  // Quick Match by tier button / selects
  const handleQuickMatch = (output: string, tierPpm: string) => {
    setCompareOutput(output);
    setCompareTier(tierPpm);
    const matchA = pickComparisonRecord(compareBrandA, output, tierPpm);
    if (matchA) setCompareModelA(matchA.model);
    const matchB = pickComparisonRecord(compareBrandB, output, tierPpm);
    if (matchB) setCompareModelB(matchB.model);
  };

  // Swap Left and Right
  const handleSwap = () => {
    const tempBrand = compareBrandA;
    const tempModel = compareModelA;
    setCompareBrandA(compareBrandB);
    setCompareModelA(compareModelB);
    setCompareBrandB(tempBrand);
    setCompareModelB(tempModel);
  };

  // Find exact records
  const recordA = useMemo(() => {
    return allRecords.find((r) => r.model === compareModelA && r.brand === compareBrandA)
        ?? allRecords.find((r) => r.model === compareModelA)
        ?? brandAModels[0]
        ?? null;
  }, [compareModelA, compareBrandA, brandAModels]);

  const recordB = useMemo(() => {
    return allRecords.find((r) => r.model === compareModelB && r.brand === compareBrandB)
        ?? allRecords.find((r) => r.model === compareModelB)
        ?? brandBModels[0]
        ?? null;
  }, [compareModelB, compareBrandB, brandBModels]);

  // Compute spec superiority diff between Record A and Record B
  const specDiff: SpecDiffMap = useMemo(() => {
    if (!recordA || !recordB || recordA.model === recordB.model) {
      return {
        ppm: 0,
        resolution: 0,
        ram: 0,
        ramMax: 0,
        storage: 0,
        scanSimplex: 0,
        scanDuplex: 0,
        adf: 0,
        scanRes: 0,
        firstOutput: 0,
        paper: 0,
        monthly: 0,
      };
    }
    return {
      ppm: cmpHigher(recordA.actual_ppm_a4 || 0, recordB.actual_ppm_a4 || 0),
      resolution: cmpHigher(parseResolutionDpi(recordA.print_resolution), parseResolutionDpi(recordB.print_resolution)),
      ram: cmpHigher(parseRamValue(recordA.ram_standard), parseRamValue(recordB.ram_standard)),
      ramMax: cmpHigher(parseRamValue(recordA.ram_max), parseRamValue(recordB.ram_max)),
      storage: cmpHigher(parseStorageValue(recordA.storage_standard), parseStorageValue(recordB.storage_standard)),
      scanSimplex: cmpHigher(parseScanIpm(recordA.scan_speed_simplex), parseScanIpm(recordB.scan_speed_simplex)),
      scanDuplex: cmpHigher(parseScanIpm(recordA.scan_speed_duplex), parseScanIpm(recordB.scan_speed_duplex)),
      adf: cmpHigher(parseAdfSheets(recordA.adf_spdf), parseAdfSheets(recordB.adf_spdf)),
      scanRes: cmpHigher(parseResolutionDpi(recordA.scan_resolution), parseResolutionDpi(recordB.scan_resolution)),
      firstOutput: cmpLower(parseFirstOutputSec(recordA.first_output), parseFirstOutputSec(recordB.first_output)),
      paper: cmpHigher(parsePaperInput(recordA.paper_input), parsePaperInput(recordB.paper_input)),
      monthly: cmpHigher(parseMonthlyVolume(recordA.monthly_volume), parseMonthlyVolume(recordB.monthly_volume)),
    };
  }, [recordA, recordB]);

  const aAdvantageCount = useMemo(() => Object.values(specDiff).filter((v) => v === 1).length, [specDiff]);
  const bAdvantageCount = useMemo(() => Object.values(specDiff).filter((v) => v === 2).length, [specDiff]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("zh-Hant");
    return allRecords.filter((record) => {
      const matchesBrand = brand === "all" || record.brand === brand;
      const matchesKind = kind === "all" || machineKind(record) === kind;
      const matchesTier = tier === "all" || record.comparison_tier.includes(`${tier} ppm`);
      const text = [
        record.brand,
        record.model,
        record.type,
        record.source_market,
        record.comparison_tier,
        record.print_resolution,
        record.ram_standard,
        record.storage_standard,
        record.scan_speed_simplex,
        record.adf_spdf,
        record.paper_input,
        record.print_language,
        record.security_features,
        record.cloud_scan_features,
        record.notes,
      ].join(" ").toLocaleLowerCase("zh-Hant");
      return matchesBrand && matchesKind && matchesTier && (!normalized || text.includes(normalized));
    });
  }, [brand, kind, query, tier]);

  const resetFilters = () => {
    setBrand("all");
    setKind("all");
    setTier("all");
    setQuery("");
  };

  return (
    <div className="spec-app-shell">
      <header className="spec-topbar">
        <a className="spec-brand-lockup" href="#" aria-label="返回標案情報監控雷達">
          <IndexMark />
          <span>
            <strong>RIC0H INTEL HUB</strong>
            <em>07 BRANDS · 20–60 PPM PLATFORM</em>
          </span>
        </a>
        <div className="spec-topbar-side">
          <span><span className="spec-live-dot" /> VERIFIED DATASET · v2.6 (2026-10-29)</span>
          <a href="#" className="spec-return"><ArrowLeft size={15} /> 影印機案件監控</a>
        </div>
      </header>
      <nav className="site-tabs site-tabs-spec" aria-label="網站主要分頁">
        <a className="site-tab" href="#">
          <span className="site-tab-index">01</span>
          <span><strong>影印機案件監控</strong><small>事務機／複合機主機</small></span>
        </a>
        <a className="site-tab" href="#/forecast">
          <span className="site-tab-index">02</span>
          <span><strong>未來半年到期預測</strong><small>涵蓋即日起半年內到期換約案件</small></span>
        </a>
        <a className="site-tab active" href="#/specs" aria-current="page">
          <span className="site-tab-index">03</span>
          <span><strong>設備規格比較平台</strong><small>7廠牌 20~60 張規格比較 (v2.5)</small></span>
        </a>
      </nav>

      <main className="spec-main">
        <section className="spec-hero" aria-labelledby="spec-title">
          <div className="spec-hero-copy">
            <div className="spec-kicker"><span>01</span> SPECIFICATION ARCHIVE / 已核對欄位 · v2.5</div>
            <h1 id="spec-title">7廠牌20~60張<br /><em>規格比較平台</em></h1>
            <p>
              從原廠來源回看列印、掃描、送稿、紙張與資安；保留實際 A4 ppm、來源市場與標準／選配差異。
              <br />
              <span style={{ color: "var(--red)", fontWeight: 600, display: "inline-block", marginTop: "6px" }}>
                【2026-10-29 v2.6 更新版】收錄 7 大主流品牌最新機型共 {allRecords.length} 款，全新支援「自由自選機型比較」與同品牌不同型號升級對照。
              </span>
            </p>
            <div className="spec-hero-facts">
              <div><strong>07</strong><span>指定品牌</span></div>
              <div><strong>{allRecords.length}</strong><span>代表機型</span></div>
              <div><strong>v2.5</strong><span>2026-10-29</span></div>
            </div>
          </div>
          <div className="spec-hero-visual spec-hero-blueprint" aria-hidden="true">
            <div className="spec-blueprint-card"><span>OFFICIAL FIELD</span><b>RESOLUTION</b><i /></div>
            <div className="spec-blueprint-scale"><i /><i /><i /><i /><i /><i /></div>
            <div className="spec-visual-overlay" />
            <div className="spec-visual-ledger"><span>ACTUAL PPM</span><b>20 / 30 / 40 / 50 / 60</b><span>NOT NORMALISED</span></div>
          </div>
        </section>

        <section className="spec-method-strip" aria-label="TEC 典型用電量測試規範">
          <div>
            <Zap size={20} />
            <p>
              <strong>TEC 典型用電量（度／週）</strong>
              <span>依經濟部節能標章與能源之星標準，模擬設備一週（7天/168小時）之典型總耗電量。數值越低越省電。</span>
            </p>
          </div>
          <div>
            <Clock size={20} />
            <p>
              <strong>測試結構（Job Structure）</strong>
              <span>5 天工作日按設備標稱速度定時執行列印與休眠轉換（量測動態作業耗電）；2 天週末維持 48 小時連續休眠或關機待機。</span>
            </p>
          </div>
          <div>
            <Award size={20} />
            <p>
              <strong>計算公式與招標標準</strong>
              <span>
                <code>TEC = (5 × 工作日耗電) + 週末耗電</code>。為政府共同供應契約、節能標章與 ESG 減碳採購之核心指標。
                <a href="https://www.energylabel.org.tw/_admin/_upload/news/efficiency/99/file/%E8%83%BD%E6%BA%90%E4%B9%8B%E6%98%9F%E5%90%88%E6%A0%BC%E5%BD%B1%E5%83%8F%E8%A8%AD%E5%82%99%E4%B9%8B%E5%85%B8%E5%9E%8B%E7%94%A8%E9%9B%BB%E9%87%8F%E6%B8%AC%E8%A9%A6%E7%A8%8B%E5%BA%8F(TEC)[1].pdf" target="_blank" rel="noreferrer" style={{ display: "inline-flex", alignItems: "center", gap: "3px", color: "#dfdcd1", marginLeft: "6px", textDecoration: "underline" }}>
                  測試程序 PDF <ArrowUpRight size={11} />
                </a>
              </span>
            </p>
          </div>
        </section>

        {/* SECTION 02: Side-by-Side Comparison with Manual Model Selection */}
        <section className="brand-compare-panel" id="brand-compare-panel" aria-labelledby="brand-compare-title">
          <div className="brand-compare-heading">
            <div>
              <div className="spec-kicker"><span>02</span> SIDE-BY-SIDE COMPARISON · 支援自由自選機型</div>
              <h2 id="brand-compare-title">自由自選機型，或依同級規格智能配對</h2>
              <p>可直接指定欲比較的特定機型（支援跨品牌或同品牌不同型號升級對照）；亦可依輸出類型與速度級距一鍵自動配對。</p>
            </div>
            <GitCompareArrows size={28} aria-hidden="true" />
          </div>

          <div className="brand-compare-controls-wrap">
            <div className="brand-compare-controls" aria-label="品牌與機型自選">
              {/* Slot A */}
              <div className="brand-compare-slot">
                <div className="brand-compare-slot-header">
                  <span className="spec-badge-slot">比較設備 A</span>
                </div>
                <div className="brand-compare-slot-inputs">
                  <label className="brand-compare-select">
                    <span>品牌 A</span>
                    <select value={compareBrandA} onChange={(e) => handleBrandAChange(e.target.value)}>
                      {allBrands.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                    <ChevronDown size={14} />
                  </label>
                  <label className="brand-compare-select">
                    <span>自選機型 A</span>
                    <select value={compareModelA} onChange={(e) => setCompareModelA(e.target.value)}>
                      {brandAModels.map((m) => (
                        <option key={m.model} value={m.model}>
                          {m.model} ({machineKind(m)} · {m.actual_ppm_a4} ppm)
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={14} />
                  </label>
                </div>
              </div>

              {/* Swap Column */}
              <div className="brand-compare-swap-col">
                <button
                  type="button"
                  className="brand-compare-swap-btn"
                  onClick={handleSwap}
                  title="左右對調比較機型"
                  aria-label="左右對調比較機型"
                >
                  <GitCompareArrows size={18} />
                  <span>對調</span>
                </button>
              </div>

              {/* Slot B */}
              <div className="brand-compare-slot">
                <div className="brand-compare-slot-header">
                  <span className="spec-badge-slot spec-badge-slot-b">比較設備 B</span>
                </div>
                <div className="brand-compare-slot-inputs">
                  <label className="brand-compare-select">
                    <span>品牌 B</span>
                    <select value={compareBrandB} onChange={(e) => handleBrandBChange(e.target.value)}>
                      {allBrands.map((item) => <option key={item} value={item}>{item}</option>)}
                    </select>
                    <ChevronDown size={14} />
                  </label>
                  <label className="brand-compare-select">
                    <span>自選機型 B</span>
                    <select value={compareModelB} onChange={(e) => setCompareModelB(e.target.value)}>
                      {brandBModels.map((m) => (
                        <option key={m.model} value={m.model}>
                          {m.model} ({machineKind(m)} · {m.actual_ppm_a4} ppm)
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={14} />
                  </label>
                </div>
              </div>
            </div>

            {/* Quick Match Bar */}
            <div className="brand-compare-quick-bar">
              <div className="brand-compare-quick-group">
                <span className="brand-compare-quick-title">
                  <SlidersHorizontal size={14} /> 同級規格快速配對：
                </span>
                <label className="brand-compare-mini-select">
                  <span>輸出</span>
                  <select value={compareOutput} onChange={(e) => handleQuickMatch(e.target.value, compareTier)}>
                    <option value="彩色">彩色</option>
                    <option value="黑白">黑白</option>
                  </select>
                  <ChevronDown size={12} />
                </label>
                <div className="brand-compare-tier-pills">
                  {["20", "30", "40", "50", "60"].map((tierNum) => (
                    <button
                      key={tierNum}
                      type="button"
                      className={`tier-pill-btn ${compareTier === tierNum ? "is-active" : ""}`}
                      onClick={() => handleQuickMatch(compareOutput, tierNum)}
                    >
                      {tierNum} ppm
                    </button>
                  ))}
                </div>
              </div>
              <span className="brand-compare-quick-hint">
                💡 點選速度級距可自動帶入同級機型；亦可直接於上方「自選機型」自由指定任意型號。
                {recordA && recordB && recordA.model !== recordB.model && (
                  <span style={{ display: "block", marginTop: "4px", color: "#0b7a42", fontWeight: 700 }}>
                    ✓ 兩機對照下，規格勝出項目將自動以【綠色粗體】標註（設備 A 勝出 {aAdvantageCount} 項 · 設備 B 勝出 {bAdvantageCount} 項）
                  </span>
                )}
              </span>
            </div>
          </div>

          {/* Cards or Notices */}
          {recordA && recordB && recordA.model === recordB.model ? (
            <div className="brand-compare-notice">
              <Info size={17} />
              左右兩側已選取相同機型 <strong>【{recordA.brand} {recordA.model}】</strong>。請於上方選單中切換不同機型以進行規格差異對照。
            </div>
          ) : (
            <div className="brand-compare-grid">
              <CompareCard
                side="A"
                record={recordA}
                allSideModels={brandAModels}
                onModelChange={setCompareModelA}
                specDiff={specDiff}
                advantageCount={aAdvantageCount}
              />
              <CompareCard
                side="B"
                record={recordB}
                allSideModels={brandBModels}
                onModelChange={setCompareModelB}
                specDiff={specDiff}
                advantageCount={bAdvantageCount}
              />
            </div>
          )}
        </section>

        {/* SECTION 03: Filtered Dataset Table */}
        <section className="spec-workbench" aria-labelledby="workbench-title">
          <div className="spec-section-heading">
            <div>
              <div className="spec-kicker"><span>03</span> FILTERED DATASET · v2.6 更新版</div>
              <h2 id="workbench-title">瀏覽 7廠牌20~60張設備資料</h2>
              <p>選擇品牌、輸出類型與速度級距；每列皆可展開原始條件與官方來源，並可一鍵帶入上方進行比較。</p>
            </div>
            <div className="spec-result-count"><strong>{filtered.length}</strong><span>/ {allRecords.length} 筆符合</span></div>
          </div>

          <div className="spec-filter-panel">
            <div className="spec-filter-title"><SlidersHorizontal size={17} /><span>篩選條件</span></div>
            <label className="spec-search-field" htmlFor="spec-search"><Search size={16} /><input id="spec-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋型號、規格或來源市場" /></label>
            <label className="spec-select-field"><span>品牌</span><select value={brand} onChange={(event) => setBrand(event.target.value)}><option value="all">全部品牌</option>{allBrands.map((item) => <option key={item} value={item}>{item}</option>)}</select><ChevronDown size={14} /></label>
            <label className="spec-select-field"><span>輸出</span><select value={kind} onChange={(event) => setKind(event.target.value)}><option value="all">黑白＋彩色</option><option value="彩色">彩色</option><option value="黑白">黑白</option></select><ChevronDown size={14} /></label>
            <label className="spec-select-field"><span>速度級距</span><select value={tier} onChange={(event) => setTier(event.target.value)}><option value="all">20 / 30 / 40 / 50 / 60</option><option value="20">20 ppm</option><option value="30">30 ppm</option><option value="40">40 ppm</option><option value="50">50 ppm</option><option value="60">60 ppm</option></select><ChevronDown size={14} /></label>
            <button type="button" className="spec-reset" onClick={resetFilters}><FilterX size={16} /> 清除</button>
          </div>

          <div className="spec-table-wrap" role="region" aria-label="品牌規格比較表" tabIndex={0}>
            <table className="spec-table">
              <thead><tr><th>品牌／機型</th><th>類型與速度</th><th>列印解析度</th><th>掃描／送稿</th><th>記憶體</th><th>標準儲存</th><th>資料狀態</th><th>快速比較</th></tr></thead>
              <tbody>
                {filtered.map((record) => (
                  <tr key={`${record.brand}-${record.model}`} className={selected?.model === record.model ? "is-selected" : ""} onClick={() => setSelected(record)}>
                    <td><div className="spec-model-cell"><span className="spec-brand-code">{record.brand}</span><strong>{record.model}</strong><small>[{record.source_market}]</small></div></td>
                    <td><div className="spec-speed-cell"><b>{record.actual_ppm_a4} <span>ppm</span></b><small>{machineKind(record)} · {record.comparison_tier}</small></div></td>
                    <td>{record.print_resolution}</td>
                    <td><strong>{record.scan_speed_simplex}</strong><small>{record.adf_spdf}</small></td>
                    <td>
                      <strong>{record.ram_standard}</strong>
                      {record.ram_max && record.ram_max !== "-" && !record.ram_max.includes("未另標示") && !record.ram_max.includes("Not") && (
                        <small>MAX：{record.ram_max}</small>
                      )}
                    </td>
                    <td>{record.storage_standard}</td>
                    <td><span className={`spec-status ${isVerifiedConfidence(record.source_confidence) ? "is-verified" : "is-caveat"}`}><CheckCircle2 size={13} />{confidenceText(record.source_confidence)}</span></td>
                    <td>
                      <div className="spec-row-compare-btns">
                        <button
                          type="button"
                          className="spec-mini-compare-btn"
                          title={`將 ${record.model} 設為比較機型 A`}
                          onClick={(e) => {
                            e.stopPropagation();
                            setCompareBrandA(record.brand);
                            setCompareModelA(record.model);
                            document.getElementById("brand-compare-panel")?.scrollIntoView({ behavior: "smooth" });
                          }}
                        >
                          設為 A
                        </button>
                        <button
                          type="button"
                          className="spec-mini-compare-btn spec-mini-compare-btn-b"
                          title={`將 ${record.model} 設為比較機型 B`}
                          onClick={(e) => {
                            e.stopPropagation();
                            setCompareBrandB(record.brand);
                            setCompareModelB(record.model);
                            document.getElementById("brand-compare-panel")?.scrollIntoView({ behavior: "smooth" });
                          }}
                        >
                          設為 B
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && <div className="spec-empty"><Info size={20} /><strong>目前沒有符合條件的型號。</strong><span>請調整級距或清除篩選條件後再試一次。</span></div>}
          </div>
        </section>

        {/* SECTION 04: Detailed Model Inspection */}
        <section className="spec-detail-panel" aria-labelledby="detail-title">
          <div className="spec-detail-index"><span>04</span><div className="spec-index-rail" /></div>
          {selected ? <>
            <div className="spec-detail-heading">
              <div>
                <span className="spec-brand-code">{selected.brand} / MODEL FILE</span>
                <h2 id="detail-title">{selected.model}</h2>
                <p>{selected.type}</p>
                <div className="spec-detail-actions">
                  <button
                    type="button"
                    className="spec-btn-action"
                    onClick={() => {
                      setCompareBrandA(selected.brand);
                      setCompareModelA(selected.model);
                      document.getElementById("brand-compare-panel")?.scrollIntoView({ behavior: "smooth" });
                    }}
                  >
                    <GitCompareArrows size={13} /> 帶入上方【比較機型 A】
                  </button>
                  <button
                    type="button"
                    className="spec-btn-action spec-btn-action-b"
                    onClick={() => {
                      setCompareBrandB(selected.brand);
                      setCompareModelB(selected.model);
                      document.getElementById("brand-compare-panel")?.scrollIntoView({ behavior: "smooth" });
                    }}
                  >
                    <GitCompareArrows size={13} /> 帶入上方【比較機型 B】
                  </button>
                </div>
              </div>
              <span className="spec-status is-verified">
                <CheckCircle2 size={13} />{confidenceText(selected.source_confidence)}
              </span>
            </div>
            <div className="spec-detail-grid">
              <div className="spec-detail-spec"><span>ACTUAL A4 SPEED</span><strong>{selected.actual_ppm_a4} <em>ppm</em></strong><small>{selected.comparison_tier}</small></div>
              <div className="spec-detail-spec"><span>PRINT RESOLUTION</span><strong>{selected.print_resolution}</strong></div>
              <div className="spec-detail-spec"><span>MEMORY</span><strong>{selected.ram_standard}</strong><small>最大：{selected.ram_max}</small></div>
              <div className="spec-detail-spec"><span>STORAGE</span><strong>{selected.storage_standard}</strong><small>選配：{selected.storage_optional}</small></div>
            </div>
            <div className="spec-detail-sections">
              <section><h3>掃描與文件送稿</h3><dl><div><dt>單面掃描</dt><dd>{selected.scan_speed_simplex}</dd></div><div><dt>雙面掃描</dt><dd>{selected.scan_speed_duplex}</dd></div><div><dt>ADF／SPDF</dt><dd>{selected.adf_spdf}</dd></div><div><dt>掃描解析度</dt><dd>{selected.scan_resolution}</dd></div></dl></section>
              <section><h3>列印效能與紙張處理</h3><dl><div><dt>雙面列印</dt><dd>{selected.duplex_print}</dd></div><div><dt>首張輸出</dt><dd>{selected.first_output}</dd></div><div><dt>進紙容量</dt><dd>{selected.paper_input}</dd></div><div><dt>最大紙張</dt><dd>{selected.max_paper_size}</dd></div><div><dt>建議／最高月印量</dt><dd>{selected.monthly_volume}</dd></div></dl></section>
              <section><h3>列印語言、資安與雲端</h3><dl><div><dt>列印語言</dt><dd>{selected.print_language}</dd></div><div><dt>資安功能</dt><dd>{selected.security_features}</dd></div><div><dt>雲端／掃描流程</dt><dd>{selected.cloud_scan_features}</dd></div></dl></section>
            </div>
            <div className="spec-source-note">
              <div>
                <span>資料限制／核對註記與能耗說明</span>
                <p>{selected.notes}</p>
                {selected.extended_source_note ? <small>{selected.extended_source_note}</small> : null}
                <div style={{ marginTop: "10px", padding: "8px 12px", background: "rgba(255,255,255,0.65)", borderLeft: "3px solid #c8102e", fontSize: "11px", color: "#56615a", lineHeight: "1.6" }}>
                  <strong>【TEC 典型用電量測試簡述】</strong> 依經濟部節能標章與能源之星規範，模擬一週 7 天運轉（5天工作日列印/休眠動態耗電 ＋ 2天週末48小時休眠耗電），計算公式為 <code>TEC = (5 × 工作日耗電) + 週末耗電</code>（單位：度/週），數值越低越省電，為政府標案評核硬指標。
                </div>
              </div>
              <div className="spec-source-links">
                <a href={selected.source_url} target="_blank" rel="noreferrer">原始規格來源 <ArrowUpRight size={15} /></a>
                {selected.extended_source_url && selected.extended_source_url !== selected.source_url ? <a href={selected.extended_source_url} target="_blank" rel="noreferrer">第二層官方來源 <ArrowUpRight size={15} /></a> : null}
                <a href="https://www.energylabel.org.tw/_admin/_upload/news/efficiency/99/file/%E8%83%BD%E6%BA%90%E4%B9%8B%E6%98%9F%E5%90%88%E6%A0%BC%E5%BD%B1%E5%83%8F%E8%A8%AD%E5%82%99%E4%B9%8B%E5%85%B8%E5%9E%8B%E7%94%A8%E9%9B%BB%E9%87%8F%E6%B8%AC%E8%A9%A6%E7%A8%8B%E5%BA%8F(TEC)[1].pdf" target="_blank" rel="noreferrer" style={{ color: "#2f6a55" }}>節能標章 TEC 程序 PDF <ArrowUpRight size={14} /></a>
              </div>
            </div>
          </> : <div className="spec-empty"><Info size={20} /><strong>請在上方表格選取一筆資料。</strong></div>}
        </section>

      </main>

      <footer className="spec-footer">
        <span>RIC0H INTEL HUB / 20–60 PPM PLATFORM · 版本：v2.6 (2026-10-29)</span>
        <span>最後查核更新日：{payload.checked_date} · 共收錄 {allRecords.length} 筆官方來源代表機型資料</span>
      </footer>
    </div>
  );
}
