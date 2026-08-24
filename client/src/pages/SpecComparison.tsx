/*
 * Design system reminder: Specification dossier / Swiss archive.
 * This page prioritizes source traceability, actual ppm and configuration caveats.
 * Keep the warm-paper palette, signal-red index markers, mono technical data and low-radius surfaces.
 */
import { useMemo, useState } from "react";
import {
  ArrowLeft,
  ArrowUpRight,
  BookOpenCheck,
  CheckCircle2,
  ChevronDown,
  Database,
  FilterX,
  HardDrive,
  Info,
  Search,
  SlidersHorizontal,
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
};

type SpecPayload = {
  checked_date: string;
  records: SpecRecord[];
};

const payload = sourceData as unknown as SpecPayload;
const allRecords = payload.records;
const allBrands = Array.from(new Set(allRecords.map((record) => record.brand)));

function machineKind(record: SpecRecord) {
  return record.type.toLowerCase().includes("monochrome") ? "黑白" : "彩色";
}

function confidenceText(value: string) {
  return value.startsWith("A —") ? "已核對" : value.startsWith("A-") ? "附註核對" : "待核對";
}

function IndexMark() {
  return (
    <span className="spec-index-mark" aria-hidden="true">
      <img src={`${import.meta.env.BASE_URL}spec-assets/ricoh-intel-index-mark.png`} alt="" />
    </span>
  );
}

