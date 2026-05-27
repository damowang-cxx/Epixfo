"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Archive, ChevronDown, ChevronRight, MoveRight, RefreshCw, Trash2, Upload } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiClient } from "@/lib/client-api";
import { compact, formatDateTime } from "@/lib/utils";
import type {
  BoxBatchOperationResult,
  CargoBox,
  PageResponse,
  WarehouseBoxConflict,
  WarehouseChannelReviewIssue,
  WarehouseFileUploadResult,
  WarehouseReceipt,
  Waybill
} from "@/lib/types";

type TransferMode = "receipt" | "unbound";
type TransferSource = "receipt" | "scatter";
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
  success_count: number;
  detected_channel?: string | null;
  warnings: string[];
  channel_tags: string[];
}

interface BatchUploadFailure {
  file_name: string;
  warehouse_no?: string | null;
  message: string;
  detected_channel?: string | null;
  warnings: string[];
  issues: WarehouseChannelReviewIssue[];
  conflicts: Array<UploadConflict | WarehouseBoxConflict>;
}

interface BatchUploadResult {
  successes: BatchUploadSuccess[];
  failures: BatchUploadFailure[];
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

function receiptLabel(item: WarehouseReceipt) {
  return item.waybill_no ? `${item.warehouse_no} · 已绑定 ${item.waybill_no}` : `${item.warehouse_no} · 未绑定`;
}

function channelTags(tags?: string[] | null) {
  return (tags || []).filter(Boolean);
}

function receiptOptionLabel(item: WarehouseReceipt) {
  const tags = channelTags(item.channel_tags);
  return tags.length ? `${receiptLabel(item)} · ${tags.join("/")}` : receiptLabel(item);
}

function channelLabel(value?: string | null) {
  if (!value) return "";
  return CHANNEL_LABELS[value] || value;
}

function warningLabel(value: string) {
  return WARNING_LABELS[value] || value;
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
      conflicts: parseConflicts(error)
    };
  }
  return {
    file_name: file.name,
    message: error instanceof Error ? error.message : "上传入仓文件失败。",
    warnings: [],
    issues: [],
    conflicts: []
  };
}

export default function WarehouseReceiptsPage() {
  const uploadInputRef = useRef<HTMLInputElement>(null);
  const [receipts, setReceipts] = useState<PageResponse<WarehouseReceipt> | null>(null);
  const [receiptPage, setReceiptPage] = useState(1);
  const [allReceipts, setAllReceipts] = useState<WarehouseReceipt[]>([]);
  const [expandedReceiptId, setExpandedReceiptId] = useState<number | null>(null);
  const [boxesByReceipt, setBoxesByReceipt] = useState<Record<number, CargoBox[]>>({});
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
  const [message, setMessage] = useState("");
  const [batchUploadResult, setBatchUploadResult] = useState<BatchUploadResult | null>(null);

  const selectedTransferIds = transferSource === "receipt" ? selectedReceiptBoxIds : selectedScatterIds;

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

  const loadAllReceipts = useCallback(() => {
    apiClient
      .get<PageResponse<WarehouseReceipt>>("/warehouse-receipts?page=1&page_size=300")
      .then((data) => setAllReceipts(data.items))
      .catch(() => setAllReceipts([]));
  }, []);

  const loadScatter = useCallback(() => {
    apiClient.get<PageResponse<CargoBox>>(`/boxes/unbound?page=${scatterPage}&page_size=20`).then(setScatterData);
  }, [scatterPage]);

  const loadWaybills = useCallback(() => {
    apiClient
      .get<PageResponse<Waybill>>("/waybills?page=1&page_size=300")
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
    refreshAll();
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
            success_count: result.success_count,
            detected_channel: result.channel_review?.detected_channel,
            warnings: result.channel_review?.warnings || [],
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
    setSaving(true);
    setMessage("");
    try {
      const payload =
        transferMode === "receipt"
          ? {
              box_ids: Array.from(selectedTransferIds),
              target_type: "receipt",
              target_receipt_id: Number(targetReceiptId)
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
            {(receipts?.items || []).length ? (
              (receipts?.items || []).map((receipt) => {
                const expanded = expandedReceiptId === receipt.id;
                const boxes = boxesByReceipt[receipt.id] || [];
                return (
                  <div key={receipt.id} className="rounded-md border border-slate-200">
                    <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 bg-slate-50 px-3 py-2">
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
                      <div className="flex flex-wrap items-center gap-2 text-xs text-slate-600">
                        <span>重量 {formatDecimal(receipt.total_weight)}</span>
                        <span>方数 {formatDecimal(receipt.total_volume)}</span>
                        <span>{formatDateTime(receipt.updated_at)}</span>
                        <Button type="button" variant="secondary" size="sm" onClick={() => setBindReceiptId(receipt.id)}>
                          <Archive className="h-4 w-4" />
                          整体绑定提单
                        </Button>
                        <Button type="button" variant="ghost" size="sm" disabled={saving} onClick={() => void deleteReceipt(receipt)}>
                          <Trash2 className="h-4 w-4 text-red-600" />
                          删除
                        </Button>
                      </div>
                    </div>
                    <div className="grid gap-2 px-3 py-2 text-xs text-slate-500 md:grid-cols-4">
                      <span>来源文件：{receipt.source_file_name || "-"}</span>
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
                                  <TH>方数</TH>
                                  <TH>重量/方</TH>
                                </TR>
                              </THead>
                              <TBody>
                                {boxes.map((box) => (
                                  <TR key={box.id}>
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
                                    <TD className="font-medium">{box.box_no}</TD>
                                    <TD>{box.items?.length || 0}</TD>
                                    <TD>{compact(box.warehouse_waybill_no)}</TD>
                                    <TD>{compact(box.goods_name)}</TD>
                                    <TD>{compact(box.quantity)}</TD>
                                    <TD>{formatDecimal(box.weight)}</TD>
                                    <TD>{formatDecimal(box.volume)}</TD>
                                    <TD>{formatDecimal(box.weight_volume_ratio)}</TD>
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
        <Panel title="散箱池">
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
        </Panel>
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
                            </TD>
                          </TR>
                        ))}
                      </TBody>
                    </Table>
                  </div>
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
                <Select value={targetReceiptId} onValueChange={setTargetReceiptId}>
                  <SelectTrigger>
                    <SelectValue placeholder="选择目标入仓号" />
                  </SelectTrigger>
                  <SelectContent>
                    {allReceipts.map((item) => (
                      <SelectItem key={item.id} value={String(item.id)}>
                        {receiptOptionLabel(item)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
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
              disabled={saving || !selectedTransferIds.size || (transferMode === "receipt" && !targetReceiptId)}
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
