import type { CargoBox } from "@/lib/types";
import { compact } from "@/lib/utils";

export function formatCbm(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function parseDimensions(value?: string | null) {
  if (!value) return null;
  const match = value.replace(/,/g, "").match(/(\d+(?:\.\d+)?)\s*(?:\*|x|X|×|脳)\s*(\d+(?:\.\d+)?)\s*(?:\*|x|X|×|脳)\s*(\d+(?:\.\d+)?)/);
  if (!match) return null;
  const dimensions = match.slice(1, 4).map(Number);
  return dimensions.every((item) => Number.isFinite(item) && item > 0) ? dimensions : null;
}

function formatDimension(value: number) {
  return String(Math.max(1, Math.round(value)));
}

export function formatCalculatedVolumeInfo(item: CargoBox) {
  const recalculation = isRecord(item.raw_data?.volume_recalculation) ? item.raw_data.volume_recalculation : null;
  const storedInfo = recalculation?.calculated_volume_info;
  if (typeof storedInfo === "string" && storedInfo.trim()) return storedInfo.trim();

  const dimensions = parseDimensions(item.original_volume_info);
  const volume = Number(item.volume);
  if (!dimensions || !Number.isFinite(volume) || volume <= 0) return formatCbm(item.volume);

  const originalVolume = (dimensions[0] * dimensions[1] * dimensions[2]) / 1_000_000;
  if (!Number.isFinite(originalVolume) || originalVolume <= 0) return formatCbm(item.volume);

  const scale = Math.cbrt(volume / originalVolume);
  const dimensionText = dimensions.map((value) => formatDimension(value * scale)).join("*");
  return `${dimensionText}(${formatCbm(item.volume)})`;
}
