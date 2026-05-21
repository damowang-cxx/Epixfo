"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { AlertLevelBadge, LifecycleBadge, LIFECYCLE_VARIANT, type LifecycleBadgeVariant } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { LIFECYCLE_ORDER, lifecycleLabels } from "@/lib/constants";
import { cn, compact, formatDateTime } from "@/lib/utils";
import type { LifecycleStatus, PageResponse, Waybill } from "@/lib/types";

const lifecycleOptions: Array<{ value: LifecycleStatus | "all"; label: string }> = [
  { value: "all", label: "全部状态" },
  ...LIFECYCLE_ORDER.map((status) => ({ value: status as LifecycleStatus, label: lifecycleLabels[status] }))
];

interface StatusCount {
  status: LifecycleStatus;
  count: number;
}

/** Status card 的背景 / 边框配色（-100 / -300 比 Badge 用的 -50 / -200 重一档，让卡片更醒目）。 */
const CARD_BG: Record<LifecycleBadgeVariant, string> = {
  default: "border-slate-200 bg-white hover:bg-slate-50",
  gray: "border-slate-300 bg-slate-100 hover:bg-slate-200",
  blue: "border-blue-300 bg-blue-100 hover:bg-blue-200",
  green: "border-emerald-300 bg-emerald-100 hover:bg-emerald-200",
  amber: "border-amber-300 bg-amber-100 hover:bg-amber-200",
  red: "border-red-300 bg-red-100 hover:bg-red-200",
  purple: "border-violet-300 bg-violet-100 hover:bg-violet-200",
  cyan: "border-cyan-300 bg-cyan-100 hover:bg-cyan-200",
  indigo: "border-indigo-300 bg-indigo-100 hover:bg-indigo-200",
  orange: "border-orange-300 bg-orange-100 hover:bg-orange-200",
  teal: "border-teal-300 bg-teal-100 hover:bg-teal-200",
  pink: "border-pink-300 bg-pink-100 hover:bg-pink-200"
};

function StatusCard({
  label,
  count,
  variant,
  active,
  onClick
}: {
  label: string;
  count: number;
  variant: LifecycleBadgeVariant;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "rounded-md border p-2 text-left transition",
        CARD_BG[variant],
        active && "ring-2 ring-purple-400"
      )}
    >
      <div className="text-xs text-slate-600">{label}</div>
      <div className="mt-0.5 text-xl font-semibold text-slate-900">{count}</div>
    </button>
  );
}

