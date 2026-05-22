"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Calculator, Check, ChevronDown, ChevronRight, Pencil, Plus, Tag, Trash2, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { cn, compact } from "@/lib/utils";
import type { BoxBatchOperationResult, BoxVolumeRecalculationResult, CargoBox, PageResponse, Waybill } from "@/lib/types";

type NewBoxDraft = {
  box_no: string;
  warehouse_waybill_no: string;
  goods_name: string;
  quantity: string;
  weight: string;
  volume: string;
  is_general_cargo: boolean;
};

function emptyNewBoxDraft(): NewBoxDraft {
  return {
    box_no: "",
    warehouse_waybill_no: "",
    goods_name: "",
    quantity: "",
    weight: "",
    volume: "",
    is_general_cargo: false
  };
}

function formatDecimal(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

function optionalText(value: string) {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function optionalNumber(value: string) {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : undefined;
}

function toNumber(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return 0;
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

interface CargoBoxesTableProps {
  boxes: CargoBox[];
  waybillId?: number;
  warehouseNo?: string | null;
  bookedVolume?: string | number | null;
  readonly?: boolean;
  onBoxUpdated?: (box: CargoBox) => void;
  onChanged?: () => void;
  onError?: (message: string) => void;
  onMessage?: (message: string) => void;
}

export function CargoBoxesTable({
  boxes,
  waybillId,
  warehouseNo,
  bookedVolume,
  readonly = false,
  onBoxUpdated,
  onChanged,
  onError,
  onMessage
}: CargoBoxesTableProps) {
  const [editingBoxId, setEditingBoxId] = useState<number | null>(null);
  const [boxNoDraft, setBoxNoDraft] = useState("");
  const [newBoxOpen, setNewBoxOpen] = useState(false);
  const [newBoxDraft, setNewBoxDraft] = useState<NewBoxDraft>(() => emptyNewBoxDraft());
  const [saving, setSaving] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [targetWaybillId, setTargetWaybillId] = useState("");
  const [waybillOptions, setWaybillOptions] = useState<Waybill[]>([]);

  const selectedCount = selectedIds.size;
  const canManageBoxes = Boolean(waybillId && !readonly);
  const canCreateBox = Boolean(canManageBoxes && warehouseNo);
  const selectableWaybills = useMemo(
    () => waybillOptions.filter((item) => item.id !== waybillId && Boolean(item.warehouse_no)),
    [waybillId, waybillOptions]
  );
  const warehouseTotals = useMemo(
    () =>
      boxes.reduce(
        (total, item) => ({
          weight: total.weight + toNumber(item.weight),
          volume: total.volume + toNumber(item.volume)
        }),
        { weight: 0, volume: 0 }
      ),
    [boxes]
  );

  const loadWaybillOptions = useCallback(() => {
    apiClient
      .get<PageResponse<Waybill>>("/waybills?page=1&page_size=200")
      .then((data) => setWaybillOptions(data.items))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (selectedCount > 0) loadWaybillOptions();
  }, [loadWaybillOptions, selectedCount]);

  function updateNewBoxDraft<K extends keyof NewBoxDraft>(key: K, value: NewBoxDraft[K]) {
    setNewBoxDraft((prev) => ({ ...prev, [key]: value }));
  }

  function startEditing(item: CargoBox) {
    setEditingBoxId(item.id);
    setBoxNoDraft(item.box_no);
  }

  function cancelEditing() {
    setEditingBoxId(null);
    setBoxNoDraft("");
  }

  function cancelNewBox() {
    setNewBoxOpen(false);
    setNewBoxDraft(emptyNewBoxDraft());
  }

  function toggleSelected(id: number, checked: boolean) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  function toggleExpanded(id: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function createBox() {
    if (!waybillId) return;
    const boxNo = newBoxDraft.box_no.trim();
    if (!boxNo) {
      onError?.("外箱条码不能为空。");
      return;
    }

    try {
      setSaving(true);
      await apiClient.post<CargoBox>(`/waybills/${waybillId}/boxes`, {
        box_no: boxNo,
        warehouse_waybill_no: optionalText(newBoxDraft.warehouse_waybill_no),
        goods_name: optionalText(newBoxDraft.goods_name),
        quantity: optionalNumber(newBoxDraft.quantity),
        weight: optionalText(newBoxDraft.weight),
        volume: optionalText(newBoxDraft.volume),
        is_general_cargo: newBoxDraft.is_general_cargo
      });
      cancelNewBox();
      onChanged?.();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "新增箱号失败。");
    } finally {
      setSaving(false);
    }
  }

  async function saveBoxNo(item: CargoBox) {
    if (!waybillId) return;
    const nextBoxNo = boxNoDraft.trim();
    if (!nextBoxNo) {
      onError?.("外箱条码不能为空。");
      return;
    }

    try {
      setSaving(true);
      const updated = await apiClient.patch<CargoBox>(`/waybills/${waybillId}/boxes/${item.id}`, {
        box_no: nextBoxNo
      });
      onBoxUpdated?.(updated);
      cancelEditing();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "外箱条码更新失败。");
    } finally {
      setSaving(false);
    }
  }

  async function toggleGeneralCargo(item: CargoBox) {
    if (!waybillId) return;
    try {
      setSaving(true);
      const updated = await apiClient.patch<CargoBox>(`/waybills/${waybillId}/boxes/${item.id}`, {
        is_general_cargo: !item.is_general_cargo
      });
      onBoxUpdated?.(updated);
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "普货标签更新失败。");
    } finally {
      setSaving(false);
    }
  }

  async function deleteBox(item: CargoBox) {
    if (!waybillId) return;
    if (!window.confirm(`确认永久删除箱号 ${item.box_no} 及其箱内明细吗？`)) return;

    try {
      setSaving(true);
      await apiClient.delete<void>(`/waybills/${waybillId}/boxes/${item.id}`);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
      onChanged?.();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "删除箱号失败。");
    } finally {
      setSaving(false);
    }
  }

  async function batchUnbind() {
    if (!selectedIds.size) return;
    try {
      await apiClient.post<BoxBatchOperationResult>("/boxes/batch-unbind", { box_ids: Array.from(selectedIds) });
      setSelectedIds(new Set());
      onChanged?.();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "批量解绑失败。");
    }
  }

  async function batchBind() {
    if (!selectedIds.size || !targetWaybillId) return;
    try {
      await apiClient.post<BoxBatchOperationResult>("/boxes/batch-bind", {
        box_ids: Array.from(selectedIds),
        target_waybill_id: Number(targetWaybillId)
      });
      setSelectedIds(new Set());
      setTargetWaybillId("");
      onChanged?.();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "批量转移失败。");
    }
  }

  async function recalculateVolumes() {
    if (!waybillId) return;
    try {
      setSaving(true);
      const result = await apiClient.post<BoxVolumeRecalculationResult>(`/waybills/${waybillId}/boxes/recalculate-volume`);
      onChanged?.();
      if (result.adjusted) {
        onMessage?.(`方数已按订舱方数 ${formatDecimal(result.booked_volume)} 等比调整：${formatDecimal(result.old_total_volume)} → ${formatDecimal(result.new_total_volume)}。`);
      } else {
        onMessage?.(`当前总方数 ${formatDecimal(result.new_total_volume)} 未超过订舱方数 ${formatDecimal(result.booked_volume)}，无需调整。`);
      }
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "方数计算失败。");
    } finally {
      setSaving(false);
    }
  }

  const totalColumns = readonly ? 9 : 11;

  return (
    <div className="space-y-3">
      {canManageBoxes ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-sm">
          <Button type="button" variant="secondary" size="sm" disabled={newBoxOpen || !canCreateBox} onClick={() => setNewBoxOpen(true)}>
            <Plus className="h-4 w-4" />
            新增箱号
          </Button>
          {!canCreateBox ? <span className="text-slate-500">当前提单没有入仓号，请先上传入仓文件。</span> : null}
          <span className="text-slate-600">已选 {selectedCount} 个箱号</span>
          <Button type="button" variant="secondary" size="sm" disabled={!selectedCount} onClick={() => void batchUnbind()}>
            批量解绑
          </Button>
          <Select value={targetWaybillId} onValueChange={setTargetWaybillId}>
            <SelectTrigger className="w-64">
              <SelectValue placeholder="选择目标提单入仓号" />
            </SelectTrigger>
            <SelectContent>
              {selectableWaybills.map((item) => (
                <SelectItem key={item.id} value={String(item.id)}>
                  {item.waybill_no} - {item.warehouse_no}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button type="button" variant="secondary" size="sm" disabled={!selectedCount || !targetWaybillId} onClick={() => void batchBind()}>
            批量转移
          </Button>
          <div className="flex items-center gap-2 rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700">
            <span>总重量：<strong>{formatDecimal(warehouseTotals.weight)}</strong></span>
            <span className="text-slate-300">|</span>
            <span>总方数：<strong>{formatDecimal(warehouseTotals.volume)}</strong></span>
          </div>
          <Button type="button" variant="secondary" size="sm" disabled={saving || !boxes.length || !bookedVolume} onClick={() => void recalculateVolumes()}>
            <Calculator className="h-4 w-4" />
            方数计算
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-sm">
          <span className="text-slate-700">总重量：<strong>{formatDecimal(warehouseTotals.weight)}</strong></span>
          <span className="text-slate-300">|</span>
          <span className="text-slate-700">总方数：<strong>{formatDecimal(warehouseTotals.volume)}</strong></span>
        </div>
      )}

      {newBoxOpen ? (
        <div className="rounded-md border border-slate-200 bg-white p-3">
          <div className="grid gap-3 md:grid-cols-6">
            <Input
              value={newBoxDraft.box_no}
              onChange={(event) => updateNewBoxDraft("box_no", event.target.value)}
              placeholder="外箱条码"
            />
            <Input
              value={newBoxDraft.warehouse_waybill_no}
              onChange={(event) => updateNewBoxDraft("warehouse_waybill_no", event.target.value)}
              placeholder="仓库文件提单号"
            />
            <Input
              value={newBoxDraft.goods_name}
              onChange={(event) => updateNewBoxDraft("goods_name", event.target.value)}
              placeholder="品名"
            />
            <Input
              type="number"
              min="0"
              step="1"
              value={newBoxDraft.quantity}
              onChange={(event) => updateNewBoxDraft("quantity", event.target.value)}
              placeholder="数量"
            />
            <Input
              type="number"
              min="0"
              step="0.001"
              value={newBoxDraft.weight}
              onChange={(event) => updateNewBoxDraft("weight", event.target.value)}
              placeholder="重量"
            />
            <Input
              type="number"
              min="0"
              step="0.001"
              value={newBoxDraft.volume}
              onChange={(event) => updateNewBoxDraft("volume", event.target.value)}
              placeholder="方数"
            />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <Button
              type="button"
              variant={newBoxDraft.is_general_cargo ? "default" : "secondary"}
              size="sm"
              className={newBoxDraft.is_general_cargo ? "bg-amber-500 text-slate-950 hover:bg-amber-600" : undefined}
              onClick={() => updateNewBoxDraft("is_general_cargo", !newBoxDraft.is_general_cargo)}
            >
              <Tag className="h-4 w-4" />
              普货
            </Button>
            <Button type="button" size="sm" disabled={saving} onClick={() => void createBox()}>
              保存
            </Button>
            <Button type="button" variant="ghost" size="sm" disabled={saving} onClick={cancelNewBox}>
              取消
            </Button>
          </div>
        </div>
      ) : null}

      {!boxes.length ? (
        <EmptyState
          title="暂无入仓箱号"
          description={warehouseNo ? "上传入仓 Excel 文件或手动新增箱号后会显示外箱条码和箱内明细。" : "上传入仓 Excel 文件生成入仓号后，可继续手动新增箱号。"}
        />
      ) : (
        <Table>
          <THead>
            <TR>
              {readonly ? null : <TH>选择</TH>}
              <TH>外箱条码</TH>
              <TH>箱内提单数</TH>
              <TH>首个仓库提单号码</TH>
              <TH>品名</TH>
              <TH>总数量</TH>
              <TH>总重量</TH>
              <TH>箱级方数</TH>
              <TH>重量/方</TH>
              <TH>源行</TH>
              {readonly ? null : <TH>操作</TH>}
            </TR>
          </THead>
          <TBody>
            {boxes.map((item) => {
              const expanded = expandedIds.has(item.id);
              return (
                <Fragment key={item.id}>
                  <TR className={item.is_general_cargo ? "bg-amber-50 hover:bg-amber-100" : undefined}>
                    {readonly ? null : (
                      <TD>
                        <input
                          type="checkbox"
                          checked={selectedIds.has(item.id)}
                          onChange={(event) => toggleSelected(item.id, event.target.checked)}
                        />
                      </TD>
                    )}
                    <TD className="min-w-64 font-medium">
                      {editingBoxId === item.id ? (
                        <div className="flex items-center gap-1">
                          <Input
                            className="h-8 min-w-32"
                            value={boxNoDraft}
                            onChange={(event) => setBoxNoDraft(event.target.value)}
                            onKeyDown={(event) => {
                              if (event.key === "Enter") void saveBoxNo(item);
                              if (event.key === "Escape") cancelEditing();
                            }}
                          />
                          <Button type="button" size="icon" variant="ghost" disabled={saving} onClick={() => void saveBoxNo(item)} aria-label="保存外箱条码">
                            <Check className="h-4 w-4" />
                          </Button>
                          <Button type="button" size="icon" variant="ghost" disabled={saving} onClick={cancelEditing} aria-label="取消编辑外箱条码">
                            <X className="h-4 w-4" />
                          </Button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-1">
                          <Button type="button" size="icon" variant="ghost" onClick={() => toggleExpanded(item.id)} aria-label="展开箱内明细">
                            {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                          </Button>
                          <span>{item.box_no}</span>
                          {item.is_general_cargo ? (
                            <span className="rounded bg-amber-200 px-1.5 py-0.5 text-xs font-semibold text-amber-900">普货</span>
                          ) : null}
                        </div>
                      )}
                    </TD>
                    <TD>{item.items?.length || 0}</TD>
                    <TD>{compact(item.warehouse_waybill_no)}</TD>
                    <TD>{compact(item.goods_name)}</TD>
                    <TD>{compact(item.quantity)}</TD>
                    <TD>{formatDecimal(item.weight)}</TD>
                    <TD>{formatDecimal(item.volume)}</TD>
                    <TD>{formatDecimal(item.weight_volume_ratio)}</TD>
                    <TD>{compact(item.source_row_number)}</TD>
                    {readonly ? null : (
                      <TD>
                        <div className="flex items-center gap-1">
                          <Button
                            type="button"
                            variant={item.is_general_cargo ? "default" : "secondary"}
                            size="sm"
                            className={cn(item.is_general_cargo && "bg-amber-500 text-slate-950 hover:bg-amber-600")}
                            disabled={saving}
                            onClick={() => void toggleGeneralCargo(item)}
                          >
                            <Tag className="h-4 w-4" />
                            {item.is_general_cargo ? "取消普货" : "普货"}
                          </Button>
                          <Button type="button" size="icon" variant="ghost" onClick={() => startEditing(item)} aria-label="编辑外箱条码">
                            <Pencil className="h-4 w-4" />
                          </Button>
                          <Button type="button" size="icon" variant="ghost" disabled={saving} onClick={() => void deleteBox(item)} aria-label="删除箱号">
                            <Trash2 className="h-4 w-4 text-red-600" />
                          </Button>
                        </div>
                      </TD>
                    )}
                  </TR>
                  {expanded ? (
                    <TR className={item.is_general_cargo ? "bg-amber-50" : undefined}>
                      <TD colSpan={totalColumns} className="bg-transparent">
                        {item.items?.length ? (
                          <Table>
                            <THead>
                              <TR>
                                <TH>仓库文件提单号码</TH>
                                <TH>品名</TH>
                                <TH>数量</TH>
                                <TH>重量</TH>
                                <TH>源行</TH>
                              </TR>
                            </THead>
                            <TBody>
                              {item.items.map((detail) => (
                                <TR key={detail.id}>
                                  <TD>{compact(detail.warehouse_waybill_no)}</TD>
                                  <TD>{compact(detail.goods_name)}</TD>
                                  <TD>{compact(detail.quantity)}</TD>
                                  <TD>{formatDecimal(detail.weight)}</TD>
                                  <TD>{compact(detail.source_row_number)}</TD>
                                </TR>
                              ))}
                            </TBody>
                          </Table>
                        ) : (
                          <div className="px-3 py-2 text-sm text-slate-500">暂无箱内明细</div>
                        )}
                      </TD>
                    </TR>
                  ) : null}
                </Fragment>
              );
            })}
          </TBody>
        </Table>
      )}
    </div>
  );
}
