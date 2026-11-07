/*
 * Design system reminder: Neo-Editorial Swiss / business intelligence archive.
 * Keep the dossier spine, restrained paper palette, red index line, source-first
 * language, and calm motion. This page intentionally avoids tracking/copy flows.
 */
import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  BarChart3,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Database,
  ExternalLink,
  FileDown,
  Filter,
  MapPin,
  MoreHorizontal,
  Search,
  ShieldAlert,
  Sparkles,
  Target,
  X,
} from "lucide-react";

export type HistoryTrackItem = {
  index: number;
  date: string;
  month: string;
  winner: string;
  award_price: number;
  discount_rate: number | string;
  job_number?: string;
  title?: string;
  source_url?: string;
};

export type ForecastCurrentStatus = {
  status: "pending" | "solicitation" | "tender" | "awarded" | "failed";
  badge_label: string;
  stage: string;
  date: string;
  job_number: string;
  title: string;
  notice_url: string;
};

export type ForecastedTender = {
  id: string;
  unit_id: string;
  unit: string;
  city: string;
  series_title: string;
  predicted_title: string;
  latest_title: string;
  latest_job_number?: string;
  latest_source_url?: string;
  latest_award_date: string;
  latest_award_price: number;
  latest_award_price_str: string;
  latest_winner: string;
  predicted_date: string;
  predicted_month: string;
  predicted_range: string;
  days_until: number;
  countdown_label: string;
  cadence_months: number;
  cadence_summary: string;
  history_count: number;
  history_track: HistoryTrackItem[];
  current_status?: ForecastCurrentStatus;
};

type TenderPayload = {
  last_updated?: string;
  tenders?: RawTender[];
  review_candidates?: RawTender[];
  forecasted_tenders?: ForecastedTender[];
  collection_status?: {
    status?: string;
    latest_attempt_status?: string;
    latest_attempt_at?: string;
  };
};
type HistoryRow = [
  date: string,
  awardCode: string,
  rate: string,
  winner: string,
  sourceUrl?: string,
  title?: string,
  sourceUnit?: string,
  relationScope?: string
];
type Tender = {
  priority: string;
  priorityLabel: string;
  city: string;
  stage: string;
  stageTone: string;
  isAwarded: boolean;
  isActive: boolean;
  isDueSoon: boolean;
  category: string;
  awardPrice: string;
  awardDate?: string;
  countdown: string;
  title: string;
  job: string;
  unit: string;
  publish: string;
  deadline: string;
  budget: string;
  samples: string;
  currentWinner: string;
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
  stream?: "copier" | "peripherals";
  subType?: "main" | "supplies" | "printer" | "scanner";
};

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
  award_date?: string;
  winner?: string;
  tender_url?: string;
  stage?: string;
  stream?: "copier" | "peripherals";
  sub_type?: "main" | "supplies" | "printer" | "scanner";
  history_records?: Array<{
    award_date?: string;
    job_number?: string;
    award_price?: number;
    discount_rate?: number;
    winner?: string;
    relation_scope?: string;
    source_url?: string;
    title?: string;
    source_unit?: string;
  }>;
  relevance?: {
    category?: string;
    confidence?: string;
    score?: number;
    matched_terms?: string[];
    reason?: string;
    stream?: "copier" | "peripherals";
    sub_type?: "main" | "supplies" | "printer" | "scanner";
  };
};

function deadlineDays(deadline?: string, now = new Date()) {
  if (!deadline || !/^\d{4}-\d{2}-\d{2}$/.test(deadline)) return null;
  const today = new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Taipei", year: "numeric", month: "2-digit", day: "2-digit" }).format(now);
  const days = (Date.parse(`${deadline}T00:00:00+08:00`) - Date.parse(`${today}T00:00:00+08:00`)) / 86400000;
  return Number.isFinite(days) ? days : null;
}

export function isActiveTender(raw: Pick<RawTender, "stage" | "deadline">, now = new Date()) {
  if (!/^(正式開標|公開招標|招標公告)$|^公開徵求/.test(raw.stage ?? "")) return false;
  const days = deadlineDays(raw.deadline, now);
  return days === null || days >= 0;
}

export function isDueSoonTender(raw: Pick<RawTender, "stage" | "deadline" | "deadline_confidence">, now = new Date()) {
  const days = deadlineDays(raw.deadline, now);
  return isActiveTender(raw, now) && raw.deadline_confidence === "verified" && days !== null && days >= 0 && days <= 3;
}

export function parseTenderPayload(value: unknown): TenderPayload & { tenders: RawTender[]; review_candidates: RawTender[]; forecasted_tenders: ForecastedTender[] } {
  if (!value || typeof value !== "object" || Array.isArray(value)) throw new Error("Invalid tender data");
  const data = value as TenderPayload;
  const isRecord = (item: unknown) => !!item && typeof item === "object" && !Array.isArray(item);
  if (data.last_updated !== undefined && typeof data.last_updated !== "string") throw new Error("Invalid data timestamp");
  if (data.collection_status !== undefined && !isRecord(data.collection_status)) throw new Error("Invalid collection status");
  if (!Array.isArray(data.tenders) || !data.tenders.every(isRecord)) throw new Error("Invalid tender list");
  for (const key of ["review_candidates", "forecasted_tenders"] as const) {
    if (data[key] !== undefined && (!Array.isArray(data[key]) || !data[key]!.every(isRecord))) throw new Error(`Invalid ${key}`);
  }
  for (const raw of [...data.tenders, ...(data.review_candidates ?? [])]) {
    for (const key of ["city", "title", "unit", "job_number", "publish_date", "deadline", "stage", "winner", "tender_url"] as const) {
      if (raw[key] !== undefined && typeof raw[key] !== "string") throw new Error(`Invalid tender ${key}`);
    }
    if (raw.history_records !== undefined && (!Array.isArray(raw.history_records) || !raw.history_records.every(isRecord))) throw new Error("Invalid history records");
  }
  for (const forecast of data.forecasted_tenders ?? []) {
    if (![forecast.id, forecast.unit, forecast.latest_winner, forecast.predicted_date].every((field) => typeof field === "string") ||
      !Array.isArray(forecast.history_track) || !forecast.history_track.every(isRecord)) throw new Error("Invalid forecast");
  }
  return { ...data, tenders: data.tenders, review_candidates: data.review_candidates ?? [], forecasted_tenders: data.forecasted_tenders ?? [] };
}

export function getDataSyncStatus(data: TenderPayload, now = new Date()): "complete" | "warning" | "unknown" {
  const status = data.collection_status?.latest_attempt_status ?? data.collection_status?.status;
  if (!status) return "unknown";
  if (status !== "complete") return "warning";
  const times = [data.last_updated, data.collection_status?.latest_attempt_at];
  const timestamps = times.map((value) => value ? Date.parse(`${value.replace(" ", "T")}+08:00`) : NaN);
  if (timestamps.some((value) => !Number.isFinite(value))) return "unknown";
  return timestamps.some((value) => now.getTime() - value > 86400000 || value > now.getTime()) ? "warning" : "complete";
}

function formatDeadlineCountdown(deadline?: string) {
  const days = deadlineDays(deadline);
  if (days === null) return "截止日待確認";
  if (days < 0) return "已逾期";
  if (days === 0) return "今日截止";
  return `距截止 ${days} 天`;
}

