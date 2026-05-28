import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDateTime(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(date);
}

export function formatDate(value?: string | null) {
  if (!value) return "-";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit"
  }).format(date);
}

function parseLocalDate(value: string) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day);
  if (date.getFullYear() !== year || date.getMonth() !== month - 1 || date.getDate() !== day) return null;
  return date;
}

export function formatOutboundDate(value?: string | null) {
  if (!value) return "";
  const date = parseLocalDate(value);
  if (!date) return value;
  const todaySource = new Date();
  const today = new Date(todaySource.getFullYear(), todaySource.getMonth(), todaySource.getDate());
  const diffDays = Math.round((date.getTime() - today.getTime()) / 86_400_000);
  const day = String(date.getDate()).padStart(2, "0");
  if (diffDays >= 0 && diffDays <= 7) {
    const weekdays = ["周日", "周一", "周二", "周三", "周四", "周五", "周六"];
    return `${weekdays[date.getDay()]}（${day}）`;
  }
  return `${String(date.getMonth() + 1).padStart(2, "0")}/${day}`;
}

export function compact(value: unknown) {
  if (value === null || value === undefined || value === "") return "-";
  return String(value);
}

/**
 * 计算重量 / 体积 比例，最多保留 9 位小数（四舍五入），尾随 0 不显示。
 * 任一输入为空或非数字、或体积为 0 时返回 null（调用方应该展示 "-" 或隐藏字段）。
 *
 * 示例：
 *   computeRatio(1041, 4.03) → "258.300248139"
 *   computeRatio(100, 2)     → "50"
 *   computeRatio(100, 8)     → "12.5"
 */
export function computeRatio(weight: unknown, volume: unknown): string | null {
  if (weight === null || weight === undefined || weight === "") return null;
  if (volume === null || volume === undefined || volume === "") return null;
  const w = Number(weight);
  const v = Number(volume);
  if (!Number.isFinite(w) || !Number.isFinite(v) || v === 0) return null;
  const ratio = w / v;
  if (!Number.isFinite(ratio)) return null;
  // toFixed(9) 内部即四舍五入；之后去掉末尾的 0 和孤立的小数点
  return ratio.toFixed(9).replace(/\.?0+$/, "");
}