export default function SpecComparison() {
  const [brand, setBrand] = useState("all");
  const [kind, setKind] = useState("all");
  const [tier, setTier] = useState("all");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<SpecRecord | null>(allRecords[0] ?? null);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("zh-Hant");
    return allRecords.filter((record) => {
      const matchesBrand = brand === "all" || record.brand === brand;
      const matchesKind = kind === "all" || machineKind(record) === kind;
      const matchesTier = tier === "all" || record.comparison_tier.includes(`${tier} ppm`);
      const text = [record.brand, record.model, record.type, record.source_market, record.comparison_tier, record.print_resolution, record.ram_standard, record.storage_standard, record.notes].join(" ").toLocaleLowerCase("zh-Hant");
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
            <em>SPECIFICATION DESK / 07 BRANDS</em>
          </span>
        </a>
        <div className="spec-topbar-side">
          <span><span className="spec-live-dot" /> VERIFIED DATASET</span>
          <a href="#" className="spec-return"><ArrowLeft size={15} /> 標案監控</a>
        </div>
      </header>

      <main className="spec-main">
        <section className="spec-hero" aria-labelledby="spec-title">
          <div className="spec-hero-copy">
            <div className="spec-kicker"><span>01</span> SPECIFICATION ARCHIVE / 已核對欄位</div>
            <h1 id="spec-title">七品牌硬規格<br /><em>比較工作檯</em></h1>
            <p>從原廠來源回看列印解析度、記憶體與內部儲存；保留實際 A4 ppm、來源市場與標準／選配差異。</p>
            <div className="spec-hero-facts">
              <div><strong>07</strong><span>指定品牌</span></div>
              <div><strong>{allRecords.length}</strong><span>代表機型</span></div>
              <div><strong>03</strong><span>硬體欄位</span></div>
            </div>
          </div>
          <div className="spec-hero-visual spec-hero-blueprint" aria-hidden="true">
            <div className="spec-blueprint-card"><span>OFFICIAL FIELD</span><b>RESOLUTION</b><i /></div>
            <div className="spec-blueprint-scale"><i /><i /><i /><i /><i /><i /></div>
            <div className="spec-visual-overlay" />
            <div className="spec-visual-ledger"><span>ACTUAL PPM</span><b>20 / 30 / 40</b><span>NOT NORMALISED</span></div>
          </div>
        </section>

        <section className="spec-method-strip" aria-label="資料使用方式">
          <div><BookOpenCheck size={19} /><p><strong>實際速度優先</strong><span>25、35、45 ppm 不會改寫成整數級距。</span></p></div>
          <div><Database size={19} /><p><strong>來源市場保留</strong><span>台灣、APAC、Europe 與 US 規格不混用。</span></p></div>
          <div><HardDrive size={19} /><p><strong>未公開不補值</strong><span>未列儲存容量會明示待核對，不填 0。</span></p></div>
        </section>

        <section className="spec-workbench" aria-labelledby="workbench-title">
          <div className="spec-section-heading">
            <div>
              <div className="spec-kicker"><span>02</span> FILTERED DATASET</div>
              <h2 id="workbench-title">從規格條件開始比對</h2>
              <p>選擇品牌、輸出類型與速度級距；每列皆可展開原始條件與官方來源。</p>
            </div>
            <div className="spec-result-count"><strong>{filtered.length}</strong><span>/ {allRecords.length} 筆符合</span></div>
          </div>

          <div className="spec-filter-panel">
            <div className="spec-filter-title"><SlidersHorizontal size={17} /><span>篩選條件</span></div>
            <label className="spec-search-field" htmlFor="spec-search"><Search size={16} /><input id="spec-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜尋型號、規格或來源市場" /></label>
            <label className="spec-select-field"><span>品牌</span><select value={brand} onChange={(event) => setBrand(event.target.value)}><option value="all">全部品牌</option>{allBrands.map((item) => <option key={item} value={item}>{item}</option>)}</select><ChevronDown size={14} /></label>
            <label className="spec-select-field"><span>輸出</span><select value={kind} onChange={(event) => setKind(event.target.value)}><option value="all">黑白＋彩色</option><option value="彩色">彩色</option><option value="黑白">黑白</option></select><ChevronDown size={14} /></label>
            <label className="spec-select-field"><span>速度級距</span><select value={tier} onChange={(event) => setTier(event.target.value)}><option value="all">20 / 30 / 40</option><option value="20">20 ppm</option><option value="30">30 ppm</option><option value="40">40 ppm</option></select><ChevronDown size={14} /></label>
            <button type="button" className="spec-reset" onClick={resetFilters}><FilterX size={16} /> 清除</button>
          </div>

          <div className="spec-table-wrap" role="region" aria-label="品牌規格比較表" tabIndex={0}>
            <table className="spec-table">
              <thead><tr><th>品牌／機型</th><th>類型與速度</th><th>列印解析度</th><th>記憶體</th><th>標準儲存</th><th>選配／備註</th><th>資料狀態</th></tr></thead>
              <tbody>
                {filtered.map((record) => (
                  <tr key={`${record.brand}-${record.model}`} className={selected?.model === record.model ? "is-selected" : ""} onClick={() => setSelected(record)}>
                    <td><div className="spec-model-cell"><span className="spec-brand-code">{record.brand}</span><strong>{record.model}</strong><small>[{record.source_market}]</small></div></td>
                    <td><div className="spec-speed-cell"><b>{record.actual_ppm_a4} <span>ppm</span></b><small>{machineKind(record)} · {record.comparison_tier}</small></div></td>
                    <td>{record.print_resolution}</td>
                    <td><strong>{record.ram_standard}</strong><small>MAX：{record.ram_max}</small></td>
                    <td>{record.storage_standard}</td>
                    <td><span>{record.storage_optional}</span></td>
                    <td><span className={`spec-status ${record.source_confidence.startsWith("A —") ? "is-verified" : "is-caveat"}`}><CheckCircle2 size={13} />{confidenceText(record.source_confidence)}</span></td>
                  </tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && <div className="spec-empty"><Info size={20} /><strong>目前沒有符合條件的型號。</strong><span>請調整級距或清除篩選條件後再試一次。</span></div>}
          </div>
        </section>

        <section className="spec-detail-panel" aria-labelledby="detail-title">
          <div className="spec-detail-index"><span>03</span><div className="spec-index-rail" /></div>
          {selected ? <>
            <div className="spec-detail-heading"><div><span className="spec-brand-code">{selected.brand} / MODEL FILE</span><h2 id="detail-title">{selected.model}</h2><p>{selected.type}</p></div><span className="spec-status is-verified"><CheckCircle2 size={13} />{confidenceText(selected.source_confidence)}</span></div>
            <div className="spec-detail-grid">
              <div className="spec-detail-spec"><span>ACTUAL A4 SPEED</span><strong>{selected.actual_ppm_a4} <em>ppm</em></strong><small>{selected.comparison_tier}</small></div>
              <div className="spec-detail-spec"><span>PRINT RESOLUTION</span><strong>{selected.print_resolution}</strong></div>
              <div className="spec-detail-spec"><span>MEMORY</span><strong>{selected.ram_standard}</strong><small>最大：{selected.ram_max}</small></div>
              <div className="spec-detail-spec"><span>STORAGE</span><strong>{selected.storage_standard}</strong><small>選配：{selected.storage_optional}</small></div>
            </div>
            <div className="spec-source-note"><div><span>資料限制／核對註記</span><p>{selected.notes}</p></div><a href={selected.source_url} target="_blank" rel="noreferrer">開啟官方來源 <ArrowUpRight size={15} /></a></div>
          </> : <div className="spec-empty"><Info size={20} /><strong>請在上方表格選取一筆資料。</strong></div>}
        </section>

        <section className="spec-reference-grid">
          <article className="spec-reference-card"><div className="spec-reference-art trace-art" aria-hidden="true"><span>01</span><i /><i /><i /></div><div><span>TRACEABLE SOURCES</span><h3>每筆資料都保留來源市場與連結。</h3><p>台灣、海外官方頁與官方 PDF 不混成單一全球規格。</p></div></article>
          <article className="spec-reference-card"><div className="spec-reference-art method-art" aria-hidden="true"><span>02</span><i /><i /><i /></div><div><span>COMPARISON METHOD</span><h3>把條件寫清楚，比數字更重要。</h3><p>half-speed、equivalent、HDD 選配與未公開容量均保留於原始欄位。</p></div></article>
        </section>
      </main>

      <footer className="spec-footer"><span>RIC0H INTEL HUB / SPECIFICATION DESK</span><span>查核日：{payload.checked_date} · 34 筆官方來源代表資料</span></footer>
    </div>
  );
}
