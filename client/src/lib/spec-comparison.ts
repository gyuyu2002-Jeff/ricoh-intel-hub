export type Comparison = 0 | 1 | 2;

const uncertain = /選配|選購|或|未列|未分|未另|等效|相當|至少|optional|not\b|equivalent|half.speed|at least/i;

export function compareNumbers(a: number | null | undefined, b: number | null | undefined): Comparison {
  if (a == null || b == null || !Number.isFinite(a) || !Number.isFinite(b) || a <= 0 || b <= 0) return 0;
  return a > b ? 1 : b > a ? 2 : 0;
}

function capacity(s = ""): number | null {
  if (uncertain.test(s)) return null;
  const values = Array.from(s.replace(/,/g, "").matchAll(/(\d+(?:\.\d+)?)\s*(TB|GB|MB)\b/gi))
    .map((m) => Number(m[1]) * (m[2].toUpperCase() === "TB" ? 1024 * 1024 : m[2].toUpperCase() === "GB" ? 1024 : 1));
  return values.length > 0 && new Set(values).size === 1 ? values[0] : null;
}

export function compareMemory(a?: string, b?: string): Comparison {
  return compareNumbers(capacity(a), capacity(b));
}

export function compareStorage(a = "", b = ""): Comparison {
  const mediaA = a.match(/\b(SSD|HDD|eMMC)\b/i)?.[1].toLowerCase();
  const mediaB = b.match(/\b(SSD|HDD|eMMC)\b/i)?.[1].toLowerCase();
  return mediaA && mediaA === mediaB ? compareNumbers(capacity(a), capacity(b)) : 0;
}

function quantity(s: string, pattern: RegExp): { value: number; unit: string; context: string } | null {
  const clean = s.replace(/,/g, "");
  const matches = Array.from(clean.matchAll(pattern));
  if (matches.length !== 1) return null;
  const match = matches[0];
  // A shared unit after a range or black/colour pair is not one measurement.
  if (/[\d./／–-]\s*$/.test(clean.slice(0, match.index))) return null;
  return {
    value: Number(match[1]),
    unit: match[0].slice(match[1].length).replace(/\s+/g, "").toLowerCase(),
    context: clean.replace(pattern, "#").replace(/[\s，,（）();；:：]/g, "").toLowerCase(),
  };
}

const scanUnit = /(\d+(?:\.\d+)?)\s*(?:ppm\b|ipm\b|張\s*\/\s*分|面\s*\/\s*分)/gi;

export function parseScanSpeed(s = "") {
  return quantity(s, scanUnit);
}

export function compareScanSpeeds(a = "", b = ""): Comparison {
  if (uncertain.test(a) || uncertain.test(b)) return 0;
  // Missing test conditions and multiple resolutions/configurations are not comparable.
  if (!/(?:\d\s*dpi\b|ISO\/IEC\s*17991)/i.test(a) || !/(?:\d\s*dpi\b|ISO\/IEC\s*17991)/i.test(b)) return 0;
  if (/\d\s*[/／]\s*\d+\s*dpi/i.test(a + b)) return 0;
  const left = parseScanSpeed(a);
  const right = parseScanSpeed(b);
  return left && right && left.unit === right.unit && left.context === right.context ? compareNumbers(left.value, right.value) : 0;
}

export function compareResolution(a = "", b = ""): Comparison {
  const pattern = /^(?:(?:最大|最高|up to)\s*)?(\d+)\s*[x×*]\s*(\d+)\s*dpi$/i;
  const left = a.replace(/,/g, "").trim().match(pattern);
  const right = b.replace(/,/g, "").trim().match(pattern);
  if (!left || !right) return 0;
  const [ax, ay, bx, by] = [left[1], left[2], right[1], right[2]].map(Number);
  if (Math.min(ax, ay, bx, by) <= 0) return 0;
  if (ax >= bx && ay >= by && (ax > bx || ay > by)) return 1;
  if (bx >= ax && by >= ay && (bx > ax || by > ay)) return 2;
  return 0;
}

export function compareTextQuantity(a = "", b = "", unit: "張" | "頁" | "秒"): Comparison {
  if (uncertain.test(a) || uncertain.test(b)) return 0;
  const pattern = new RegExp(`(\\d+(?:\\.\\d+)?)\\s*${unit}`, "g");
  const left = quantity(a, pattern);
  const right = quantity(b, pattern);
  if (!left || !right || left.context !== right.context || /\d/.test(left.context + right.context)) return 0;
  return unit === "秒" ? compareNumbers(right.value, left.value) : compareNumbers(left.value, right.value);
}
