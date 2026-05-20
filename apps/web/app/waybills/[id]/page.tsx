"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Ban, Pencil, Play } from "lucide-react";
import { AlertLevelBadge, LifecycleBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { WaybillForm } from "@/components/waybills/waybill-form";
import { useAuth } from "@/components/layout/auth-provider";
import { apiClient } from "@/lib/client-api";
import { compact, computeRatio, formatDateTime } from "@/lib/utils";
import { lifecycleLabels } from "@/lib/constants";
import type {
  Alert,
  AssemblyEvent,
  LifecycleStatus,
  OfficialFlightSegment,
  OfficialInfo,
  QuerySnapshot,
  StatusEvent,
  Waybill
} from "@/lib/types";

const statusOptions: LifecycleStatus[] = [
  "created",
  "waiting_monitor",
  "monitoring",
  "warehouse_received",
  "loaded",
  "departed",
  "arrived",
  "pickup_notified",
  "picked_up",
  "closed",
  "voided"
];

function FieldGrid({ items }: { items: Array<[string, unknown]> }) {
  return (
    <div className="grid gap-3 text-sm md:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label} className="rounded-md border border-slate-100 p-3">
          <div className="text-xs text-slate-500">{label}</div>
          <div className="mt-1 font-medium text-slate-800">{compact(value)}</div>
        </div>
      ))}
    </div>
  );
}

