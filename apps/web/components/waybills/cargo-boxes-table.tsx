"use client";

import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { Calculator, ChevronDown, ChevronRight, ListChecks, Pencil, Plus, Tag, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { formatCalculatedVolumeInfo, formatCbm } from "@/lib/box-volume";
import { ApiError, apiClient } from "@/lib/client-api";
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

type BoxEditDraft = NewBoxDraft & {
  weight_volume_ratio: string;
};

type TransferTargetType = "waybill" | "unbound";
type UnboundReason = "customs_inspection" | "other";

type VolumeErrorDialog = {
  message: string;
  details: { label: string; value: string }[];
};

type BatchSelectResult = {
  inputCount: number;
  matchedCount: number;
  missing: string[];
  duplicates: string[];
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

function boxEditDraftFrom(item: CargoBox): BoxEditDraft {
  return {
    box_no: item.box_no || "",
    warehouse_waybill_no: item.warehouse_waybill_no ? String(item.warehouse_waybill_no) : "",
    goods_name: item.goods_name ? String(item.goods_name) : "",
    quantity: item.quantity === null || item.quantity === undefined ? "" : String(item.quantity),
    weight: item.weight === null || item.weight === undefined ? "" : String(item.weight),
    volume: item.volume === null || item.volume === undefined ? "" : String(item.volume),
    weight_volume_ratio: item.weight_volume_ratio === null || item.weight_volume_ratio === undefined ? "" : String(item.weight_volume_ratio),
    is_general_cargo: Boolean(item.is_general_cargo)
  };
}

function formatDecimal(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

function conflictTitle(conflict?: CargoBox["box_conflict"] | null) {
  if (!conflict) return "";
  const receiptName = conflict.source_file_name || conflict.warehouse_no || "-";
  if (conflict.waybill_no) {
    return `与提单 ${conflict.waybill_no} 的入仓号文件 ${receiptName} 冲突`;
  }
  return `与入仓号文件 ${receiptName} 冲突`;
}

function ConflictWaybillBadge({ conflict }: { conflict?: CargoBox["box_conflict"] | null }) {
  if (!conflict) return null;
  return (
    <span
      className="inline-flex rounded bg-violet-100 px-1.5 py-0.5 text-xs font-semibold text-violet-700"
      title={conflictTitle(conflict)}
    >
      冲突运单
    </span>
  );
}

function optionalText(value: string) {
  const trimmed = value.trim();
  return trimmed || undefined;
}

function optionalNumber(value: string) {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : undefined;
}

function nullableText(value: string) {
  const trimmed = value.trim();
  return trimmed || null;
}

function nullableNumber(value: string) {
  const trimmed = value.trim();
  return trimmed ? Number(trimmed) : null;
}

function nullableDecimalText(value: string) {
  const trimmed = value.trim();
  return trimmed || null;
}

function parseBatchSelectText(value: string) {
  const seen = new Set<string>();
  const duplicateSeen = new Set<string>();
  const boxNos: string[] = [];
  const duplicates: string[] = [];

  for (const line of value.split("\n")) {
    const boxNo = line.trim();
    if (!boxNo) continue;
    if (seen.has(boxNo)) {
      if (!duplicateSeen.has(boxNo)) {
        duplicateSeen.add(boxNo);
        duplicates.push(boxNo);
      }
      continue;
    }
    seen.add(boxNo);
    boxNos.push(boxNo);
  }

  return { boxNos, duplicates };
}

function toNumber(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return 0;
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

function volumeCalculationError(error: unknown): VolumeErrorDialog {
  const fallback = error instanceof Error ? error.message : "方数计算失败。";
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== "object") {
    return { message: fallback, details: [] };
  }

  const detail = error.detail as Record<string, unknown>;
  const details = [
    ["错误码", detail.error_code],
    ["目标方数(CBM)", detail.target_volume],
    ["原始总方数(CBM)", detail.original_total_volume],
    ["一箱多件固定方数(CBM)", detail.fixed_total_volume],
    ["可调整方数(CBM)", detail.adjustable_total_volume],
    ["当前总方数(CBM)", detail.total_volume]
  ]
    .filter((item): item is [string, string | number] => item[1] !== undefined && item[1] !== null && item[1] !== "")
    .map(([label, value]) => ({ label, value: String(value) }));

  return {
    message: typeof detail.message === "string" && detail.message ? detail.message : fallback,
    details
  };
}


interface CargoBoxesTableProps {
  boxes: CargoBox[];
  waybillId?: number;
  boxApiBasePath?: string;
  warehouseNo?: string | null;
  warehouseReceiptId?: number | null;
  allowCreate?: boolean;
  readonly?: boolean;
  onBoxUpdated?: (box: CargoBox) => void;
  onBoxDeleted?: (boxId: number) => void;
  onChanged?: () => void;
  onError?: (message: string) => void;
  onMessage?: (message: string) => void;
}

export function CargoBoxesTable({
  boxes,
  waybillId,
  boxApiBasePath,
  warehouseNo,
  warehouseReceiptId,
  allowCreate = true,
  readonly = false,
  onBoxUpdated,
  onBoxDeleted,
  onChanged,
  onError,
  onMessage
}: CargoBoxesTableProps) {
  const [editingBoxId, setEditingBoxId] = useState<number | null>(null);
  const [boxEditDraft, setBoxEditDraft] = useState<BoxEditDraft | null>(null);
  const [newBoxOpen, setNewBoxOpen] = useState(false);
  const [newBoxDraft, setNewBoxDraft] = useState<NewBoxDraft>(() => emptyNewBoxDraft());
  const [saving, setSaving] = useState(false);
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());
  const [selectionAnchorId, setSelectionAnchorId] = useState<number | null>(null);
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());
  const [batchSelectOpen, setBatchSelectOpen] = useState(false);
  const [batchSelectText, setBatchSelectText] = useState("");
  const [batchSelectResult, setBatchSelectResult] = useState<BatchSelectResult | null>(null);
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferTargetType, setTransferTargetType] = useState<TransferTargetType>("waybill");
  const [targetWaybillId, setTargetWaybillId] = useState("");
  const [unboundReason, setUnboundReason] = useState<UnboundReason>("other");
  const [unboundRemark, setUnboundRemark] = useState("");
  const [waybillOptions, setWaybillOptions] = useState<Waybill[]>([]);
  const [volumeError, setVolumeError] = useState<VolumeErrorDialog | null>(null);
  const [volumeCalcOpen, setVolumeCalcOpen] = useState(false);
  const [targetVolumeDraft, setTargetVolumeDraft] = useState("");
  const [targetVolumeError, setTargetVolumeError] = useState("");

  const selectedCount = selectedIds.size;
  const apiBasePath = boxApiBasePath || (waybillId ? `/waybills/${waybillId}` : "");
  const canManageBoxes = Boolean(apiBasePath && !readonly);
  const canCreateBox = Boolean(canManageBoxes && warehouseNo && allowCreate);
  const createDisabledMessage = !warehouseNo
    ? "当前提单没有入仓号，请先上传入仓文件。"
    : !allowCreate
      ? "手动新增箱号仅支持当前提单最近入仓号。"
      : "";
  const selectableWaybills = useMemo(
    () => waybillOptions.filter((item) => item.id !== waybillId && Boolean(item.warehouse_no)),
    [waybillId, waybillOptions]
  );
  const boxIds = useMemo(() => boxes.map((item) => item.id), [boxes]);
  const boxByNo = useMemo(() => new Map(boxes.map((item) => [item.box_no, item])), [boxes]);
  const editingBox = useMemo(() => boxes.find((item) => item.id === editingBoxId) || null, [boxes, editingBoxId]);
  const batchSelectDraft = useMemo(() => parseBatchSelectText(batchSelectText), [batchSelectText]);
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
      .get<PageResponse<Waybill>>("/waybills?page=1&page_size=100")
      .then((data) => setWaybillOptions(data.items))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (selectedCount > 0) loadWaybillOptions();
  }, [loadWaybillOptions, selectedCount]);

  function updateNewBoxDraft<K extends keyof NewBoxDraft>(key: K, value: NewBoxDraft[K]) {
    setNewBoxDraft((prev) => ({ ...prev, [key]: value }));
  }

  function updateBoxEditDraft<K extends keyof BoxEditDraft>(key: K, value: BoxEditDraft[K]) {
    setBoxEditDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function startEditing(item: CargoBox) {
    setEditingBoxId(item.id);
    setBoxEditDraft(boxEditDraftFrom(item));
  }

  function cancelEditing() {
    setEditingBoxId(null);
    setBoxEditDraft(null);
  }

  function cancelNewBox() {
    setNewBoxOpen(false);
    setNewBoxDraft(emptyNewBoxDraft());
  }

  function toggleSelected(id: number, checked: boolean, shiftKey = false) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      const currentIndex = boxIds.indexOf(id);
      const anchorIndex = selectionAnchorId === null ? -1 : boxIds.indexOf(selectionAnchorId);

      if (shiftKey && currentIndex >= 0 && anchorIndex >= 0) {
        const start = Math.min(currentIndex, anchorIndex);
        const end = Math.max(currentIndex, anchorIndex);
        for (const rangeId of boxIds.slice(start, end + 1)) {
          if (checked) next.add(rangeId);
          else next.delete(rangeId);
        }
      } else if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
    setSelectionAnchorId(id);
  }

  function toggleExpanded(id: number) {
    setExpandedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function closeBatchSelectDialog() {
    setBatchSelectOpen(false);
    setBatchSelectText("");
  }

  function confirmBatchSelect() {
    const matchedIds = new Set<number>();
    const missing: string[] = [];

    for (const boxNo of batchSelectDraft.boxNos) {
      const box = boxByNo.get(boxNo);
      if (box) matchedIds.add(box.id);
      else missing.push(boxNo);
    }

    setSelectedIds(matchedIds);
    setSelectionAnchorId(null);
    closeBatchSelectDialog();
    setBatchSelectResult({
      inputCount: batchSelectDraft.boxNos.length,
      matchedCount: matchedIds.size,
      missing,
      duplicates: batchSelectDraft.duplicates
    });
  }

  async function createBox() {
    if (!apiBasePath) return;
    const boxNo = newBoxDraft.box_no.trim();
    if (!boxNo) {
      onError?.("外箱条码不能为空。");
      return;
    }

    try {
      setSaving(true);
      await apiClient.post<CargoBox>(`${apiBasePath}/boxes`, {
        box_no: boxNo,
        warehouse_receipt_id: warehouseReceiptId || undefined,
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

  async function saveBoxEdit() {
    if (!apiBasePath || !editingBox || !boxEditDraft) return;
    const nextBoxNo = boxEditDraft.box_no.trim();
    if (!nextBoxNo) {
      onError?.("外箱条码不能为空。");
      return;
    }

    try {
      setSaving(true);
      const ratioDraft = boxEditDraft.weight_volume_ratio.trim();
      const originalRatio = editingBox.weight_volume_ratio === null || editingBox.weight_volume_ratio === undefined ? "" : String(editingBox.weight_volume_ratio).trim();
      const payload: Record<string, unknown> = {
        box_no: nextBoxNo,
        warehouse_waybill_no: nullableText(boxEditDraft.warehouse_waybill_no),
        goods_name: nullableText(boxEditDraft.goods_name),
        quantity: nullableNumber(boxEditDraft.quantity),
        weight: nullableDecimalText(boxEditDraft.weight),
        volume: nullableDecimalText(boxEditDraft.volume),
        is_general_cargo: boxEditDraft.is_general_cargo
      };
      if (ratioDraft !== originalRatio) {
        payload.weight_volume_ratio = nullableDecimalText(boxEditDraft.weight_volume_ratio);
      }
      const updated = await apiClient.patch<CargoBox>(`${apiBasePath}/boxes/${editingBox.id}`, payload);
      onBoxUpdated?.(updated);
      onChanged?.();
      cancelEditing();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "箱号数据更新失败。");
    } finally {
      setSaving(false);
    }
  }

  async function toggleGeneralCargo(item: CargoBox) {
    if (!apiBasePath) return;
    try {
      setSaving(true);
      const updated = await apiClient.patch<CargoBox>(`${apiBasePath}/boxes/${item.id}`, {
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
    if (!apiBasePath) return;
    if (!window.confirm(`确认永久删除箱号 ${item.box_no} 及其箱内明细吗？`)) return;

    try {
      setSaving(true);
      await apiClient.delete<void>(`${apiBasePath}/boxes/${item.id}`);
      setSelectedIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
      onBoxDeleted?.(item.id);
      onChanged?.();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "删除箱号失败。");
    } finally {
      setSaving(false);
    }
  }

  function closeTransferDialog() {
    setTransferOpen(false);
    setTransferTargetType("waybill");
    setTargetWaybillId("");
    setUnboundReason("other");
    setUnboundRemark("");
  }

  async function submitTransfer() {
    if (!selectedIds.size) return;
    if (transferTargetType === "waybill" && !targetWaybillId) {
      onError?.("请选择目标提单入仓号。");
      return;
    }

    try {
      setSaving(true);
      const payload =
        transferTargetType === "waybill"
          ? {
              box_ids: Array.from(selectedIds),
              target_type: "waybill",
              target_waybill_id: Number(targetWaybillId)
            }
          : {
              box_ids: Array.from(selectedIds),
              target_type: "unbound",
              unbound_reason: unboundReason,
              unbound_remark: optionalText(unboundRemark)
            };
      await apiClient.post<BoxBatchOperationResult>("/boxes/batch-transfer", payload);
      closeTransferDialog();
      setSelectedIds(new Set());
      onChanged?.();
    } catch (error) {
      onError?.(error instanceof Error ? error.message : "批量转移失败。");
    } finally {
      setSaving(false);
    }
  }

  function openVolumeCalculationDialog() {
    setTargetVolumeDraft(warehouseTotals.volume > 0 ? warehouseTotals.volume.toFixed(3).replace(/\.?0+$/, "") : "");
    setTargetVolumeError("");
    setVolumeCalcOpen(true);
  }

  async function recalculateVolumes() {
    if (!apiBasePath) return;
    const targetVolume = Number(targetVolumeDraft);
    if (!Number.isFinite(targetVolume) || targetVolume <= 0) {
      setTargetVolumeError("请输入大于 0 的目标方数。");
      return;
    }
    try {
      setSaving(true);
      const result = await apiClient.post<BoxVolumeRecalculationResult>(`${apiBasePath}/boxes/recalculate-volume`, {
        target_volume: targetVolume,
        warehouse_receipt_id: warehouseReceiptId || undefined
      });
      setVolumeCalcOpen(false);
      onChanged?.();
      if (result.adjusted) {
        onMessage?.(
          `方数已按目标 ${formatDecimal(result.target_volume)} CBM 等比调整：${formatDecimal(result.old_total_volume)} → ${formatDecimal(result.new_total_volume)}。一箱多件固定 ${formatDecimal(result.fixed_total_volume)} CBM，调整一箱一件 ${result.adjusted_box_count} 个。`
        );
      } else {
        onMessage?.(`当前总方数已等于目标 ${formatDecimal(result.target_volume)} CBM，无需调整。`);
      }
    } catch (error) {
      setVolumeCalcOpen(false);
      setVolumeError(volumeCalculationError(error));
    } finally {
      setSaving(false);
    }
  }

  const totalColumns = readonly ? 11 : 13;

  return (
    <>
    <div className="space-y-3">
      {canManageBoxes ? (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-sm">
          <Button type="button" variant="secondary" size="sm" disabled={newBoxOpen || !canCreateBox} onClick={() => setNewBoxOpen(true)}>
            <Plus className="h-4 w-4" />
            新增箱号
          </Button>
          {!canCreateBox ? <span className="text-slate-500">{createDisabledMessage}</span> : null}
          <span className="text-slate-600">已选 {selectedCount} 个箱号</span>
          <Button type="button" variant="secondary" size="sm" disabled={!boxes.length} onClick={() => setBatchSelectOpen(true)}>
            <ListChecks className="h-4 w-4" />
            批量选中
          </Button>
          <Button type="button" variant="secondary" size="sm" disabled={!selectedCount} onClick={() => setTransferOpen(true)}>
            转移
          </Button>
          <div className="flex items-center gap-2 rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700">
            <span>总重量：<strong>{formatDecimal(warehouseTotals.weight)}</strong></span>
            <span className="text-slate-300">|</span>
            <span>总方数(CBM)：<strong>{formatDecimal(warehouseTotals.volume)}</strong></span>
          </div>
          <Button type="button" variant="secondary" size="sm" disabled={saving || !boxes.length} onClick={openVolumeCalculationDialog}>
            <Calculator className="h-4 w-4" />
            方数计算
          </Button>
        </div>
      ) : (
        <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-slate-50 p-2 text-sm">
          <span className="text-slate-700">总重量：<strong>{formatDecimal(warehouseTotals.weight)}</strong></span>
          <span className="text-slate-300">|</span>
          <span className="text-slate-700">总方数(CBM)：<strong>{formatDecimal(warehouseTotals.volume)}</strong></span>
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
              placeholder="方数(CBM)"
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
              <TH>原始收货体积信息</TH>
              <TH>原始收货重量/方</TH>
              <TH>收货体积信息</TH>
              <TH>收货重量/方(CBM)</TH>
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
                          onChange={(event) =>
                            toggleSelected(
                              item.id,
                              event.target.checked,
                              event.nativeEvent instanceof MouseEvent ? event.nativeEvent.shiftKey : false
                            )
                          }
                        />
                      </TD>
                    )}
                    <TD className="min-w-64 font-medium">
                      <div className="flex items-center gap-1">
                        <Button type="button" size="icon" variant="ghost" onClick={() => toggleExpanded(item.id)} aria-label="展开箱内明细">
                          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                        </Button>
                        <span>{item.box_no}</span>
                        {item.is_general_cargo ? (
                          <span className="rounded bg-amber-200 px-1.5 py-0.5 text-xs font-semibold text-amber-900">普货</span>
                        ) : null}
                      </div>
                    </TD>
                    <TD>{item.items?.length || 0}</TD>
                    <TD>
                      <div className="flex flex-wrap items-center gap-1">
                        <span>{compact(item.warehouse_waybill_no)}</span>
                        <ConflictWaybillBadge conflict={item.box_conflict} />
                      </div>
                    </TD>
                    <TD>{compact(item.goods_name)}</TD>
                    <TD>{compact(item.quantity)}</TD>
                    <TD>{formatDecimal(item.weight)}</TD>
                    <TD>{compact(item.original_volume_info)}</TD>
                    <TD>{compact(item.original_weight_volume_ratio)}</TD>
                    <TD>{formatCalculatedVolumeInfo(item)}</TD>
                    <TD>{formatCbm(item.volume)}</TD>
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
                          <Button type="button" size="icon" variant="ghost" onClick={() => startEditing(item)} aria-label="编辑箱号数据">
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
                                  <TD>
                                    <div className="flex flex-wrap items-center gap-1">
                                      <span>{compact(detail.warehouse_waybill_no)}</span>
                                      <ConflictWaybillBadge conflict={item.box_conflict} />
                                    </div>
                                  </TD>
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
      <Dialog open={Boolean(editingBox && boxEditDraft)} onOpenChange={(open) => !open && cancelEditing()}>
        <DialogContent className="w-[min(720px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">编辑箱号数据</DialogTitle>
          {boxEditDraft ? (
            <div className="mt-3 space-y-4">
              <div className="grid gap-3 md:grid-cols-2">
                <label className="space-y-1 text-sm">
                  <span className="text-slate-700">外箱条码</span>
                  <Input value={boxEditDraft.box_no} onChange={(event) => updateBoxEditDraft("box_no", event.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-700">仓库文件提单号</span>
                  <Input value={boxEditDraft.warehouse_waybill_no} onChange={(event) => updateBoxEditDraft("warehouse_waybill_no", event.target.value)} />
                </label>
                <label className="space-y-1 text-sm md:col-span-2">
                  <span className="text-slate-700">品名</span>
                  <Input value={boxEditDraft.goods_name} onChange={(event) => updateBoxEditDraft("goods_name", event.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-700">数量</span>
                  <Input type="number" min="0" step="1" value={boxEditDraft.quantity} onChange={(event) => updateBoxEditDraft("quantity", event.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-700">重量</span>
                  <Input type="number" min="0" step="0.001" value={boxEditDraft.weight} onChange={(event) => updateBoxEditDraft("weight", event.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-700">方数(CBM)</span>
                  <Input type="number" min="0" step="0.001" value={boxEditDraft.volume} onChange={(event) => updateBoxEditDraft("volume", event.target.value)} />
                </label>
                <label className="space-y-1 text-sm">
                  <span className="text-slate-700">重量/方</span>
                  <Input type="number" min="0" step="0.001" value={boxEditDraft.weight_volume_ratio} onChange={(event) => updateBoxEditDraft("weight_volume_ratio", event.target.value)} />
                </label>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={boxEditDraft.is_general_cargo}
                  onChange={(event) => updateBoxEditDraft("is_general_cargo", event.target.checked)}
                />
                普货
              </label>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" disabled={saving} onClick={cancelEditing}>
                  取消
                </Button>
                <Button type="button" disabled={saving} onClick={() => void saveBoxEdit()}>
                  保存
                </Button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
      <Dialog open={batchSelectOpen} onOpenChange={(open) => (open ? setBatchSelectOpen(true) : closeBatchSelectDialog())}>
        <DialogContent className="w-[min(620px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">批量选中箱号</DialogTitle>
          <div className="mt-3 space-y-3">
            <Textarea
              value={batchSelectText}
              onChange={(event) => setBatchSelectText(event.target.value)}
              placeholder={"每行输入一个外箱条码\nBOX-001\nBOX-002"}
              rows={10}
            />
            <div className="flex flex-wrap gap-3 text-sm text-slate-600">
              <span>已填写 {batchSelectDraft.boxNos.length} 个外箱</span>
              {batchSelectDraft.duplicates.length ? (
                <span className="text-amber-700">重复 {batchSelectDraft.duplicates.length} 个，已按首次出现计数</span>
              ) : null}
            </div>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button type="button" variant="secondary" onClick={closeBatchSelectDialog}>
              取消
            </Button>
            <Button type="button" disabled={!batchSelectDraft.boxNos.length} onClick={confirmBatchSelect}>
              确定
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(batchSelectResult)} onOpenChange={(open) => !open && setBatchSelectResult(null)}>
        <DialogContent className="w-[min(620px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">
            {batchSelectResult?.missing.length ? "批量选中完成，部分未找到" : "批量选中成功"}
          </DialogTitle>
          <div className="mt-3 space-y-3 text-sm">
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
              已填写 {batchSelectResult?.inputCount ?? 0} 个外箱，已勾选 {batchSelectResult?.matchedCount ?? 0} 个，
              未找到 {batchSelectResult?.missing.length ?? 0} 个。
            </div>
            {batchSelectResult?.duplicates.length ? (
              <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-900">
                <div className="font-medium">重复输入</div>
                <div className="mt-1 max-h-28 overflow-auto break-words">
                  {batchSelectResult.duplicates.join("、")}
                </div>
              </div>
            ) : null}
            {batchSelectResult?.missing.length ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-800">
                <div className="font-medium">未找到的外箱条码</div>
                <div className="mt-1 max-h-40 overflow-auto break-words">
                  {batchSelectResult.missing.join("、")}
                </div>
              </div>
            ) : null}
          </div>
          <div className="mt-5 flex justify-end">
            <Button type="button" onClick={() => setBatchSelectResult(null)}>
              知道了
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={transferOpen} onOpenChange={(open) => (open ? setTransferOpen(true) : closeTransferDialog())}>
        <DialogContent className="w-[min(620px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">转移箱号</DialogTitle>
          <div className="mt-3 space-y-4">
            <div className="text-sm text-slate-600">已选 {selectedCount} 个箱号</div>
            <div className="grid gap-2 sm:grid-cols-2">
              <Button
                type="button"
                variant={transferTargetType === "waybill" ? "default" : "secondary"}
                onClick={() => setTransferTargetType("waybill")}
              >
                转移到目标提单入仓号
              </Button>
              <Button
                type="button"
                variant={transferTargetType === "unbound" ? "default" : "secondary"}
                onClick={() => setTransferTargetType("unbound")}
              >
                转移到未绑定箱号池
              </Button>
            </div>

            {transferTargetType === "waybill" ? (
              <div className="space-y-2">
                <div className="text-sm font-medium text-slate-700">目标提单入仓号</div>
                <Select value={targetWaybillId} onValueChange={setTargetWaybillId}>
                  <SelectTrigger>
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
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">转移原因</div>
                  <Select value={unboundReason} onValueChange={(value) => setUnboundReason(value as UnboundReason)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="other">其他</SelectItem>
                      <SelectItem value="customs_inspection">海关查验</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-medium text-slate-700">备注</div>
                  <Textarea
                    value={unboundRemark}
                    onChange={(event) => setUnboundRemark(event.target.value)}
                    placeholder="可填写补充说明"
                    rows={3}
                  />
                </div>
              </div>
            )}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button type="button" variant="secondary" disabled={saving} onClick={closeTransferDialog}>
              取消
            </Button>
            <Button
              type="button"
              disabled={saving || !selectedCount || (transferTargetType === "waybill" && !targetWaybillId)}
              onClick={() => void submitTransfer()}
            >
              确认转移
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={volumeCalcOpen} onOpenChange={(open) => !saving && setVolumeCalcOpen(open)}>
        <DialogContent>
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">方数计算</DialogTitle>
          <div className="mt-3 space-y-3">
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              当前总方数 {formatDecimal(warehouseTotals.volume)} CBM。请输入希望当前入仓号调整到的目标总方数；系统只会等比调整一箱一件的箱号，一箱多件箱号保持原始方数。
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-700" htmlFor="target-volume">
                目标总方数(CBM)
              </label>
              <Input
                id="target-volume"
                type="number"
                min="0.001"
                step="0.001"
                value={targetVolumeDraft}
                onChange={(event) => {
                  setTargetVolumeDraft(event.target.value);
                  setTargetVolumeError("");
                }}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    void recalculateVolumes();
                  }
                }}
              />
              {targetVolumeError ? <div className="text-xs text-red-600">{targetVolumeError}</div> : null}
            </div>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button type="button" variant="secondary" disabled={saving} onClick={() => setVolumeCalcOpen(false)}>
              取消
            </Button>
            <Button type="button" disabled={saving} onClick={() => void recalculateVolumes()}>
              确认计算
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(volumeError)} onOpenChange={(open) => !open && setVolumeError(null)}>
        <DialogContent>
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">方数计算失败</DialogTitle>
          <div className="mt-3 space-y-3">
            <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
              {volumeError?.message || "方数计算失败。"}
            </div>
            {volumeError?.details.length ? (
              <div className="rounded-md border border-slate-200">
                {volumeError.details.map((item) => (
                  <div key={item.label} className="grid grid-cols-[140px_1fr] border-b border-slate-100 px-3 py-2 text-sm last:border-b-0">
                    <span className="text-slate-500">{item.label}</span>
                    <span className="font-medium text-slate-900">{item.value}</span>
                  </div>
                ))}
              </div>
            ) : null}
          </div>
          <div className="mt-4 flex justify-end">
            <Button type="button" onClick={() => setVolumeError(null)}>
              知道了
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
