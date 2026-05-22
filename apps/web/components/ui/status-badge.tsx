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

/** `picked_up` 视为提单终结态，使用灰色；`voided` 使用橙色表示作废。 */
export const LIFECYCLE_VARIANT: Record<string, LifecycleBadgeVariant> = {
  created: "red",
  waiting_monitor: "cyan",
  monitoring: "amber",
  warehouse_received: "indigo",
  loaded: "green",
  departed: "purple",
  arrived: "teal",
  pickup_notified: "pink",
  picked_up: "gray",
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