export default function WaybillsPage() {
  const [data, setData] = useState<PageResponse<Waybill> | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [waybillNo, setWaybillNo] = useState("");
  const [carrierCode, setCarrierCode] = useState("");
  const [destinationPort, setDestinationPort] = useState("");
  const [plannedFlightNo, setPlannedFlightNo] = useState("");
  const [lifecycleStatus, setLifecycleStatus] = useState<LifecycleStatus | "all">("all");
  const [page, setPage] = useState(1);

  const query = useMemo(() => {
    const params = new URLSearchParams({ page: String(page), page_size: "20" });
    if (waybillNo) params.set("waybill_no", waybillNo);
    if (carrierCode) params.set("carrier_code", carrierCode);
    if (destinationPort) params.set("destination_port", destinationPort);
    if (plannedFlightNo) params.set("planned_flight_no", plannedFlightNo);
    if (lifecycleStatus !== "all") params.set("lifecycle_status", lifecycleStatus);
    return params;
  }, [carrierCode, destinationPort, lifecycleStatus, page, plannedFlightNo, waybillNo]);

  const load = useCallback(() => {
    apiClient.get<PageResponse<Waybill>>(`/waybills?${query.toString()}`).then(setData);
  }, [query]);

  const loadCounts = useCallback(() => {
    apiClient
      .get<StatusCount[]>("/waybills/status-counts")
      .then((rows) => setCounts(Object.fromEntries(rows.map((r) => [r.status, r.count]))))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadCounts();
  }, [data, loadCounts]);

  const totalCount = useMemo(() => Object.values(counts).reduce((a, b) => a + b, 0), [counts]);

  function applyFilters() {
    setPage(1);
    load();
  }

  function selectStatus(status: LifecycleStatus | "all") {
    setLifecycleStatus(status);
    setPage(1);
  }

  return (
    <>
      <PageHeader
        title="提单管理"
        description="录入、筛选、追踪航空头程提单"
        action={
          <Button asChild>
            <Link href="/waybills/new">
              <Plus className="h-4 w-4" />
              新建提单
            </Link>
          </Button>
        }
      />
      <Panel title="状态总览">
        <div className="grid grid-cols-3 gap-1.5 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-6 xl:grid-cols-12">
          <StatusCard
            label="全部"
            count={totalCount}
            variant="default"
            active={lifecycleStatus === "all"}
            onClick={() => selectStatus("all")}
          />
          {LIFECYCLE_ORDER.map((status) => (
            <StatusCard
              key={status}
              label={lifecycleLabels[status]}
              count={counts[status] || 0}
              variant={LIFECYCLE_VARIANT[status]}
              active={lifecycleStatus === status}
              onClick={() => selectStatus(status as LifecycleStatus)}
            />
          ))}
        </div>
      </Panel>
      <Panel className="mt-4">
        <div className="mb-4 grid gap-2 lg:grid-cols-[1.2fr_0.8fr_0.8fr_1fr_180px_44px]">
          <Input placeholder="提单号" value={waybillNo} onChange={(event) => setWaybillNo(event.target.value)} />
          <Input placeholder="航司代码" value={carrierCode} onChange={(event) => setCarrierCode(event.target.value)} />
          <Input placeholder="目的港" value={destinationPort} onChange={(event) => setDestinationPort(event.target.value)} />
          <Input placeholder="计划航班" value={plannedFlightNo} onChange={(event) => setPlannedFlightNo(event.target.value)} />
          <Select value={lifecycleStatus} onValueChange={(value) => setLifecycleStatus(value as LifecycleStatus | "all")}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              {lifecycleOptions.map((item) => (
                <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="secondary" onClick={applyFilters} aria-label="搜索">
            <Search className="h-4 w-4" />
          </Button>
        </div>
        <Table>
          <THead>
            <TR>
              <TH>提单号</TH>
              <TH>航代</TH>
              <TH>始发港</TH>
              <TH>目的港</TH>
              <TH>计划航班</TH>
              <TH>生命周期</TH>
              <TH>异常</TH>
              <TH>下次查询</TH>
              <TH>操作</TH>
            </TR>
          </THead>
          <TBody>
            {(data?.items || []).map((item) => (
              <TR key={item.id}>
                <TD className="font-medium">{item.waybill_no}</TD>
                <TD>{compact(item.agent)}</TD>
                <TD>{compact(item.departure_port)}</TD>
                <TD>{compact(item.destination_port)}</TD>
                <TD>{compact(item.plan?.planned_flight_no)} / {compact(item.plan?.planned_flight_date)}</TD>
                <TD><LifecycleBadge value={item.lifecycle_status} /></TD>
                <TD><AlertLevelBadge value={item.alert_level} /></TD>
                <TD>{formatDateTime(item.next_query_at)}</TD>
                <TD><Button asChild variant="ghost" size="sm"><Link href={`/waybills/${item.id}`}>详情</Link></Button></TD>
              </TR>
            ))}
          </TBody>
        </Table>
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <span>共 {data?.total ?? 0} 条</span>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((prev) => prev - 1)}>上一页</Button>
            <Button variant="secondary" size="sm" disabled={!data || page * data.page_size >= data.total} onClick={() => setPage((prev) => prev + 1)}>下一页</Button>
          </div>
        </div>
      </Panel>
    </>
  );
}
