"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { AlertLevelBadge, LifecycleBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { compact, formatDateTime } from "@/lib/utils";
import type { LifecycleStatus, PageResponse, Waybill } from "@/lib/types";

const lifecycleOptions: Array<{ value: LifecycleStatus | "all"; label: string }> = [
  { value: "all", label: "全部状态" },
  { value: "created", label: "已创建" },
  { value: "waiting_monitor", label: "待监控" },
  { value: "monitoring", label: "监控中" },
  { value: "warehouse_received", label: "已入仓" },
  { value: "loaded", label: "已装机" },
  { value: "departed", label: "已起飞" },
  { value: "arrived", label: "已到达" },
  { value: "pickup_notified", label: "已通知提取" },
  { value: "picked_up", label: "已提取" },
  { value: "closed", label: "已结束" },
  { value: "voided", label: "已作废" }
];

export default function WaybillsPage() {
  const [data, setData] = useState<PageResponse<Waybill> | null>(null);
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

  useEffect(() => {
    load();
  }, [load]);

  function applyFilters() {
    setPage(1);
    load();
  }

  return (
    <>
      <PageHeader
        title="运单管理"
        description="录入、筛选、追踪航空头程运单"
        action={
          <Button asChild>
            <Link href="/waybills/new">
              <Plus className="h-4 w-4" />
              新建运单
            </Link>
          </Button>
        }
      />
      <Panel>
        <div className="mb-4 grid gap-2 lg:grid-cols-[1.2fr_0.8fr_0.8fr_1fr_180px_44px]">
          <Input placeholder="运单号" value={waybillNo} onChange={(event) => setWaybillNo(event.target.value)} />
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
              <TH>运单号</TH>
              <TH>航司</TH>
              <TH>航代</TH>
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
                <TD>{compact(item.carrier_code)}</TD>
                <TD>{compact(item.agent)}</TD>
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
