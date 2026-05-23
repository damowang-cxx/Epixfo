"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { Pencil, Plus, Search, Trash2 } from "lucide-react";
import { AlertLevelBadge, LifecycleBadge, LIFECYCLE_VARIANT, type LifecycleBadgeVariant } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useAuth } from "@/components/layout/auth-provider";
import { WarehouseFileUploadButton } from "@/components/waybills/warehouse-file-upload-button";
import { apiClient } from "@/lib/client-api";
import { LIFECYCLE_ORDER, lifecycleLabels } from "@/lib/constants";
import { cn, compact, formatDateTime } from "@/lib/utils";
import { formatWarehouseUploadMessage } from "@/lib/warehouse-upload";
import type { BoxBatchOperationResult, CargoBox, LifecycleStatus, PageResponse, WarehouseFileUploadResult, Waybill } from "@/lib/types";

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

const UNBOUND_REASON_LABELS: Record<string, string> = {
  customs_inspection: "海关查验",
  other: "其他"
};

function unboundReasonLabel(reason?: string | null) {
  if (!reason) return "";
  return UNBOUND_REASON_LABELS[reason] || reason;
}

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
  const { hasRole } = useAuth();
  const canDeleteWaybills = hasRole("admin") || hasRole("route_staff");
  const [data, setData] = useState<PageResponse<Waybill> | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [waybillNo, setWaybillNo] = useState("");
  const [carrierCode, setCarrierCode] = useState("");
  const [destinationPort, setDestinationPort] = useState("");
  const [plannedFlightNo, setPlannedFlightNo] = useState("");
  const [lifecycleStatus, setLifecycleStatus] = useState<LifecycleStatus | "all">("all");
  const [page, setPage] = useState(1);
  const [message, setMessage] = useState("");
  const [unboundOpen, setUnboundOpen] = useState(false);
  const [unboundData, setUnboundData] = useState<PageResponse<CargoBox> | null>(null);
  const [unboundPage, setUnboundPage] = useState(1);
  const [selectedBoxIds, setSelectedBoxIds] = useState<Set<number>>(new Set());
  const [targetWaybillId, setTargetWaybillId] = useState("");
  const [waybillOptions, setWaybillOptions] = useState<Waybill[]>([]);
  const [deletingWaybillId, setDeletingWaybillId] = useState<number | null>(null);

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

  const loadUnbound = useCallback(() => {
    apiClient.get<PageResponse<CargoBox>>(`/boxes/unbound?page=${unboundPage}&page_size=20`).then(setUnboundData);
  }, [unboundPage]);

  const loadWaybillOptions = useCallback(() => {
    apiClient
      .get<PageResponse<Waybill>>("/waybills?page=1&page_size=200")
      .then((rows) => setWaybillOptions(rows.items.filter((item) => Boolean(item.warehouse_no))))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadCounts();
  }, [data, loadCounts]);

  useEffect(() => {
    if (unboundOpen) {
      loadUnbound();
      loadWaybillOptions();
    }
  }, [loadUnbound, loadWaybillOptions, unboundOpen]);

  const totalCount = useMemo(() => Object.values(counts).reduce((a, b) => a + b, 0), [counts]);
  const boardRowSpans = useMemo(() => {
    const spans = new Map<number, number>();
    const items = data?.items || [];
    let index = 0;
    while (index < items.length) {
      const boardId = items[index].board_id;
      if (!boardId) {
        spans.set(index, 1);
        index += 1;
        continue;
      }
      let next = index + 1;
      while (next < items.length && items[next].board_id === boardId) next += 1;
      spans.set(index, next - index);
      index = next;
    }
    return spans;
  }, [data?.items]);

  function applyFilters() {
    setPage(1);
    load();
  }

  function selectStatus(status: LifecycleStatus | "all") {
    setLifecycleStatus(status);
    setPage(1);
  }

  function handleUploadSuccess(result: WarehouseFileUploadResult) {
    setMessage(formatWarehouseUploadMessage(result));
    load();
    loadCounts();
  }

  function toggleUnboundBox(id: number, checked: boolean) {
    setSelectedBoxIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  async function bindSelectedUnboundBoxes() {
    if (!selectedBoxIds.size || !targetWaybillId) return;
    try {
      const result = await apiClient.post<BoxBatchOperationResult>("/boxes/batch-transfer", {
        box_ids: Array.from(selectedBoxIds),
        target_type: "waybill",
        target_waybill_id: Number(targetWaybillId)
      });
      setMessage(`已绑定 ${result.updated_count} 个箱号。`);
      setSelectedBoxIds(new Set());
      setTargetWaybillId("");
      loadUnbound();
      load();
      loadCounts();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "批量绑定失败。");
    }
  }

  async function deleteWaybill(item: Waybill) {
    if (!window.confirm(`确认删除提单 ${item.waybill_no} 吗？删除后不可恢复，关联的入仓箱号会转为未绑定。`)) return;
    setDeletingWaybillId(item.id);
    setMessage("");
    try {
      await apiClient.delete<void>(`/waybills/${item.id}`);
      setMessage(`提单 ${item.waybill_no} 已删除。`);
      load();
      loadCounts();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除提单失败。");
    } finally {
      setDeletingWaybillId(null);
    }
  }

  return (
    <>
      <PageHeader
        title="提单管理"
        description="录入、筛选、追踪航空头程提单"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setUnboundOpen(true)}>
              未绑定箱号
            </Button>
            <Button asChild>
              <Link href="/waybills/new">
                <Plus className="h-4 w-4" />
                新建提单
              </Link>
            </Button>
          </div>
        }
      />
      {message ? (
        <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div>
      ) : null}
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
              <TH>系统板号</TH>
              <TH>实际板号</TH>
              <TH>收件人</TH>
              <TH>订舱方数/板总方数</TH>
              <TH>航代</TH>
              <TH>入仓号/入仓文件</TH>
              <TH>始发港</TH>
              <TH>目的港</TH>
              <TH>计划航班</TH>
              <TH>约定航班起飞日期</TH>
              <TH>官方预计航班日期</TH>
              <TH>生命周期</TH>
              <TH>异常</TH>
              <TH>下次查询</TH>
              <TH>操作</TH>
            </TR>
          </THead>
          <TBody>
            {(data?.items || []).map((item, index) => {
              const boardSpan = boardRowSpans.get(index) || 0;
              const shouldRenderBoardCells = !item.board_id || boardSpan > 0;
              return (
              <TR
                key={item.id}
                className={cn(
                  item.lifecycle_status === "picked_up" &&
                    "[&_td]:text-slate-400 [&_td_*]:text-slate-400"
                )}
              >
                <TD className="font-medium">
                  <Link
                    href={`/waybills/${item.id}`}
                    className="text-purple-700 underline-offset-2 hover:text-purple-900 hover:underline"
                  >
                    {item.waybill_no}
                  </Link>
                </TD>
                {shouldRenderBoardCells ? (
                  <>
                    <TD rowSpan={boardSpan} className="align-middle font-medium">
                      {item.board?.board_no || ""}
                    </TD>
                    <TD rowSpan={boardSpan} className="align-middle">
                      {item.board?.actual_board_no || ""}
                    </TD>
                    <TD rowSpan={boardSpan} className="align-middle">
                      {item.board ? compact(item.board.consignee_text) : compact(item.consignee)}
                    </TD>
                    <TD rowSpan={boardSpan} className="align-middle">
                      {item.board ? compact(item.board.total_booked_volume) : compact(item.booked_volume)}
                    </TD>
                  </>
                ) : null}
                <TD>{compact(item.agent)}</TD>
                <TD>
                  <div className="flex min-w-40 flex-col items-start gap-1">
                    {item.warehouse_no ? <span className="font-medium text-slate-800">{item.warehouse_no}</span> : null}
                    <WarehouseFileUploadButton
                      waybillId={item.id}
                      label={item.warehouse_no ? "上传新入仓文件" : "上传入仓文件"}
                      variant={item.warehouse_no ? "ghost" : "secondary"}
                      onUploaded={handleUploadSuccess}
                      onError={setMessage}
                    />
                  </div>
                </TD>
                <TD>{compact(item.departure_port)}</TD>
                <TD>{compact(item.destination_port)}</TD>
                <TD>{compact(item.plan?.planned_flight_no)}</TD>
                <TD>{compact(item.plan?.planned_flight_date)}</TD>
                <TD>{item.official_estimated_flight_date || ""}</TD>
                <TD><LifecycleBadge value={item.lifecycle_status} /></TD>
                <TD><AlertLevelBadge value={item.alert_level} /></TD>
                <TD>{formatDateTime(item.next_query_at)}</TD>
                <TD>
                  <div className="flex flex-wrap gap-1">
                    <Button asChild variant="ghost" size="sm">
                      <Link href={`/waybills/${item.id}/edit`}>
                        <Pencil className="h-4 w-4" />
                        编辑
                      </Link>
                    </Button>
                    {canDeleteWaybills ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        disabled={deletingWaybillId === item.id}
                        onClick={() => void deleteWaybill(item)}
                        aria-label={`删除提单 ${item.waybill_no}`}
                      >
                        <Trash2 className="h-4 w-4 text-red-600" />
                        删除
                      </Button>
                    ) : null}
                  </div>
                </TD>
              </TR>
              );
            })}
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
      <Dialog open={unboundOpen} onOpenChange={setUnboundOpen}>
        <DialogContent className="w-[min(960px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">未绑定箱号</DialogTitle>
          <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-600">已选 {selectedBoxIds.size} 个箱号</span>
              <Select value={targetWaybillId} onValueChange={setTargetWaybillId}>
                <SelectTrigger className="w-72">
                  <SelectValue placeholder="选择目标提单入仓号" />
                </SelectTrigger>
                <SelectContent>
                  {waybillOptions.map((item) => (
                    <SelectItem key={item.id} value={String(item.id)}>
                      {item.waybill_no} · {item.warehouse_no}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Button
                variant="secondary"
                disabled={!selectedBoxIds.size || !targetWaybillId}
                onClick={() => void bindSelectedUnboundBoxes()}
              >
                批量绑定
              </Button>
            </div>
            <Table>
              <THead>
                <TR>
                  <TH>选择</TH>
                  <TH>外箱条码</TH>
                  <TH>箱内提单数</TH>
                  <TH>首个仓库提单号码</TH>
                  <TH>品名</TH>
                  <TH>原因</TH>
                  <TH>备注</TH>
                  <TH>数量</TH>
                  <TH>重量</TH>
                  <TH>方数</TH>
                  <TH>重量/方</TH>
                </TR>
              </THead>
              <TBody>
                {(unboundData?.items || []).map((item) => (
                  <TR key={item.id}>
                    <TD>
                      <input
                        type="checkbox"
                        checked={selectedBoxIds.has(item.id)}
                        onChange={(event) => toggleUnboundBox(item.id, event.target.checked)}
                      />
                    </TD>
                    <TD className="font-medium">{item.box_no}</TD>
                    <TD>{item.items?.length || 0}</TD>
                    <TD>{compact(item.warehouse_waybill_no)}</TD>
                    <TD>{compact(item.goods_name)}</TD>
                    <TD>
                      {item.unbound_reason ? (
                        <span className="rounded bg-slate-100 px-1.5 py-0.5 text-xs font-medium text-slate-700">
                          {unboundReasonLabel(item.unbound_reason)}
                        </span>
                      ) : null}
                    </TD>
                    <TD>{compact(item.unbound_remark)}</TD>
                    <TD>{compact(item.quantity)}</TD>
                    <TD>{compact(item.weight)}</TD>
                    <TD>{compact(item.volume)}</TD>
                    <TD>{compact(item.weight_volume_ratio)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
            <div className="flex items-center justify-between text-sm text-slate-500">
              <span>共 {unboundData?.total ?? 0} 个未绑定箱号</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={unboundPage <= 1} onClick={() => setUnboundPage((prev) => prev - 1)}>
                  上一页
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!unboundData || unboundPage * unboundData.page_size >= unboundData.total}
                  onClick={() => setUnboundPage((prev) => prev + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
