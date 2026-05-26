import type { WaybillPlan } from "@/lib/types";

const PLANNED_FLIGHT_INFO_RE = /^\s*([A-Za-z0-9]+)\s*[/_]\s*(\d{1,2})\s*$/;

export function purePlannedFlightNo(value?: string | null) {
  const cleaned = (value || "").trim();
  if (!cleaned) return "";
  const match = PLANNED_FLIGHT_INFO_RE.exec(cleaned);
  return (match?.[1] || cleaned).toUpperCase();
}

export function formatPlannedFlightInfo(plan?: WaybillPlan | null) {
  const flightNo = purePlannedFlightNo(plan?.planned_flight_no);
  if (!flightNo) return "";
  const day = plan?.planned_flight_date?.slice(8, 10);
  return day ? `${flightNo}/${day}` : flightNo;
}
