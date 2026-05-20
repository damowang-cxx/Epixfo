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
