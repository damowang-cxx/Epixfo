"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Archive, Calculator, ChevronDown, ChevronRight, Download, GripVertical, MoveRight, Pencil, RefreshCw, Trash2, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { formatCalculatedVolumeInfo } from "@/lib/box-volume";
import { ApiError, apiClient } from "@/lib/client-api";
import { compact, formatDateTime } from "@/lib/utils";
import type {
  BoxBatchOperationResult,
  BoxVolumeRecalculationResult,
  CargoBox,
  PageResponse,
  WarehouseBoxConflict,
  WarehouseChannelReviewIssue,
  WarehouseFileImportError,
  WarehouseFileUploadResult,
  WarehouseProhibitedGoodsIssue,
  WarehouseReceiptBatchDeleteResult,
  WarehouseUploadIntegrityIssue,
  WarehouseReceipt,
  Waybill
} from "@/lib/types";

type TransferMode = "receipt" | "unbound";
type TransferSource = "receipt" | "scatter";
type RightPanelMode = "scatter" | "receipt_summary";
type UnboundReason = "customs_inspection" | "other";

const UNBOUND_REASON_LABELS: Record<string, string> = {
  customs_inspection: "海关查验",
  other: "其他"
};

interface UploadConflict {
  box_no?: string;
  current_waybill_id?: number | null;
  current_warehouse_no?: string | null;
}

interface BatchUploadSuccess {
  file_name: string;
  warehouse_no: string;
  uploaded_at: string;
  success_count: number;
  detected_channel?: string | null;
  warnings: string[];
  issues: WarehouseChannelReviewIssue[];
  integrity_issues: WarehouseUploadIntegrityIssue[];
  prohibited_goods_issues: WarehouseProhibitedGoodsIssue[];
  errors: WarehouseFileImportError[];
  channel_tags: string[];
}

interface BatchUploadFailure {
  file_name: string;
  warehouse_no?: string | null;
  message: string;
  detected_channel?: string | null;
  warnings: string[];
  issues: WarehouseChannelReviewIssue[];
  integrity_issues: WarehouseUploadIntegrityIssue[];
  conflicts: Array<UploadConflict | WarehouseBoxConflict>;
}

interface BatchUploadResult {
  successes: BatchUploadSuccess[];
  failures: BatchUploadFailure[];
}

interface VolumeErrorDialog {
  message: string;
  details: { label: string; value: string }[];
}

interface BoxEditDraft {
  box_no: string;
  warehouse_waybill_no: string;
  goods_name: string;
  quantity: string;
  weight: string;
  volume: string;
  weight_volume_ratio: string;
  is_general_cargo: boolean;
}

const CHANNEL_LABELS: Record<string, string> = {
  europe: "欧洲",
  uk: "英国",
  unknown: "待确认",
  mixed: "混合"
};

const WARNING_LABELS: Record<string, string> = {
  dpd_only_channel_pending: "全部为 DPD 箱号，渠道待确认"
};

function reasonLabel(reason?: string | null) {
  if (!reason) return "";
  return UNBOUND_REASON_LABELS[reason] || reason;
}

function formatDecimal(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

function formatTargetVolumeRange(value?: string | number | null) {
  const num = Number(value);
  if (!Number.isFinite(num)) return `${formatDecimal(value)}~${formatDecimal(value)}`;
  return `${formatDecimal(num)}~${formatDecimal(num + 0.5)}`;
}

function formatReceiptDensity(receipt: WarehouseReceipt) {
  const volume = Number(receipt.total_volume);
  if (!Number.isFinite(volume) || volume <= 0) return "-";
  return formatDecimal(receipt.weight_volume_ratio);
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
    <span title={conflictTitle(conflict)}>
      <Badge variant="amber">冲突运单</Badge>
    </span>
  );
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

function volumeCalculationError(error: unknown): VolumeErrorDialog {
  const fallback = error instanceof Error ? error.message : "方数计算失败。";
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== "object") {
    return { message: fallback, details: [] };
  }

  const detail = error.detail as Record<string, unknown>;
  const details = [
    ["错误码", detail.error_code],
    ["目标方数(CBM)", detail.target_volume],
    ["目标方数上限(CBM)", detail.target_volume_upper],
    ["原始总方数(CBM)", detail.original_total_volume],
    ["固定箱号方数(CBM)", detail.fixed_total_volume],
    ["可整数调整方数(CBM)", detail.adjustable_total_volume],
    ["当前总方数(CBM)", detail.total_volume]
  ]
    .filter((item): item is [string, string | number] => item[1] !== undefined && item[1] !== null && item[1] !== "")
    .map(([label, value]) => ({ label, value: String(value) }));

  return {
    message: typeof detail.message === "string" && detail.message ? detail.message : fallback,
    details
  };
}

function receiptLabel(item: WarehouseReceipt) {
  if (item.waybill_no) {
    return `${item.warehouse_no} · 已绑定提单 ${item.waybill_no}`;
  }
  if (item.prebooking_id) {
    const label = item.prebooking_label || `#${item.prebooking_id}`;
    return `${item.warehouse_no} · 预排仓 ${label}`;
  }
  return `${item.warehouse_no} · 未绑定`;
}

function channelTags(tags?: string[] | null) {
  return (tags || []).filter(Boolean);
}

function channelLabel(value?: string | null) {
  if (!value) return "";
  return CHANNEL_LABELS[value] || value;
}

function warningLabel(value: string) {
  return WARNING_LABELS[value] || value;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

function parseConflicts(error: unknown) {
  if (!(error instanceof ApiError) || !error.detail || typeof error.detail !== "object") return [];
  const detail = error.detail as { conflicts?: unknown };
  if (!Array.isArray(detail.conflicts)) return [];
  return detail.conflicts.filter((item): item is UploadConflict => Boolean(item) && typeof item === "object");
}

function parseIssues(value: unknown): WarehouseChannelReviewIssue[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is WarehouseChannelReviewIssue =>
      Boolean(item) &&
      typeof item === "object" &&
      typeof (item as WarehouseChannelReviewIssue).box_no === "string" &&
      typeof (item as WarehouseChannelReviewIssue).prefix === "string" &&
      typeof (item as WarehouseChannelReviewIssue).reason === "string" &&
      typeof (item as WarehouseChannelReviewIssue).message === "string"
  );
}

function parseIntegrityIssues(value: unknown): WarehouseUploadIntegrityIssue[] {
  if (!Array.isArray(value)) return [];
  return value.filter(
    (item): item is WarehouseUploadIntegrityIssue =>
      Boolean(item) &&
      typeof item === "object" &&
      typeof (item as WarehouseUploadIntegrityIssue).row_number === "number" &&
      typeof (item as WarehouseUploadIntegrityIssue).box_no === "string" &&
      typeof (item as WarehouseUploadIntegrityIssue).message === "string"
  );
}

function parseWarnings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === "string") : [];
}

function uploadFailureFromError(file: File, error: unknown): BatchUploadFailure {
  if (error instanceof ApiError && error.detail && typeof error.detail === "object") {
    const detail = error.detail as Record<string, unknown>;
    return {
      file_name: typeof detail.file_name === "string" ? detail.file_name : file.name,
      warehouse_no: typeof detail.warehouse_no === "string" ? detail.warehouse_no : undefined,
      message: error.message,
      detected_channel: typeof detail.detected_channel === "string" ? detail.detected_channel : undefined,
      warnings: parseWarnings(detail.warnings),
      issues: parseIssues(detail.issues),
      integrity_issues: parseIntegrityIssues(detail.issues),
      conflicts: parseConflicts(error)
    };
  }
  return {
    file_name: file.name,
    message: error instanceof Error ? error.message : "上传入仓文件失败。",
    warnings: [],
    issues: [],
    integrity_issues: [],
    conflicts: []
  };
}