export default function WaybillDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const { hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const [waybill, setWaybill] = useState<Waybill | null>(null);
  const [officialInfo, setOfficialInfo] = useState<OfficialInfo | null>(null);
  const [segments, setSegments] = useState<OfficialFlightSegment[]>([]);
  const [events, setEvents] = useState<StatusEvent[]>([]);
  const [assemblies, setAssemblies] = useState<AssemblyEvent[]>([]);
  const [snapshots, setSnapshots] = useState<QuerySnapshot[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [manualStatus, setManualStatus] = useState<LifecycleStatus>("created");
  const [message, setMessage] = useState("");

  const load = useCallback(() => {
    if (!id) return;
    apiClient.get<Waybill>(`/waybills/${id}`).then((data) => {
      setWaybill(data);
      setManualStatus(data.lifecycle_status);
    });
    apiClient.get<OfficialInfo | null>(`/waybills/${id}/official-info`).then(setOfficialInfo).catch(() => setOfficialInfo(null));
    apiClient.get<OfficialFlightSegment[]>(`/waybills/${id}/official-flight-segments`).then(setSegments);
    apiClient.get<StatusEvent[]>(`/waybills/${id}/status-events`).then(setEvents);
    apiClient.get<AssemblyEvent[]>(`/waybills/${id}/assembly-events`).then(setAssemblies);
    apiClient.get<QuerySnapshot[]>(`/waybills/${id}/query-snapshots`).then(setSnapshots);
    apiClient.get<Alert[]>(`/waybills/${id}/alerts`).then(setAlerts);
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  async function triggerQuery() {
    if (!id) return;
    await apiClient.post<QuerySnapshot>(`/waybills/${id}/trigger-query`);
    setMessage("已触发查询。本期 CZ 适配器会返回未配置真实查询的占位失败结果。");
    load();
  }

  async function updateManualStatus() {
    if (!id || !manualStatus) return;
    await apiClient.post<Waybill>(`/waybills/${id}/manual-status`, { lifecycle_status: manualStatus });
    setMessage("生命周期已手动更新。");
    load();
  }

  async function voidWaybill() {
    if (!id) return;
    await apiClient.post<Waybill>(`/waybills/${id}/void`);
    setMessage("运单已作废。");
    load();
  }

  if (!waybill) return <div className="text-sm text-slate-500">正在加载运单...</div>;

  return (
    <>
      <PageHeader
        title={`运单 ${waybill.waybill_no}`}
        description="查看生命周期、官方事件、查询快照和异常"
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link href="/waybills">
                <Pencil className="h-4 w-4" />
                返回列表
              </Link>
            </Button>
            <Button onClick={triggerQuery}>
              <Play className="h-4 w-4" />
              触发查询
            </Button>
            {isAdmin ? (
              <Button variant="danger" onClick={voidWaybill}>
                <Ban className="h-4 w-4" />
                作废
              </Button>
            ) : null}
          </div>
        }
      />
      {message ? <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div> : null}
      <div className="mb-4 grid gap-4 md:grid-cols-4">
        <Panel><div className="text-xs text-slate-500">生命周期</div><div className="mt-2"><LifecycleBadge value={waybill.lifecycle_status} /></div></Panel>
        <Panel><div className="text-xs text-slate-500">异常等级</div><div className="mt-2"><AlertLevelBadge value={waybill.alert_level} /></div></Panel>
        <Panel><div className="text-xs text-slate-500">航司</div><div className="mt-2 text-sm font-semibold">{compact(waybill.carrier_code)}</div></Panel>
        <Panel><div className="text-xs text-slate-500">下次查询</div><div className="mt-2 text-sm font-semibold">{formatDateTime(waybill.next_query_at)}</div></Panel>
      </div>
      <Tabs defaultValue="base">
        <TabsList>
          <TabsTrigger value="base">基础信息</TabsTrigger>
          <TabsTrigger value="official">官方信息</TabsTrigger>
          <TabsTrigger value="events">状态事件</TabsTrigger>
          <TabsTrigger value="snapshots">查询快照</TabsTrigger>
          <TabsTrigger value="alerts">异常</TabsTrigger>
          <TabsTrigger value="edit">编辑</TabsTrigger>
        </TabsList>
        <TabsContent value="base">
          <Panel title="运单信息">
            <FieldGrid
              items={[
                ["目的港", waybill.destination_port],
                ["航代", waybill.agent],
                ["入仓号", waybill.warehouse_no],
                ["收货人", waybill.consignee],
                ["计划航班", waybill.plan?.planned_flight_no],
                ["计划日期", waybill.plan?.planned_flight_date],
                ["计划航程", waybill.plan?.planned_route_text],
                ["订舱重量", waybill.booked_weight],
                ["订舱方数", waybill.booked_volume],
                ["密度", waybill.density],
                ["报价", waybill.quotation],
                ["航空费", waybill.air_freight_cost],
                ["付款日期", waybill.payment_date],
                ["做数据收费", waybill.data_charge],
                ["客服备注", waybill.customer_remark],
                ["内部备注", waybill.internal_remark]
              ]}
            />
            {isAdmin ? (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Select value={manualStatus} onValueChange={(value) => setManualStatus(value as LifecycleStatus)}>
                  <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {statusOptions.map((status) => (
                      <SelectItem key={status} value={status}>{lifecycleLabels[status]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="secondary" onClick={updateManualStatus}>手动更新状态</Button>
              </div>
            ) : null}
          </Panel>
        </TabsContent>
        <TabsContent value="official">
          <Panel title="官方运单信息">
            <FieldGrid
              items={[
                ["官方运单号", officialInfo?.official_waybill_no],
                ["承运人", officialInfo?.carrier_text],
                ["航程", officialInfo?.route_text],
                ["货物品名", officialInfo?.goods_name],
                ["总件数", officialInfo?.total_pieces],
                ["总重量", officialInfo?.total_weight],
                ["总体积", officialInfo?.total_volume],
                ["比例", computeRatio(officialInfo?.total_weight, officialInfo?.total_volume)]
              ]}
            />
          </Panel>
          <Panel title="官方订舱航段" className="mt-4">
            {segments.length ? (
              <Table>
                <THead>
                  <TR>
                    <TH rowSpan={2}>序号</TH>
                    <TH rowSpan={2}>订舱号</TH>
                    <TH rowSpan={2}>航班</TH>
                    <TH rowSpan={2}>日期</TH>
                    <TH rowSpan={2}>出发</TH>
                    <TH rowSpan={2}>到达</TH>
                    <TH colSpan={2} className="border-l border-slate-200 text-center">起飞时间</TH>
                    <TH colSpan={2} className="border-l border-slate-200 text-center">到达时间</TH>
                    <TH rowSpan={2} className="border-l border-slate-200">件/重/体</TH>
                  </TR>
                  <TR>
                    <TH className="border-l border-slate-200">计划</TH>
                    <TH>实际</TH>
                    <TH className="border-l border-slate-200">计划</TH>
                    <TH>实际</TH>
                  </TR>
                </THead>
                <TBody>
                  {segments.map((item) => (
                    <TR key={item.id}>
                      <TD>{item.segment_order}</TD>
                      <TD>{compact(item.booking_no)}</TD>
                      <TD>{compact(item.flight_no)}</TD>
                      <TD>{compact(item.flight_date)}</TD>
                      <TD>{compact(item.departure_airport)}</TD>
                      <TD>{compact(item.arrival_airport)}</TD>
                      <TD className="border-l border-slate-100">{formatDateTime(item.departure_planned_time)}</TD>
                      <TD>{formatDateTime(item.departure_actual_time)}</TD>
                      <TD className="border-l border-slate-100">{formatDateTime(item.arrival_planned_time)}</TD>
                      <TD>{formatDateTime(item.arrival_actual_time)}</TD>
                      <TD className="border-l border-slate-100">{compact(item.pieces)} / {compact(item.weight)} / {compact(item.volume)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : <EmptyState title="暂无官方航段" description="真实航司查询接入后会写入订舱航段。" />}
          </Panel>
        </TabsContent>
        <TabsContent value="events">
          <Panel title="货物状态事件">
            {events.length ? (
              <Table><THead><TR><TH>时间</TH><TH>城市</TH><TH>航班</TH><TH>状态</TH><TH>类型</TH><TH>件/重</TH></TR></THead>
                <TBody>{events.map((item) => <TR key={item.id}><TD>{formatDateTime(item.event_time_local) || item.event_time_text}</TD><TD>{compact(item.event_city)}</TD><TD>{compact(item.flight_no)}</TD><TD>{item.status_text}</TD><TD><Badge>{item.normalized_event_type}</Badge></TD><TD>{compact(item.pieces)} / {compact(item.weight)}</TD></TR>)}</TBody>
              </Table>
            ) : <EmptyState title="暂无状态事件" description="官方货物状态解析后会形成时间线。" />}
          </Panel>
          <Panel title="货物组装事件" className="mt-4">
            {assemblies.length ? (
              <Table><THead><TR><TH>时间</TH><TH>城市</TH><TH>状态</TH><TH>板号</TH><TH>件/重</TH></TR></THead>
                <TBody>{assemblies.map((item) => <TR key={item.id}><TD>{formatDateTime(item.event_time_local) || item.event_time_text}</TD><TD>{compact(item.event_city)}</TD><TD>{item.status_text}</TD><TD>{compact(item.uld_no)}</TD><TD>{compact(item.pieces)} / {compact(item.weight)}</TD></TR>)}</TBody>
              </Table>
            ) : <EmptyState title="暂无组装事件" description="如 PMC 板号等信息会显示在这里。" />}
          </Panel>
        </TabsContent>
        <TabsContent value="snapshots">
          <Panel title="查询快照">
            {snapshots.length ? (
              <Table><THead><TR><TH>时间</TH><TH>状态</TH><TH>适配器</TH><TH>错误码</TH><TH>错误信息</TH></TR></THead>
                <TBody>{snapshots.map((item) => <TR key={item.id}><TD>{formatDateTime(item.queried_at)}</TD><TD>{item.query_status}</TD><TD>{compact(item.adapter_code)}</TD><TD>{compact(item.error_code)}</TD><TD>{compact(item.error_message)}</TD></TR>)}</TBody>
              </Table>
            ) : <EmptyState title="暂无查询快照" description="手动触发或调度执行后会记录查询结果。" />}
          </Panel>
        </TabsContent>
        <TabsContent value="alerts">
          <Panel title="异常列表">
            {alerts.length ? (
              <Table><THead><TR><TH>标题</TH><TH>类型</TH><TH>等级</TH><TH>状态</TH><TH>新值</TH><TH>时间</TH></TR></THead>
                <TBody>{alerts.map((item) => <TR key={item.id}><TD>{item.title}</TD><TD>{item.alert_type}</TD><TD><AlertLevelBadge value={item.alert_level} /></TD><TD>{item.status}</TD><TD>{compact(item.new_value)}</TD><TD>{formatDateTime(item.created_at)}</TD></TR>)}</TBody>
              </Table>
            ) : <EmptyState title="暂无异常" description="这票运单当前没有异常记录。" />}
          </Panel>
        </TabsContent>
        <TabsContent value="edit">
          <WaybillForm waybill={waybill} />
        </TabsContent>
      </Tabs>
    </>
  );
}
