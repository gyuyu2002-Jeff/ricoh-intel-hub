/*
 * Design system reminder: Neo-Editorial Swiss / business intelligence archive.
 * Keep the dossier spine, restrained paper palette, red index line, source-first
 * language, and calm motion. This page intentionally avoids tracking/copy flows.
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  BarChart3,
  ChevronDown,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  FileDown,
  Filter,
  MapPin,
  MoreHorizontal,
  Search,
  Sparkles,
} from "lucide-react";

type TenderPayload = {
  last_updated?: string;
  tenders?: RawTender[];
  review_candidates?: RawTender[];
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
  isReview?: boolean;
  deadlineConfidence?: string;
  publishConfidence?: string;
  scope: string;
  summary: string;
  next: string;
  terms: string[];
  sourceUrl: string;
  history: HistoryRow[];
};

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
  publish_date_confidence?: "verified" | "inferred" | "unknown" | string;
  deadline?: string;
  deadline_confidence?: "verified" | "inferred" | "unknown" | string;
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
  relevance?: { confidence?: string; score?: number; matched_terms?: string[]; reason?: string };
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

function mapRawTender(raw: RawTender, isReview = false): Tender {
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
  const stage = isReview ? "待確認" : raw.stage ?? "狀態待確認";
  const isAwarded = stage === "已決標";
  const stageTone = isReview ? "stage-review" : isAwarded ? "stage-awarded" : stage.includes("無法決標") ? "stage-failed" : stage.includes("公開") ? "stage-amber" : stage.includes("評選") ? "stage-dark" : "stage-blue";
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
    isReview,
    deadlineConfidence: raw.deadline_confidence ?? "unknown",
    publishConfidence: raw.publish_date_confidence ?? "unknown",
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

function SectionSkeleton() {
  return (
    <div className="loading-panel" aria-live="polite" aria-busy="true">
      <div className="loading-kicker">
        <span className="loading-pulse" /> {"載入標案情報與歷史紀錄"}
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
    <article className={`tender-card ${tender.isAwarded ? "tender-card-awarded" : ""} ${tender.isReview ? "tender-card-review" : ""}`}>
      <div className="tender-status-bar">
        <div className="status-left">
          <Stamp tone={tender.priority === "P1" ? "stamp-red" : "stamp-ink"}>{tender.priority} · {tender.priorityLabel}</Stamp>
          <Stamp tone="stamp-sage">{tender.city}</Stamp>
          <Stamp tone={tender.stageTone}>{tender.isReview ? "待人工確認" : tender.isAwarded ? "✓ 已決標" : tender.stage}</Stamp>
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
        <Metric label="截止日" value={tender.deadline} note={`${tender.stage} · ${tender.deadlineConfidence === "verified" ? "官方日期" : tender.deadlineConfidence === "inferred" ? "日期推估" : "日期待確認"}`} alert={tender.priority === "P1"} />
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
          <div className="decision-label"><Database size={14} /> {tender.isReview ? "待確認原因" : "資料可信度"}</div>
          <div className="confidence-value"><span className={`confidence-dot ${tender.confidenceTone}`} />{tender.isReview ? "需人工核對" : tender.confidence}</div>
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

export default function Home() {
  const [filter, setFilter] = useState("全部案件");
  const [cityFilter, setCityFilter] = useState("全部縣市");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [tenders, setTenders] = useState<Tender[]>(fallbackTenders);
  const [reviewTenders, setReviewTenders] = useState<Tender[]>([]);
  const [dataUpdated, setDataUpdated] = useState("待確認");
  const [dataSyncStatus, setDataSyncStatus] = useState<"loading" | "complete" | "warning" | "unknown">("loading");
  const [dataSyncAttempt, setDataSyncAttempt] = useState("");
  const cityOptions = useMemo(() => {
    const counts = new Map<string, number>();
    tenders.forEach(({ city }) => counts.set(city, (counts.get(city) ?? 0) + 1));
    return Array.from(counts.entries()).sort(([cityA, countA], [cityB, countB]) => countB - countA || cityA.localeCompare(cityB, "zh-Hant"));
  }, [tenders]);
  const matchesSearch = (tender: Tender, query: string) => {
    const normalized = query.trim().toLocaleLowerCase("zh-Hant");
    if (!normalized) return true;
    return [tender.title, tender.unit, tender.job, tender.city, tender.stage, tender.competitor, ...tender.terms].join(" ").toLocaleLowerCase("zh-Hant").includes(normalized);
  };
  const filteredTenders = useMemo(() => {
    let next = tenders;
    if (filter === "3 日內") next = next.filter((tender) => tender.priority === "P1");
    if (cityFilter !== "全部縣市") next = next.filter((tender) => tender.city === cityFilter);
    return next.filter((tender) => matchesSearch(tender, searchQuery));
  }, [cityFilter, filter, searchQuery, tenders]);
  const filteredReviewTenders = useMemo(() => {
    const byCity = cityFilter === "全部縣市" ? reviewTenders : reviewTenders.filter((tender) => tender.city === cityFilter);
    return byCity.filter((tender) => matchesSearch(tender, searchQuery));
  }, [cityFilter, reviewTenders, searchQuery]);
  useEffect(() => {
    let active = true;
    const dataUrl = new URL("data.json", document.baseURI).toString();
    fetch(dataUrl, { cache: "no-store" })
      .then((response) => response.ok ? response.json() as Promise<TenderPayload> : Promise.reject(new Error("data.json unavailable")))
      .then((data) => {
        if (!active) return;
        if (Array.isArray(data.tenders) && data.tenders.length > 0) setTenders(data.tenders.map((raw) => mapRawTender(raw)));
        if (Array.isArray(data.review_candidates)) setReviewTenders(data.review_candidates.map((raw) => mapRawTender(raw, true)));
        if (data.last_updated) setDataUpdated(data.last_updated);
        const latestStatus = data.collection_status?.latest_attempt_status ?? data.collection_status?.status;
        setDataSyncAttempt(data.collection_status?.latest_attempt_at ?? "");
        setDataSyncStatus(data.last_updated ? latestStatus && latestStatus !== "complete" ? "warning" : "complete" : "unknown");
      })
      .catch(() => { if (active) { setDataUpdated("待確認"); setDataSyncStatus("unknown"); } })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  if (loading) return <div className="app-shell loading-shell"><header className="topbar"><div className="brand-lockup"><Mark /><div><div className="brand-title">互盛情報中樞</div><div className="brand-subtitle">INTERNAL BUSINESS INTELLIGENCE <span>/</span> 桃園業務情報</div></div></div><span className="loading-top-note"><span className="loading-pulse" /> 讀取來源索引</span></header><main className="page-container"><SectionSkeleton /></main></div>;
  const dataUpdateCopy = dataSyncStatus === "warning" ? `最後成功更新：${dataUpdated}` : `資料更新：${dataUpdated}`;
  const dataUpdateTitle = dataSyncStatus === "warning" && dataSyncAttempt ? `最近一次同步嘗試：${dataSyncAttempt}；目前顯示最後成功更新資料。` : "標案資料集最後成功同步時間";
  return <div className="app-shell"><header className="topbar"><div className="brand-lockup"><Mark /><div><div className="brand-title">互盛情報中樞</div><div className="brand-subtitle">INTERNAL BUSINESS INTELLIGENCE <span>/</span> 桃園業務情報</div></div></div><div className="topbar-actions"><a className="topbar-route" href="#/specs">規格比較</a><span className={`live-indicator ${dataSyncStatus === "warning" ? "data-update-warning" : ""}`} title={dataUpdateTitle}><span /> LIVE <em>{dataSyncStatus === "warning" ? `最後成功 ${dataUpdated}` : `資料更新 ${dataUpdated}`}</em></span><button className="icon-button" aria-label="列印工作區"><FileDown size={17} /></button></div></header><nav className="site-tabs" aria-label="網站主要分頁"><a className="site-tab active" href="#" aria-current="page"><span className="site-tab-index">01</span><span><strong>標案監控</strong><small>即時案件與縣市篩選</small></span></a><a className="site-tab" href="#/specs"><span className="site-tab-index">02</span><span><strong>規格比較</strong><small>七品牌硬規格工作檯</small></span></a></nav><main className="page-container"><div className="page-heading"><div><div className="eyebrow">互盛情報中樞 <span>/</span> 2026.08.14</div><h1>標案情報監控雷達</h1><p>先看今天該追的案，再回頭核對前次得標紀錄。</p></div><div className="heading-actions"><span className={`update-note ${dataSyncStatus === "warning" ? "data-update-warning" : ""}`} title={dataUpdateTitle}><Database size={14} /><time>{dataUpdateCopy}</time></span><a className="outline-button" href="#/specs">進入規格比較</a><button className="outline-button"><FileDown size={15} /> 列印工作區</button></div></div><div className="tender-overview"><div className="overview-main"><div className="overview-kicker">TODAY'S OPPORTUNITY INDEX</div><div className="overview-number">{tenders.length}</div><div className="overview-copy"><strong>件進行中標案</strong><span>已完成縣市判定，依業務優先級重新排序</span></div></div><div className="overview-stat overview-awarded"><span>已決標案件</span><strong>{tenders.filter((tender) => tender.isAwarded).length}</strong><small>近期結果醒目追蹤</small></div><div className="overview-stat"><span>今日來源公告</span><strong>{tenders.length}</strong><small>目前資料集案件量</small></div><div className="overview-stat"><span>可比歷史資料</span><strong>{tenders.filter((tender) => tender.history.length >= 2).length}</strong><small>具可比歷史資料</small></div><div className="overview-stat overview-review"><span>待人工確認</span><strong className="red-text">{reviewTenders.length}</strong><small>不列入正式案件</small></div></div><div className="city-quick-filter" aria-label="縣市快速選擇"><div className="city-filter-heading"><div className="city-filter-title"><MapPin size={17} /><div><strong>縣市快速選擇</strong><span>先按地區縮小案件範圍，再搭配案件狀態篩選</span></div></div><div className="city-filter-meta"><span>{cityFilter === "全部縣市" ? "全台案件" : cityFilter}</span><small>{filteredTenders.length + filteredReviewTenders.length} 件符合目前條件</small></div></div><div className="city-pill-list" role="group" aria-label="標案縣市"><button type="button" aria-pressed={cityFilter === "全部縣市"} className={cityFilter === "全部縣市" ? "city-pill active" : "city-pill"} onClick={() => setCityFilter("全部縣市")}><span>全部縣市</span><strong>{tenders.length}</strong></button>{cityOptions.map(([city, count]) => <button type="button" aria-pressed={cityFilter === city} className={cityFilter === city ? "city-pill active" : "city-pill"} key={city} onClick={() => setCityFilter(city)}><span>{city}</span><strong>{count}</strong></button>)}</div></div><div className="workspace-toolbar"><div className="filter-intro"><Filter size={16} /><strong>案件檔案</strong><span>{filteredTenders.length} / {tenders.length} 顯示{searchQuery ? ` · 搜尋「${searchQuery}」` : ""}</span></div><div className="filter-tabs">{["全部案件", "3 日內"].map((item) => <button key={item} className={filter === item ? "active" : ""} onClick={() => setFilter(item)}>{item}</button>)}</div><label className="tender-search" htmlFor="tender-search"><Search size={15} /><input id="tender-search" type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="搜尋案名、機關、案號或關鍵字" aria-label="搜尋標案" />{searchQuery && <button type="button" className="search-clear" onClick={() => setSearchQuery("")} aria-label="清除搜尋">×</button>}</label></div><section className="tender-section formal-section" aria-labelledby="formal-tenders-heading"><div className="tender-section-heading"><div><span className="section-kicker">FORMAL OPPORTUNITIES</span><h2 id="formal-tenders-heading">正式案件</h2><p>已確認為目標設備，且符合首頁日期與狀態保留規則。</p></div><strong>{filteredTenders.length} 件</strong></div><div className="tender-list">{filteredTenders.length > 0 ? filteredTenders.map((tender) => <TenderCard key={tender.job} tender={tender} />) : <div className="empty-state">目前沒有符合條件的正式案件。</div>}</div></section><section className="tender-section review-section" aria-labelledby="review-tenders-heading"><div className="tender-section-heading"><div><span className="section-kicker">REVIEW QUEUE</span><h2 id="review-tenders-heading">待確認案件</h2><p>可能相關但明細不足或設備範圍不明，需人工核對後才會進入正式案件。</p></div><strong>{filteredReviewTenders.length} 件</strong></div><div className="tender-list">{filteredReviewTenders.length > 0 ? filteredReviewTenders.map((tender) => <TenderCard key={`review-${tender.job}`} tender={tender} />) : <div className="empty-state">目前沒有待確認案件。</div>}</div></section></main><footer className="page-footer"><span>互盛情報中樞 / INTERNAL BUSINESS INTELLIGENCE</span><span>資料查核與同步：官方採購公告</span></footer></div>;
}