export function mapRawTender(raw: RawTender, isReview = false): Tender {
  const sortedRecords = [...(raw.history_records ?? [])].sort((a, b) =>
    String(b.award_date ?? "").localeCompare(String(a.award_date ?? ""))
  );

  const sameUnitRecord = sortedRecords.find((r) => r.relation_scope === "same_unit");
  const primaryRecord = sameUnitRecord || sortedRecords[0];

  const history = sortedRecords.map((record) => [
    record.award_date ?? "待確認",
    record.job_number ?? "歷史案件",
    typeof record.discount_rate === "number" ? `${record.discount_rate}%` : "資料不足",
    record.winner ?? "待人工確認",
    record.source_url ?? "",
    record.title ?? "",
    record.source_unit ?? "",
    record.relation_scope ?? (record.source_unit === raw.unit ? "same_unit" : "same_parent_org"),
  ] as HistoryRow);
  
  const confidence = raw.relevance?.confidence === "high" ? "高" : raw.relevance?.confidence === "medium" ? "中" : "待確認";
  const priority = !isReview && isDueSoonTender(raw) ? "P1" : "P2";
  const stage = isReview ? "待確認" : raw.stage ?? "狀態待確認";
  const isAwarded = stage === "已決標";
  const currentWinner = raw.winner ?? (isAwarded ? "官方來源未列" : "待人工確認");
  const previousWinner = primaryRecord?.winner ?? (isAwarded ? "尚無可比前次紀錄" : "尚無歷史得標紀錄");
  const stageTone = isReview ? "stage-review" : isAwarded ? "stage-awarded" : stage.includes("無法決標") ? "stage-failed" : stage.includes("公開") ? "stage-amber" : stage.includes("評選") ? "stage-dark" : "stage-blue";
  
  const sameUnitCount = sortedRecords.filter((r) => r.relation_scope === "same_unit").length;
  const relatedCount = sortedRecords.filter((r) => r.relation_scope !== "same_unit").length;
  const comparable = sameUnitCount > 0
    ? `同機關 ${sameUnitCount} 筆${relatedCount > 0 ? ` · 同體系 ${relatedCount} 筆` : ""}`
    : sortedRecords.length > 0
    ? `近 5 年｜同體系 ${sortedRecords.length} 筆`
    : "目前無完整可比紀錄";

  const summary = isAwarded
    ? history.length > 0
      ? `本次由${currentWinner}得標；${sameUnitRecord ? `同機關前次得標廠商為${sameUnitRecord.winner}` : `同體系參考前次為${previousWinner}`}。`
      : `本次由${currentWinner}得標；目前尚無同機關可比的前次得標紀錄。`
    : sameUnitRecord
    ? `${raw.unit ?? "本案機關"}前次租賃案由${sameUnitRecord.winner}得標（折率 ${sameUnitRecord.discount_rate}%）；全案計 ${history.length} 筆可比紀錄。`
    : history.length > 0
    ? `${raw.unit ?? "本案機關"}尚無自身歷史，參考同體系 ${history.length} 筆資料，前次參考得標商為${previousWinner}。`
    : "目前尚無足夠歷史得標資料，先以公告規格與資格條件為主。";

  const next = stage.includes("公開")
    ? "請核對官方公告、規格附件與參與條件。"
    : "案件狀態、資格與日期以官方最新公告為準。";

  return {
    priority,
    priorityLabel: priority === "P1" ? "3 日內截止" : "公告追蹤",
    city: raw.city ?? "地點待確認",
    stage,
    stageTone,
    isAwarded,
    isActive: !isReview && isActiveTender(raw),
    isDueSoon: !isReview && isDueSoonTender(raw),
    category: raw.relevance?.category ?? "office_output_equipment",
    awardPrice: typeof raw.award_price === "number" ? `NT$ ${raw.award_price.toLocaleString("en-US")}` : raw.award_price ?? "未公開",
    awardDate: raw.award_date,
    countdown: isAwarded ? "已正式決標" : stage === "無法決標" ? "無法決標" : formatDeadlineCountdown(raw.deadline),
    title: raw.title ?? "未命名標案",
    job: raw.job_number ?? "待查",
    unit: raw.unit ?? "機關待確認",
    publish: raw.publish_date ?? "待確認",
    deadline: raw.deadline ?? "待確認",
    budget: typeof raw.budget === "number" ? `NT$ ${raw.budget.toLocaleString("en-US")}` : raw.budget ?? "無公開數據",
    samples: comparable,
    currentWinner,
    previousWinner,
    confidence,
    confidenceTone: confidence === "高" ? "confidence-high" : confidence === "中" ? "confidence-mid" : "confidence-low",
    isReview,
    deadlineConfidence: raw.deadline_confidence ?? "unknown",
    publishConfidence: raw.publish_date_confidence ?? "unknown",
    scope: sameUnitCount > 0 ? "同一機關" : history.length > 0 ? "同體系機關" : "尚無歷史範圍",
    summary,
    next,
    terms: raw.relevance?.category === "target_agency_procurement" ? ["機關專案採購"] : [],
    sourceUrl: raw.tender_url ?? "https://web.pcc.gov.tw/",
    history,
    stream: raw.stream || (raw.relevance?.stream as "copier" | "peripherals") || "copier",
    subType: raw.sub_type || (raw.relevance?.sub_type as "main" | "supplies" | "printer" | "scanner") || (raw.stream === "peripherals" ? "supplies" : "main"),
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
  const isSolicitation = tender.stage.includes("公開徵求") || tender.stage.includes("徵求");
  return (
    <article className={`tender-card ${tender.isAwarded ? "tender-card-awarded" : ""} ${tender.isReview ? "tender-card-review" : ""}`}>
      <div className="tender-status-bar">
        <div className="status-left">
          <Stamp tone={tender.priority === "P1" ? "stamp-red" : "stamp-ink"}>{tender.priority} · {tender.priorityLabel}</Stamp>
          <Stamp tone="stamp-sage">{tender.city}</Stamp>
          {tender.category === "target_agency_procurement" ? (
            <Stamp tone="stamp-blue">機關專案採購</Stamp>
          ) : tender.stream === "peripherals" ? (
            <Stamp tone="stamp-blue">
              {tender.subType === "supplies" ? "🖨️ 碳粉耗材" : tender.subType === "printer" ? "🖨️ 印表設備" : tender.subType === "scanner" ? "📄 文件掃描" : "周邊商機"}
            </Stamp>
          ) : (
            <Stamp tone="stamp-blue">🏢 影印機主機</Stamp>
          )}
          <Stamp tone={tender.stageTone}>{tender.isReview ? "待人工確認" : tender.isAwarded ? "✓ 已決標" : isSolicitation ? "📢 公開徵求" : tender.stage}</Stamp>
        </div>
        <div className={`countdown ${tender.priority === "P1" ? "countdown-hot" : ""}`}><Clock3 size={14} />{tender.countdown}</div>
      </div>
      {tender.isAwarded && (
        <div className="award-result-banner">
          <span className="award-result-mark">✓</span>
          <div>
            <strong>本案已決標</strong>
            <span>本次得標廠商：{tender.currentWinner} · 決標金額：{tender.awardPrice}</span>
          </div>
          <span className="award-result-label">RESULT</span>
        </div>
      )}
      {isSolicitation && (
        <div className="solicitation-banner">
          <span className="solicitation-mark">📢</span>
          <div>
            <strong>本案處於【公開徵求報價／企劃書】階段</strong>
            <span>招標前訪價與規格徵詢中 · 參與方式與期限請以官方公告為準</span>
          </div>
          <span className="solicitation-label">SOLICITATION</span>
        </div>
      )}
      <div className="tender-identity">
        <div>
          <div className="eyebrow">TENDER FILE <span>/</span> {tender.publish}</div>
          <h3>{tender.title}</h3>
          <div className="tender-meta"><span>{tender.unit}</span><span className="job-code">案號 {tender.job}</span></div>
        </div>
        <button className="icon-button" aria-label="更多案件操作"><MoreHorizontal size={18} /></button>
      </div>
      <div className={`metric-grid ${tender.isAwarded ? "" : "public-tender-metrics"}`}>
        {tender.isAwarded ? (
          <Metric
            label="決標日期"
            value={tender.awardDate || (tender.deadlineConfidence === "verified" ? `截標 ${tender.deadline}` : "已決標")}
            note={
              tender.awardDate && tender.deadline && tender.deadline !== "未公開" && tender.deadlineConfidence === "verified"
                ? `原截標日 ${tender.deadline}`
                : "官方決標公告"
            }
          />
        ) : (
          <Metric
            label="截止日"
            value={tender.deadline}
            note={`${tender.stage} · ${tender.deadlineConfidence === "verified" ? "官方日期" : tender.deadlineConfidence === "inferred" ? "日期推估" : "日期待確認"}`}
            alert={tender.priority === "P1"}
          />
        )}
        <Metric label={tender.isAwarded ? "決標金額" : "預算"} value={tender.isAwarded ? tender.awardPrice : tender.budget} note={tender.isAwarded ? "官方決標公告已提供" : tender.budget.includes("無") ? "附件／後續公告待確認" : "官方公告已提供"} />
        {tender.isAwarded ? <>
          <Metric label="本次得標廠商" value={tender.currentWinner} note="本次官方決標公告" />
          <Metric label="前次得標廠商" value={tender.previousWinner} note={latestHistory ? `${latestHistory[0]} · 案號 ${latestHistory[1]}` : "同機關尚無可比前次紀錄"} />
          <Metric label="前次決標" value={latestHistory ? latestHistory[0] : "尚無紀錄"} note={latestHistory ? `得標折率 ${latestHistory[2]}` : "未以本次得標者回填"} />
        </> : <>
          <Metric label="公開歷史紀錄" value={`${tender.history.length} 筆`} note={tender.samples} />
          <Metric
            label="前次得標廠商"
            value={tender.previousWinner}
            note={
              latestHistory
                ? `${(tender.history.find((r) => r[7] === "same_unit") || latestHistory)[0]} · ${(tender.history.find((r) => r[7] === "same_unit") || latestHistory)[2]} · ${(tender.history.find((r) => r[7] === "same_unit") || latestHistory)[7] === "same_unit" ? "同機關前次" : "同體系參考"}`
                : "尚無歷史得標紀錄"
            }
          />
        </>}
      </div>
      <div className="decision-strip">
        <div className="decision-main">
          <div className="decision-label"><Sparkles size={14} /> 判讀</div>
          <p>{tender.summary}</p>
          <div className="decision-action"><span>下一步</span>{tender.next}</div>
        </div>
        <div className="confidence-box">
          <div className="decision-label"><Database size={14} /> {tender.isReview ? "待確認原因" : tender.category === "target_agency_procurement" ? "公告分類" : "設備匹配信心"}</div>
          <div className="confidence-value"><span className={`confidence-dot ${tender.confidenceTone}`} />{tender.isReview ? "需人工核對" : tender.category === "target_agency_procurement" ? "機關專案採購" : tender.confidence}</div>
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
            {tender.history.length === 0 ? <div className="empty-history">尚無同機關可比的前次得標紀錄。</div> : tender.history.map((row) => {
              const isSameUnit = row[7] === "same_unit";
              const isPreviousWinner = row[3] === tender.previousWinner && isSameUnit;
              const unitClean = (row[6] || "").replace("海洋委員會", "").replace("股份有限公司", "");
              return (
                <div className={`history-row ${isSameUnit ? "history-row-same-unit" : "history-row-related"}`} key={`${row[1]}-${row[0]}`}>
                  <div className="history-col-date">
                    <span>{row[0]}</span>
                  </div>
                  <div className="history-col-job">
                    <strong>{row[1]}</strong>
                    {unitClean && <small className="history-unit-badge" title={row[6]}>{unitClean}</small>}
                  </div>
                  <div className="history-col-rate">
                    <span>{row[2]}</span>
                  </div>
                  <div className="history-col-winner">
                    <span className="history-winner-name">{row[3]}</span>
                    {row[5] && <small className="history-tender-title" title={row[5]}>{row[5]}</small>}
                  </div>
                  <div className="history-col-action">
                    {row[4] ? (
                      <a
                        href={row[4]}
                        target="_blank"
                        rel="noreferrer"
                        className="history-link"
                        title={`查看政府採購網官方決標原始公告 (${row[5] || row[1]})`}
                      >
                        原始決標 <ExternalLink size={11} />
                      </a>
                    ) : (
                      <span className="history-no-link">官方紀錄</span>
                    )}
                  </div>
                  <div className="history-col-stamp">
                    <Stamp tone={isPreviousWinner ? "stamp-red" : isSameUnit ? "stamp-blue" : "stamp-green"}>
                      {isPreviousWinner ? "同機關前次" : isSameUnit ? "同一機關" : "同體系參考"}
                    </Stamp>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="award-note">
            <span>判讀提示</span>
            {tender.isAwarded && <strong>本次得標廠商：{tender.currentWinner}</strong>}
            <strong>同機關前次得標：{tender.previousWinner}</strong>
            <em>{tender.isAwarded ? "本次與前次資料分列；無歷史紀錄時不以本次得標者回填。" : "歷史清單若含同主管機關其他分署之案件，已標註「同體系參考」以資區隔。"}</em>
          </div>
        </div>
      )}
    </article>
  );
}

// 動態即時計算預估倒數天數（依今日真實日期比對 target predicted_date，避免靜態寫死倒數凍結）
function recalcForecastDynamically(item: ForecastedTender): ForecastedTender {
  const days = deadlineDays(item.predicted_date);
  if (days === null) return { ...item, countdown_label: "推估日期待確認" };
  return { ...item, days_until: days, countdown_label: days < 0 ? "推估日期已過" : days === 0 ? "推估日期為今日" : `距推估日期 ${days} 天` };
}

function ForecastCard({ forecast }: { forecast: ForecastedTender }) {
  const [expanded, setExpanded] = useState(false);
  const isUrgent = forecast.days_until <= 30;
  const isOverdue = forecast.days_until < 0;

  const curStatus = forecast.current_status;
  const isSolicitation = curStatus?.status === "solicitation";
  const isTender = curStatus?.status === "tender";
  const isAwarded = curStatus?.status === "awarded";
  const isFailed = curStatus?.status === "failed";

  const pccSearchUrl = `https://web.pcc.gov.tw/prkms/tender/common/basic/indexTenderBasic?tenderName=${encodeURIComponent(forecast.series_title || forecast.unit)}`;

  return (
    <article className="forecast-card">
      <div className="tender-status-bar">
        <div className="status-left">
          <Stamp tone="stamp-sage">{forecast.city}</Stamp>
          {isSolicitation ? (
            <Stamp tone="stamp-red">🔥 公開徵求中（案號 {curStatus.job_number}）</Stamp>
          ) : isTender ? (
            <Stamp tone="stamp-blue">🎯 正式招標中（案號 {curStatus.job_number}）</Stamp>
          ) : isFailed ? (
            <Stamp tone="stage-failed">本期無法決標／已取消</Stamp>
          ) : isAwarded ? (
            <Stamp tone="stamp-green">✓ 已決標</Stamp>
          ) : (
            <Stamp tone={isOverdue ? "stamp-red" : isUrgent ? "stamp-amber" : "stamp-sage"}>
              {isOverdue ? "🚨 推估日期已過" : `⏳ 倒數 ${forecast.days_until} 天`}
            </Stamp>
          )}

        </div>
        <div className={`countdown ${isSolicitation || isTender || isUrgent ? "countdown-hot" : ""}`}>
          <Clock3 size={14} />
          <span>
            {isAwarded
              ? `✓ 本案已於 ${curStatus.date} 完成決標`
              : isFailed
              ? `本期公告狀態：${curStatus.stage}`
              : isTender
              ? `已確認公告 · ${curStatus.date}`
              : isSolicitation
              ? `🔥 機關已啟動 · ${curStatus.date} 公告`
              : `${forecast.countdown_label} · 預估 ${forecast.predicted_month}`}
          </span>
        </div>
      </div>

      {/* Closed-loop Active Notice Banner */}
      {isSolicitation && (
        <div className="solicitation-banner" style={{ margin: "14px 20px 0" }}>
          <span className="solicitation-mark">🔥</span>
          <div style={{ flex: 1 }}>
            <strong style={{ fontSize: "15px" }}>【本案機關已啟動招標前置：公開徵求廠商提供參考資料】</strong>
            <span style={{ fontSize: "13px", marginTop: "2px" }}>
              機關於 {curStatus.date} 發布最新公告「{curStatus.title}」（案號 {curStatus.job_number}）· 參與方式與期限請核對官方公告。
            </span>
          </div>
          {curStatus.notice_url && (
            <a
              href={curStatus.notice_url}
              target="_blank"
              rel="noopener noreferrer"
              className="action-primary"
              style={{ padding: "8px 14px", fontSize: "13px", whiteSpace: "nowrap", textDecoration: "none" }}
            >
              <ExternalLink size={14} /> 查看本案公開徵求公告 ↗
            </a>
          )}
        </div>
      )}

      {isTender && (
        <div className="solicitation-banner" style={{ margin: "14px 20px 0", borderColor: "#bfdbfe", background: "#eff6ff" }}>
          <span className="solicitation-mark">🎯</span>
          <div style={{ flex: 1 }}>
            <strong style={{ fontSize: "15px", color: "#1e40af" }}>【已確認本期招標公告】</strong>
            <span style={{ fontSize: "13px", color: "#1e3a8a", marginTop: "2px" }}>
              機關於 {curStatus.date} 公告「{curStatus.title}」（案號 {curStatus.job_number}）· 實際公告日與原推估區間分列，請以官方資訊為準。
            </span>
          </div>
          {curStatus.notice_url && (
            <a
              href={curStatus.notice_url}
              target="_blank"
              rel="noopener noreferrer"
              className="action-primary"
              style={{ padding: "8px 14px", fontSize: "13px", whiteSpace: "nowrap", textDecoration: "none" }}
            >
              <ExternalLink size={14} /> 查看官方招標公告 ↗
            </a>
          )}
        </div>
      )}

      <div className="tender-identity">
        <div>
          <div className="tender-meta">
            <span>發包機關：<strong>{forecast.unit}</strong></span>
            <span className="job-code">機關代碼 {forecast.unit_id}</span>
          </div>
          <h3 style={{ margin: "8px 0 6px", fontSize: "24px", lineHeight: "1.35", fontWeight: 700 }}>
            <span style={{ color: isSolicitation ? "#c2410c" : isTender ? "#2563eb" : "var(--deep)", fontWeight: 700, marginRight: "6px", fontSize: "20px" }}>
              {isSolicitation ? "【已啟動徵求】" : isTender ? "【已公告招標】" : isAwarded ? "【已決標】" : isFailed ? "【本期未決標】" : "【推估上架】"}
            </span>
            {curStatus?.status !== "pending" && curStatus?.title ? curStatus.title : forecast.predicted_title}
          </h3>
          <div style={{ fontSize: "14px", color: "#54645b", marginTop: "4px" }}>
            同機關同案名歷史依據：<strong>{forecast.latest_title}</strong>（累計 {forecast.history_count} 筆歷史紀錄）
          </div>
        </div>
      </div>

      <div className="metric-grid public-tender-metrics">
        <Metric
          label={curStatus?.date ? "本期公告日期" : "原始推估公告區間"}
          value={curStatus?.date || forecast.predicted_range}
          note={curStatus?.date ? `案號 ${curStatus.job_number} · ${curStatus.stage}` : "歷史推估，並非已確認合約到期日"}
          alert={isSolicitation || isUrgent}
        />
        <Metric
          label="定期換約週期"
          value={forecast.cadence_summary}
          note={`平均約期 ${forecast.cadence_months} 個月`}
        />
        <Metric
          label="前次決標總額"
          value={forecast.latest_award_price_str}
          note={`前次開標 ${forecast.latest_award_date}`}
        />
        <Metric
          label="前次得標廠商"
          value={forecast.latest_winner}
          note="歷史官方決標公告"
        />
      </div>

      {forecast.history_track && forecast.history_track.length > 0 && (
        <div className="cadence-track-container">
          <div className="cadence-track-title">
            <span>📋 歷史開標履歷軌跡（點擊各筆可直通該次官方決標公告）</span>
            <button
              type="button"
              className="outline-button"
              style={{ padding: "4px 10px", fontSize: "12px", height: "auto" }}
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "收起履歷" : `展開完整 ${forecast.history_track.length} 次開標履歷`}
            </button>
          </div>
          <div className="cadence-track-flow">
            {forecast.history_track.slice(expanded ? 0 : -3).map((h) => {
              const pillContent = (
                <>
                  <span>#{h.index}</span>
                  <strong>{h.month}</strong>
                  <span>{h.winner}</span>
                  <span style={{ color: "#617268", fontSize: "12px" }}>
                    ({typeof h.award_price === "number" ? `NT$${(h.award_price / 10000).toFixed(0)}萬` : h.award_price} · {h.discount_rate}%)
                  </span>
                  {h.source_url ? (
                    <ExternalLink size={12} className="cadence-arrow" style={{ opacity: 0.8 }} />
                  ) : (
                    <ChevronRight size={13} className="cadence-arrow" />
                  )}
                </>
              );
              return h.source_url ? (
                <a
                  key={h.index}
                  href={h.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="cadence-pill cadence-pill-link"
                  title={`點擊在新分頁查看政府採購網官方決標公告 (${forecast.unit} · ${h.date} · 得標商：${h.winner} · 案號 ${h.job_number || ""} · ${h.title || ""})`}
                >
                  {pillContent}
                </a>
              ) : (
                <span key={h.index} className="cadence-pill">
                  {pillContent}
                </span>
              );
            })}
            <span
              className={`cadence-pill ${isSolicitation ? "" : "predicted"}`}
              style={isSolicitation ? { background: "#fff7ed", borderColor: "#fed7aa", color: "#c2410c", fontWeight: 700 } : undefined}
            >
              <Sparkles size={13} />
              <span>{isSolicitation ? `🔥 本期已公開徵求：${curStatus.date}` : `原始推估：${forecast.predicted_month}`}</span>
              <span style={{ fontSize: "12px", opacity: 0.9 }}>（{curStatus?.date ? `本期公告 ${curStatus.date}` : forecast.countdown_label}）</span>
            </span>
          </div>
        </div>
      )}

      <div className="decision-strip"><p>原始推估區間：{forecast.predicted_range}。依 {forecast.history_count} 筆歷史紀錄與案名推估；尚未核實合約到期與擴充條款，不保證機關將於此期間公告。</p></div>

      <div className="tender-footer">
        <div className="term-list">
          <span>影印機定期租賃</span>
          <span>同機關履歷推估</span>
          <span>{forecast.cadence_summary}</span>
          {isSolicitation && <span style={{ color: "#c2410c", background: "#ffedd5", fontWeight: 700 }}>🔥 公開徵求中</span>}
        </div>
        <div className="action-row">
          {curStatus?.notice_url && (
            <a
              href={curStatus.notice_url}
              target="_blank"
              rel="noopener noreferrer"
              className="action-primary"
              title={`開啟政府採購網查看【${forecast.unit}】本期最新公告 (${curStatus.stage})`}
            >
              <ExternalLink size={13} /> 查看本期公告 ({curStatus.stage}) ↗
            </a>
          )}
          {forecast.latest_source_url && (
            <a
              href={forecast.latest_source_url}
              target="_blank"
              rel="noopener noreferrer"
              className={curStatus?.notice_url ? "action-secondary" : "action-primary"}
              title={`開啟政府採購網查看前次官方決標公告 (${forecast.unit} · ${forecast.latest_award_date} · 得標商：${forecast.latest_winner} · 案號 ${forecast.latest_job_number || ""})`}
            >
              <ExternalLink size={13} /> 查看前次官方決標 ({forecast.latest_winner.length > 6 ? forecast.latest_winner.slice(0, 6) + "…" : forecast.latest_winner}) ↗
            </a>
          )}
          <a
            href={pccSearchUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="action-secondary"
            title="開啟政府電子採購網查詢此系列相關標案"
          >
            查詢相關標案 ↗
          </a>
        </div>
      </div>
    </article>
  );
}

const TAIWAN_REGIONS: { region: string; cities: string[] }[] = [
  {
    region: "北部地區",
    cities: ["基隆市", "台北市", "新北市", "桃園市", "新竹市", "新竹縣", "宜蘭縣"],
  },
  {
    region: "中部地區",
    cities: ["苗栗縣", "台中市", "彰化縣", "南投縣", "雲林縣"],
  },
  {
    region: "南部地區",
    cities: ["嘉義市", "嘉義縣", "台南市", "高雄市", "屏東縣"],
  },
  {
    region: "東部與離島",
    cities: ["花蓮縣", "台東縣", "澎湖縣", "金門縣", "連江縣"],
  },
];

const ALL_TAIWAN_CITIES = TAIWAN_REGIONS.flatMap((r) => r.cities);
const PREFERENCES_KEY = "ricoh_public_preferences";

export function readCityPreference(storage: Pick<Storage, "getItem" | "removeItem">): string {
  storage.removeItem("ricoh_subscriber_info");
  storage.removeItem("SUBSCRIBERS_URL");
  try {
    const saved = JSON.parse(storage.getItem(PREFERENCES_KEY) ?? "null");
    return saved?.city === "全部縣市" || ALL_TAIWAN_CITIES.includes(saved?.city) ? saved.city : "全部縣市";
  } catch {
    return "全部縣市";
  }
}

function PreferencesModal({ isOpen, onClose, onSave }: { isOpen: boolean; onClose: () => void; onSave: (city: string) => void }) {
  const [city, setCity] = useState("全部縣市");
  const [error, setError] = useState("");
  useEffect(() => {
    if (!isOpen) return;
    setError("");
    try { setCity(readCityPreference(localStorage)); } catch { setCity("全部縣市"); }
  }, [isOpen]);
  return (
    <Dialog.Root open={isOpen} onOpenChange={(open) => { if (!open) onClose(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="preferences-backdrop" />
        <Dialog.Content className="subscribe-modal preferences-modal">
          <div className="modal-header">
            <div><Dialog.Title>本機篩選偏好</Dialog.Title><Dialog.Description>儲存在此瀏覽器，開啟網站時套用。此功能不會寄送電子郵件。</Dialog.Description></div>
            <Dialog.Close className="icon-button" aria-label="關閉"><X size={18} /></Dialog.Close>
          </div>
          <form className="subscribe-form" onSubmit={(event) => {
            event.preventDefault();
            try {
              localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ city }));
              onSave(city);
              onClose();
            } catch { setError("瀏覽器未允許儲存偏好，請直接使用頁面上的縣市篩選。"); }
          }}>
            <label className="form-group" htmlFor="preferred-city">預設縣市
              <select id="preferred-city" className="subscribe-input" value={city} onChange={(event) => setCity(event.target.value)}>
                <option value="全部縣市">全部縣市</option>
                {ALL_TAIWAN_CITIES.map((name) => <option key={name} value={name}>{name}</option>)}
              </select>
            </label>
            {error && <p role="alert">{error}</p>}
            <div className="action-row">
              <button type="button" className="outline-button" onClick={() => {
                try { localStorage.removeItem(PREFERENCES_KEY); setCity("全部縣市"); onSave("全部縣市"); } catch { setError("無法清除儲存資料。"); }
              }}>清除偏好</button>
              <button className="action-primary" type="submit">儲存並套用</button>
            </div>
          </form>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function PaginationControl({
  currentPage,
  totalPages,
  totalCount,
  pageSize,
  onPageChange,
  itemLabel = "案件",
}: {
  currentPage: number;
  totalPages: number;
  totalCount: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  itemLabel?: string;
}) {
  if (totalCount === 0 || totalPages <= 1) {
    if (totalCount > 0) {
      return (
        <div className="pagination-wrapper single-page">
          <span className="pagination-info">
            顯示全部 <strong>{totalCount}</strong> 筆{itemLabel}（共 1 頁）
          </span>
        </div>
      );
    }
    return null;
  }

  const startItem = (currentPage - 1) * pageSize + 1;
  const endItem = Math.min(currentPage * pageSize, totalCount);

  const pageNumbers: (number | string)[] = [];
  if (totalPages <= 7) {
    for (let i = 1; i <= totalPages; i++) pageNumbers.push(i);
  } else {
    pageNumbers.push(1);
    if (currentPage > 3) pageNumbers.push("...");
    const start = Math.max(2, currentPage - 1);
    const end = Math.min(totalPages - 1, currentPage + 1);
    for (let i = start; i <= end; i++) pageNumbers.push(i);
    if (currentPage < totalPages - 2) pageNumbers.push("...");
    pageNumbers.push(totalPages);
  }

  return (
    <nav className="pagination-wrapper" aria-label="案件分頁導航">
      <div className="pagination-info">
        顯示第 <strong>{startItem} - {endItem}</strong> 筆，共 <strong>{totalCount}</strong> 筆{itemLabel}
      </div>

      <div className="pagination-buttons">
        <button
          type="button"
          className="pagination-nav-btn prev-btn"
          disabled={currentPage <= 1}
          onClick={() => onPageChange(currentPage - 1)}
          aria-label="前往上一頁"
        >
          <ChevronLeft size={18} />
          <span>上一頁</span>
        </button>

        <div className="pagination-numbers">
          {pageNumbers.map((p, idx) =>
            typeof p === "number" ? (
              <button
                key={p}
                type="button"
                className={`pagination-num-btn ${currentPage === p ? "active" : ""}`}
                onClick={() => onPageChange(p)}
                aria-current={currentPage === p ? "page" : undefined}
                aria-label={`前往第 ${p} 頁`}
              >
                {p}
              </button>
            ) : (
              <span key={`dots-${idx}`} className="pagination-ellipsis">…</span>
            )
          )}
        </div>

        <button
          type="button"
          className="pagination-nav-btn next-btn"
          disabled={currentPage >= totalPages}
          onClick={() => onPageChange(currentPage + 1)}
          aria-label="前往下一頁"
        >
          <span>下一頁</span>
          <ChevronRight size={18} />
        </button>
      </div>

      <div className="pagination-page-badge">
        第 <strong>{currentPage}</strong> / {totalPages} 頁
      </div>
    </nav>
  );
}

function MiniPager({
  currentPage,
  totalPages,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <div className="mini-pager" role="navigation" aria-label="快速翻頁">
      <button
        type="button"
        className="mini-pager-btn"
        disabled={currentPage <= 1}
        onClick={() => onPageChange(currentPage - 1)}
        title="上一頁"
        aria-label="上一頁"
      >
        <ChevronLeft size={16} />
      </button>
      <span className="mini-pager-text">
        <strong>{currentPage}</strong> / {totalPages} 頁
      </span>
      <button
        type="button"
        className="mini-pager-btn"
        disabled={currentPage >= totalPages}
        onClick={() => onPageChange(currentPage + 1)}
        title="下一頁"
        aria-label="下一頁"
      >
        <ChevronRight size={16} />
      </button>
    </div>
  );
}

export default function Home({ stream = "copier" }: { stream?: "copier" | "forecast" | "peripherals" }) {
  const isForecast = stream === "forecast" || stream === "peripherals";
  const [filter, setFilter] = useState("全部案件");
  const [cityFilter, setCityFilter] = useState("全部縣市");
  const [peripheralFilter, setPeripheralFilter] = useState<"all" | "supplies" | "printer" | "scanner">("all");
  const [forecastDaysFilter, setForecastDaysFilter] = useState<"all" | "30" | "60" | "90" | "180">("all");
  const [forecastStatusFilter, setForecastStatusFilter] = useState<"all" | "tender" | "solicitation" | "awarded" | "failed" | "pending">("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [subscribeOpen, setSubscribeOpen] = useState(false);
  const [unsubscribeNotice, setUnsubscribeNotice] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [tenders, setTenders] = useState<Tender[]>([]);
  const [reviewTenders, setReviewTenders] = useState<Tender[]>([]);
  const [forecastedTenders, setForecastedTenders] = useState<ForecastedTender[]>([]);
  const [dataUpdated, setDataUpdated] = useState("待確認");
  const [dataSyncStatus, setDataSyncStatus] = useState<"loading" | "complete" | "warning" | "unknown">("loading");
  const [dataSyncAttempt, setDataSyncAttempt] = useState("");

  useEffect(() => {
    setPeripheralFilter("all");
    try { setCityFilter(readCityPreference(localStorage)); } catch { setCityFilter("全部縣市"); }
    setFilter("全部案件");
    setForecastDaysFilter("all");
    setForecastStatusFilter("all");
    setSearchQuery("");
  }, [stream]);

  useEffect(() => {
    const url = new URL(window.location.href);
    if (url.searchParams.get("action") === "unsubscribe") {
      setUnsubscribeNotice(true);
      url.searchParams.delete("action");
      url.searchParams.delete("email");
      window.history.replaceState(null, "", `${url.pathname}${url.search}${url.hash}`);
    }
  }, []);

  const streamTenders = useMemo(() => {
    return tenders.filter((t) => stream === "peripherals" ? t.stream === "peripherals" : t.stream !== "peripherals");
  }, [tenders, stream]);

  const streamReviewTenders = useMemo(() => {
    return reviewTenders.filter((t) => stream === "peripherals" ? t.stream === "peripherals" : t.stream !== "peripherals");
  }, [reviewTenders, stream]);

  const peripheralCounts = useMemo(() => {
    if (stream !== "peripherals") return { all: 0, supplies: 0, printer: 0, scanner: 0 };
    return {
      all: streamTenders.length,
      supplies: streamTenders.filter((t) => t.subType === "supplies").length,
      printer: streamTenders.filter((t) => t.subType === "printer").length,
      scanner: streamTenders.filter((t) => t.subType === "scanner").length,
    };
  }, [stream, streamTenders]);

  const cityOptions = useMemo(() => {
    const counts = new Map<string, number>();
    streamTenders.forEach(({ city }) => counts.set(city, (counts.get(city) ?? 0) + 1));
    return Array.from(counts.entries()).sort(([cityA, countA], [cityB, countB]) => countB - countA || cityA.localeCompare(cityB, "zh-Hant"));
  }, [streamTenders]);

  const forecastCityOptions = useMemo(() => {
    const counts = new Map<string, number>();
    forecastedTenders.forEach(({ city }) => counts.set(city, (counts.get(city) ?? 0) + 1));
    return Array.from(counts.entries()).sort(([cityA, countA], [cityB, countB]) => countB - countA || cityA.localeCompare(cityB, "zh-Hant"));
  }, [forecastedTenders]);

  const matchesSearch = (tender: Tender, query: string) => {
    const normalized = query.trim().toLocaleLowerCase("zh-Hant");
    if (!normalized) return true;
    return [tender.title, tender.unit, tender.job, tender.city, tender.stage, tender.currentWinner, tender.previousWinner, ...tender.terms].join(" ").toLocaleLowerCase("zh-Hant").includes(normalized);
  };

  const filteredTenders = useMemo(() => {
    let next = streamTenders;
    if (stream === "peripherals" && peripheralFilter !== "all") {
      next = next.filter((tender) => tender.subType === peripheralFilter);
    }
    if (filter === "進行中") next = next.filter((tender) => tender.isActive);
    if (filter === "3 日內") next = next.filter((tender) => tender.isDueSoon);
    if (filter === "其他狀態") next = next.filter((tender) => !tender.isActive && !tender.isAwarded);
    if (filter === "已決標") next = next.filter((tender) => tender.isAwarded);
    if (cityFilter !== "全部縣市") next = next.filter((tender) => tender.city === cityFilter);
    return next.filter((tender) => matchesSearch(tender, searchQuery));
  }, [cityFilter, filter, peripheralFilter, searchQuery, stream, streamTenders]);

  const filteredReviewTenders = useMemo(() => {
    let next = streamReviewTenders;
    if (stream === "peripherals" && peripheralFilter !== "all") {
      next = next.filter((tender) => tender.subType === peripheralFilter);
    }
    const byCity = cityFilter === "全部縣市" ? next : next.filter((tender) => tender.city === cityFilter);
    return byCity.filter((tender) => matchesSearch(tender, searchQuery));
  }, [cityFilter, peripheralFilter, searchQuery, stream, streamReviewTenders]);

  const filteredForecasts = useMemo(() => {
    return forecastedTenders.filter((fc) => {
      if (forecastDaysFilter !== "all" && fc.days_until < 0) return false;
      if (forecastDaysFilter === "30" && fc.days_until > 30) return false;
      if (forecastDaysFilter === "60" && fc.days_until > 60) return false;
      if (forecastDaysFilter === "90" && fc.days_until > 90) return false;
      if (forecastDaysFilter === "180" && fc.days_until > 180) return false;



      if (forecastStatusFilter === "tender" && fc.current_status?.status !== "tender") return false;
      if (forecastStatusFilter === "solicitation" && fc.current_status?.status !== "solicitation") return false;
      if (forecastStatusFilter === "awarded" && fc.current_status?.status !== "awarded") return false;
      if (forecastStatusFilter === "failed" && fc.current_status?.status !== "failed") return false;
      if (forecastStatusFilter === "pending" && fc.current_status?.status && fc.current_status.status !== "pending") return false;

      if (cityFilter !== "全部縣市" && fc.city !== cityFilter) return false;

      if (searchQuery.trim()) {
        const q = searchQuery.trim().toLowerCase();
        const text = [
          fc.predicted_title,
          fc.latest_title,
          fc.latest_job_number || "",
          fc.current_status?.title || "",
          fc.current_status?.job_number || "",
          fc.unit,
          fc.city,
          fc.latest_winner,
        ].join(" ").toLowerCase();
        if (!text.includes(q)) return false;
      }

      return true;
    });
  }, [forecastedTenders, forecastDaysFilter, forecastStatusFilter, cityFilter, searchQuery]);

  const FORECAST_PAGE_SIZE = 4;
  const TENDER_PAGE_SIZE = 4;

  const [forecastPage, setForecastPage] = useState(1);
  const [tenderPage, setTenderPage] = useState(1);

  useEffect(() => {
    setForecastPage(1);
  }, [stream, forecastDaysFilter, forecastStatusFilter, cityFilter, searchQuery]);

  useEffect(() => {
    setTenderPage(1);
  }, [stream, filter, cityFilter, peripheralFilter, searchQuery]);

  const totalForecastPages = Math.max(1, Math.ceil(filteredForecasts.length / FORECAST_PAGE_SIZE));
  const validForecastPage = Math.min(forecastPage, totalForecastPages);
  const paginatedForecasts = useMemo(() => {
    const start = (validForecastPage - 1) * FORECAST_PAGE_SIZE;
    return filteredForecasts.slice(start, start + FORECAST_PAGE_SIZE);
  }, [filteredForecasts, validForecastPage]);

  const totalTenderPages = Math.max(1, Math.ceil(filteredTenders.length / TENDER_PAGE_SIZE));
  const validTenderPage = Math.min(tenderPage, totalTenderPages);
  const paginatedTenders = useMemo(() => {
    const start = (validTenderPage - 1) * TENDER_PAGE_SIZE;
    return filteredTenders.slice(start, start + TENDER_PAGE_SIZE);
  }, [filteredTenders, validTenderPage]);

  const handleForecastPageChange = (newPage: number) => {
    const target = Math.max(1, Math.min(newPage, totalForecastPages));
    setForecastPage(target);
    const el = document.getElementById("forecast-tenders-heading");
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  const handleTenderPageChange = (newPage: number) => {
    const target = Math.max(1, Math.min(newPage, totalTenderPages));
    setTenderPage(target);
    const el = document.getElementById("formal-tenders-heading");
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  };

  useEffect(() => {
    let active = true;
    const dataUrl = new URL(`data.json?_t=${Date.now()}`, document.baseURI).toString();
    fetch(dataUrl, { cache: "no-store" })
      .then((response) => response.ok ? response.json() as Promise<TenderPayload> : Promise.reject(new Error("data.json unavailable")))
      .then((value) => {
        if (!active) return;
        const data = parseTenderPayload(value);
        const nextTenders = data.tenders.map((raw) => mapRawTender(raw));
        const nextReviews = data.review_candidates.map((raw) => mapRawTender(raw, true));
        const nextForecasts = data.forecasted_tenders.map(recalcForecastDynamically);
        setTenders(nextTenders);
        setReviewTenders(nextReviews);
        setForecastedTenders(nextForecasts);
        setLoadError(false);
        setDataUpdated(data.last_updated ?? "待確認");
        setDataSyncAttempt(data.collection_status?.latest_attempt_at ?? "");
        setDataSyncStatus(getDataSyncStatus(data));
      })
      .catch(() => {
        if (!active) return;
        setTenders([]);
        setReviewTenders([]);
        setForecastedTenders([]);
        setLoadError(true);
        setDataUpdated("待確認");
        setDataSyncStatus("unknown");
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);
  if (loading) return <div className="app-shell loading-shell"><header className="topbar"><div className="brand-lockup"><Mark /><div><div className="brand-title">互盛情報中樞</div><div className="brand-subtitle">PUBLIC PROCUREMENT INFORMATION <span>/</span> 互盛情報中樞</div></div></div><span className="loading-top-note"><span className="loading-pulse" /> 讀取來源索引</span></header><main className="page-container"><SectionSkeleton /></main></div>;
  const dataUpdateTitle = `資料快照產生時間：${dataUpdated}。${dataSyncAttempt ? `最近抓取嘗試：${dataSyncAttempt}。` : "抓取狀態未提供。"}${dataSyncStatus === "warning" ? "最近抓取未完整成功，或快照已超過 24 小時；資料可能不完整，請核對官方公告。" : "快照時間不代表所有公告皆已完整抓取。"}`;
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand-lockup">
          <Mark />
          <div>
            <div className="brand-title">互盛情報中樞</div>
            <div className="brand-subtitle">PUBLIC PROCUREMENT INFORMATION <span>/</span> 互盛情報中樞</div>
          </div>
        </div>
        <div className="topbar-actions">
          <span className={`live-indicator ${dataSyncStatus === "warning" ? "data-update-warning" : ""}`} title={dataUpdateTitle}>
            <span /> {dataSyncStatus === "complete" ? "已更新" : "待確認"}<em>快照 {dataUpdated}</em>
          </span>
        </div>
      </header>
      <nav className="site-tabs" aria-label="網站主要分頁">
        <a className={`site-tab ${stream === "copier" ? "active" : ""}`} href="#" aria-current={stream === "copier" ? "page" : undefined}>
          <span className="site-tab-index">01</span>
          <span><strong>影印機案件監控</strong><small>事務機／複合機主機</small></span>
        </a>
        <a className={`site-tab ${isForecast ? "active" : ""}`} href="#/forecast" aria-current={isForecast ? "page" : undefined}>
          <span className="site-tab-index">02</span>
          <span><strong>未來半年到期預測</strong><small>涵蓋即日起半年內到期換約案件</small></span>
        </a>
        <a className="site-tab" href="#/specs">
          <span className="site-tab-index">03</span>
          <span><strong>設備規格比較平台</strong><small>7廠牌 20~60 張規格比較</small></span>
        </a>
      </nav>
      <main className="page-container">
        {unsubscribeNotice && (
          <div className="data-status-notice" role="status">
            <strong>尚未完成退訂</strong>
            <p>公開網站無法變更寄信名單。請回覆原通知信或聯繫寄件者，要求停止寄送；網址中的信箱資訊已移除。</p>
            <button className="outline-button" onClick={() => setUnsubscribeNotice(false)}>關閉</button>
          </div>
        )}
        {loadError && <div className="data-status-notice" role="alert"><strong>資料載入失敗</strong><p>目前無法取得有效的公告資料。請稍後重新整理，或直接查看政府電子採購網。</p></div>}
        {!loadError && dataSyncStatus !== "complete" && <div className="data-status-notice" role="status"><strong>{dataSyncStatus === "warning" ? "資料同步需注意" : "資料時效待確認"}</strong><p>{dataUpdateTitle}</p></div>}

        {isForecast ? (
          <>
            <div className="page-heading">
              <div>
                <div className="eyebrow">
                  互盛情報中樞 / 未來半年到期換約預測雷達
                </div>
                <div className="page-heading-title-row">
                  <h1>未來半年到期換約預測雷達</h1>
                  <button
                    type="button"
                    className="primary-subscribe-btn"
                    onClick={() => setSubscribeOpen(true)}
                  >
                    <Filter size={18} /> 本機篩選偏好
                  </button>
                </div>
                <p>
                  以歷史決標日期與案名推估未來半年可能公告的案件，並分列已找到的本期公告。推估不是已核實的合約到期日，也不保證重新招標。
                </p>
              </div>
              <div className="heading-actions">
                <button type="button" className="outline-button" onClick={() => window.print()}><FileDown size={15} /> 列印工作區</button>
              </div>
            </div>

            <div className="tender-overview">
              <div className="overview-main">
                <div className="overview-kicker">6-MONTH FORECAST RADAR</div>
                <div className="overview-number">{forecastedTenders.length}</div>
                <div className="overview-copy">
                  <strong>件推估即將到期／上架案件</strong>
                  <span>對照公開歷史紀錄與最新公告，推估區間僅供查詢參考</span>
                </div>
              </div>
              <div className="overview-stat">
                <span>已公告招標</span>
                <strong>{forecastedTenders.filter((f) => f.current_status?.status === "tender").length}</strong>
                <small>已找到本期公告</small>
              </div>
              <div className="overview-stat">
                <span>已決標</span>
                <strong>{forecastedTenders.filter((f) => f.current_status?.status === "awarded").length}</strong>
                <small>以正式決標結果為準</small>
              </div>
              <div className="overview-stat" style={{ borderLeftColor: "#d97706" }}>
                <span>⏳ 30 日內推估</span>
                <strong style={{ color: "#d97706" }}>
                  {forecastedTenders.filter((f) => f.days_until >= 0 && f.days_until <= 30).length}
                </strong>
                <small>未來 30 日內推估日期</small>
              </div>
              <div className="overview-stat" style={{ borderLeftColor: "#ea580c" }}>
                <span>🔥 已啟動公開徵求</span>
                <strong style={{ color: "#ea580c" }}>
                  {forecastedTenders.filter((f) => f.current_status?.status === "solicitation").length}
                </strong>
                <small>已找到公開徵求公告</small>
              </div>

            </div>

            <div className="forecast-filter-bar" aria-label="推估條件篩選">
              <div className="forecast-filter-group">
                <span className="forecast-filter-label">
                  <Database size={14} /> 招標進度：
                </span>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastStatusFilter === "all" ? "active" : ""}`}
                  onClick={() => setForecastStatusFilter("all")}
                >
                  全部 ({forecastedTenders.length})
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastStatusFilter === "tender" ? "active" : ""}`}
                  onClick={() => setForecastStatusFilter("tender")}
                >
                  🎯 正式招標中 ({forecastedTenders.filter((f) => f.current_status?.status === "tender").length})
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastStatusFilter === "solicitation" ? "active" : ""}`}
                  onClick={() => setForecastStatusFilter("solicitation")}
                >
                  🔥 公開徵求中 ({forecastedTenders.filter((f) => f.current_status?.status === "solicitation").length})
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastStatusFilter === "awarded" ? "active" : ""}`}
                  onClick={() => setForecastStatusFilter("awarded")}
                >
                  ✓ 已決標 ({forecastedTenders.filter((f) => f.current_status?.status === "awarded").length})
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastStatusFilter === "failed" ? "active" : ""}`}
                  onClick={() => setForecastStatusFilter("failed")}
                >
                  無法決標／已取消 ({forecastedTenders.filter((f) => f.current_status?.status === "failed").length})
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastStatusFilter === "pending" ? "active" : ""}`}
                  onClick={() => setForecastStatusFilter("pending")}
                >
                  ⏳ 尚未公告推估中 ({forecastedTenders.filter((f) => !f.current_status?.status || f.current_status.status === "pending").length})
                </button>
              </div>

              <div className="forecast-filter-group">
                <span className="forecast-filter-label">
                  <Clock3 size={14} /> 時效倒數：
                </span>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastDaysFilter === "all" ? "active" : ""}`}
                  onClick={() => setForecastDaysFilter("all")}
                >
                  全部
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastDaysFilter === "30" ? "active" : ""}`}
                  onClick={() => setForecastDaysFilter("30")}
                >
                  ⏳ 30 日內 ({forecastedTenders.filter((f) => f.days_until >= 0 && f.days_until <= 30).length})
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastDaysFilter === "60" ? "active" : ""}`}
                  onClick={() => setForecastDaysFilter("60")}
                >
                  60 日內 ({forecastedTenders.filter((f) => f.days_until >= 0 && f.days_until <= 60).length})
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastDaysFilter === "90" ? "active" : ""}`}
                  onClick={() => setForecastDaysFilter("90")}
                >
                  90 日內 ({forecastedTenders.filter((f) => f.days_until >= 0 && f.days_until <= 90).length})
                </button>
                <button
                  type="button"
                  className={`peripheral-pill ${forecastDaysFilter === "180" ? "active" : ""}`}
                  onClick={() => setForecastDaysFilter("180")}
                >
                  半年內 ({forecastedTenders.filter((f) => f.days_until >= 0 && f.days_until <= 180).length})
                </button>
              </div>

            </div>

            <div className="city-quick-filter" aria-label="縣市快速選擇">
              <div className="city-filter-heading">
                <div className="city-filter-title">
                  <MapPin size={17} />
                  <div><strong>縣市快速選擇</strong><span>依機關所在縣市篩選推估案件</span></div>
                </div>
                <div className="city-filter-meta">
                  <span>{cityFilter === "全部縣市" ? "全台案件" : cityFilter}</span>
                  <small>{filteredForecasts.length} 件符合目前條件</small>
                </div>
              </div>
              <div className="city-pill-list" role="group" aria-label="推估標案縣市">
                <button
                  type="button"
                  aria-pressed={cityFilter === "全部縣市"}
                  className={cityFilter === "全部縣市" ? "city-pill active" : "city-pill"}
                  onClick={() => setCityFilter("全部縣市")}
                >
                  <span>全部縣市</span>
                  <strong>{forecastedTenders.length}</strong>
                </button>
                {forecastCityOptions.map(([city, count]) => (
                  <button
                    type="button"
                    aria-pressed={cityFilter === city}
                    className={cityFilter === city ? "city-pill active" : "city-pill"}
                    key={city}
                    onClick={() => setCityFilter(city)}
                  >
                    <span>{city}</span>
                    <strong>{count}</strong>
                  </button>
                ))}
              </div>
            </div>

            <div className="workspace-toolbar">
              <div className="filter-intro">
                <Filter size={16} /><strong>推估上架案件</strong>
                <span>{filteredForecasts.length} / {forecastedTenders.length} 顯示{searchQuery ? ` · 搜尋「${searchQuery}」` : ""}</span>
              </div>
              <MiniPager
                currentPage={validForecastPage}
                totalPages={totalForecastPages}
                onPageChange={handleForecastPageChange}
              />
              <label className="tender-search" htmlFor="tender-search" style={{ marginLeft: "auto" }}>
                <Search size={15} />
                <input
                  id="tender-search"
                  type="search"
                  value={searchQuery}
                  onChange={(event) => setSearchQuery(event.target.value)}
                  placeholder="搜尋機關、案名、得標廠商或關鍵字"
                  aria-label="搜尋推估標案"
                />
                {searchQuery && (
                  <button type="button" className="search-clear" onClick={() => setSearchQuery("")} aria-label="清除搜尋">×</button>
                )}
              </label>
            </div>

            <section className="tender-section formal-section" aria-labelledby="forecast-tenders-heading">
              <div className="tender-section-heading">
                <div>
                  <span className="section-kicker">PREDICTED COPIER OPPORTUNITIES</span>
                  <h2 id="forecast-tenders-heading">未來半年到期換約案件清單</h2>
                  <p>依推估日期排序；已公告案件另列實際公告日。合約期限與採購方式仍須核對官方文件。</p>
                </div>
                <strong>{filteredForecasts.length} 件{totalForecastPages > 1 ? `（第 ${validForecastPage} / ${totalForecastPages} 頁）` : ""}</strong>
              </div>
              <div key={`forecast-page-${validForecastPage}`} className="tender-list page-flip-animate">
                {paginatedForecasts.length > 0 ? (
                  paginatedForecasts.map((forecast) => (
                    <ForecastCard key={forecast.id} forecast={forecast} />
                  ))
                ) : (
                  <div className="empty-state">目前沒有符合條件的推估案件。</div>
                )}
              </div>
              <PaginationControl
                currentPage={validForecastPage}
                totalPages={totalForecastPages}
                totalCount={filteredForecasts.length}
                pageSize={FORECAST_PAGE_SIZE}
                onPageChange={handleForecastPageChange}
                itemLabel="推估案件"
              />
            </section>
          </>
        ) : (
          <>
            <div className="page-heading">
              <div>
                <div className="eyebrow">互盛情報中樞 / 影印機案件</div>
                <div className="page-heading-title-row">
                  <h1>影印機案件監控雷達</h1>
                  <button
                    type="button"
                    className="primary-subscribe-btn"
                    onClick={() => setSubscribeOpen(true)}
                  >
                    <Filter size={18} /> 本機篩選偏好
                  </button>
                </div>
                <p>先看今天該追的案，再回頭核對前次得標紀錄。</p>
              </div>
              <div className="heading-actions">
                <button type="button" className="outline-button" onClick={() => window.print()}><FileDown size={15} /> 列印工作區</button>
              </div>
            </div>

            <div className="tender-overview">
              <div className="overview-main">
                <div className="overview-kicker">TODAY'S OPPORTUNITY INDEX</div>
                <div className="overview-number">{streamTenders.filter((t) => t.isActive).length}</div>
                <div className="overview-copy">
                  <strong>件進行中標案</strong>
                  <span>可參與公告，已排除決標、無法決標與已逾期案件</span>
                </div>
              </div>
              <div
                className={`overview-stat overview-awarded ${filter === "已決標" ? "active" : ""}`}
                style={{ cursor: "pointer", transition: "all 0.2s" }}
                onClick={() => setFilter(filter === "已決標" ? "全部案件" : "已決標")}
                title="點擊切換查看已決標案件"
              >
                <span>已決標案件</span>
                <strong>{streamTenders.filter((tender) => tender.isAwarded).length}</strong>
                <small>{filter === "已決標" ? "✓ 篩選中（點擊還原）" : "點擊篩選近期結果"}</small>
              </div>
              <div className="overview-stat">
                <span>資料集公告</span>
                <strong>{streamTenders.length}</strong>
                <small>目前資料集案件量</small>
              </div>
              <div className="overview-stat">
                <span>可比歷史資料</span>
                <strong>{streamTenders.filter((tender) => tender.history.length >= 2).length}</strong>
                <small>具可比歷史資料</small>
              </div>
              <div className="overview-stat overview-review">
                <span>待人工確認</span>
                <strong className="red-text">{streamReviewTenders.length}</strong>
                <small>不列入正式案件</small>
              </div>
            </div>

            <div className="city-quick-filter" aria-label="縣市快速選擇">
              <div className="city-filter-heading">
                <div className="city-filter-title">
                  <MapPin size={17} />
                  <div><strong>縣市快速選擇</strong><span>先按地區縮小案件範圍，再搭配案件狀態篩選</span></div>
                </div>
                <div className="city-filter-meta">
                  <span>{cityFilter === "全部縣市" ? "全台案件" : cityFilter}</span>
                  <small>{filteredTenders.length + filteredReviewTenders.length} 件符合目前條件</small>
                </div>
              </div>
              <div className="city-pill-list" role="group" aria-label="標案縣市">
                <button type="button" aria-pressed={cityFilter === "全部縣市"} className={cityFilter === "全部縣市" ? "city-pill active" : "city-pill"} onClick={() => setCityFilter("全部縣市")}><span>全部縣市</span><strong>{streamTenders.length}</strong></button>
                {cityOptions.map(([city, count]) => (
                  <button type="button" aria-pressed={cityFilter === city} className={cityFilter === city ? "city-pill active" : "city-pill"} key={city} onClick={() => setCityFilter(city)}>
                    <span>{city}</span><strong>{count}</strong>
                  </button>
                ))}
              </div>
            </div>

            <div className="workspace-toolbar">
              <div className="filter-intro">
                <Filter size={16} /><strong>案件檔案</strong><span>{filteredTenders.length} / {streamTenders.length} 顯示{searchQuery ? ` · 搜尋「${searchQuery}」` : ""}</span>
              </div>
              <div className="filter-tabs">
                {[
                  { label: "全部案件", count: streamTenders.length },
                  { label: "進行中", count: streamTenders.filter((t) => t.isActive).length },
                  { label: "3 日內", count: streamTenders.filter((t) => t.isDueSoon).length },
                  { label: "已決標", count: streamTenders.filter((t) => t.isAwarded).length },
                  { label: "其他狀態", count: streamTenders.filter((t) => !t.isActive && !t.isAwarded).length },
                ].map(({ label, count }) => (
                  <button
                    key={label}
                    className={filter === label ? "active" : ""}
                    onClick={() => setFilter(label)}
                  >
                    {label} ({count})
                  </button>
                ))}
              </div>
              <MiniPager
                currentPage={validTenderPage}
                totalPages={totalTenderPages}
                onPageChange={handleTenderPageChange}
              />
              <label className="tender-search" htmlFor="tender-search">
                <Search size={15} />
                <input id="tender-search" type="search" value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="搜尋案名、機關、案號或關鍵字" aria-label="搜尋標案" />
                {searchQuery && <button type="button" className="search-clear" onClick={() => setSearchQuery("")} aria-label="清除搜尋">×</button>}
              </label>
            </div>

            <section className="tender-section formal-section" aria-labelledby="formal-tenders-heading">
              <div className="tender-section-heading">
                <div><span className="section-kicker">FORMAL OPPORTUNITIES</span><h2 id="formal-tenders-heading">正式案件</h2><p>設備案件與機關專案採購分別標示，請搭配公告狀態篩選。</p></div>
                <strong>{filteredTenders.length} 件{totalTenderPages > 1 ? `（第 ${validTenderPage} / ${totalTenderPages} 頁）` : ""}</strong>
              </div>
              <div key={`tender-page-${validTenderPage}`} className="tender-list page-flip-animate">
                {paginatedTenders.length > 0 ? paginatedTenders.map((tender) => <TenderCard key={tender.job} tender={tender} />) : <div className="empty-state">目前沒有符合條件的正式案件。</div>}
              </div>
              <PaginationControl
                currentPage={validTenderPage}
                totalPages={totalTenderPages}
                totalCount={filteredTenders.length}
                pageSize={TENDER_PAGE_SIZE}
                onPageChange={handleTenderPageChange}
                itemLabel="正式案件"
              />
            </section>

            <section className="tender-section review-section" aria-labelledby="review-tenders-heading">
              <div className="tender-section-heading">
                <div><span className="section-kicker">REVIEW QUEUE</span><h2 id="review-tenders-heading">待確認案件</h2><p>可能相關但明細不足或設備範圍不明，需人工核對後才會進入正式案件。</p></div>
                <strong>{filteredReviewTenders.length} 件</strong>
              </div>
              <div className="tender-list">
                {filteredReviewTenders.length > 0 ? filteredReviewTenders.map((tender) => <TenderCard key={`review-${tender.job}`} tender={tender} />) : <div className="empty-state">目前沒有待確認案件。</div>}
              </div>
            </section>
          </>
        )}
      </main>
      <footer className="page-footer">
        <span>互盛情報中樞 / PUBLIC PROCUREMENT INFORMATION</span>
        <span>資料查核與同步：官方採購公告</span>
      </footer>
      <PreferencesModal isOpen={subscribeOpen} onClose={() => setSubscribeOpen(false)} onSave={setCityFilter} />
    </div>
  );
}
