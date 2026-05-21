import { Badge } from "@/components/ui/badge";
import { alertLevelLabels, lifecycleLabels } from "@/lib/constants";

export type LifecycleBadgeVariant =
  | "default"
  | "blue"
  | "green"
  | "amber"
  | "red"
  | "purple"
  | "gray"
  | "cyan"
  | "indigo"
  | "orange"
  | "teal"
  | "pink";

/**
 * 11 个生命周期状态色相分布：每相邻状态色相跨度足够大，整体避免任何两个紧邻状态出现同色系。
 *
 *   created(红)       → waiting_monitor(青)  → monitoring(琥珀)     → warehouse_received(靛蓝紫)
 *   → loaded(绿)      → departed(紫)         → arrived(青绿)        → pickup_notified(粉)
 *   → picked_up(蓝)   → closed(灰，归档)     → voided(橙，作废)
 *
 * `closed` / `voided` 由用户指定（灰 / 橙），其他 9 个状态各占独立色系。
 */
export const LIFECYCLE_VARIANT: Record<string, LifecycleBadgeVariant> = {
  created: "red",
  waiting_monitor: "cyan",
  monitoring: "amber",
  warehouse_received: "indigo",
  loaded: "green",
  departed: "purple",
  arrived: "teal",
  pickup_notified: "pink",
  picked_up: "blue",
  closed: "gray",
  voided: "orange"
};

export function LifecycleBadge({ value }: { value?: string | null }) {
  const variant = LIFECYCLE_VARIANT[value ?? ""] ?? "default";
  return <Badge variant={variant}>{lifecycleLabels[value || ""] || value || "-"}</Badge>;
}

export function AlertLevelBadge({ value }: { value?: string | null }) {
  if (!value) return <Badge variant="gray">无异常</Badge>;
  const variant = value === "critical" ? "red" : value === "warning" ? "amber" : "blue";
  return <Badge variant={variant}>{alertLevelLabels[value] || value}</Badge>;
}
