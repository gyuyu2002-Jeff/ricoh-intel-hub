/*
 * Design system reminder: Neo-Editorial Swiss / business intelligence archive.
 * Keep the dossier spine, restrained paper palette, red index line, source-first
 * language, and calm motion. This page intentionally avoids tracking/copy flows.
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowUpRight,
  BarChart3,
  BookOpen,
  Check,
  ChevronDown,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  FileDown,
  Filter,
  Layers3,
  MoreHorizontal,
  PanelLeft,
  Search,
  Sparkles,
} from "lucide-react";
import brandPayload from "../data/brands.json";

type View = "tenders" | "brands";
type BrandField = { value: string; status?: string; checkedAt: string; sourceUrl: string; sourceLabel: string };
type Brand = {
  id: string;
  index: string;
  name: string;
  regionStatus: string;
  statusTone: string;
  checkedAt: string;
  models: string;
  summary: { entryPoint: string; competitiveStrength: string; mustAsk: string };
  sources: Array<{ title: string; description: string; status: string; checkedAt: string; url: string }>;
  fields: Record<string, BrandField>;
};
type Payload = {
  checkedAt: string;
  brandDirectory: Array<{ id: string; name: string; checkedAt: string; sourceUrl: string; loaded: boolean }>;
  brands: Brand[];
};
type HistoryRow = [date: string, awardCode: string, rate: string, winner: string];
type Tender = {
  priority: string;
  priorityLabel: string;
  city: string;
  stage: string;
  stageTone: string;
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
const { brands, brandDirectory } = payload;
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
  const stageTone = stage.includes("公開") ? "stage-amber" : stage.includes("評選") ? "stage-dark" : "stage-blue";
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
    <article className="tender-card">
      <div className="dossier-spine" aria-hidden="true"><span>{tender.priority}</span><i>{tender.job}</i></div>
      <div className="tender-status-bar">
        <div className="status-left">
          <Stamp tone={tender.priority === "P1" ? "stamp-red" : "stamp-ink"}>{tender.priority} · {tender.priorityLabel}</Stamp>
          <Stamp tone="stamp-sage">{tender.city}</Stamp>
          <Stamp tone={tender.stageTone}>{tender.stage}</Stamp>
        </div>
        <div className={`countdown ${tender.priority === "P1" ? "countdown-hot" : ""}`}><Clock3 size={14} />{tender.countdown}</div>
      </div>
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
        <Metric label="預算" value={tender.budget} note={tender.budget.includes("無") ? "附件／後續公告待確認" : "官方公告已提供"} />
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
  const [scenario, setScenario] = useState("政府標案");
  const [openGroups, setOpenGroups] = useState({ core: true, workflow: true, security: true, service: false });
  const [matrixLoading, setMatrixLoading] = useState(false);
  const updateScenario = (next: string) => { setMatrixLoading(true); setScenario(next); window.setTimeout(() => setMatrixLoading(false), 280); };
  const ricoh = brands[0];
  const competitor = brands[1];
  const third = brands[2];
  if (matrixLoading) return <SectionSkeleton view="brands" />;
  return (
    <section className="brand-workspace">
      <div className="comparison-toolbar">
        <div className="toolbar-field"><span>客戶情境</span><button className="select-button">{scenario}<ChevronDown size={15} /></button></div>
        <div className="toolbar-field"><span>型號層級</span><button className="select-button">代表型號 <ChevronDown size={15} /></button></div>
        <div className="toolbar-field"><span>資料狀態</span><button className="select-button">台灣已確認 <ChevronDown size={15} /></button></div>
      </div>
      <div className="scenario-chips">{["政府標案", "企業多據點", "醫療／高資安", "價格導向"].map((item) => <button key={item} className={scenario === item ? "active" : ""} onClick={() => updateScenario(item)}>{item}</button>)}</div>
      <div className="matrix-summary">
        <div className="summary-block summary-red"><span className="summary-kicker">RICOH 切入點</span><strong>{ricoh.summary.entryPoint}</strong><small>查核 {ricoh.checkedAt} · <a href={ricoh.sources[0].url} target="_blank" rel="noreferrer">官方來源</a></small></div>
        <div className="summary-block"><span className="summary-kicker">競品可見強項</span><strong>{competitor.summary.competitiveStrength}</strong><a className="summary-source-link" href={competitor.sources[0].url} target="_blank" rel="noreferrer">查看官方來源 <ArrowUpRight size={13} /></a></div>
        <div className="summary-block"><span className="summary-kicker">業務必問項目</span><strong>{third.summary.mustAsk}</strong><small>查核 {third.checkedAt} · 海外資料需人工確認</small></div>
      </div>
      <div className="matrix-shell">
        <div className="matrix-scroll-hint"><span><PanelLeft size={14} /> 固定比較項目</span><span>左右滑動查看競品 <ArrowUpRight size={13} /></span></div>
        <div className="matrix-table" role="table">
          <div className="matrix-row matrix-head"><div className="matrix-label-cell">比較項目</div>{brands.map((brand) => <div className={`matrix-brand-cell ${brand.id === "ricoh" ? "matrix-ricoh" : ""}`} key={brand.id}><span className="brand-index">{brand.index}</span><strong>{brand.name}</strong><Stamp tone={brand.statusTone}>{brand.regionStatus}</Stamp><small>查核 {brand.checkedAt}</small></div>)}</div>
          {groups.map((group) => openGroups[group.id as keyof typeof openGroups] && <div key={group.id} className="matrix-group"><button className="matrix-group-title" onClick={() => setOpenGroups({ ...openGroups, [group.id]: !openGroups[group.id as keyof typeof openGroups] })}><span><span className="group-rule" />{group.label}</span><ChevronDown size={15} /></button>{rows.slice(group.start, group.end).map(([key, label]) => <div className="matrix-row" key={key}><div className="matrix-label-cell"><span>{label}</span></div>{brands.map((brand) => { const field = brand.fields[key]; return <div className={`matrix-value-cell ${brand.id === "ricoh" ? "matrix-ricoh" : ""}`} key={`${brand.id}-${key}`}><span>{field?.value ?? "待建檔"}</span>{field?.status && <span className={`cell-flag ${field.status === "待確認" ? "flag-blue" : "flag-amber"}`}>{field.status}</span>}{field?.sourceUrl && <a className="cell-evidence" href={field.sourceUrl} target="_blank" rel="noreferrer">來源 <ExternalLink size={11} /></a>}</div>; })}</div>)}</div>)}
        </div>
      </div>
      <div className="matrix-footer-note"><Database size={15} /><span>矩陣資料於 {payload.checkedAt} 查核；海外來源、選配與授權條件不代表台灣承諾，請在提案前完成人工確認。</span></div>
    </section>
  );
}

export default function Home() {
  const [view, setView] = useState<View>("tenders");
  const [filter, setFilter] = useState("全部案件");
  const [loading, setLoading] = useState(true);
  const [viewLoading, setViewLoading] = useState(false);
  const [tenders, setTenders] = useState<Tender[]>(fallbackTenders);
  const [dataUpdated, setDataUpdated] = useState("2026-08-14 15:51");
  const filteredTenders = useMemo(() => filter === "3 日內" ? tenders.filter((t) => t.priority === "P1") : filter === "待確認" ? tenders.filter((t) => t.confidence !== "高") : tenders, [filter, tenders]);
  useEffect(() => {
    let active = true;
    const dataUrl = new URL("data.json", document.baseURI).toString();
    fetch(dataUrl, { cache: "no-store" })
      .then((response) => response.ok ? response.json() as Promise<{ last_updated?: string; tenders?: RawTender[] }> : Promise.reject(new Error("data.json unavailable")))
      .then((data) => {
        if (!active) return;
        if (Array.isArray(data.tenders) && data.tenders.length > 0) setTenders(data.tenders.map(mapRawTender));
        if (data.last_updated) setDataUpdated(data.last_updated);
      })
      .catch(() => undefined)
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  const switchView = (next: View) => { if (next === view) return; setViewLoading(true); setView(next); window.setTimeout(() => setViewLoading(false), 380); };
  if (loading) return <div className="app-shell loading-shell"><header className="topbar"><div className="brand-lockup"><Mark /><div><div className="brand-title">互盛情報中樞</div><div className="brand-subtitle">INTERNAL BUSINESS INTELLIGENCE <span>/</span> 桃園業務情報</div></div></div><span className="loading-top-note"><span className="loading-pulse" /> 讀取來源索引</span></header><main className="page-container"><SectionSkeleton view="tenders" /></main></div>;
  return <div className="app-shell"><header className="topbar"><div className="brand-lockup"><Mark /><div><div className="brand-title">互盛情報中樞</div><div className="brand-subtitle">INTERNAL BUSINESS INTELLIGENCE <span>/</span> 桃園業務情報</div></div></div><div className="topbar-actions"><span className="live-indicator"><span /> LIVE <em>15:51</em></span><button className="icon-button" aria-label="列印工作區"><FileDown size={17} /></button></div></header><main className="page-container"><div className="workspace-switcher" role="tablist" aria-label="主要功能切換"><div className="switcher-label">主要功能</div><button role="tab" aria-selected={view === "tenders"} className={view === "tenders" ? "switcher-tab active" : "switcher-tab"} onClick={() => switchView("tenders")}><BarChart3 size={16} /><span><strong>標案情報監控雷達</strong><small>案件優先級與前次得標</small></span></button><button role="tab" aria-selected={view === "brands"} className={view === "brands" ? "switcher-tab active" : "switcher-tab"} onClick={() => switchView("brands")}><Layers3 size={16} /><span><strong>各廠牌產品與市場資訊</strong><small>官方來源與規格比較</small></span></button></div><div className="page-heading"><div><div className="eyebrow">互盛情報中樞 <span>/</span> 2026.08.14</div><h1>{view === "tenders" ? "標案情報監控雷達" : "各廠牌規格比較"}</h1><p>{view === "tenders" ? "先看今天該追的案，再回頭核對前次得標紀錄。" : "依官方來源比較產品、資安、雲端與管理規格。"}</p></div><div className="heading-actions"><span className="update-note"><Database size={14} /> 資料查核 15:51</span><button className="outline-button"><FileDown size={15} /> 列印工作區</button></div></div>{viewLoading ? <SectionSkeleton view={view} /> : view === "tenders" ? <><div className="tender-overview"><div className="overview-main"><div className="overview-kicker">TODAY'S OPPORTUNITY INDEX</div><div className="overview-number">{tenders.length}</div><div className="overview-copy"><strong>件進行中標案</strong><span>已完成縣市判定，依業務優先級重新排序</span></div></div><div className="overview-stat"><span>今日來源公告</span><strong>{tenders.length}</strong><small>目前資料集案件量</small></div><div className="overview-stat"><span>可比歷史資料</span><strong>{tenders.filter((tender) => tender.history.length >= 2).length}</strong><small>具可比歷史資料</small></div><div className="overview-stat"><span>待人工確認</span><strong className="red-text">{tenders.filter((tender) => tender.confidence !== "高").length}</strong><small>資料需補查核</small></div></div><div className="workspace-toolbar"><div className="filter-intro"><Filter size={16} /><strong>案件檔案</strong><span>{filteredTenders.length} / {tenders.length} 顯示</span></div><div className="filter-tabs">{["全部案件", "3 日內", "待確認"].map((item) => <button key={item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{item}</button>)}</div><button className="outline-button"><Search size={15} /> 搜尋案件</button></div><div className="tender-list">{filteredTenders.map((tender) => <TenderCard key={tender.job} tender={tender} />)}</div></> : <div className="brand-layout"><aside className="brand-index-panel"><div className="index-heading"><span>BRAND INDEX</span><small>選擇比較對象</small></div>{brandDirectory.map((brand, index) => <a key={brand.id} className={`brand-index-item ${brand.loaded ? "selected" : "brand-index-muted"}`} href={brand.sourceUrl} target="_blank" rel="noreferrer"><span>{String(index + 1).padStart(2, "0")}</span><strong>{brand.name}</strong>{brand.loaded ? <Check size={14} /> : <small>待建檔</small>}</a>)}<div className="brand-index-tip"><BookOpen size={15} /><span>固定 RICOH 基準，已載入三個官方來源；其餘品牌先保留索引。</span></div></aside><div className="brand-main"><BrandMatrix /></div></div>}</main><footer className="page-footer"><span>互盛情報中樞 / INTERNAL BUSINESS INTELLIGENCE</span><span>品牌查核日期：{payload.checkedAt}</span></footer></div>;
}
