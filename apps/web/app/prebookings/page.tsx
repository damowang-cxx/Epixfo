"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { CalendarClock, CheckCircle2, Edit, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { CargoBoxesTable } from "@/components/waybills/cargo-boxes-table";
import { WarehouseFileUploadButton } from "@/components/waybills/warehouse-file-upload-button";
import { apiClient } from "@/lib/client-api";
import { compact } from "@/lib/utils";
import { formatWarehouseUploadMessage } from "@/lib/warehouse-upload";
import type { CargoBox, CarrierAgent, PageResponse, WarehouseReceipt, Waybill, WaybillPrebooking } from "@/lib/types";

type PrebookingDraft = {
  carrier_agent_id: string;
  planned_flight_date: string;
  booked_volume: string;
  internal_remark: string;
};

type ConvertDraft = {
  waybill_no: string;
  carrier_agent_id: string;
  departure_port: string;
  destination_port: string;
  planned_flight_info: string;
  planned_route_text: string;
  booked_weight: string;
  booked_volume: string;
  quotation: string;
  internal_remark: string;
};

function emptyPrebookingDraft(): PrebookingDraft {
  return { carrier_agent_id: "", planned_flight_date: "", booked_volume: "", internal_remark: "" };
}

function prebookingDraftFrom(item: WaybillPrebooking): PrebookingDraft {
  return {
    carrier_agent_id: String(item.carrier_agent_id || ""),
    planned_flight_date: item.planned_flight_date || "",
    booked_volume: item.booked_volume ? String(item.booked_volume) : "",
    internal_remark: item.internal_remark || ""
  };
}

function convertDraftFrom(item: WaybillPrebooking): ConvertDraft {
  return {
    waybill_no: item.waybill_no || "",
    carrier_agent_id: String(item.carrier_agent_id || ""),
    departure_port: item.departure_port || "",
    destination_port: item.destination_port || "",
    planned_flight_info: item.planned_flight_no ? `${item.planned_flight_no}/${String(new Date(item.planned_flight_date).getDate()).padStart(2, "0")}` : "",
    planned_route_text: item.planned_route_text || "",
    booked_weight: item.booked_weight ? String(item.booked_weight) : "",
    booked_volume: item.booked_volume ? String(item.booked_volume) : "",
    quotation: item.quotation ? String(item.quotation) : "",
    internal_remark: item.internal_remark || ""
  };
}

function numberOrUndefined(value: string) {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : undefined;
}

