/*
 * Design system reminder: Neo-Editorial Swiss / business intelligence archive.
 * Keep the dossier spine, restrained paper palette, red index line, source-first
 * language, and calm motion. This page intentionally avoids tracking/copy flows.
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowUpRight,
  BarChart3,
  ChevronDown,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  FileDown,
  Filter,
  Layers3,
  MapPin,
  MoreHorizontal,
  PanelLeft,
  Search,
  Sparkles,
} from "lucide-react";
import brandPayload from "../data/brands.json";

type View = "tenders" | "brands";
type BrandField = { value: string; status?: string; checkedAt: string; sourceUrl: string; sourceLabel: string };
type ModelOption = {
  id: string;
  label: string;
  status: string;
  note: string;
  checkedAt: string;
  sourceUrl: string;
  sourceLabel: string;
  fields: Record<string, BrandField>;
};
type Brand = {
  id: string;
  index: string;
  name: string;
  regionStatus: string;
  statusTone: string;
  checkedAt: string;
  models: string;
  modelOptions: ModelOption[];
  summary: { entryPoint: string; competitiveStrength: string; mustAsk: string };
  sources: Array<{ title: string; description: string; status: string; checkedAt: string; url: string }>;
  fields: Record<string, BrandField>;
};
type Payload = {
  checkedAt: string;
  brandDirectory: Array<{ id: string; name: string; checkedAt: string; sourceUrl: string; loaded: boolean }>;
  brands: Brand[];
};
type TenderPayload = {
  last_updated?: string;
  tenders?: RawTender[];
  collection_status?: {
    status?: string;
    latest_attempt_status?: string;
    latest_attempt_at?: string;
  };
};
type HistoryRow = [date: string, awardCode: string, rate: string, winner: string];
type Tender = {
  priority: string;
  priorityLabel: string;
  city: string;
  stage: string;
  stageTone: string;
  isAwarded: boolean;
  awardPrice: string;
  countdown: string;
  title: string;
  job: string;
  unit: string;
  publish: string;
  deadline: string;
  budget: string;
  discount: string;
  samples: string;
  reference: string;
  competitor: string;
  previousWinner: string;
  confidence: string;
  confidenceTone: string;
  scope: string;
  summary: string;
  next: string;
  terms: string[];
  sourceUrl: string;
  history: HistoryRow[];
};

const payload = brandPayload as Payload;
const { brands } = payload;
const modelStampTone = (status: string) => status.includes("海外") ? "stamp-amber" : status.includes("台灣") ? "stamp-green" : "stamp-blue";
const resolveBrandModel = (brand: Brand, modelId?: string) => {
  const activeModel = brand.modelOptions.find((model) => model.id === modelId) ?? brand.modelOptions[0];
  if (!activeModel) return { ...brand, activeModel: undefined };
  return { ...brand, activeModel, fields: { ...brand.fields, ...activeModel.fields } };
};
const rows = [
  ["model", "代表系列／型號"],
  ["positioning", "定位"],
  ["printSpeed", "列印速度"],
  ["scanSpeed", "掃描速度"],
  ["scanDestinations", "掃描目的地"],
  ["transportSecurity", "傳輸安全"],
  ["deviceSecurity", "裝置安全"],
  ["cloudManagement", "雲端／管理"],
  ["taiwanSuitability", "台灣適用性"],
  ["limitations", "主要限制"],
] as const;
const groups = [
  { id: "core", label: "定位與核心規格", start: 0, end: 4 },
  { id: "workflow", label: "文件工作流程", start: 4, end: 5 },
  { id: "security", label: "資安與裝置管理", start: 5, end: 7 },
  { id: "service", label: "台灣適用性與限制", start: 7, end: 10 },
];

const fallbackTenders: Tender[] = [
  {
    priority: "P1",
    priorityLabel: "優先追蹤",
    city: "台北市",
    stage: "正式開標",
    stageTone: "stage-blue",
    isAwarded: false,
    awardPrice: "未公開",
    countdown: "距截止 24 天",
    title: "影印機租賃案",
    job: "115-033",
    unit: "財政部臺北國稅局",
    publish: "2026-08-07",
    deadline: "2026-09-07",
    budget: "NT$ 12,582,464",
    discount: "83.8%",
    samples: "近 5 年｜同設備同契約｜4 筆",
    reference: "NT$ 10,544,000",
    competitor: "宏羚股份有限公司",
    previousWinner: "宏羚股份有限公司",
    confidence: "高",
    confidenceTone: "confidence-high",
    scope: "同一機關",
    summary: "同機關近 5 年有 4 筆可比資料，且已有競爭廠商紀錄。",
    next: "今日確認規格與投標資格，建立兩組價格情境。",
    terms: ["影印機", "租賃"],
    sourceUrl: "https://web.pcc.gov.tw/",
    history: [
      ["2024-08-05", "113-026", "83.8%", "宏羚股份有限公司"],
      ["2023-08-01", "112-018", "81.2%", "金儀 Konica Minolta"],
      ["2021-07-26", "110-021", "86.4%", "新印科技股份有限公司"],
    ],
  },
  {
    priority: "P1",
    priorityLabel: "優先追蹤",
    city: "桃園市",
    stage: "公開徵求價單",
    stageTone: "stage-amber",
    isAwarded: false,
    awardPrice: "未公開",
    countdown: "距截止 10 天",
    title: "115117年度影印機租賃長約",
    job: "I7315D063",
    unit: "台灣中油股份有限公司煉製事業部桃園煉油廠",
    publish: "2026-08-10",
    deadline: "2026-08-24",
    budget: "無公開數據",
    discount: "資料不足",
    samples: "近 5 年僅 1 筆有效可比資料",
    reference: "不產生價格推估",
    competitor: "宏羚股份有限公司",
    previousWinner: "宏羚股份有限公司",
    confidence: "中",
    confidenceTone: "confidence-mid",
    scope: "同一機關",
    summary: "早期需求訊號已出現，但目前只有 1 筆可比資料，不宜直接推估價格。",
    next: "先確認規格附件、租賃年限與預算揭露時間。",
    terms: ["影印機", "租賃", "長約"],
    sourceUrl: "https://web.pcc.gov.tw/",
    history: [["2024-11-07", "I7313D053", "94.5%", "宏羚股份有限公司"]],
  },
  {
    priority: "P2",
    priorityLabel: "持續觀察",
    city: "新北市",
    stage: "評選中",
    stageTone: "stage-dark",
    isAwarded: false,
    awardPrice: "未公開",
    countdown: "資料更新 2 小時前",
    title: "多功能事務機設備租賃暨維護",
    job: "115-0718",
    unit: "新北市政府採購處",
    publish: "2026-08-04",
    deadline: "2026-08-28",
    budget: "NT$ 6,840,000",
    discount: "79.6%",
    samples: "跨機關｜近 5 年｜6 筆",
    reference: "NT$ 5,444,640",
    competitor: "待人工確認",
    previousWinner: "金儀 Konica Minolta",
    confidence: "中",
    confidenceTone: "confidence-mid",
    scope: "跨機關",
    summary: "採購範圍含租賃與維護，歷史資料可作背景參考，但競品名稱尚待核對。",
    next: "確認維護 SLA、服務據點與評選配分，再更新比較矩陣。",
    terms: ["多功能事務機", "維護", "租賃"],
    sourceUrl: "https://web.pcc.gov.tw/",
    history: [
      ["2025-09-18", "114-083", "78.4%", "金儀 Konica Minolta"],
      ["2024-09-12", "113-076", "81.1%", "佳能台灣"],
    ],
  },
];

type RawTender = {
  city?: string;
  title?: string;
  unit?: string;
  job_number?: string;
  publish_date?: string;
  deadline?: string;
  budget?: string | number;
  award_price?: string | number;
  avg_discount?: string;
  suggested_price?: string;
  main_competitor?: string;
  tender_url?: string;
  stage?: string;
  history_records?: Array<{
    award_date?: string;
    job_number?: string;
    award_price?: number;
    discount_rate?: number;
    winner?: string;
    relation_scope?: string;
  }>;
  relevance?: { confidence?: string; score?: number; matched_terms?: string[] };
};

function formatDeadlineCountdown(deadline?: string) {
  if (!deadline) return "截止日待確認";
  const date = new Date(`${deadline}T23:59:59`);
  if (Number.isNaN(date.getTime())) return "截止日待確認";
  const days = Math.ceil((date.getTime() - Date.now()) / 86400000);
  if (days < 0) return "已逾期";
  if (days === 0) return "今日截止";
  return `距截止 ${days} 天`;
}

function mapRawTender(raw: RawTender): Tender {
  const history = [...(raw.history_records ?? [])]
    .sort((a, b) => String(b.award_date ?? "").localeCompare(String(a.award_date ?? "")))
    .map((record) => [
      record.award_date ?? "待確認",
      record.job_number ?? "歷史案件",
      typeof record.discount_rate === "number" ? `${record.discount_rate}%` : "資料不足",
      record.winner ?? "待人工確認",
    ] as HistoryRow);
  const previousWinner = history[0]?.[3] ?? raw.main_competitor ?? "待人工確認";
  const confidence = raw.relevance?.confidence === "high" ? "高" : raw.relevance?.confidence === "medium" ? "中" : "待確認";
  const priority = raw.relevance?.score && raw.relevance.score >= 4 ? "P1" : "P2";
  const stage = raw.stage ?? "狀態待確認";
  const isAwarded = stage === "已決標";
  const stageTone = isAwarded ? "stage-awarded" : stage.includes("無法決標") ? "stage-failed" : stage.includes("公開") ? "stage-amber" : stage.includes("評選") ? "stage-dark" : "stage-blue";
  const comparable = history.length > 0 ? `近 5 年｜可比紀錄 ${history.length} 筆` : "目前無完整可比紀錄";
  const summary = history.length > 0
    ? `${raw.unit ?? "本案機關"}過去有 ${history.length} 筆可比資料，前次由${previousWinner}得標。`
    : "目前尚無足夠歷史得標資料，先以公告規格與資格條件為主。";
  const next = stage.includes("公開")
    ? "先確認規格附件、預算揭露與投標資格，再安排客戶拜訪。"
    : "確認服務條件、評選配分與競品紀錄，再更新業務判讀。";
  return {
    priority,
    priorityLabel: priority === "P1" ? "優先追蹤" : "持續觀察",
    city: raw.city ?? "地點待確認",
    stage,
    stageTone,
    isAwarded,
    awardPrice: typeof raw.award_price === "number" ? `NT$ ${raw.award_price.toLocaleString("en-US")}` : raw.award_price ?? "未公開",
    countdown: formatDeadlineCountdown(raw.deadline),
    title: raw.title ?? "未命名標案",
    job: raw.job_number ?? "待查",
    unit: raw.unit ?? "機關待確認",
    publish: raw.publish_date ?? "待確認",
    deadline: raw.deadline ?? "待確認",
    budget: typeof raw.budget === "number" ? `NT$ ${raw.budget.toLocaleString("en-US")}` : raw.budget ?? "無公開數據",
    discount: raw.avg_discount ?? "資料不足",
    samples: comparable,
    reference: raw.suggested_price ?? "資料不足",
    competitor: raw.main_competitor ?? "待人工確認",
    previousWinner,
    confidence,
    confidenceTone: confidence === "高" ? "confidence-high" : confidence === "中" ? "confidence-mid" : "confidence-low",
    scope: history[0] ? (raw.history_records?.[0]?.relation_scope === "same_unit" ? "同一機關" : "跨機關") : "尚無歷史範圍",
    summary,
    next,
    terms: raw.relevance?.matched_terms?.slice(0, 4) ?? [],
    sourceUrl: raw.tender_url ?? "https://web.pcc.gov.tw/",
    history,
  };
}

function Mark() {
  return (
    <div className="archive-mark" aria-label="RICOH Intelligence logo">
      <svg viewBox="0 0 40 40" aria-hidden="true">
        <path d="M8 8.5h17.5l6.5 5.5v18H8z" fill="none" stroke="currentColor" strokeWidth="2.4" />
        <path d="M25.5 8.5V14H32M13 20h13M13 25h9" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" />
        <path d="M31 12v19" stroke="#C92D3F" strokeWidth="3.5" strokeLinecap="round" />
      </svg>
    </div>
  );
}

function Stamp({ children, tone = "neutral" }: { children: ReactNode; tone?: string }) {
  return <span className={`status-stamp ${tone}`}>{children}</span>;
}

function Metric({ label, value, note, alert = false }: { label: string; value: string; note: string; alert?: boolean }) {
  return (
    <div className={`metric ${alert ? "metric-alert" : ""}`}>
      <div className="metric-label">{label}</div>
      <div className="metric-value">{value}</div>
      <div className="metric-note">{note}</div>
    </div>
  );
}

function SectionSkeleton({ view }: { view: View }) {
  return (
    <div className="loading-panel" aria-live="polite" aria-busy="true">
      <div className="loading-kicker">
        <span className="loading-pulse" /> {view === "brands" ? "載入品牌資料與來源索引" : "載入標案情報與歷史紀錄"}
      </div>
      <div className="skeleton-heading" />
      <div className="skeleton-subheading" />
      <div className="skeleton-summary"><span /><span /><span /><span /></div>
      <div className="skeleton-list"><span /><span /><span /></div>
    </div>
  );
}

function TenderCard({ tender }: { tender: Tender }) {
  const [expanded, setExpanded] = useState(false);
  const latestHistory = tender.history[0];
  return (
    <article className={`tender-card ${tender.isAwarded ? "tender-card-awarded" : ""}`}>
      <div className="dossier-spine" aria-hidden="true"><span>{tender.priority}</span><i>{tender.job}</i></div>
      <div className="tender-status-bar">
        <div className="status-left">
          <Stamp tone={tender.priority === "P1" ? "stamp-red" : "stamp-ink"}>{tender.priority} · {tender.priorityLabel}</Stamp>
          <Stamp tone="stamp-sage">{tender.city}</Stamp>
          <Stamp tone={tender.stageTone}>{tender.isAwarded ? "✓ 已決標" : tender.stage}</Stamp>
        </div>
        <div className={`countdown ${tender.priority === "P1" ? "countdown-hot" : ""}`}><Clock3 size={14} />{tender.countdown}</div>
      </div>
      {tender.isAwarded && <div className="award-result-banner"><span className="award-result-mark">✓</span><div><strong>本案已決標</strong><span>得標廠商：{tender.competitor} · 決標金額：{tender.awardPrice}</span></div><span className="award-result-label">RESULT</span></div>}
      <div className="tender-identity">
        <div>
          <div className="eyebrow">TENDER FILE <span>/</span> {tender.publish}</div>
          <h3>{tender.title}</h3>
          <div className="tender-meta"><span>{tender.unit}</span><span className="job-code">案號 {tender.job}</span></div>
        </div>
        <button className="icon-button" aria-label="更多案件操作"><MoreHorizontal size={18} /></button>
      </div>
      <div className="metric-grid">
        <Metric label="截止日" value={tender.deadline} note={tender.stage} alert={tender.priority === "P1"} />
        <Metric label={tender.isAwarded ? "決標金額" : "預算"} value={tender.isAwarded ? tender.awardPrice : tender.budget} note={tender.isAwarded ? "官方決標公告已提供" : tender.budget.includes("無") ? "附件／後續公告待確認" : "官方公告已提供"} />
        <Metric label="歷史折率中位數" value={tender.discount} note={tender.samples} />
        <Metric label={tender.reference.includes("不") ? "歷史優勢商" : "歷史參考價格"} value={tender.reference} note={tender.reference.includes("不") ? tender.competitor : "依中位折率推算｜僅供參考"} />
        <Metric label="前次得標廠商" value={tender.previousWinner} note={latestHistory ? `${latestHistory[0]} · ${latestHistory[2]}` : "尚無歷史得標紀錄"} />
      </div>
      <div className="decision-strip">
        <div className="decision-main">
          <div className="decision-label"><Sparkles size={14} /> 判讀</div>
          <p>{tender.summary}</p>
          <div className="decision-action"><span>下一步</span>{tender.next}</div>
        </div>
        <div className="confidence-box">
          <div className="decision-label"><Database size={14} /> 資料可信度</div>
          <div className="confidence-value"><span className={`confidence-dot ${tender.confidenceTone}`} />{tender.confidence}</div>
          <div className="confidence-meta">來源：官方查核 · {tender.scope} · {tender.history.length} 筆</div>
        </div>
      </div>
      <div className="tender-footer">
        <div className="term-list">{tender.terms.map((term) => <span key={term}>{term}</span>)}</div>
        <div className="action-row">
          <a className="action-primary" href={tender.sourceUrl} target="_blank" rel="noreferrer"><ExternalLink size={15} /> 查看官方公告</a>
          <button className="action-secondary action-compact" onClick={() => setExpanded(!expanded)}>{expanded ? <ChevronDown size={15} /> : <ChevronRight size={15} />} {expanded ? "收合前次紀錄" : "前次得標與歷史"}</button>
        </div>
      </div>
      {expanded && (
        <div className="tender-details">
          <div className="details-header">
            <div><span className="eyebrow">AWARD HISTORY</span><h4>前次得標與歷史紀錄</h4></div>
            <Stamp tone="stamp-blue">{tender.history.length} 筆可比紀錄</Stamp>
          </div>
          <div className="history-list">
            {tender.history.map((row) => (
              <div className="history-row" key={row[1]}>
                <span>{row[0]}</span><strong>{row[1]}</strong><span>{row[2]}</span><span>{row[3]}</span>
                <Stamp tone={row[3] === tender.previousWinner ? "stamp-red" : "stamp-green"}>{row[3] === tender.previousWinner ? "前次得標" : "歷史紀錄"}</Stamp>
              </div>
            ))}
          </div>
          <div className="award-note"><span>判讀提示</span><strong>前次得標廠商：{tender.previousWinner}</strong><em>本欄為歷史資訊，不代表本案結果。</em></div>
        </div>
      )}
    </article>
  );
}

function BrandMatrix() {
  const [openGroups, setOpenGroups] = useState({ core: true, workflow: true, security: true, service: false });
  const [matrixLoading, setMatrixLoading] = useState(false);
  const ricoh = brands.find((brand) => brand.id === "ricoh") ?? brands[0];
  const competitorOptions = brands.filter((brand) => brand.id !== "ricoh");
  const [comparisonBrandId, setComparisonBrandId] = useState(competitorOptions[0]?.id ?? "");
  const [comparisonModelId, setComparisonModelId] = useState(competitorOptions[0]?.modelOptions[0]?.id ?? "");
  const competitorBase = competitorOptions.find((brand) => brand.id === comparisonBrandId) ?? competitorOptions[0];
  const selectedRicoh = ricoh ? resolveBrandModel(ricoh) : undefined;
  const competitor = competitorBase ? resolveBrandModel(competitorBase, comparisonModelId) : undefined;
  const visibleBrands = selectedRicoh && competitor ? [selectedRicoh, competitor] : [];
  if (matrixLoading) return <SectionSkeleton view="brands" />;
  if (!ricoh || !selectedRicoh || !competitor || !competitor.activeModel || !selectedRicoh.activeModel) return <div className="brand-empty-state">目前沒有足夠的已建檔型號資料可供比較。</div>;
  return (
    <section className="brand-workspace">
      <div className="comparison-toolbar">
        <label className="toolbar-field" htmlFor="comparison-brand"><span>比較品牌</span><select id="comparison-brand" className="select-button brand-select-native" value={competitor.id} onChange={(event) => { const nextBrand = competitorOptions.find((brand) => brand.id === event.target.value); setMatrixLoading(true); setComparisonBrandId(event.target.value); setComparisonModelId(nextBrand?.modelOptions[0]?.id ?? ""); window.setTimeout(() => setMatrixLoading(false), 280); }}>{competitorOptions.map((brand) => <option key={brand.id} value={brand.id}>{brand.name}</option>)}</select></label>
        <label className="toolbar-field" htmlFor="comparison-model"><span>比較型號</span><select id="comparison-model" className="select-button brand-select-native" value={competitor.activeModel.id} onChange={(event) => { setMatrixLoading(true); setComparisonModelId(event.target.value); window.setTimeout(() => setMatrixLoading(false), 280); }}>{competitorBase.modelOptions.map((model) => <option key={model.id} value={model.id}>{model.label}</option>)}</select></label>
        <div className="toolbar-field toolbar-status"><span>資料狀態</span><div className="toolbar-status-copy"><strong>{competitor.activeModel.status}</strong><small>查核 {competitor.activeModel.checkedAt}</small></div></div>
      </div>
      <div className="model-verification-strip">
        <div><span>固定主品牌</span><strong>{selectedRicoh.activeModel.label}</strong></div>
        <div><span>已選比較型號</span><strong>{competitor.activeModel.label}</strong><a href={competitor.activeModel.sourceUrl} target="_blank" rel="noreferrer">{competitor.activeModel.sourceLabel} <ExternalLink size={11} /></a></div>
        <div><span>待核對動作</span><strong>{competitor.activeModel.note}</strong></div>
      </div>
      <div className="matrix-summary">
        <div className="summary-block summary-red"><span className="summary-kicker">RICOH 主品牌 · {selectedRicoh.activeModel.label}</span><strong>{selectedRicoh.summary.entryPoint}</strong><small>查核 {selectedRicoh.activeModel.checkedAt} · <a href={selectedRicoh.activeModel.sourceUrl} target="_blank" rel="noreferrer">型號官方來源</a></small></div>
        <div className="summary-block"><span className="summary-kicker">{competitor.name} · {competitor.activeModel.label}</span><strong>{competitor.summary.competitiveStrength}</strong><a className="summary-source-link" href={competitor.activeModel.sourceUrl} target="_blank" rel="noreferrer">查看型號官方來源 <ArrowUpRight size={13} /></a></div>
        <div className="summary-block"><span className="summary-kicker">待核對動作</span><strong>{competitor.activeModel.note}</strong><small>此型號狀態：{competitor.activeModel.status} · 查核 {competitor.activeModel.checkedAt}</small></div>
      </div>
      <div className="matrix-shell">
        <div className="matrix-scroll-hint"><span><PanelLeft size={14} /> RICOH 固定主品牌 · {selectedRicoh.activeModel.label}</span><span>{competitor.name} · {competitor.activeModel.label} <ArrowUpRight size={13} /></span></div>
        <div className="matrix-table" role="table">
          <div className="matrix-row matrix-head"><div className="matrix-label-cell">比較項目</div>{visibleBrands.map((brand) => <div className={`matrix-brand-cell ${brand.id === "ricoh" ? "matrix-ricoh" : "matrix-competitor"}`} data-brand-id={brand.id} key={brand.id}><span className="brand-index">{brand.index}</span><div className="matrix-brand-identity"><strong>{brand.name}</strong><small>{brand.activeModel?.label} · 查核 {brand.activeModel?.checkedAt}</small></div><Stamp tone={modelStampTone(brand.activeModel?.status ?? "")}>{brand.activeModel?.status ?? brand.regionStatus}</Stamp></div>)}</div>
          {groups.map((group) => openGroups[group.id as keyof typeof openGroups] && <div key={group.id} className="matrix-group"><button className="matrix-group-title" onClick={() => setOpenGroups({ ...openGroups, [group.id]: !openGroups[group.id as keyof typeof openGroups] })}><span><span className="group-rule" />{group.label}</span><ChevronDown size={15} /></button>{rows.slice(group.start, group.end).map(([key, label]) => <div className="matrix-row" key={key}><div className="matrix-label-cell"><span>{label}</span></div>{visibleBrands.map((brand) => { const field = brand.fields[key]; return <div className={`matrix-value-cell ${brand.id === "ricoh" ? "matrix-ricoh" : "matrix-competitor"}`} key={`${brand.id}-${key}`}><span>{field?.value ?? "待建檔"}</span>{field?.status && <span className={`cell-flag ${field.status === "待確認" ? "flag-blue" : "flag-amber"}`}>{field.status}</span>}{field?.sourceUrl && <a className="cell-evidence" href={field.sourceUrl} target="_blank" rel="noreferrer">來源 <ExternalLink size={11} /></a>}</div>; })}</div>)}</div>)}
        </div>
      </div>
      <div className="matrix-footer-note"><Database size={15} /><span>RICOH 為固定主品牌；右側比較品牌可由上方選擇器切換。矩陣資料於 {payload.checkedAt} 查核，海外來源、選配與授權條件不代表台灣承諾，請在提案前完成人工確認。</span></div>
    </section>
  );
}

export default function Home() {
  const [view, setView] = useState<View>("tenders");
  const [filter, setFilter] = useState("全部案件");
  const [cityFilter, setCityFilter] = useState("全部縣市");
  const [loading, setLoading] = useState(true);
  const [viewLoading, setViewLoading] = useState(false);
  const [tenders, setTenders] = useState<Tender[]>(fallbackTenders);
  const [dataUpdated, setDataUpdated] = useState("待確認");
  const [dataSyncStatus, setDataSyncStatus] = useState<"loading" | "complete" | "warning" | "unknown">("loading");
  const [dataSyncAttempt, setDataSyncAttempt] = useState("");
  const cityOptions = useMemo(() => {
    const counts = new Map<string, number>();
    tenders.forEach(({ city }) => counts.set(city, (counts.get(city) ?? 0) + 1));
    return Array.from(counts.entries()).sort(([cityA, countA], [cityB, countB]) => countB - countA || cityA.localeCompare(cityB, "zh-Hant"));
  }, [tenders]);
  const filteredTenders = useMemo(() => {
    let next = tenders;
    if (filter === "3 日內") next = next.filter((tender) => tender.priority === "P1");
    if (filter === "待確認") next = next.filter((tender) => tender.confidence !== "高");
    if (cityFilter !== "全部縣市") next = next.filter((tender) => tender.city === cityFilter);
    return next;
  }, [cityFilter, filter, tenders]);
  useEffect(() => {
    let active = true;
    const dataUrl = new URL("data.json", document.baseURI).toString();
    fetch(dataUrl, { cache: "no-store" })
      .then((response) => response.ok ? response.json() as Promise<TenderPayload> : Promise.reject(new Error("data.json unavailable")))
      .then((data) => {
        if (!active) return;
        if (Array.isArray(data.tenders) && data.tenders.length > 0) setTenders(data.tenders.map(mapRawTender));
        if (data.last_updated) setDataUpdated(data.last_updated);
        const latestStatus = data.collection_status?.latest_attempt_status ?? data.collection_status?.status;
        setDataSyncAttempt(data.collection_status?.latest_attempt_at ?? "");
        setDataSyncStatus(data.last_updated ? latestStatus && latestStatus !== "complete" ? "warning" : "complete" : "unknown");
      })
      .catch(() => { if (active) { setDataUpdated("待確認"); setDataSyncStatus("unknown"); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const switchView = (next: View) => { if (next === view) return; setViewLoading(true); setView(next); window.setTimeout(() => setViewLoading(false), 380); };
  if (loading) return <div className="app-shell loading-shell"><header className="topbar"><div className="brand-lockup"><Mark /><div><div className="brand-title">互盛情報中樞</div><div className="brand-subtitle">INTERNAL BUSINESS INTELLIGENCE <span>/</span> 桃園業務情報</div></div></div><span className="loading-top-note"><span className="loading-pulse" /> 讀取來源索引</span></header><main className="page-container"><SectionSkeleton view="tenders" /></main></div>;
  const dataUpdateCopy = dataSyncStatus === "warning" ? `最後成功更新：${dataUpdated}` : `資料更新：${dataUpdated}`;
  const dataUpdateTitle = dataSyncStatus === "warning" && dataSyncAttempt ? `最近一次同步嘗試：${dataSyncAttempt}；目前顯示最後成功更新資料。` : "標案資料集最後成功同步時間";
  return <div className="app-shell"><header className="topbar"><div className="brand-lockup"><Mark /><div><div className="brand-title">互盛情報中樞</div><div className="brand-subtitle">INTERNAL BUSINESS INTELLIGENCE <span>/</span> 桃園業務情報</div></div></div><div className="topbar-actions"><span className={`live-indicator ${dataSyncStatus === "warning" ? "data-update-warning" : ""}`} title={dataUpdateTitle}><span /> LIVE <em>{dataSyncStatus === "warning" ? `最後成功 ${dataUpdated}` : `資料更新 ${dataUpdated}`}</em></span><button className="icon-button" aria-label="列印工作區"><FileDown size={17} /></button></div></header><main className="page-container"><div className="workspace-switcher" role="tablist" aria-label="主要功能切換"><div className="switcher-label">主要功能</div><button role="tab" aria-selected={view === "tenders"} className={view === "tenders" ? "switcher-tab active" : "switcher-tab"} onClick={() => switchView("tenders")}><BarChart3 size={16} /><span><strong>標案情報監控雷達</strong><small>案件優先級與前次得標</small></span></button><button role="tab" aria-selected={view === "brands"} className={view === "brands" ? "switcher-tab active" : "switcher-tab"} onClick={() => switchView("brands")}><Layers3 size={16} /><span><strong>各廠牌產品與市場資訊</strong><small>官方來源與規格比較</small></span></button></div><div className="page-heading"><div><div className="eyebrow">互盛情報中樞 <span>/</span> 2026.08.14</div><h1>{view === "tenders" ? "標案情報監控雷達" : "各廠牌規格比較"}</h1><p>{view === "tenders" ? "先看今天該追的案，再回頭核對前次得標紀錄。" : "以 RICOH 為主要品牌，選擇單一比較品牌快速核對產品、資安、雲端與管理規格。"}</p></div><div className="heading-actions"><span className={`update-note ${dataSyncStatus === "warning" ? "data-update-warning" : ""}`} title={dataUpdateTitle}><Database size={14} /><time>{dataUpdateCopy}</time></span><button className="outline-button"><FileDown size={15} /> 列印工作區</button></div></div>{viewLoading ? <SectionSkeleton view={view} /> : view === "tenders" ? <><div className="tender-overview"><div className="overview-main"><div className="overview-kicker">TODAY'S OPPORTUNITY INDEX</div><div className="overview-number">{tenders.length}</div><div className="overview-copy"><strong>件進行中標案</strong><span>已完成縣市判定，依業務優先級重新排序</span></div></div><div className="overview-stat overview-awarded"><span>已決標案件</span><strong>{tenders.filter((tender) => tender.isAwarded).length}</strong><small>近期結果醒目追蹤</small></div><div className="overview-stat"><span>今日來源公告</span><strong>{tenders.length}</strong><small>目前資料集案件量</small></div><div className="overview-stat"><span>可比歷史資料</span><strong>{tenders.filter((tender) => tender.history.length >= 2).length}</strong><small>具可比歷史資料</small></div><div className="overview-stat"><span>待人工確認</span><strong className="red-text">{tenders.filter((tender) => tender.confidence !== "高").length}</strong><small>資料需補查核</small></div></div><div className="city-quick-filter" aria-label="縣市快速選擇"><div className="city-filter-heading"><div className="city-filter-title"><MapPin size={17} /><div><strong>縣市快速選擇</strong><span>先按地區縮小案件範圍，再搭配案件狀態篩選</span></div></div><div className="city-filter-meta"><span>{cityFilter === "全部縣市" ? "全台案件" : cityFilter}</span><small>{filteredTenders.length} 件符合目前條件</small></div></div><div className="city-pill-list" role="group" aria-label="標案縣市"><button type="button" aria-pressed={cityFilter === "全部縣市"} className={cityFilter === "全部縣市" ? "city-pill active" : "city-pill"} onClick={() => setCityFilter("全部縣市")}><span>全部縣市</span><strong>{tenders.length}</strong></button>{cityOptions.map(([city, count]) => <button type="button" aria-pressed={cityFilter === city} className={cityFilter === city ? "city-pill active" : "city-pill"} key={city} onClick={() => setCityFilter(city)}><span>{city}</span><strong>{count}</strong></button>)}</div></div><div className="workspace-toolbar"><div className="filter-intro"><Filter size={16} /><strong>案件檔案</strong><span>{filteredTenders.length} / {tenders.length} 顯示</span></div><div className="filter-tabs">{["全部案件", "3 日內", "待確認"].map((item) => <button key={item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{item}</button>)}</div><button className="outline-button"><Search size={15} /> 搜尋案件</button></div><div className="tender-list">{filteredTenders.map((tender) => <TenderCard key={tender.job} tender={tender} />)}</div></> : <div className="brand-main brand-main-focused"><BrandMatrix /></div>}</main><footer className="page-footer"><span>互盛情報中樞 / INTERNAL BUSINESS INTELLIGENCE</span><span>品牌查核日期：{payload.checkedAt}</span></footer></div>;
}