function successWarningCount(item: BatchUploadSuccess) {
  return (
    item.warnings.length +
    item.issues.length +
    item.integrity_issues.length +
    item.prohibited_goods_issues.length +
    item.errors.length
  );
}

export default function WarehouseReceiptsPage() {
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const [receipts, setReceipts] = useState<PageResponse<WarehouseReceipt> | null>(null);
  const [receiptPage, setReceiptPage] = useState(1);
  const [allReceipts, setAllReceipts] = useState<WarehouseReceipt[]>([]);
  const [expandedReceiptId, setExpandedReceiptId] = useState<number | null>(null);
  const [boxesByReceipt, setBoxesByReceipt] = useState<Record<number, CargoBox[]>>({});
  const [selectedReceiptIds, setSelectedReceiptIds] = useState<Set<number>>(new Set());
  const [selectedReceiptBoxIds, setSelectedReceiptBoxIds] = useState<Set<number>>(new Set());
  const [receiptSelectionAnchor, setReceiptSelectionAnchor] = useState<number | null>(null);
  const [scatterData, setScatterData] = useState<PageResponse<CargoBox> | null>(null);
  const [scatterPage, setScatterPage] = useState(1);
  const [selectedScatterIds, setSelectedScatterIds] = useState<Set<number>>(new Set());
  const [scatterSelectionAnchor, setScatterSelectionAnchor] = useState<number | null>(null);
  const [waybillOptions, setWaybillOptions] = useState<Waybill[]>([]);
  const [bindReceiptId, setBindReceiptId] = useState<number | null>(null);
  const [targetWaybillId, setTargetWaybillId] = useState("");
  const [transferOpen, setTransferOpen] = useState(false);
  const [transferSource, setTransferSource] = useState<TransferSource>("receipt");
  const [transferMode, setTransferMode] = useState<TransferMode>("receipt");
  const [targetReceiptId, setTargetReceiptId] = useState("");
  const [unboundReason, setUnboundReason] = useState<UnboundReason>("other");
  const [unboundRemark, setUnboundRemark] = useState("");
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [exportingReceiptId, setExportingReceiptId] = useState<number | null>(null);
  const [receiptOrderSaving, setReceiptOrderSaving] = useState(false);
  const [receiptSortDragId, setReceiptSortDragId] = useState<number | null>(null);
  const [receiptOptionsLoading, setReceiptOptionsLoading] = useState(false);
  const [receiptOptionsError, setReceiptOptionsError] = useState("");
  const [rightPanelMode, setRightPanelMode] = useState<RightPanelMode>("scatter");
  const [message, setMessage] = useState("");
  const [batchUploadResult, setBatchUploadResult] = useState<BatchUploadResult | null>(null);
  const [volumeReceipt, setVolumeReceipt] = useState<WarehouseReceipt | null>(null);
  const [targetVolumeDraft, setTargetVolumeDraft] = useState("");
  const [targetVolumeError, setTargetVolumeError] = useState("");
  const [volumeError, setVolumeError] = useState<VolumeErrorDialog | null>(null);
  const [editingReceiptBox, setEditingReceiptBox] = useState<{ receiptId: number; box: CargoBox } | null>(null);
  const [boxEditDraft, setBoxEditDraft] = useState<BoxEditDraft | null>(null);

  const selectedTransferIds = transferSource === "receipt" ? selectedReceiptBoxIds : selectedScatterIds;
  const targetReceiptGroups = useMemo(() => {
    const sourceReceiptId = transferSource === "receipt" ? expandedReceiptId : null;
    const options = allReceipts.filter((item) => item.id !== sourceReceiptId);
    return [
      {
        key: "unbound",
        label: "未绑定入仓号",
        items: options.filter((item) => !item.waybill_id && !item.prebooking_id)
      },
      {
        key: "prebooking",
        label: "预排仓入仓号",
        items: options.filter((item) => Boolean(item.prebooking_id))
      },
      {
        key: "waybill",
        label: "提单管理入仓号",
        items: options.filter((item) => Boolean(item.waybill_id))
      }
    ];
  }, [allReceipts, expandedReceiptId, transferSource]);
  const hasTargetReceipts = targetReceiptGroups.some((group) => group.items.length > 0);
  const unboundReceiptSummaries = useMemo(
    () => allReceipts.filter((item) => !item.waybill_id && !item.prebooking_id),
    [allReceipts]
  );

  const loadReceipts = useCallback(() => {
    apiClient
      .get<PageResponse<WarehouseReceipt>>(`/warehouse-receipts/unbound?page=${receiptPage}&page_size=20`)
      .then(setReceipts);
  }, [receiptPage]);

  const loadReceiptPage = useCallback((page: number) => {
    return apiClient
      .get<PageResponse<WarehouseReceipt>>(`/warehouse-receipts/unbound?page=${page}&page_size=20`)
      .then(setReceipts);
  }, []);

  const loadAllReceipts = useCallback(async () => {
    setReceiptOptionsLoading(true);
    setReceiptOptionsError("");
    try {
      const firstPage = await apiClient.get<PageResponse<WarehouseReceipt>>("/warehouse-receipts?page=1&page_size=100");
      const items = [...firstPage.items];
      const pageSize = firstPage.page_size || 100;
      const totalPages = Math.ceil(firstPage.total / pageSize);
      for (let page = 2; page <= totalPages; page += 1) {
        const data = await apiClient.get<PageResponse<WarehouseReceipt>>(`/warehouse-receipts?page=${page}&page_size=${pageSize}`);
        items.push(...data.items);
      }
      setAllReceipts(items);
    } catch (error) {
      setAllReceipts([]);
      setReceiptOptionsError(error instanceof Error ? error.message : "加载目标入仓号失败。");
    } finally {
      setReceiptOptionsLoading(false);
    }
  }, []);

  const loadScatter = useCallback(() => {
    apiClient.get<PageResponse<CargoBox>>(`/boxes/unbound?page=${scatterPage}&page_size=20`).then(setScatterData);
  }, [scatterPage]);

  const loadWaybills = useCallback(() => {
    apiClient
      .get<PageResponse<Waybill>>("/waybills?page=1&page_size=100")
      .then((data) => setWaybillOptions(data.items))
      .catch(() => setWaybillOptions([]));
  }, []);

  const refreshAll = useCallback(() => {
    loadReceipts();
    loadAllReceipts();
    loadScatter();
    loadWaybills();
  }, [loadAllReceipts, loadReceipts, loadScatter, loadWaybills]);

  useEffect(() => {
    void Promise.resolve().then(refreshAll);
  }, [refreshAll]);

  useEffect(() => {
    if (expandedReceiptId === null || boxesByReceipt[expandedReceiptId]) return;
    apiClient
      .get<CargoBox[]>(`/warehouse-receipts/${expandedReceiptId}/boxes`)
      .then((items) => setBoxesByReceipt((prev) => ({ ...prev, [expandedReceiptId]: items })));
  }, [boxesByReceipt, expandedReceiptId]);

  const receiptBoxIds = useMemo(() => {
    if (expandedReceiptId === null) return [];
    return (boxesByReceipt[expandedReceiptId] || []).map((item) => item.id);
  }, [boxesByReceipt, expandedReceiptId]);

  const scatterBoxIds = useMemo(() => (scatterData?.items || []).map((item) => item.id), [scatterData?.items]);

  async function persistReceiptOrder(nextOrderedReceipts: WarehouseReceipt[], currentPageIds: Set<number>) {
    setReceipts((prev) =>
      prev
        ? {
            ...prev,
            items: nextOrderedReceipts.filter((item) => currentPageIds.has(item.id))
          }
        : prev
    );
    setAllReceipts((prev) => [
      ...nextOrderedReceipts,
      ...prev.filter((item) => item.waybill_id || item.prebooking_id)
    ]);
    setReceiptOrderSaving(true);
    setMessage("");
    try {
      await apiClient.put<void>("/warehouse-receipts/unbound/order", {
        receipt_ids: nextOrderedReceipts.map((item) => item.id)
      });
      void loadAllReceipts();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存入仓号排序失败。");
      refreshAll();
    } finally {
      setReceiptOrderSaving(false);
    }
  }

  function moveUnboundReceiptBefore(dragId: number, targetId: number) {
    if (dragId === targetId) return;
    const baseReceipts = unboundReceiptSummaries.length ? unboundReceiptSummaries : receipts?.items || [];
    const source = baseReceipts.find((item) => item.id === dragId);
    const target = baseReceipts.find((item) => item.id === targetId);
    if (!source || !target) return;

    const withoutSource = baseReceipts.filter((item) => item.id !== dragId);
    const targetIndex = withoutSource.findIndex((item) => item.id === targetId);
    if (targetIndex < 0) return;

    const nextOrderedReceipts = [
      ...withoutSource.slice(0, targetIndex),
      source,
      ...withoutSource.slice(targetIndex)
    ];
    const currentPageIds = new Set((receipts?.items || []).map((item) => item.id));
    void persistReceiptOrder(nextOrderedReceipts, currentPageIds);
  }

  function updateBoxEditDraft<K extends keyof BoxEditDraft>(key: K, value: BoxEditDraft[K]) {
    setBoxEditDraft((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  function startReceiptBoxEditing(receiptId: number, box: CargoBox) {
    setEditingReceiptBox({ receiptId, box });
    setBoxEditDraft(boxEditDraftFrom(box));
  }

  function cancelReceiptBoxEditing() {
    setEditingReceiptBox(null);
    setBoxEditDraft(null);
  }

  function toggleBoxSelection(
    id: number,
    checked: boolean,
    shiftKey: boolean,
    ids: number[],
    anchor: number | null,
    setAnchor: (id: number) => void,
    setSelected: (updater: (prev: Set<number>) => Set<number>) => void
  ) {
    setSelected((prev) => {
      const next = new Set(prev);
      const currentIndex = ids.indexOf(id);
      const anchorIndex = anchor === null ? -1 : ids.indexOf(anchor);
      if (shiftKey && currentIndex >= 0 && anchorIndex >= 0) {
        const start = Math.min(currentIndex, anchorIndex);
        const end = Math.max(currentIndex, anchorIndex);
        for (const itemId of ids.slice(start, end + 1)) {
          if (checked) next.add(itemId);
          else next.delete(itemId);
        }
      } else if (checked) {
        next.add(id);
      } else {
        next.delete(id);
      }
      return next;
    });
    setAnchor(id);
  }

  function toggleReceiptExpanded(receiptId: number) {
    setExpandedReceiptId((prev) => (prev === receiptId ? null : receiptId));
    setSelectedReceiptBoxIds(new Set());
    setReceiptSelectionAnchor(null);
  }

  async function uploadUnboundReceiptFiles(files: File[] | null | undefined) {
    const uploadFiles = (files || []).filter((file) => Boolean(file));
    if (!uploadFiles.length) return;
    setUploading(true);
    setMessage("");
    setBatchUploadResult(null);
    const successes: BatchUploadSuccess[] = [];
    const failures: BatchUploadFailure[] = [];
    try {
      for (const file of uploadFiles) {
        try {
          const formData = new FormData();
          formData.append("file", file);
          const result = await apiClient.postForm<WarehouseFileUploadResult>("/warehouse-receipts/unbound/warehouse-file", formData);
          successes.push({
            file_name: result.file_name,
            warehouse_no: result.warehouse_no,
            uploaded_at: result.uploaded_at,
            success_count: result.success_count,
            detected_channel: result.channel_review?.detected_channel,
            warnings: result.channel_review?.warnings || [],
            issues: result.channel_review?.issues || [],
            integrity_issues: result.integrity_issues || [],
            prohibited_goods_issues: result.prohibited_goods_issues || [],
            errors: result.errors || [],
            channel_tags: result.channel_tags || []
          });
        } catch (error) {
          failures.push(uploadFailureFromError(file, error));
        }
      }
      setBatchUploadResult({ successes, failures });
      setMessage(`批量上传完成：成功 ${successes.length} 个文件，失败 ${failures.length} 个文件。`);
      if (successes.length) {
        setReceiptPage(1);
        setBoxesByReceipt({});
        setExpandedReceiptId(null);
        await loadReceiptPage(1);
        loadAllReceipts();
        loadScatter();
        loadWaybills();
      }
    } finally {
      setUploading(false);
    }
  }

  async function bindWholeReceipt() {
    if (!bindReceiptId || !targetWaybillId) return;
    setSaving(true);
    setMessage("");
    try {
      await apiClient.post<WarehouseReceipt>(`/warehouse-receipts/${bindReceiptId}/bind-waybill`, {
        target_waybill_id: Number(targetWaybillId)
      });
      setMessage("入仓号已整体绑定到目标提单。");
      setBindReceiptId(null);
      setTargetWaybillId("");
      setExpandedReceiptId(null);
      setBoxesByReceipt({});
      refreshAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "绑定入仓号失败。");
    } finally {
      setSaving(false);
    }
  }

  async function deleteReceipt(item: WarehouseReceipt) {
    if (!window.confirm(`确认永久删除未绑定入仓号 ${item.warehouse_no} 及其所有外箱明细吗？`)) return;
    setSaving(true);
    setMessage("");
    try {
      await apiClient.delete<void>(`/warehouse-receipts/${item.id}`);
      setMessage(`入仓号 ${item.warehouse_no} 已删除。`);
      setBoxesByReceipt((prev) => {
        const next = { ...prev };
        delete next[item.id];
        return next;
      });
      setSelectedReceiptIds((prev) => {
        if (!prev.has(item.id)) return prev;
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
      setSelectedReceiptBoxIds(new Set());
      setReceiptSelectionAnchor(null);
      if (expandedReceiptId === item.id) setExpandedReceiptId(null);
      setReceipts((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.filter((row) => row.id !== item.id),
              total: Math.max(0, prev.total - 1)
            }
          : prev
      );
      refreshAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除入仓号失败。");
    } finally {
      setSaving(false);
    }
  }

  async function exportReceipt(item: WarehouseReceipt) {
    setExportingReceiptId(item.id);
    setMessage("");
    try {
      const { blob, filename } = await apiClient.download(`/warehouse-receipts/${item.id}/export`);
      downloadBlob(blob, filename || `${item.source_file_name || item.warehouse_no}-入仓号文件.xlsx`);
      setMessage(`入仓号 ${item.warehouse_no} 已导出。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出入仓号文件失败。");
    } finally {
      setExportingReceiptId(null);
    }
  }

  function toggleReceiptSelection(receiptId: number, checked: boolean) {
    setSelectedReceiptIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(receiptId);
      } else {
        next.delete(receiptId);
      }
      return next;
    });
  }

  async function batchDeleteReceipts() {
    const receiptIds = Array.from(selectedReceiptIds);
    if (!receiptIds.length) return;
    if (!window.confirm(`确认永久删除选中的 ${receiptIds.length} 个未绑定入仓号及其所有外箱明细吗？`)) return;
    setSaving(true);
    setMessage("");
    try {
      const result = await apiClient.deleteWithBody<WarehouseReceiptBatchDeleteResult>("/warehouse-receipts/unbound/batch", {
        receipt_ids: receiptIds
      });
      const deletedIds = new Set(result.deleted_receipts.map((item) => item.id));
      setBoxesByReceipt((prev) => {
        const next = { ...prev };
        deletedIds.forEach((id) => {
          delete next[id];
        });
        return next;
      });
      setSelectedReceiptIds((prev) => {
        const next = new Set(prev);
        deletedIds.forEach((id) => next.delete(id));
        return next;
      });
      setSelectedReceiptBoxIds(new Set());
      setReceiptSelectionAnchor(null);
      if (expandedReceiptId !== null && deletedIds.has(expandedReceiptId)) setExpandedReceiptId(null);
      setReceipts((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.filter((row) => !deletedIds.has(row.id)),
              total: Math.max(0, prev.total - result.success_count)
            }
          : prev
      );
      const errorPreview = result.errors
        .slice(0, 3)
        .map((item) => `${item.warehouse_no || item.id}: ${item.message}`)
        .join("；");
      setMessage(
        result.failed_count
          ? `批量删除完成：成功 ${result.success_count} 个，失败 ${result.failed_count} 个。${errorPreview}`
          : `已删除 ${result.success_count} 个未绑定入仓号。`
      );
      refreshAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "批量删除入仓号失败。");
    } finally {
      setSaving(false);
    }
  }

  function openVolumeCalculation(receipt: WarehouseReceipt) {
    const currentVolume = Number(receipt.total_volume);
    setVolumeReceipt(receipt);
    setTargetVolumeDraft(Number.isFinite(currentVolume) && currentVolume > 0 ? currentVolume.toFixed(3).replace(/\.?0+$/, "") : "");
    setTargetVolumeError("");
  }

  async function recalculateReceiptVolumes() {
    if (!volumeReceipt) return;
    const targetVolume = Number(targetVolumeDraft);
    if (!Number.isFinite(targetVolume) || targetVolume <= 0) {
      setTargetVolumeError("请输入大于 0 的目标方数。");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const result = await apiClient.post<BoxVolumeRecalculationResult>(
        `/warehouse-receipts/${volumeReceipt.id}/boxes/recalculate-volume`,
        { target_volume: targetVolume }
      );
      setBoxesByReceipt((prev) => ({ ...prev, [volumeReceipt.id]: result.boxes }));
      setVolumeReceipt(null);
      loadReceipts();
      void loadAllReceipts();
      setMessage(
        result.adjusted
          ? `入仓号 ${volumeReceipt.warehouse_no} 方数已按整数长宽高调整到目标区间 ${formatTargetVolumeRange(result.target_volume)} CBM：${formatDecimal(result.old_total_volume)} → ${formatDecimal(result.new_total_volume)}。固定箱号 ${formatDecimal(result.fixed_total_volume)} CBM，实际调整 ${result.adjusted_box_count} 个。`
          : `入仓号 ${volumeReceipt.warehouse_no} 当前总方数已在目标区间 ${formatTargetVolumeRange(result.target_volume)} CBM，无需调整。`
      );
    } catch (error) {
      setVolumeReceipt(null);
      setVolumeError(volumeCalculationError(error));
    } finally {
      setSaving(false);
    }
  }

  async function saveReceiptBoxEdit() {
    if (!editingReceiptBox || !boxEditDraft) return;
    const nextBoxNo = boxEditDraft.box_no.trim();
    if (!nextBoxNo) {
      setMessage("外箱条码不能为空。");
      return;
    }

    setSaving(true);
    setMessage("");
    try {
      const ratioDraft = boxEditDraft.weight_volume_ratio.trim();
      const originalRatio =
        editingReceiptBox.box.weight_volume_ratio === null || editingReceiptBox.box.weight_volume_ratio === undefined
          ? ""
          : String(editingReceiptBox.box.weight_volume_ratio).trim();
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
      const updated = await apiClient.patch<CargoBox>(
        `/warehouse-receipts/${editingReceiptBox.receiptId}/boxes/${editingReceiptBox.box.id}`,
        payload
      );
      setBoxesByReceipt((prev) => ({
        ...prev,
        [editingReceiptBox.receiptId]: (prev[editingReceiptBox.receiptId] || []).map((box) =>
          box.id === updated.id ? updated : box
        )
      }));
      cancelReceiptBoxEditing();
      setMessage("箱号数据已更新。");
      loadReceipts();
      void loadAllReceipts();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "箱号数据更新失败。");
    } finally {
      setSaving(false);
    }
  }

  async function deleteScatterBox(item: CargoBox) {
    if (!window.confirm(`确认删除散箱 ${item.box_no} 及其箱内明细吗？删除后不可恢复。`)) return;
    setSaving(true);
    setMessage("");
    try {
      await apiClient.delete<void>(`/boxes/unbound/${item.id}`);
      setSelectedScatterIds((prev) => {
        const next = new Set(prev);
        next.delete(item.id);
        return next;
      });
      setScatterData((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.filter((box) => box.id !== item.id),
              total: Math.max(0, prev.total - 1)
            }
          : prev
      );
      setMessage(`散箱 ${item.box_no} 已删除。`);
      loadScatter();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除散箱失败。");
    } finally {
      setSaving(false);
    }
  }

  function openTransfer(source: TransferSource) {
    setTransferSource(source);
    setTransferMode("receipt");
    setTargetReceiptId("");
    setUnboundReason("other");
    setUnboundRemark("");
    void loadAllReceipts();
    setTransferOpen(true);
  }

  function closeTransfer() {
    setTransferOpen(false);
    setTargetReceiptId("");
    setUnboundReason("other");
    setUnboundRemark("");
  }

  async function submitTransfer() {
    if (!selectedTransferIds.size) return;
    if (transferMode === "receipt" && !targetReceiptId) {
      setMessage("请选择目标入仓号。");
      return;
    }
    const targetReceiptNumber = transferMode === "receipt" ? Number(targetReceiptId) : null;
    if (transferMode === "receipt" && (!targetReceiptNumber || !Number.isFinite(targetReceiptNumber))) {
      setMessage("请选择有效的目标入仓号。");
      return;
    }
    if (transferMode === "receipt" && transferSource === "receipt" && targetReceiptNumber === expandedReceiptId) {
      setMessage("不能移动到当前入仓号，请选择其他目标入仓号。");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const payload =
        transferMode === "receipt"
          ? {
              box_ids: Array.from(selectedTransferIds),
              target_type: "receipt",
              target_receipt_id: targetReceiptNumber
            }
          : {
              box_ids: Array.from(selectedTransferIds),
              target_type: "unbound",
              unbound_reason: unboundReason,
              unbound_remark: unboundRemark.trim() || undefined
            };
      const result = await apiClient.post<BoxBatchOperationResult>("/boxes/batch-transfer", payload);
      setMessage(`已转移 ${result.updated_count} 个箱号。`);
      setSelectedReceiptBoxIds(new Set());
      setSelectedScatterIds(new Set());
      setReceiptSelectionAnchor(null);
      setScatterSelectionAnchor(null);
      setBoxesByReceipt({});
      closeTransfer();
      refreshAll();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "转移箱号失败。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <input
        ref={uploadInputRef}
        type="file"
        accept=".xlsx"
        multiple
        className="hidden"
        onChange={(event) => {
          const files = Array.from(event.currentTarget.files || []);
          event.currentTarget.value = "";
          void uploadUnboundReceiptFiles(files);
        }}
      />
      <PageHeader
        title="未绑定箱号"
        description="维护未绑定入仓号文件和不属于任何入仓号的散箱池"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={refreshAll}>
              <RefreshCw className="h-4 w-4" />
              刷新
            </Button>
            <Button disabled={uploading} onClick={() => uploadInputRef.current?.click()}>
              <Upload className="h-4 w-4" />
              {uploading ? "上传中..." : "上传入仓文件"}
            </Button>
          </div>
        }
      />
      {message ? (
        <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div>
      ) : null}
      <div className="grid gap-4 xl:grid-cols-[1.25fr_0.75fr]">
        <Panel title="未绑定入仓号文件">
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm">
              <span className="text-slate-600">已选 {selectedReceiptIds.size} 个入仓号</span>
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  disabled={!selectedReceiptIds.size || saving}
                  onClick={() => void batchDeleteReceipts()}
                >
                  <Trash2 className="h-4 w-4 text-red-600" />
                  批量删除
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  disabled={!selectedReceiptIds.size || saving}
                  onClick={() => setSelectedReceiptIds(new Set())}
                >
                  取消选择
                </Button>
              </div>
            </div>
            {(receipts?.items || []).length ? (
              (receipts?.items || []).map((receipt) => {
                const expanded = expandedReceiptId === receipt.id;
                const boxes = boxesByReceipt[receipt.id] || [];
                return (
                  <div
                    key={receipt.id}
                    className="rounded-md border border-slate-200"
                    onDragOver={(event) => {
                      if (receiptSortDragId !== null) {
                        event.preventDefault();
                        event.dataTransfer.dropEffect = "move";
                      }
                    }}
                    onDrop={(event) => {
                      if (receiptSortDragId !== null) {
                        event.preventDefault();
                        moveUnboundReceiptBefore(receiptSortDragId, receipt.id);
                        setReceiptSortDragId(null);
                      }
                    }}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-3 py-2">
                      <div className="flex min-w-0 items-center gap-1">
                        <Button
                          type="button"
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 cursor-grab text-slate-400 active:cursor-grabbing"
                          draggable
                          disabled={receiptOrderSaving}
                          aria-label="拖动排序入仓号"
                          onDragStart={(event) => {
                            event.stopPropagation();
                            setReceiptSortDragId(receipt.id);
                            event.dataTransfer.effectAllowed = "move";
                            event.dataTransfer.setData("text/plain", String(receipt.id));
                          }}
                          onDragEnd={() => setReceiptSortDragId(null)}
                        >
                          <GripVertical className="h-4 w-4" />
                        </Button>
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300"
                          checked={selectedReceiptIds.has(receipt.id)}
                          aria-label={`选择入仓号 ${receipt.warehouse_no}`}
                          onClick={(event) => event.stopPropagation()}
                          onChange={(event) => toggleReceiptSelection(receipt.id, event.target.checked)}
                        />
                        <button
                          type="button"
                          className="flex min-w-0 items-center gap-2 text-left"
                          onClick={() => toggleReceiptExpanded(receipt.id)}
                        >
                          {expanded ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                          <span className="font-semibold text-slate-900">{receipt.warehouse_no}</span>
                          <Badge>{receipt.box_count ?? 0} 箱</Badge>
                          {channelTags(receipt.channel_tags).map((tag) => (
                            <Badge key={tag} variant="amber">
                              {tag}
                            </Badge>
                          ))}
                        </button>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                        <span>重量 {formatDecimal(receipt.total_weight)}</span>
                        <span>方数 {formatDecimal(receipt.total_volume)}</span>
                        {(receipt.general_cargo_count ?? 0) > 0 ? <span>普货：{receipt.general_cargo_count}件</span> : null}
                        <span>密度：{formatReceiptDensity(receipt)}</span>
                        <span>上传 {formatDateTime(receipt.uploaded_at)}</span>
                        <Button type="button" variant="secondary" size="sm" onClick={() => setBindReceiptId(receipt.id)}>
                          <Archive className="h-4 w-4" />
                          整体绑定提单
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={saving || (receipt.box_count ?? 0) <= 0}
                          onClick={() => openVolumeCalculation(receipt)}
                        >
                          <Calculator className="h-4 w-4" />
                          方数计算
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          disabled={exportingReceiptId === receipt.id || (receipt.box_count ?? 0) <= 0}
                          onClick={() => void exportReceipt(receipt)}
                        >
                          <Download className="h-4 w-4" />
                          {exportingReceiptId === receipt.id ? "导出中..." : "导出"}
                        </Button>
                        <Button type="button" variant="ghost" size="sm" disabled={saving} onClick={() => void deleteReceipt(receipt)}>
                          <Trash2 className="h-4 w-4 text-red-600" />
                          删除
                        </Button>
                      </div>
                    </div>
                    <div className="grid gap-2 px-3 py-2 text-xs text-slate-500 md:grid-cols-5">
                      <span>来源文件：{receipt.source_file_name || "-"}</span>
                      <span>上传时间：{formatDateTime(receipt.uploaded_at)}</span>
                      <span>总数量：{compact(receipt.total_quantity)}</span>
                      <span>重量/方：{formatDecimal(receipt.weight_volume_ratio)}</span>
                      <span>标记：{channelTags(receipt.channel_tags).join(" / ") || "-"}</span>
                    </div>
                    {expanded ? (
                      <div className="space-y-2 px-3 pb-3">
                        <div className="flex flex-wrap items-center gap-2 text-sm">
                          <span className="text-slate-600">已选 {selectedReceiptBoxIds.size} 个箱号</span>
                          <Button type="button" variant="secondary" size="sm" disabled={!selectedReceiptBoxIds.size} onClick={() => openTransfer("receipt")}>
                            <MoveRight className="h-4 w-4" />
                            移动选中箱号
                          </Button>
                        </div>
                        {boxes.length ? (
                          <div className="max-h-[420px] overflow-auto">
                            <Table>
                              <THead>
                                <TR>
                                  <TH>选择</TH>
                                  <TH>外箱条码</TH>
                                  <TH>箱内提单数</TH>
                                  <TH>首个仓库提单号</TH>
                                  <TH>品名</TH>
                                  <TH>数量</TH>
                                  <TH>重量</TH>
                                  <TH>收货体积信息</TH>
                                  <TH>重量/方</TH>
                                  <TH>操作</TH>
                                </TR>
                              </THead>
                              <TBody>
                                {boxes.map((box) => (
                                  <TR key={box.id} className={box.is_general_cargo ? "bg-amber-50 hover:bg-amber-100" : undefined}>
                                    <TD>
                                      <input
                                        type="checkbox"
                                        checked={selectedReceiptBoxIds.has(box.id)}
                                        onChange={(event) =>
                                          toggleBoxSelection(
                                            box.id,
                                            event.target.checked,
                                            event.nativeEvent instanceof MouseEvent ? event.nativeEvent.shiftKey : false,
                                            receiptBoxIds,
                                            receiptSelectionAnchor,
                                            setReceiptSelectionAnchor,
                                            setSelectedReceiptBoxIds
                                          )
                                        }
                                      />
                                    </TD>
                                    <TD className="font-medium">
                                      <span>{box.box_no}</span>
                                      {box.is_general_cargo ? (
                                        <span className="ml-1 rounded bg-amber-200 px-1.5 py-0.5 text-xs font-semibold text-amber-900">普货</span>
                                      ) : null}
                                    </TD>
                                    <TD>{box.items?.length || 0}</TD>
                                    <TD>
                                      <div className="flex flex-wrap items-center gap-1">
                                        <span>{compact(box.warehouse_waybill_no)}</span>
                                        <ConflictWaybillBadge conflict={box.box_conflict} />
                                      </div>
                                    </TD>
                                    <TD>{compact(box.goods_name)}</TD>
                                    <TD>{compact(box.quantity)}</TD>
                                    <TD>{formatDecimal(box.weight)}</TD>
                                    <TD>{formatCalculatedVolumeInfo(box)}</TD>
                                    <TD>{formatDecimal(box.weight_volume_ratio)}</TD>
                                    <TD>
                                      <Button type="button" variant="ghost" size="sm" disabled={saving} onClick={() => startReceiptBoxEditing(receipt.id, box)}>
                                        <Pencil className="h-4 w-4" />
                                        编辑
                                      </Button>
                                    </TD>
                                  </TR>
                                ))}
                              </TBody>
                            </Table>
                          </div>
                        ) : (
                          <EmptyState title="正在加载或暂无箱号" />
                        )}
                      </div>
                    ) : null}
                  </div>
                );
              })
            ) : (
              <EmptyState title="暂无未绑定入仓号" description="上传入仓 Excel 文件后会先形成未绑定入仓号，再按需整体或部分绑定到提单。" />
            )}
            <div className="flex items-center justify-between text-sm text-slate-500">
              <span>共 {receipts?.total ?? 0} 个未绑定入仓号</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={receiptPage <= 1} onClick={() => setReceiptPage((prev) => prev - 1)}>
                  上一页
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!receipts || receiptPage * receipts.page_size >= receipts.total}
                  onClick={() => setReceiptPage((prev) => prev + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
          </div>
        </Panel>
        <div className="xl:sticky xl:top-4 xl:self-start">
          <Panel
            title={rightPanelMode === "scatter" ? "散箱池" : "入仓号汇总"}
            action={
              <div className="flex rounded-md bg-slate-100 p-1">
                <Button
                  type="button"
                  size="sm"
                  variant={rightPanelMode === "scatter" ? "default" : "ghost"}
                  onClick={() => setRightPanelMode("scatter")}
                >
                  散箱池
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant={rightPanelMode === "receipt_summary" ? "default" : "ghost"}
                  onClick={() => setRightPanelMode("receipt_summary")}
                >
                  入仓号汇总
                </Button>
              </div>
            }
          >
            {rightPanelMode === "scatter" ? (
              <div className="space-y-3">
            <div className="flex flex-wrap items-center gap-2 text-sm">
              <span className="text-slate-600">已选 {selectedScatterIds.size} 个散箱</span>
              <Button type="button" variant="secondary" size="sm" disabled={!selectedScatterIds.size} onClick={() => openTransfer("scatter")}>
                <MoveRight className="h-4 w-4" />
                移动到入仓号
              </Button>
            </div>
            {(scatterData?.items || []).length ? (
              <div className="max-h-[680px] overflow-auto">
                <Table>
                  <THead>
                    <TR>
                      <TH>选择</TH>
                      <TH>外箱条码</TH>
                      <TH>来源</TH>
                      <TH>原因</TH>
                      <TH>备注</TH>
                      <TH>品名</TH>
                      <TH>重量</TH>
                      <TH>方数</TH>
                      <TH>操作</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {(scatterData?.items || []).map((box) => (
                      <TR key={box.id}>
                        <TD>
                          <input
                            type="checkbox"
                            checked={selectedScatterIds.has(box.id)}
                            onChange={(event) =>
                              toggleBoxSelection(
                                box.id,
                                event.target.checked,
                                event.nativeEvent instanceof MouseEvent ? event.nativeEvent.shiftKey : false,
                                scatterBoxIds,
                                scatterSelectionAnchor,
                                setScatterSelectionAnchor,
                                setSelectedScatterIds
                              )
                            }
                          />
                        </TD>
                        <TD className="font-medium">{box.box_no}</TD>
                        <TD>
                          {box.never_bound_direct_upload ? (
                            <Badge variant="amber">从未绑定过任何提单</Badge>
                          ) : null}
                        </TD>
                        <TD>{box.unbound_reason ? <Badge>{reasonLabel(box.unbound_reason)}</Badge> : null}</TD>
                        <TD>{compact(box.unbound_remark)}</TD>
                        <TD>{compact(box.goods_name)}</TD>
                        <TD>{formatDecimal(box.weight)}</TD>
                        <TD>{formatDecimal(box.volume)}</TD>
                        <TD>
                          <Button type="button" variant="ghost" size="sm" disabled={saving} onClick={() => void deleteScatterBox(box)}>
                            <Trash2 className="h-4 w-4 text-red-600" />
                            删除
                          </Button>
                        </TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
            ) : (
              <EmptyState title="暂无散箱" description="从入仓号移出到未绑定箱号池后会在这里显示原因和备注。" />
            )}
            <div className="flex items-center justify-between text-sm text-slate-500">
              <span>共 {scatterData?.total ?? 0} 个散箱</span>
              <div className="flex gap-2">
                <Button variant="secondary" size="sm" disabled={scatterPage <= 1} onClick={() => setScatterPage((prev) => prev - 1)}>
                  上一页
                </Button>
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={!scatterData || scatterPage * scatterData.page_size >= scatterData.total}
                  onClick={() => setScatterPage((prev) => prev + 1)}
                >
                  下一页
                </Button>
              </div>
            </div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm text-slate-600">
                  <span>共 {unboundReceiptSummaries.length} 个未绑定入仓号文件</span>
                </div>
                {receiptOptionsLoading ? <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-4 text-sm text-slate-500">正在加载入仓号汇总...</div> : null}
                {receiptOptionsError ? <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-4 text-sm text-rose-600">{receiptOptionsError}</div> : null}
                {!receiptOptionsLoading && !receiptOptionsError && unboundReceiptSummaries.length ? (
                  <div className="max-h-[680px] overflow-auto">
                    <Table className="min-w-[900px]">
                      <THead>
                        <TR>
                          <TH>入仓号文件名</TH>
                          <TH>上传时间</TH>
                          <TH>箱数</TH>
                          <TH>渠道标签</TH>
                          <TH>件数</TH>
                          <TH>重量</TH>
                          <TH>方数</TH>
                          <TH>普货</TH>
                          <TH>密度</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {unboundReceiptSummaries.map((receipt) => {
                          const fileName = receipt.source_file_name || receipt.warehouse_no;
                          const tags = channelTags(receipt.channel_tags);
                          return (
                            <TR key={receipt.id}>
                              <TD>
                                <span className="inline-block max-w-56 truncate align-bottom" title={fileName}>
                                  {fileName}
                                </span>
                              </TD>
                              <TD>{formatDateTime(receipt.uploaded_at)}</TD>
                              <TD>{receipt.box_count ?? 0}</TD>
                              <TD>
                                {tags.length ? (
                                  <span className="flex flex-wrap gap-1">
                                    {tags.map((tag) => (
                                      <Badge key={tag} variant="amber">{tag}</Badge>
                                    ))}
                                  </span>
                                ) : (
                                  "-"
                                )}
                              </TD>
                              <TD>{compact(receipt.total_quantity)}</TD>
                              <TD>{formatDecimal(receipt.total_weight)}</TD>
                              <TD>{formatDecimal(receipt.total_volume)}</TD>
                              <TD>{(receipt.general_cargo_count ?? 0) > 0 ? `${receipt.general_cargo_count}件` : "-"}</TD>
                              <TD>{formatReceiptDensity(receipt)}</TD>
                            </TR>
                          );
                        })}
                      </TBody>
                    </Table>
                  </div>
                ) : null}
                {!receiptOptionsLoading && !receiptOptionsError && !unboundReceiptSummaries.length ? (
                  <EmptyState title="暂无入仓号汇总" description="上传未绑定入仓号文件后，这里会汇总全部未绑定入仓号。" />
                ) : null}
              </div>
            )}
          </Panel>
        </div>
      </div>
      <Dialog open={Boolean(batchUploadResult)} onOpenChange={(open) => !open && setBatchUploadResult(null)}>
        <DialogContent className="w-[min(980px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">批量上传结果</DialogTitle>
          {batchUploadResult ? (
            <div className="mt-3 space-y-4 text-sm">
              <div className="flex flex-wrap gap-3 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
                <span>成功 {batchUploadResult.successes.length} 个文件</span>
                <span>失败 {batchUploadResult.failures.length} 个文件</span>
                <span>
                  警告 {batchUploadResult.successes.filter((item) => successWarningCount(item) > 0).length} 个文件
                </span>
                <span>
                  待确认{" "}
                  {
                    batchUploadResult.successes.filter((item) =>
                      item.warnings.includes("dpd_only_channel_pending")
                    ).length
                  }{" "}
                  个文件
                </span>
              </div>

              {batchUploadResult.successes.length ? (
                <section className="space-y-2">
                  <div className="font-medium text-emerald-700">上传成功</div>
                  <div className="max-h-52 overflow-auto rounded-md border border-emerald-200">
                    <Table>
                      <THead>
                        <TR>
                          <TH>文件名</TH>
                          <TH>入仓号</TH>
                          <TH>上传时间</TH>
                          <TH>箱数</TH>
                          <TH>渠道</TH>
                          <TH>标记</TH>
                          <TH>提示</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {batchUploadResult.successes.map((item) => (
                          <TR key={`${item.file_name}-${item.warehouse_no}`}>
                            <TD>{item.file_name}</TD>
                            <TD className="font-medium">{item.warehouse_no}</TD>
                            <TD>{formatDateTime(item.uploaded_at)}</TD>
                            <TD>{item.success_count}</TD>
                            <TD>{channelLabel(item.detected_channel)}</TD>
                            <TD>
                              {channelTags(item.channel_tags).map((tag) => (
                                <Badge key={tag} variant="amber" className="mr-1">
                                  {tag}
                                </Badge>
                              ))}
                            </TD>
                            <TD>
                              {item.warnings.map((warning) => (
                                <Badge key={warning} variant="amber" className="mr-1">
                                  {warningLabel(warning)}
                                </Badge>
                              ))}
                              {item.issues.length ? (
                                <Badge variant="amber" className="mr-1">
                                  渠道警告 {item.issues.length}
                                </Badge>
                              ) : null}
                              {item.integrity_issues.length ? (
                                <Badge variant="amber" className="mr-1">
                                  完整性警告 {item.integrity_issues.length}
                                </Badge>
                              ) : null}
                              {item.prohibited_goods_issues.length ? (
                                <Badge variant="amber" className="mr-1">
                                  品名警告 {item.prohibited_goods_issues.length}
                                </Badge>
                              ) : null}
                              {item.errors.length ? (
                                <Badge variant="amber" className="mr-1">
                                  行级警告 {item.errors.length}
                                </Badge>
                              ) : null}
                            </TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                  </div>
                  {batchUploadResult.successes.some((item) => successWarningCount(item) > 0) ? (
                    <div className="max-h-72 overflow-auto space-y-3 rounded-md border border-amber-200 bg-amber-50 p-3">
                      <div className="font-medium text-amber-900">已上传，存在警告</div>
                      {batchUploadResult.successes
                        .filter((item) => successWarningCount(item) > 0)
                        .map((item) => (
                          <div key={`${item.file_name}-${item.warehouse_no}-warnings`} className="rounded-md border border-amber-200 bg-white p-3 text-amber-950">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold">{item.warehouse_no || item.file_name}</span>
                              <span className="text-xs text-amber-700">{item.file_name}</span>
                            </div>
                            {item.issues.length ? (
                              <Table className="mt-3">
                                <THead>
                                  <TR>
                                    <TH>外箱条码</TH>
                                    <TH>前三字母</TH>
                                    <TH>规则原因</TH>
                                    <TH>说明</TH>
                                  </TR>
                                </THead>
                                <TBody>
                                  {item.issues.map((issue) => (
                                    <TR key={`${item.file_name}-${issue.box_no}-${issue.reason}`}>
                                      <TD className="font-medium">{issue.box_no}</TD>
                                      <TD>{issue.prefix}</TD>
                                      <TD>{issue.reason}</TD>
                                      <TD>{issue.message}</TD>
                                    </TR>
                                  ))}
                                </TBody>
                              </Table>
                            ) : null}
                            {item.integrity_issues.length ? (
                              <Table className="mt-3">
                                <THead>
                                  <TR>
                                    <TH>Excel 行号</TH>
                                    <TH>外箱条码</TH>
                                    <TH>说明</TH>
                                  </TR>
                                </THead>
                                <TBody>
                                  {item.integrity_issues.map((issue) => (
                                    <TR key={`${item.file_name}-${issue.row_number}-${issue.box_no}`}>
                                      <TD>{issue.row_number}</TD>
                                      <TD className="font-medium">{issue.box_no}</TD>
                                      <TD>{issue.message}</TD>
                                    </TR>
                                  ))}
                                </TBody>
                              </Table>
                            ) : null}
                            {item.prohibited_goods_issues.length ? (
                              <Table className="mt-3">
                                <THead>
                                  <TR>
                                    <TH>Excel 行号</TH>
                                    <TH>外箱条码</TH>
                                    <TH>运单号</TH>
                                    <TH>品名</TH>
                                    <TH>命中词</TH>
                                    <TH>说明</TH>
                                  </TR>
                                </THead>
                                <TBody>
                                  {item.prohibited_goods_issues.map((issue) => (
                                    <TR key={`${item.file_name}-${issue.row_number}-${issue.box_no}-${issue.keyword}`}>
                                      <TD>{issue.row_number}</TD>
                                      <TD className="font-medium">{issue.box_no}</TD>
                                      <TD>{compact(issue.warehouse_waybill_no)}</TD>
                                      <TD>{issue.goods_name}</TD>
                                      <TD>{issue.keyword}</TD>
                                      <TD>{issue.message}</TD>
                                    </TR>
                                  ))}
                                </TBody>
                              </Table>
                            ) : null}
                            {item.errors.length ? (
                              <Table className="mt-3">
                                <THead>
                                  <TR>
                                    <TH>Excel 行号</TH>
                                    <TH>说明</TH>
                                  </TR>
                                </THead>
                                <TBody>
                                  {item.errors.map((error, index) => (
                                    <TR key={`${item.file_name}-${error.row_number}-${index}`}>
                                      <TD>{error.row_number}</TD>
                                      <TD>{error.message}</TD>
                                    </TR>
                                  ))}
                                </TBody>
                              </Table>
                            ) : null}
                          </div>
                        ))}
                    </div>
                  ) : null}
                </section>
              ) : null}

              {batchUploadResult.failures.length ? (
                <section className="space-y-2">
                  <div className="font-medium text-red-700">上传失败</div>
                  <div className="max-h-80 overflow-auto space-y-3 rounded-md border border-red-200 p-3">
                    {batchUploadResult.failures.map((failure) => (
                      <div key={failure.file_name} className="rounded-md border border-red-100 bg-red-50 p-3 text-red-900">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold">{failure.warehouse_no || failure.file_name}</span>
                          {failure.warehouse_no ? <span className="text-xs text-red-700">{failure.file_name}</span> : null}
                          {failure.detected_channel ? <Badge variant="red">渠道：{channelLabel(failure.detected_channel)}</Badge> : null}
                        </div>
                        <div className="mt-1 text-sm">{failure.message}</div>
                        {failure.issues.length ? (
                          <Table className="mt-3 bg-white">
                            <THead>
                              <TR>
                                <TH>外箱条码</TH>
                                <TH>前三字母</TH>
                                <TH>规则原因</TH>
                                <TH>说明</TH>
                              </TR>
                            </THead>
                            <TBody>
                              {failure.issues.map((issue) => (
                                <TR key={`${failure.file_name}-${issue.box_no}`}>
                                  <TD className="font-medium">{issue.box_no}</TD>
                                  <TD>{issue.prefix}</TD>
                                  <TD>{issue.reason}</TD>
                                  <TD>{issue.message}</TD>
                                </TR>
                              ))}
                            </TBody>
                          </Table>
                        ) : null}
                        {failure.integrity_issues.length ? (
                          <Table className="mt-3 bg-white">
                            <THead>
                              <TR>
                                <TH>Excel 行号</TH>
                                <TH>外箱条码</TH>
                                <TH>说明</TH>
                              </TR>
                            </THead>
                            <TBody>
                              {failure.integrity_issues.map((issue) => (
                                <TR key={`${failure.file_name}-${issue.row_number}-${issue.box_no}`}>
                                  <TD>{issue.row_number}</TD>
                                  <TD className="font-medium">{issue.box_no}</TD>
                                  <TD>{issue.message}</TD>
                                </TR>
                              ))}
                            </TBody>
                          </Table>
                        ) : null}
                        {failure.conflicts.length ? (
                          <Table className="mt-3 bg-white">
                            <THead>
                              <TR>
                                <TH>冲突箱号</TH>
                                <TH>当前入仓号</TH>
                                <TH>当前提单ID</TH>
                              </TR>
                            </THead>
                            <TBody>
                              {failure.conflicts.map((item, index) => (
                                <TR key={`${failure.file_name}-${item.box_no || "box"}-${index}`}>
                                  <TD className="font-medium">{item.box_no}</TD>
                                  <TD>{compact(item.current_warehouse_no)}</TD>
                                  <TD>{compact(item.current_waybill_id)}</TD>
                                </TR>
                              ))}
                            </TBody>
                          </Table>
                        ) : null}
                      </div>
                    ))}
                  </div>
                </section>
              ) : null}
            </div>
          ) : null}
          <div className="mt-5 flex justify-end">
            <Button type="button" onClick={() => setBatchUploadResult(null)}>
              知道了
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={Boolean(editingReceiptBox && boxEditDraft)} onOpenChange={(open) => !open && cancelReceiptBoxEditing()}>
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
                <Button type="button" variant="secondary" disabled={saving} onClick={cancelReceiptBoxEditing}>
                  取消
                </Button>
                <Button type="button" disabled={saving} onClick={() => void saveReceiptBoxEdit()}>
                  保存
                </Button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
      <Dialog open={volumeReceipt !== null} onOpenChange={(open) => !open && setVolumeReceipt(null)}>
        <DialogContent className="w-[min(520px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">方数计算</DialogTitle>
          <div className="mt-3 space-y-4 text-sm">
            <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-slate-700">
              <div>入仓号：<span className="font-medium text-slate-900">{volumeReceipt?.warehouse_no}</span></div>
              <div>当前方数：<span className="font-medium text-slate-900">{formatDecimal(volumeReceipt?.total_volume)} CBM</span></div>
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700" htmlFor="unbound-target-volume">
                目标总方数(CBM)
              </label>
              <Input
                id="unbound-target-volume"
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
                    void recalculateReceiptVolumes();
                  }
                }}
              />
              {targetVolumeError ? <div className="text-xs text-red-600">{targetVolumeError}</div> : null}
            </div>
            <div className="text-xs text-slate-500">系统会按整数长宽高调整有尺寸的一箱一件箱号；结果允许落在目标值到目标值 +0.5 CBM 区间，一箱多件或缺少长宽高的箱号保持原始方数。</div>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button type="button" variant="secondary" disabled={saving} onClick={() => setVolumeReceipt(null)}>
              取消
            </Button>
            <Button type="button" disabled={saving} onClick={() => void recalculateReceiptVolumes()}>
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
                  <div key={item.label} className="grid grid-cols-[150px_1fr] border-b border-slate-100 px-3 py-2 text-sm last:border-b-0">
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
      <Dialog open={bindReceiptId !== null} onOpenChange={(open) => !open && setBindReceiptId(null)}>
        <DialogContent className="w-[min(560px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">整体绑定入仓号</DialogTitle>
          <div className="mt-3 space-y-3">
            <div className="text-sm text-slate-600">选择目标提单后，该入仓号下所有外箱都会绑定到该提单；目标提单已有其他入仓号也会保留。</div>
            <Select value={targetWaybillId} onValueChange={setTargetWaybillId}>
              <SelectTrigger>
                <SelectValue placeholder="选择目标提单" />
              </SelectTrigger>
              <SelectContent>
                {waybillOptions.map((item) => (
                  <SelectItem key={item.id} value={String(item.id)}>
                    {item.waybill_no} {item.warehouse_no ? `· 当前 ${item.warehouse_no}` : ""}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button type="button" variant="secondary" disabled={saving} onClick={() => setBindReceiptId(null)}>
              取消
            </Button>
            <Button type="button" disabled={saving || !targetWaybillId} onClick={() => void bindWholeReceipt()}>
              确认绑定
            </Button>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={transferOpen} onOpenChange={(open) => (open ? setTransferOpen(true) : closeTransfer())}>
        <DialogContent className="w-[min(620px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">移动箱号</DialogTitle>
          <div className="mt-3 space-y-4 text-sm">
            <div className="text-slate-600">已选 {selectedTransferIds.size} 个箱号</div>
            <div className="grid gap-2 sm:grid-cols-2">
              <Button
                type="button"
                variant={transferMode === "receipt" ? "default" : "secondary"}
                onClick={() => setTransferMode("receipt")}
              >
                移动到入仓号
              </Button>
              {transferSource === "receipt" ? (
                <Button
                  type="button"
                  variant={transferMode === "unbound" ? "default" : "secondary"}
                  onClick={() => setTransferMode("unbound")}
                >
                  移动到散箱池
                </Button>
              ) : null}
            </div>
            {transferMode === "receipt" ? (
              <div className="space-y-2">
                <div className="font-medium text-slate-700">目标入仓号</div>
                <div className="max-h-72 overflow-y-auto rounded-md border border-slate-200 bg-white">
                  {receiptOptionsLoading ? <div className="px-3 py-4 text-sm text-slate-500">正在加载目标入仓号...</div> : null}
                  {receiptOptionsError ? <div className="px-3 py-4 text-sm text-rose-600">{receiptOptionsError}</div> : null}
                  {!receiptOptionsLoading && !receiptOptionsError && !hasTargetReceipts ? (
                    <div className="px-3 py-4 text-sm text-slate-500">暂无可移动的其他入仓号。</div>
                  ) : null}
                  {targetReceiptGroups.map((group) =>
                    group.items.length ? (
                      <div key={group.key} className="border-b border-slate-100 last:border-b-0">
                        <div className="sticky top-0 bg-slate-50 px-3 py-2 text-xs font-semibold text-slate-500">{group.label}</div>
                        <div className="divide-y divide-slate-100">
                          {group.items.map((item) => {
                            const selected = targetReceiptId === String(item.id);
                            const tags = channelTags(item.channel_tags);
                            return (
                              <button
                                key={item.id}
                                type="button"
                                onClick={() => setTargetReceiptId(String(item.id))}
                                className={`flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm transition ${
                                  selected ? "bg-slate-900 text-white" : "bg-white text-slate-700 hover:bg-slate-50"
                                }`}
                              >
                                <span className="min-w-0">
                                  <span className="block truncate font-medium">{receiptLabel(item)}</span>
                                  <span className={`block text-xs ${selected ? "text-slate-200" : "text-slate-500"}`}>
                                    箱数 {item.box_count ?? 0} / 重量 {formatDecimal(item.total_weight)} / 方数 {formatDecimal(item.total_volume)}
                                  </span>
                                  <span className={`block text-xs ${selected ? "text-slate-200" : "text-slate-500"}`}>
                                    上传 {formatDateTime(item.uploaded_at)}
                                  </span>
                                </span>
                                {tags.length ? (
                                  <span className="flex shrink-0 flex-wrap justify-end gap-1">
                                    {tags.map((tag) => (
                                      <Badge key={tag} variant={selected ? "default" : "amber"}>{tag}</Badge>
                                    ))}
                                  </span>
                                ) : null}
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    ) : null
                  )}
                </div>
                <div className="text-xs text-slate-500">支持移动到未绑定入仓号、预排仓入仓号、提单管理入仓号。</div>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="space-y-2">
                  <div className="font-medium text-slate-700">转移原因</div>
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
                  <div className="font-medium text-slate-700">备注</div>
                  <Textarea value={unboundRemark} onChange={(event) => setUnboundRemark(event.target.value)} rows={3} />
                </div>
              </div>
            )}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button type="button" variant="secondary" disabled={saving} onClick={closeTransfer}>
              取消
            </Button>
            <Button
              type="button"
              disabled={saving || !selectedTransferIds.size || (transferMode === "receipt" && (!targetReceiptId || !hasTargetReceipts))}
              onClick={() => void submitTransfer()}
            >
              确认移动
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