function textOrUndefined(value: string) {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function formatDecimal(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

function statusLabel(status: string) {
  if (status === "draft") return "预排中";
  if (status === "converted") return "已转正式";
  if (status === "cancelled") return "已取消";
  return status;
}

function agentName(item?: CarrierAgent | null) {
  return item?.agent_name || "-";
}

function channelTags(tags?: string[] | null) {
  return (tags || []).filter(Boolean);
}

export default function PrebookingsPage() {
  const router = useRouter();
  const [data, setData] = useState<PageResponse<WaybillPrebooking> | null>(null);
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<WaybillPrebooking | null>(null);
  const [boxes, setBoxes] = useState<CargoBox[]>([]);
  const [agents, setAgents] = useState<CarrierAgent[]>([]);
  const [unboundReceipts, setUnboundReceipts] = useState<WarehouseReceipt[]>([]);
  const [createOpen, setCreateOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const [convertOpen, setConvertOpen] = useState(false);
  const [bindOpen, setBindOpen] = useState(false);
  const [draft, setDraft] = useState<PrebookingDraft>(() => emptyPrebookingDraft());
  const [convertDraft, setConvertDraft] = useState<ConvertDraft | null>(null);
  const [targetReceiptId, setTargetReceiptId] = useState("");
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [receiptOptionsLoading, setReceiptOptionsLoading] = useState(false);
  const [receiptOptionsError, setReceiptOptionsError] = useState("");

  const loadList = useCallback(() => {
    apiClient.get<PageResponse<WaybillPrebooking>>(`/prebookings?page=${page}&page_size=20`).then((result) => {
      setData(result);
      if (!selectedId && result.items.length) setSelectedId(result.items[0].id);
    });
  }, [page, selectedId]);

  const loadAgents = useCallback(() => {
    apiClient.get<CarrierAgent[]>("/carrier-agents").then((items) => setAgents(items.filter((item) => item.enabled)));
  }, []);

  const loadUnboundReceipts = useCallback(async () => {
    setReceiptOptionsLoading(true);
    setReceiptOptionsError("");
    try {
      const firstPage = await apiClient.get<PageResponse<WarehouseReceipt>>("/warehouse-receipts/unbound?page=1&page_size=100");
      const items = [...firstPage.items];
      const pageSize = firstPage.page_size || 200;
      const totalPages = Math.ceil(firstPage.total / pageSize);
      for (let pageNumber = 2; pageNumber <= totalPages; pageNumber += 1) {
        const result = await apiClient.get<PageResponse<WarehouseReceipt>>(`/warehouse-receipts/unbound?page=${pageNumber}&page_size=${pageSize}`);
        items.push(...result.items);
      }
      setUnboundReceipts(items);
    } catch (error) {
      setUnboundReceipts([]);
      setReceiptOptionsError(error instanceof Error ? error.message : "加载未绑定入仓号失败。");
    } finally {
      setReceiptOptionsLoading(false);
    }
  }, []);

  const loadSelected = useCallback(() => {
    if (!selectedId) {
      setSelected(null);
      setBoxes([]);
      return;
    }
    apiClient.get<WaybillPrebooking>(`/prebookings/${selectedId}`).then(setSelected);
    apiClient.get<CargoBox[]>(`/prebookings/${selectedId}/boxes`).then(setBoxes);
  }, [selectedId]);

  const refreshAll = useCallback(() => {
    loadList();
    loadSelected();
    loadUnboundReceipts();
  }, [loadList, loadSelected, loadUnboundReceipts]);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  useEffect(() => {
    const timer = window.setTimeout(refreshAll, 0);
    return () => window.clearTimeout(timer);
  }, [refreshAll]);

  const boxGroups = useMemo(() => {
    if (!selected) return [];
    const groups = new Map<
      string,
      {
        key: string;
        receiptId: number;
        warehouseNo: string;
        totalQuantity?: number | null;
        totalWeight?: string | number | null;
        totalVolume?: string | number | null;
        weightVolumeRatio?: string | number | null;
        channelTags: string[];
        boxes: CargoBox[];
      }
    >();
    for (const receipt of selected.receipts || []) {
      groups.set(String(receipt.id), {
        key: String(receipt.id),
        receiptId: receipt.id,
        warehouseNo: receipt.warehouse_no,
        totalQuantity: receipt.total_quantity,
        totalWeight: receipt.total_weight,
        totalVolume: receipt.total_volume,
        weightVolumeRatio: receipt.weight_volume_ratio,
        channelTags: channelTags(receipt.channel_tags),
        boxes: []
      });
    }
    for (const box of boxes) {
      const receipt = box.warehouse_receipt;
      if (!receipt?.id) continue;
      const key = String(receipt.id);
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          receiptId: receipt.id,
          warehouseNo: receipt.warehouse_no,
          totalQuantity: receipt.total_quantity,
          totalWeight: receipt.total_weight,
          totalVolume: receipt.total_volume,
          weightVolumeRatio: receipt.weight_volume_ratio,
          channelTags: channelTags(receipt.channel_tags),
          boxes: []
        });
      }
      groups.get(key)?.boxes.push(box);
    }
    return Array.from(groups.values());
  }, [boxes, selected]);

  function openCreate() {
    setDraft(emptyPrebookingDraft());
    setCreateOpen(true);
  }

  function openEdit() {
    if (!selected) return;
    setDraft(prebookingDraftFrom(selected));
    setEditOpen(true);
  }

  function openConvert() {
    if (!selected) return;
    setConvertDraft(convertDraftFrom(selected));
    setConvertOpen(true);
  }

  async function savePrebooking(isEdit: boolean) {
    const payload = {
      carrier_agent_id: Number(draft.carrier_agent_id),
      planned_flight_date: draft.planned_flight_date,
      booked_volume: Number(draft.booked_volume),
      internal_remark: textOrUndefined(draft.internal_remark)
    };
    if (!payload.carrier_agent_id || !payload.planned_flight_date || !payload.booked_volume) {
      setMessage("请填写航代、起飞日期和方数。");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const result = isEdit && selected
        ? await apiClient.patch<WaybillPrebooking>(`/prebookings/${selected.id}`, payload)
        : await apiClient.post<WaybillPrebooking>("/prebookings", payload);
      setSelectedId(result.id);
      setCreateOpen(false);
      setEditOpen(false);
      refreshAll();
      setMessage(isEdit ? "预排仓已更新。" : "预排仓已创建。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存预排仓失败。");
    } finally {
      setSaving(false);
    }
  }

  async function bindReceipt() {
    if (!selected || !targetReceiptId) return;
    setSaving(true);
    setMessage("");
    try {
      await apiClient.post<WarehouseReceipt>(`/prebookings/${selected.id}/receipts`, { receipt_id: Number(targetReceiptId) });
      setBindOpen(false);
      setTargetReceiptId("");
      refreshAll();
      setMessage("入仓号已绑定到预排仓。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "绑定入仓号失败。");
    } finally {
      setSaving(false);
    }
  }

  function openBindReceipt() {
    setTargetReceiptId("");
    setBindOpen(true);
    void loadUnboundReceipts();
  }

  async function convertPrebooking() {
    if (!selected || !convertDraft) return;
    const payload = {
      waybill_no: convertDraft.waybill_no.trim(),
      carrier_agent_id: Number(convertDraft.carrier_agent_id),
      departure_port: textOrUndefined(convertDraft.departure_port),
      destination_port: textOrUndefined(convertDraft.destination_port),
      planned_flight_info: textOrUndefined(convertDraft.planned_flight_info),
      planned_route_text: textOrUndefined(convertDraft.planned_route_text),
      booked_weight: numberOrUndefined(convertDraft.booked_weight),
      booked_volume: numberOrUndefined(convertDraft.booked_volume),
      quotation: textOrUndefined(convertDraft.quotation),
      internal_remark: textOrUndefined(convertDraft.internal_remark)
    };
    setSaving(true);
    setMessage("");
    try {
      const waybill = await apiClient.post<Waybill>(`/prebookings/${selected.id}/convert`, payload);
      setConvertOpen(false);
      setMessage("已转为正式提单。");
      router.push(`/waybills/${waybill.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "转正式提单失败，请检查必填信息。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <PageHeader
        title="预排仓"
        description="用于处理提单号和航班号暂缺，但已订出发日期与方数的排仓条目。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={refreshAll}>
              <RefreshCw className="h-4 w-4" />
              刷新
            </Button>
            <Button onClick={openCreate}>
              <CalendarClock className="h-4 w-4" />
              新建预排仓
            </Button>
          </div>
        }
      />
      {message ? <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <Panel title="预排仓列表">
          {(data?.items || []).length ? (
            <div className="space-y-2">
              {(data?.items || []).map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className={`w-full rounded-md border px-3 py-2 text-left transition ${
                    selectedId === item.id ? "border-purple-300 bg-purple-50" : "border-slate-200 bg-white hover:bg-slate-50"
                  }`}
                  onClick={() => setSelectedId(item.id)}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-semibold text-slate-900">预排仓 #{item.id}</span>
                    <Badge variant={item.status === "converted" ? "green" : item.status === "cancelled" ? "gray" : "amber"}>
                      {statusLabel(item.status)}
                    </Badge>
                  </div>
                  <div className="mt-1 grid gap-1 text-xs text-slate-600">
                    <span>起飞日期：{item.planned_flight_date}</span>
                    <span>方数：{formatDecimal(item.booked_volume)}</span>
                    <span>航代：{agentName(item.carrier_agent)}</span>
                    <span>入仓号：{item.receipts?.length || 0} 个</span>
                  </div>
                </button>
              ))}
              <div className="flex items-center justify-between pt-2 text-sm text-slate-600">
                <span>共 {data?.total || 0} 条</span>
                <div className="flex gap-2">
                  <Button variant="secondary" size="sm" disabled={page <= 1} onClick={() => setPage((prev) => Math.max(1, prev - 1))}>
                    上一页
                  </Button>
                  <Button
                    variant="secondary"
                    size="sm"
                    disabled={!data || page * data.page_size >= data.total}
                    onClick={() => setPage((prev) => prev + 1)}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            </div>
          ) : (
            <EmptyState title="暂无预排仓条目" description="点击新建预排仓，先录入航代、起飞日期和方数。" />
          )}
        </Panel>

        {selected ? (
          <div className="space-y-4">
            <Panel
              title={`预排仓 #${selected.id}`}
              action={
                <div className="flex flex-wrap gap-2">
                  {selected.converted_waybill_id ? (
                    <Button variant="secondary" onClick={() => router.push(`/waybills/${selected.converted_waybill_id}`)}>
                      查看正式提单
                    </Button>
                  ) : null}
                  {selected.status === "draft" ? (
                    <>
                      <Button variant="secondary" onClick={openEdit}>
                        <Edit className="h-4 w-4" />
                        编辑
                      </Button>
                      <Button onClick={openConvert}>
                        <CheckCircle2 className="h-4 w-4" />
                        转为正式提单
                      </Button>
                    </>
                  ) : null}
                </div>
              }
            >
              <div className="grid gap-3 text-sm md:grid-cols-4">
                <div className="rounded-md border border-slate-100 p-3"><div className="text-xs text-slate-500">状态</div><div className="mt-1 font-medium">{statusLabel(selected.status)}</div></div>
                <div className="rounded-md border border-slate-100 p-3"><div className="text-xs text-slate-500">航代</div><div className="mt-1 font-medium">{agentName(selected.carrier_agent)}</div></div>
                <div className="rounded-md border border-slate-100 p-3"><div className="text-xs text-slate-500">起飞日期</div><div className="mt-1 font-medium">{selected.planned_flight_date}</div></div>
                <div className="rounded-md border border-slate-100 p-3"><div className="text-xs text-slate-500">方数</div><div className="mt-1 font-medium">{formatDecimal(selected.booked_volume)}</div></div>
                <div className="rounded-md border border-slate-100 p-3 md:col-span-4"><div className="text-xs text-slate-500">备注</div><div className="mt-1 font-medium">{compact(selected.internal_remark)}</div></div>
              </div>
            </Panel>

            <Panel
              title="入仓货物明细"
              action={
                selected.status === "draft" ? (
                  <div className="flex flex-wrap justify-end gap-2">
                    <Button variant="secondary" onClick={openBindReceipt}>
                      绑定已有入仓号
                    </Button>
                    <WarehouseFileUploadButton
                      uploadPath={`/prebookings/${selected.id}/warehouse-file`}
                      label="上传入仓文件"
                      onUploaded={(result) => {
                        setMessage(formatWarehouseUploadMessage(result));
                        refreshAll();
                      }}
                      onError={setMessage}
                    />
                  </div>
                ) : null
              }
            >
              {boxGroups.length ? (
                <div className="space-y-4">
                  {boxGroups.map((group) => (
                    <div key={group.key} className="rounded-md border border-slate-200">
                      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 bg-slate-50 px-3 py-2 text-sm">
                        <div className="flex flex-wrap items-center gap-2 font-semibold text-slate-900">
                          <span>入仓号：{group.warehouseNo}</span>
                          {group.channelTags.map((tag) => <Badge key={tag} variant="amber">{tag}</Badge>)}
                        </div>
                        <div className="flex flex-wrap gap-3 text-xs text-slate-600">
                          <span>箱数 {group.boxes.length}</span>
                          <span>总数量 {compact(group.totalQuantity)}</span>
                          <span>总重量 {compact(group.totalWeight)}</span>
                          <span>总方数 {compact(group.totalVolume)}</span>
                          <span>重量/方 {compact(group.weightVolumeRatio)}</span>
                        </div>
                      </div>
                      <div className="p-3">
                        <CargoBoxesTable
                          boxes={group.boxes}
                          boxApiBasePath={`/prebookings/${selected.id}`}
                          warehouseNo={group.warehouseNo}
                          warehouseReceiptId={group.receiptId}
                          readonly={selected.status !== "draft"}
                          onBoxUpdated={(updated) => setBoxes((prev) => prev.map((item) => (item.id === updated.id ? updated : item)))}
                          onBoxDeleted={(boxId) => setBoxes((prev) => prev.filter((item) => item.id !== boxId))}
                          onChanged={refreshAll}
                          onError={setMessage}
                          onMessage={setMessage}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState title="暂无入仓号" description="上传入仓文件或绑定未绑定入仓号后，即可在这里排货。" />
              )}
            </Panel>
          </div>
        ) : (
          <Panel>
            <EmptyState title="请选择预排仓条目" description="左侧选择一条记录后查看和维护入仓货物明细。" />
          </Panel>
        )}
      </div>

      <Dialog open={createOpen || editOpen} onOpenChange={(open) => {
        if (!open) {
          setCreateOpen(false);
          setEditOpen(false);
        }
      }}>
        <DialogContent>
          <DialogTitle>{editOpen ? "编辑预排仓" : "新建预排仓"}</DialogTitle>
          <div className="mt-3 grid gap-3">
            <Select value={draft.carrier_agent_id} onValueChange={(value) => setDraft((prev) => ({ ...prev, carrier_agent_id: value }))}>
              <SelectTrigger><SelectValue placeholder="选择航代" /></SelectTrigger>
              <SelectContent>
                {agents.map((agent) => (
                  <SelectItem key={agent.id} value={String(agent.id)}>{agent.agent_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input type="date" value={draft.planned_flight_date} onChange={(event) => setDraft((prev) => ({ ...prev, planned_flight_date: event.target.value }))} />
            <Input type="number" min="0" step="0.001" placeholder="方数" value={draft.booked_volume} onChange={(event) => setDraft((prev) => ({ ...prev, booked_volume: event.target.value }))} />
            <Textarea rows={3} placeholder="备注" value={draft.internal_remark} onChange={(event) => setDraft((prev) => ({ ...prev, internal_remark: event.target.value }))} />
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" disabled={saving} onClick={() => { setCreateOpen(false); setEditOpen(false); }}>取消</Button>
            <Button disabled={saving} onClick={() => void savePrebooking(editOpen)}>保存</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={bindOpen} onOpenChange={setBindOpen}>
        <DialogContent>
          <DialogTitle>绑定已有入仓号</DialogTitle>
          <div className="mt-3 space-y-3">
            <div className="max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white">
              {receiptOptionsLoading ? <div className="px-3 py-4 text-sm text-slate-500">正在加载未绑定入仓号...</div> : null}
              {receiptOptionsError ? <div className="px-3 py-4 text-sm text-rose-600">{receiptOptionsError}</div> : null}
              {!receiptOptionsLoading && !receiptOptionsError && !unboundReceipts.length ? (
                <div className="px-3 py-4 text-sm text-slate-500">暂无可绑定的未绑定入仓号。</div>
              ) : null}
              <div className="divide-y divide-slate-100">
                {unboundReceipts.map((receipt) => {
                  const selectedReceipt = targetReceiptId === String(receipt.id);
                  const tags = channelTags(receipt.channel_tags);
                  return (
                    <button
                      key={receipt.id}
                      type="button"
                      onClick={() => setTargetReceiptId(String(receipt.id))}
                      className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition ${
                        selectedReceipt ? "bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-50"
                      }`}
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-medium">{receipt.warehouse_no}</span>
                        <span className={`block text-xs ${selectedReceipt ? "text-slate-200" : "text-slate-500"}`}>
                          箱数 {receipt.box_count ?? 0} / 重量 {formatDecimal(receipt.total_weight)} / 方数 {formatDecimal(receipt.total_volume)}
                        </span>
                      </span>
                      {tags.length ? (
                        <span className="flex shrink-0 flex-wrap justify-end gap-1">
                          {tags.map((tag) => (
                            <Badge key={tag} variant={selectedReceipt ? "default" : "amber"}>{tag}</Badge>
                          ))}
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" disabled={saving} onClick={() => setBindOpen(false)}>取消</Button>
            <Button disabled={saving || !targetReceiptId} onClick={() => void bindReceipt()}>绑定</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={convertOpen} onOpenChange={setConvertOpen}>
        <DialogContent className="w-[min(760px,calc(100vw-32px))]">
          <DialogTitle>转为正式提单</DialogTitle>
          {convertDraft ? (
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <Input placeholder="提单号" value={convertDraft.waybill_no} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, waybill_no: event.target.value }))} />
              <Select value={convertDraft.carrier_agent_id} onValueChange={(value) => setConvertDraft((prev) => prev && ({ ...prev, carrier_agent_id: value }))}>
                <SelectTrigger><SelectValue placeholder="航代" /></SelectTrigger>
                <SelectContent>{agents.map((agent) => <SelectItem key={agent.id} value={String(agent.id)}>{agent.agent_name}</SelectItem>)}</SelectContent>
              </Select>
              <Input placeholder="始发港" value={convertDraft.departure_port} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, departure_port: event.target.value }))} />
              <Input placeholder="目的港" value={convertDraft.destination_port} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, destination_port: event.target.value }))} />
              <Input placeholder="航班信息，例如 QR8943/01" value={convertDraft.planned_flight_info} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, planned_flight_info: event.target.value }))} />
              <Input placeholder="航程，例如 CAN-DOH-AMS" value={convertDraft.planned_route_text} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, planned_route_text: event.target.value }))} />
              <Input type="number" min="0" step="0.001" placeholder="订舱重量" value={convertDraft.booked_weight} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, booked_weight: event.target.value }))} />
              <Input type="number" min="0" step="0.001" placeholder="方数" value={convertDraft.booked_volume} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, booked_volume: event.target.value }))} />
              <Input placeholder="报价" value={convertDraft.quotation} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, quotation: event.target.value }))} />
              <Textarea className="md:col-span-2" rows={3} placeholder="内部备注" value={convertDraft.internal_remark} onChange={(event) => setConvertDraft((prev) => prev && ({ ...prev, internal_remark: event.target.value }))} />
            </div>
          ) : null}
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" disabled={saving} onClick={() => setConvertOpen(false)}>取消</Button>
            <Button disabled={saving || !convertDraft} onClick={() => void convertPrebooking()}>确认转正式</Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
