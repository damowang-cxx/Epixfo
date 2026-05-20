import { Badge } from "@/components/ui/badge";
import { alertLevelLabels, lifecycleLabels } from "@/lib/constants";

export function LifecycleBadge({ value }: { value?: string | null }) {
  const variant =
    value === "voided" || value === "closed"
      ? "gray"
      : value === "picked_up" || value === "warehouse_received"
        ? "green"
        : value === "departed" || value === "arrived"
          ? "blue"
          : value === "pickup_notified"
            ? "purple"
            : "default";
  return <Badge variant={variant}>{lifecycleLabels[value || ""] || value || "-"}</Badge>;
}

export function AlertLevelBadge({ value }: { value?: string | null }) {
  if (!value) return <Badge variant="gray">无异常</Badge>;
  const variant = value === "critical" ? "red" : value === "warning" ? "amber" : "blue";
  return <Badge variant={variant}>{alertLevelLabels[value] || value}</Badge>;
}
