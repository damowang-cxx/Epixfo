"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from "react";
import { Download, GripVertical, ListPlus, PanelRightClose, PanelRightOpen, RefreshCw, RotateCcw, Save, Trash2, Upload } from "lucide-react";
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
import { apiClient } from "@/lib/client-api";
import { cn, compact, formatDateTime, formatOutboundDate } from "@/lib/utils";
import type {
  CarrierAgent,
  User,
  WarehousePlannerCandidate,
  WarehousePlannerBulkImportResult,
  WarehousePlannerCandidates,
  WarehousePlannerCommitResult,
  WarehousePlannerRow,
  WarehousePlannerRowResult,
  WarehousePlannerValidateResult,
  WarehouseReceipt,
  TableColumnPreference,
  PlannerChannel
} from "@/lib/types";

type RightPanelMode = "candidates" | "receipts";
type ReceiptViewMode = "list" | "summary";
type PlannerField =
  | "carrier_agent_id"
  | "planned_flight_no"
  | "waybill_no"
  | "outbound_date"
  | "customs_staff_id"
  | "booked_volume"
  | "planned_flight_date"
  | "booked_weight"
  | "density"
  | "quotation"
  | "include_tc"
  | "departure_port"
  | "destination_port"
  | "planned_route_text"
  | "internal_remark";

const CLEAR_VALUE = "__clear__";
const CANDIDATE_DRAG_TYPE = "application/x-warehouse-planner-candidates";
const RECEIPT_DRAG_TYPE = "application/x-warehouse-planner-receipts";
const PLANNER_ROW_DRAG_TYPE = "application/x-warehouse-planner-rows";
const PLANNER_SPLIT_PREFERENCE_KEY = "warehouse-planner:split-width";
const PLANNER_COLUMNS_PREFERENCE_KEY = "warehouse-planner:columns";
const DEFAULT_MAIN_PANE_PERCENT = 68;
const MIN_MAIN_PANE_PERCENT = 44;
const MAX_MAIN_PANE_PERCENT = 82;
const PLANNER_CHANNELS: PlannerChannel[] = ["AMS", "LHR"];

const DEFAULT_PLANNER_COLUMN_ORDER = [
  "source",
  "carrier_agent",
  "planned_flight_no",
  "waybill_no",
  "outbound_date",
  "receipts",
  "receipt_summary",
  "customs_staff",
  "booked_volume",
  "planned_flight_date",
  "booked_weight",
  "density",
  "quotation",
  "include_tc",
  "departure_port",
  "destination_port",
  "planned_route_text",
  "internal_remark",
  "actions"
] as const;

type PlannerColumnKey = (typeof DEFAULT_PLANNER_COLUMN_ORDER)[number];

const PLANNER_COLUMN_LABELS: Record<PlannerColumnKey, string> = {
  source: "来源",
  carrier_agent: "航代",
  planned_flight_no: "计划航班",
  waybill_no: "提单号",
  outbound_date: "出仓日期",
  receipts: "入仓号/入仓文件",
  receipt_summary: "入仓汇总",
  customs_staff: "指定清关人员",
  booked_volume: "订舱方数/板总方数",
  planned_flight_date: "约定航班起飞日期",
  booked_weight: "订舱重量",
  density: "密度",
  quotation: "报价",
  include_tc: "含T",
  departure_port: "始发港",
  destination_port: "目的港",
  planned_route_text: "航程",
  internal_remark: "内部备注",
  actions: "操作"
};

const BATCH_FIELDS: Array<{ key: PlannerField; label: string; kind: "select" | "text" | "number" | "date" | "boolean" }> = [
  { key: "carrier_agent_id", label: "航代", kind: "select" },
  { key: "planned_flight_no", label: "计划航班", kind: "text" },
  { key: "outbound_date", label: "出仓日期", kind: "date" },
  { key: "customs_staff_id", label: "指定清关人员", kind: "select" },
  { key: "booked_volume", label: "订舱方数", kind: "number" },
  { key: "planned_flight_date", label: "约定航班起飞日期", kind: "date" },
  { key: "booked_weight", label: "订舱重量", kind: "number" },
  { key: "density", label: "密度", kind: "number" },
  { key: "quotation", label: "报价", kind: "text" },
  { key: "include_tc", label: "含T", kind: "boolean" },
  { key: "departure_port", label: "始发港", kind: "text" },
  { key: "destination_port", label: "目的港", kind: "text" },
  { key: "planned_route_text", label: "航程", kind: "text" },
  { key: "internal_remark", label: "内部备注", kind: "text" }
];

function rowKey(row: Pick<WarehousePlannerRow, "source_type" | "source_id">) {
  return `${row.source_type}:${row.source_id}`;
}

function normalizePlannerChannel(value?: string | null): PlannerChannel {
  return value === "LHR" ? "LHR" : "AMS";
}

function candidateToRow(item: WarehousePlannerCandidate, channel: PlannerChannel = "AMS"): WarehousePlannerRow {
  return {
    source_type: item.source_type,
    source_id: item.source_id,
    planning_channel: channel,
    waybill_no: item.waybill_no || "",
    carrier_agent_id: item.carrier_agent_id ?? null,
    planned_flight_no: item.planned_flight_no || "",
    planned_flight_date: item.planned_flight_date || null,
    outbound_date: item.outbound_date || null,
    receipt_ids: (item.receipts || []).map((receipt) => receipt.id),
    customs_staff_id: item.customs_staff_id ?? null,
    booked_volume: item.booked_volume ?? null,
    booked_weight: item.booked_weight ?? null,
    density: item.density ?? null,
    quotation: item.quotation || "",
    include_tc: Boolean(item.include_tc),
    departure_port: item.departure_port || "",
    destination_port: item.destination_port || "",
    planned_route_text: item.planned_route_text || "",
    internal_remark: item.internal_remark || "",
    source_updated_at: item.source_updated_at
  };
}

function formatDecimal(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

function formatReceiptDensity(receipt: WarehouseReceipt) {
  const volume = Number(receipt.total_volume);
  if (!Number.isFinite(volume) || volume <= 0) return "-";
  return formatDecimal(receipt.weight_volume_ratio);
}

function receiptNumber(value?: string | number | null) {
  const num = Number(value);
  return Number.isFinite(num) ? num : 0;
}

function receiptSummary(row: WarehousePlannerRow, receiptMap: Map<number, WarehouseReceipt>) {
  const receiptIds = row.receipt_ids || [];
  let totalWeight = 0;
  let totalVolume = 0;
  let missingCount = 0;
  for (const receiptId of receiptIds) {
    const receipt = receiptMap.get(receiptId);
    if (!receipt) {
      missingCount += 1;
      continue;
    }
    totalWeight += receiptNumber(receipt.total_weight);
    totalVolume += receiptNumber(receipt.total_volume);
  }
  return {
    hasReceipt: receiptIds.length > 0,
    missingCount,
    totalWeight,
    totalVolume,
    density: totalVolume > 0 ? totalWeight / totalVolume : null
  };
}

function sourceLabel(value: WarehousePlannerRow["source_type"]) {
  if (value === "waybill") return "正式提单";
  if (value === "prebooking") return "预排仓";
  if (value === "import_waybill") return "导入提单";
  return "导入预排仓";
}

function channelTags(tags?: string[] | null) {
  return (tags || []).filter(Boolean);
}

function clampMainPanePercent(value: number) {
  if (!Number.isFinite(value)) return DEFAULT_MAIN_PANE_PERCENT;
  return Math.min(MAX_MAIN_PANE_PERCENT, Math.max(MIN_MAIN_PANE_PERCENT, value));
}

function preferenceToMainPanePercent(preference?: TableColumnPreference | null) {
  const value = Number(preference?.column_order?.[0]);
  return clampMainPanePercent(value);
}

function normalizePlannerColumnOrder(order?: string[] | null): PlannerColumnKey[] {
  const validColumns = new Set<string>(DEFAULT_PLANNER_COLUMN_ORDER);
  const seen = new Set<string>();
  const normalized: PlannerColumnKey[] = [];
  const providedColumns = order || [];
  for (const column of providedColumns) {
    if (!validColumns.has(column) || seen.has(column)) continue;
    seen.add(column);
    normalized.push(column as PlannerColumnKey);
  }
  if (providedColumns.length && !seen.has("receipt_summary")) {
    const receiptIndex = normalized.indexOf("receipts");
    if (receiptIndex >= 0) {
      normalized.splice(receiptIndex + 1, 0, "receipt_summary");
      seen.add("receipt_summary");
    }
  }
  for (const column of DEFAULT_PLANNER_COLUMN_ORDER) {
    if (!seen.has(column)) normalized.push(column);
  }
  return normalized;
}

function reorderPlannerColumns(
  order: PlannerColumnKey[],
  draggedKey: PlannerColumnKey,
  targetKey: PlannerColumnKey,
  insertAfter: boolean,
): PlannerColumnKey[] {
  if (draggedKey === targetKey) return order;
  const withoutDragged = order.filter((column) => column !== draggedKey);
  const targetIndex = withoutDragged.indexOf(targetKey);
  if (targetIndex < 0) return order;
  const insertIndex = targetIndex + (insertAfter ? 1 : 0);
  return [
    ...withoutDragged.slice(0, insertIndex),
    draggedKey,
    ...withoutDragged.slice(insertIndex)
  ];
}

interface BoardCellSpan {
  render: boolean;
  rowSpan: number;
}

interface PlannerCommitScope {
  allRows: WarehousePlannerRow[];
  commitRows: WarehousePlannerRow[];
  commitKeys: string[];
  selectedOnly: boolean;
}

function clearBoardGroup(row: WarehousePlannerRow): WarehousePlannerRow {
  return {
    ...row,
    board_group_id: null,
    board_group_order: null,
    board_booked_volume: null,
    board_booked_weight: null
  };
}

function normalizeBoardGroups(rows: WarehousePlannerRow[]) {
  const counts = new Map<string, number>();
  for (const row of rows) {
    if (row.board_group_id) counts.set(row.board_group_id, (counts.get(row.board_group_id) || 0) + 1);
  }
  return rows.map((row) => (row.board_group_id && (counts.get(row.board_group_id) || 0) < 2 ? clearBoardGroup(row) : row));
}

function buildCommitScope(rows: WarehousePlannerRow[], selectedKeys: Set<string>): PlannerCommitScope {
  if (!selectedKeys.size) {
    return {
      allRows: rows,
      commitRows: rows,
      commitKeys: rows.map(rowKey),
      selectedOnly: false
    };
  }

  const commitKeys = new Set<string>();
  const selectedGroupIds = new Set(
    rows
      .filter((row) => selectedKeys.has(rowKey(row)) && row.board_group_id)
      .map((row) => row.board_group_id as string)
  );

  for (const row of rows) {
    const key = rowKey(row);
    if (selectedKeys.has(key) || (row.board_group_id && selectedGroupIds.has(row.board_group_id))) {
      commitKeys.add(key);
    }
  }

  return {
    allRows: rows,
    commitRows: rows.filter((row) => commitKeys.has(rowKey(row))),
    commitKeys: [...commitKeys],
    selectedOnly: true
  };
}

function mergeCommitRemainingRows(
  allRows: WarehousePlannerRow[],
  commitKeys: string[],
  remainingRows: WarehousePlannerRow[]
) {
  const commitKeySet = new Set(commitKeys);
  const remainingByKey = new Map(remainingRows.map((row) => [rowKey(row), row]));
  return normalizeBoardGroups(
    allRows.flatMap((row) => {
      const key = rowKey(row);
      if (!commitKeySet.has(key)) return [row];
      const remaining = remainingByKey.get(key);
      return remaining ? [remaining] : [];
    })
  );
}

function placeGroupAtFirstOccurrence(rows: WarehousePlannerRow[], groupId: string) {
  const firstIndex = rows.findIndex((row) => row.board_group_id === groupId);
  if (firstIndex < 0) return rows;
  const groupRows = rows.filter((row) => row.board_group_id === groupId);
  const next: WarehousePlannerRow[] = [];
  let inserted = false;
  for (let index = 0; index < rows.length; index += 1) {
    const row = rows[index];
    if (row.board_group_id === groupId) {
      if (!inserted && index === firstIndex) {
        next.push(...groupRows);
        inserted = true;
      }
      continue;
    }
    next.push(row);
  }
  return next;
}

function buildBoardCellSpans(rows: WarehousePlannerRow[], kind: "volume" | "weight") {
  const spans = new Map<string, BoardCellSpan>();
  let index = 0;
  while (index < rows.length) {
    const row = rows[index];
    const groupId = row.board_group_id;
    const useGroupCell = Boolean(groupId && (kind === "volume" || row.board_booked_weight !== null && row.board_booked_weight !== undefined && row.board_booked_weight !== ""));
    if (!groupId || !useGroupCell) {
      index += 1;
      continue;
    }
    let end = index + 1;
    while (end < rows.length && rows[end].board_group_id === groupId) end += 1;
    const span = end - index;
    if (span > 1) {
      spans.set(rowKey(rows[index]), { render: true, rowSpan: span });
      for (let skipIndex = index + 1; skipIndex < end; skipIndex += 1) {
        spans.set(rowKey(rows[skipIndex]), { render: false, rowSpan: 0 });
      }
    }
    index = end;
  }
  return spans;
}

function sumNumeric(values: Array<string | number | null | undefined>) {
  let total = 0;
  let hasValue = false;
  for (const value of values) {
    if (value === null || value === undefined || value === "") continue;
    const numeric = Number(value);
    if (!Number.isFinite(numeric)) continue;
    total += numeric;
    hasValue = true;
  }
  return hasValue ? Number(total.toFixed(3)) : null;
}

interface PlannerColumnRenderArgs {
  row: WarehousePlannerRow;
  key: string;
  error?: WarehousePlannerRowResult;
  volumeSpan?: BoardCellSpan;
  weightSpan?: BoardCellSpan;
}

interface PlannerTableColumn {
  key: PlannerColumnKey;
  label: string;
  render: (args: PlannerColumnRenderArgs) => ReactNode;
}

export default function WarehousePlannerPage() {
  const saveTimerRef = useRef<number | null>(null);
  const splitSaveTimerRef = useRef<number | null>(null);
  const plannerLayoutRef = useRef<HTMLDivElement>(null);
  const plannerImportInputRef = useRef<HTMLInputElement>(null);
  const [rows, setRows] = useState<WarehousePlannerRow[]>([]);
  const [loadedDraft, setLoadedDraft] = useState(false);
  const [loadedSplitPreference, setLoadedSplitPreference] = useState(false);
  const [mainPanePercent, setMainPanePercent] = useState(DEFAULT_MAIN_PANE_PERCENT);
  const [resizingSplit, setResizingSplit] = useState(false);
  const [plannerColumnOrder, setPlannerColumnOrder] = useState<PlannerColumnKey[]>(() => normalizePlannerColumnOrder());
  const [draggingPlannerColumn, setDraggingPlannerColumn] = useState<PlannerColumnKey | null>(null);
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [rowSortDragKey, setRowSortDragKey] = useState<string | null>(null);
  const [activePlannerChannel, setActivePlannerChannel] = useState<PlannerChannel>("AMS");
  const [candidates, setCandidates] = useState<WarehousePlannerCandidates | null>(null);
  const [selectedCandidates, setSelectedCandidates] = useState<Set<string>>(new Set());
  const [selectedReceipts, setSelectedReceipts] = useState<Set<number>>(new Set());
  const [receiptSortDragId, setReceiptSortDragId] = useState<number | null>(null);
  const [receiptOrderSaving, setReceiptOrderSaving] = useState(false);
  const [rightPanelMode, setRightPanelMode] = useState<RightPanelMode>("candidates");
  const [receiptViewMode, setReceiptViewMode] = useState<ReceiptViewMode>("list");
  const [rightPanelVisible, setRightPanelVisible] = useState(true);
  const [agents, setAgents] = useState<CarrierAgent[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [message, setMessage] = useState("");
  const [saving, setSaving] = useState(false);
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchField, setBatchField] = useState<PlannerField>("outbound_date");
  const [batchValue, setBatchValue] = useState("");
  const [validationOpen, setValidationOpen] = useState(false);
  const [validationResult, setValidationResult] = useState<WarehousePlannerValidateResult | null>(null);
  const [commitResult, setCommitResult] = useState<WarehousePlannerCommitResult | null>(null);
  const [commitScope, setCommitScope] = useState<PlannerCommitScope | null>(null);
  const [rowErrors, setRowErrors] = useState<Record<string, WarehousePlannerRowResult>>({});
  const [plannerImportOpen, setPlannerImportOpen] = useState(false);
  const [plannerImportResult, setPlannerImportResult] = useState<WarehousePlannerBulkImportResult | null>(null);
  const [plannerImportError, setPlannerImportError] = useState("");
  const [uploadingPlannerImport, setUploadingPlannerImport] = useState(false);

  const allCandidates = useMemo(
    () => [...(candidates?.waybills || []), ...(candidates?.prebookings || [])],
    [candidates]
  );
  const rowKeySet = useMemo(() => new Set(rows.map(rowKey)), [rows]);
  const assignedReceiptIds = useMemo(() => {
    const ids = new Set<number>();
    for (const row of rows) {
      for (const receiptId of row.receipt_ids || []) ids.add(receiptId);
    }
    return ids;
  }, [rows]);
  const channelRows = useMemo(
    () => ({
      AMS: rows.filter((row) => normalizePlannerChannel(row.planning_channel) === "AMS"),
      LHR: rows.filter((row) => normalizePlannerChannel(row.planning_channel) === "LHR")
    }),
    [rows]
  );
  const activeRows = channelRows[activePlannerChannel];
  const activeSelectedRows = useMemo(() => activeRows.filter((row) => selectedRows.has(rowKey(row))), [activeRows, selectedRows]);
  const selectedRowKeys = useMemo(() => [...selectedRows], [selectedRows]);
  const selectedRowCount = selectedRows.size;
  const activeVolumeSpans = useMemo(() => buildBoardCellSpans(activeRows, "volume"), [activeRows]);
  const activeWeightSpans = useMemo(() => buildBoardCellSpans(activeRows, "weight"), [activeRows]);
  const customsStaff = useMemo(
    () => users.filter((item) => item.is_active && item.roles.some((role) => role.code === "customs_staff")),
    [users]
  );
  const receiptMap = useMemo(() => {
    const map = new Map<number, WarehouseReceipt>();
    for (const receipt of candidates?.unbound_receipts || []) map.set(receipt.id, receipt);
    for (const candidate of allCandidates) for (const receipt of candidate.receipts || []) map.set(receipt.id, receipt);
    return map;
  }, [allCandidates, candidates?.unbound_receipts]);

  const loadAll = useCallback(async () => {
    setMessage("");
    const [draft, candidateData, agentData, userData] = await Promise.all([
      apiClient.get<{ rows: WarehousePlannerRow[]; updated_at?: string | null }>("/warehouse-planner/draft"),
      apiClient.get<WarehousePlannerCandidates>("/warehouse-planner/candidates"),
      apiClient.get<CarrierAgent[]>("/carrier-agents"),
      apiClient.get<User[]>("/users")
    ]);
    setRows(normalizeBoardGroups((draft.rows || []).map((row) => ({ ...row, planning_channel: normalizePlannerChannel(row.planning_channel) }))));
    setCandidates(candidateData);
    setAgents(agentData.filter((item) => item.enabled));
    setUsers(userData);
    setLoadedDraft(true);
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAll().catch((error) => setMessage(error instanceof Error ? error.message : "加载排仓编辑器失败。"));
    }, 0);
    return () => window.clearTimeout(timer);
  }, [loadAll]);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<TableColumnPreference>(`/user-preferences/table-columns/${encodeURIComponent(PLANNER_SPLIT_PREFERENCE_KEY)}`)
      .then((preference) => {
        if (cancelled) return;
        setMainPanePercent(preferenceToMainPanePercent(preference));
        setLoadedSplitPreference(true);
      })
      .catch(() => {
        if (cancelled) return;
        setMainPanePercent(DEFAULT_MAIN_PANE_PERCENT);
        setLoadedSplitPreference(true);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;
    apiClient
      .get<TableColumnPreference>(`/user-preferences/table-columns/${encodeURIComponent(PLANNER_COLUMNS_PREFERENCE_KEY)}`)
      .then((preference) => {
        if (!cancelled) setPlannerColumnOrder(normalizePlannerColumnOrder(preference.column_order));
      })
      .catch(() => {
        if (!cancelled) setPlannerColumnOrder(normalizePlannerColumnOrder());
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const savePlannerColumnOrder = useCallback(async (nextOrder: PlannerColumnKey[]) => {
    try {
      await apiClient.put<TableColumnPreference>(
        `/user-preferences/table-columns/${encodeURIComponent(PLANNER_COLUMNS_PREFERENCE_KEY)}`,
        { column_order: nextOrder }
      );
    } catch (error) {
      setMessage(error instanceof Error ? `排仓编辑区列顺序保存失败：${error.message}` : "排仓编辑区列顺序保存失败。");
    }
  }, []);

  useEffect(() => {
    if (!loadedDraft) return;
    if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    saveTimerRef.current = window.setTimeout(() => {
      apiClient.put("/warehouse-planner/draft", { rows }).catch((error) => {
        setMessage(error instanceof Error ? error.message : "保存排仓草稿失败。");
      });
    }, 600);
    return () => {
      if (saveTimerRef.current) window.clearTimeout(saveTimerRef.current);
    };
  }, [loadedDraft, rows]);

  useEffect(() => {
    if (!loadedSplitPreference) return;
    if (splitSaveTimerRef.current) window.clearTimeout(splitSaveTimerRef.current);
    splitSaveTimerRef.current = window.setTimeout(() => {
      apiClient
        .put<TableColumnPreference>(
          `/user-preferences/table-columns/${encodeURIComponent(PLANNER_SPLIT_PREFERENCE_KEY)}`,
          { column_order: [String(Math.round(mainPanePercent))] }
        )
        .catch((error) => {
          setMessage(error instanceof Error ? `排仓宽度保存失败：${error.message}` : "排仓宽度保存失败。");
        });
    }, 500);
    return () => {
      if (splitSaveTimerRef.current) window.clearTimeout(splitSaveTimerRef.current);
    };
  }, [loadedSplitPreference, mainPanePercent]);

  useEffect(() => {
    if (!resizingSplit) return;
    function onPointerMove(event: PointerEvent) {
      const rect = plannerLayoutRef.current?.getBoundingClientRect();
      if (!rect || rect.width <= 0) return;
      const nextPercent = ((event.clientX - rect.left) / rect.width) * 100;
      setMainPanePercent(clampMainPanePercent(nextPercent));
    }
    function onPointerUp() {
      setResizingSplit(false);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }

    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    };
  }, [resizingSplit]);

  function updateRow(key: string, changes: Partial<WarehousePlannerRow>) {
    setRows((prev) => prev.map((row) => (rowKey(row) === key ? { ...row, ...changes } : row)));
    setRowErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function updateBoardGroup(groupId: string, changes: Partial<WarehousePlannerRow>) {
    setRows((prev) => prev.map((row) => (row.board_group_id === groupId ? { ...row, ...changes } : row)));
    setRowErrors((prev) => {
      const next = { ...prev };
      for (const row of rows) {
        if (row.board_group_id === groupId) delete next[rowKey(row)];
      }
      return next;
    });
  }

  function removeFromBoardGroup(key: string) {
    setRows((prev) => normalizeBoardGroups(prev.map((row) => (rowKey(row) === key ? clearBoardGroup(row) : row))));
  }

  function addSelectedRowsToBoardGroup(groupId: string) {
    const groupRows = rows.filter((row) => row.board_group_id === groupId);
    const groupSource = groupRows[0];
    if (!groupSource) return;
    const candidateKeys = new Set(activeSelectedRows.map(rowKey));
    setRows((prev) => {
      const next = prev.map((row) => {
        if (!candidateKeys.has(rowKey(row)) || row.board_group_id === groupId) return row;
        return {
          ...row,
          board_group_id: groupId,
          board_group_order: groupSource.board_group_order ?? 0,
          board_booked_volume: groupSource.board_booked_volume ?? null,
          board_booked_weight: groupSource.board_booked_weight ?? null,
          booked_volume: null,
          booked_weight: groupSource.board_booked_weight !== null && groupSource.board_booked_weight !== undefined ? null : row.booked_weight
        };
      });
      return normalizeBoardGroups(placeGroupAtFirstOccurrence(next, groupId));
    });
  }

  function mergeSelectedRowsAsBoard() {
    const selectedActiveRows = activeRows.filter((row) => selectedRows.has(rowKey(row)));
    if (selectedActiveRows.length < 2) return;
    const groupId = `manual-board-${Date.now()}`;
    const boardVolume =
      selectedActiveRows.find((row) => row.board_booked_volume !== null && row.board_booked_volume !== undefined)?.board_booked_volume ??
      sumNumeric(selectedActiveRows.map((row) => row.booked_volume));
    const boardWeight =
      selectedActiveRows.find((row) => row.board_booked_weight !== null && row.board_booked_weight !== undefined)?.board_booked_weight ??
      sumNumeric(selectedActiveRows.map((row) => row.booked_weight));
    const selectedKeys = new Set(selectedActiveRows.map(rowKey));
    setRows((prev) => {
      const next = prev.map((row) => {
        if (!selectedKeys.has(rowKey(row))) return row;
        return {
          ...row,
          board_group_id: groupId,
          board_group_order: Date.now(),
          board_booked_volume: boardVolume,
          board_booked_weight: boardWeight,
          booked_volume: null,
          booked_weight: boardWeight !== null && boardWeight !== undefined ? null : row.booked_weight
        };
      });
      return normalizeBoardGroups(placeGroupAtFirstOccurrence(next, groupId));
    });
  }

  function moveRowOrGroupToChannel(key: string, channel: PlannerChannel) {
    const targetRow = rows.find((row) => rowKey(row) === key);
    if (!targetRow?.board_group_id) {
      updateRow(key, { planning_channel: channel });
      return;
    }
    updateBoardGroup(targetRow.board_group_id, { planning_channel: channel });
  }

  function handlePlannerColumnDrop(event: DragEvent<HTMLTableCellElement>, targetKey: PlannerColumnKey) {
    event.preventDefault();
    if (!draggingPlannerColumn || draggingPlannerColumn === targetKey) {
      setDraggingPlannerColumn(null);
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const insertAfter = event.clientX > rect.left + rect.width / 2;
    const nextOrder = reorderPlannerColumns(plannerColumnOrder, draggingPlannerColumn, targetKey, insertAfter);
    setPlannerColumnOrder(nextOrder);
    setDraggingPlannerColumn(null);
    void savePlannerColumnOrder(nextOrder);
  }

  function resetPlannerColumnOrder() {
    const nextOrder = normalizePlannerColumnOrder();
    setPlannerColumnOrder(nextOrder);
    setMessage("已恢复排仓编辑区默认列顺序。");
    void savePlannerColumnOrder([]);
  }

  function removeRow(key: string) {
    setRows((prev) => normalizeBoardGroups(prev.filter((row) => rowKey(row) !== key)));
    setSelectedRows((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }

  function toggleActiveChannelSelection(checked: boolean) {
    const activeKeys = new Set(activeRows.map(rowKey));
    setSelectedRows((prev) => {
      const next = new Set([...prev].filter((key) => !activeKeys.has(key)));
      if (checked) {
        for (const key of activeKeys) next.add(key);
      }
      return next;
    });
  }

  function addCandidates(items: WarehousePlannerCandidate[], channel: PlannerChannel = activePlannerChannel) {
    setRows((prev) => {
      const existing = new Set(prev.map(rowKey));
      const additions = items.map((item) => candidateToRow(item, channel)).filter((row) => !existing.has(rowKey(row)));
      return [...prev, ...additions];
    });
    setSelectedCandidates(new Set());
  }

  function selectedCandidateItems() {
    return allCandidates.filter((item) => selectedCandidates.has(rowKey(item)));
  }

  function onCandidateDragStart(event: DragEvent<HTMLDivElement>, item?: WarehousePlannerCandidate) {
    const keys = item && !selectedCandidates.has(rowKey(item)) ? [rowKey(item)] : [...selectedCandidates];
    event.dataTransfer.setData(CANDIDATE_DRAG_TYPE, JSON.stringify(keys));
    event.dataTransfer.effectAllowed = "copy";
  }

  function onReceiptDragStart(event: DragEvent<HTMLDivElement>, receipt?: WarehouseReceipt) {
    const ids = receipt && !selectedReceipts.has(receipt.id) ? [receipt.id] : [...selectedReceipts];
    event.dataTransfer.setData(RECEIPT_DRAG_TYPE, JSON.stringify(ids));
    event.dataTransfer.effectAllowed = "copy";
  }

  function onReceiptSortDragStart(event: DragEvent<HTMLElement>, receipt: WarehouseReceipt) {
    event.stopPropagation();
    setReceiptSortDragId(receipt.id);
    event.dataTransfer.setData("text/plain", String(receipt.id));
    event.dataTransfer.effectAllowed = "move";
  }

  function onPlannerRowSortDragStart(event: DragEvent<HTMLElement>, row: WarehousePlannerRow) {
    event.stopPropagation();
    const key = rowKey(row);
    const activeKeys = activeRows.map(rowKey);
    const activeSelectedKeys = activeKeys.filter((item) => selectedRows.has(item));
    const expandedSelectedKeys = new Set(activeSelectedKeys);
    for (const selectedRow of activeRows.filter((item) => selectedRows.has(rowKey(item)) && item.board_group_id)) {
      for (const groupRow of activeRows.filter((item) => item.board_group_id === selectedRow.board_group_id)) {
        expandedSelectedKeys.add(rowKey(groupRow));
      }
    }
    const groupKeys = row.board_group_id ? activeRows.filter((item) => item.board_group_id === row.board_group_id).map(rowKey) : [];
    const dragKeys = selectedRows.has(key) && expandedSelectedKeys.size ? [...expandedSelectedKeys] : groupKeys.length ? groupKeys : [key];
    setRowSortDragKey(key);
    event.dataTransfer.setData(PLANNER_ROW_DRAG_TYPE, JSON.stringify(dragKeys));
    event.dataTransfer.effectAllowed = "move";
  }

  function movePlannerRowsBefore(dragKeys: string[], targetKey: string, channel: PlannerChannel) {
    setRows((prev) => {
      const activeKeys = prev
        .filter((row) => normalizePlannerChannel(row.planning_channel) === channel)
        .map(rowKey);
      const activeKeySet = new Set(activeKeys);
      if (!activeKeySet.has(targetKey)) return prev;
      const movingKeySet = new Set(dragKeys.filter((key) => key !== targetKey && activeKeySet.has(key)));
      if (!movingKeySet.size) return prev;
      const movingRows = prev.filter((row) => movingKeySet.has(rowKey(row)));
      const remainingActiveRows = prev.filter(
        (row) => normalizePlannerChannel(row.planning_channel) === channel && !movingKeySet.has(rowKey(row))
      );
      const targetIndex = remainingActiveRows.findIndex((row) => rowKey(row) === targetKey);
      if (targetIndex < 0) return prev;
      const reorderedActiveRows = [
        ...remainingActiveRows.slice(0, targetIndex),
        ...movingRows,
        ...remainingActiveRows.slice(targetIndex)
      ];
      const nextActiveRows = [...reorderedActiveRows];
      return prev.map((row) => (normalizePlannerChannel(row.planning_channel) === channel ? nextActiveRows.shift() || row : row));
    });
  }

  function onPlannerRowDrop(event: DragEvent<HTMLTableRowElement>, targetRow: WarehousePlannerRow) {
    const rowPayload = event.dataTransfer.getData(PLANNER_ROW_DRAG_TYPE);
    if (rowPayload) {
      event.preventDefault();
      event.stopPropagation();
      try {
        movePlannerRowsBefore(JSON.parse(rowPayload) as string[], rowKey(targetRow), normalizePlannerChannel(targetRow.planning_channel));
      } catch {
        setMessage("移动排仓条目失败，请重新拖动。");
      } finally {
        setRowSortDragKey(null);
      }
      return;
    }
    onDropReceipts(event, rowKey(targetRow));
  }

  async function persistPlannerReceiptOrder(nextReceipts: WarehouseReceipt[]) {
    setCandidates((prev) => (prev ? { ...prev, unbound_receipts: nextReceipts } : prev));
    setReceiptOrderSaving(true);
    setMessage("");
    try {
      await apiClient.put<void>("/warehouse-receipts/unbound/order", {
        receipt_ids: nextReceipts.map((item) => item.id)
      });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存入仓号排序失败。");
      void loadAll().catch((loadError) => setMessage(loadError instanceof Error ? loadError.message : "重新加载排仓编辑器失败。"));
    } finally {
      setReceiptOrderSaving(false);
    }
  }

  function movePlannerReceiptBefore(dragId: number, targetId: number) {
    if (dragId === targetId || !candidates?.unbound_receipts.length) return;
    const source = candidates.unbound_receipts.find((item) => item.id === dragId);
    if (!source) return;
    const withoutSource = candidates.unbound_receipts.filter((item) => item.id !== dragId);
    const targetIndex = withoutSource.findIndex((item) => item.id === targetId);
    if (targetIndex < 0) return;
    const nextReceipts = [
      ...withoutSource.slice(0, targetIndex),
      source,
      ...withoutSource.slice(targetIndex)
    ];
    void persistPlannerReceiptOrder(nextReceipts);
  }

  function toggleReceiptSelection(receiptId: number, checked: boolean) {
    setSelectedReceipts((prev) => {
      const next = new Set(prev);
      if (checked) next.add(receiptId);
      else next.delete(receiptId);
      return next;
    });
  }

  function onDropIntoRows(event: DragEvent<HTMLDivElement>) {
    const raw = event.dataTransfer.getData(CANDIDATE_DRAG_TYPE);
    if (!raw) return;
    event.preventDefault();
    const keys = JSON.parse(raw) as string[];
    addCandidates(allCandidates.filter((item) => keys.includes(rowKey(item))));
  }

  function onDropReceipts(event: DragEvent<HTMLElement>, targetKey?: string) {
    const raw = event.dataTransfer.getData(RECEIPT_DRAG_TYPE);
    if (!raw) return;
    event.preventDefault();
    const ids = (JSON.parse(raw) as number[]).filter((id) => Number.isFinite(id));
    const targets = targetKey ? [targetKey] : selectedRowKeys;
    if (!targets.length) {
      setMessage("请先选择排仓编辑区里的提单，再拖入入仓号。");
      return;
    }
    setRows((prev) =>
      prev.map((row) => {
        if (!targets.includes(rowKey(row))) return row;
        return { ...row, receipt_ids: [...new Set([...(row.receipt_ids || []), ...ids])] };
      })
    );
    setSelectedReceipts(new Set());
  }

  function applyBatchEdit() {
    const keys = selectedRowKeys;
    if (!keys.length) return;
    const field = BATCH_FIELDS.find((item) => item.key === batchField);
    let value: string | number | boolean | null = batchValue;
    if (field?.kind === "number") value = batchValue === "" ? null : Number(batchValue);
    if (field?.kind === "boolean") value = batchValue === "true";
    if (field?.kind === "select") value = batchValue === CLEAR_VALUE || batchValue === "" ? null : Number(batchValue);
    if (field?.kind === "date") value = batchValue || null;
    setRows((prev) => {
      if (batchField === "booked_volume" || batchField === "booked_weight") {
        const selectedKeySet = new Set(keys);
        const selectedGroupIds = new Set(
          prev
            .filter((row) => selectedKeySet.has(rowKey(row)) && row.board_group_id)
            .map((row) => row.board_group_id as string)
        );
        return prev.map((row) => {
          const selected = selectedKeySet.has(rowKey(row));
          const grouped = row.board_group_id && selectedGroupIds.has(row.board_group_id);
          if (batchField === "booked_volume" && grouped) return { ...row, board_booked_volume: value as number | null, booked_volume: null };
          if (batchField === "booked_weight" && grouped) return { ...row, board_booked_weight: value as number | null, booked_weight: null };
          if (!selected) return row;
          return { ...row, [batchField]: value };
        });
      }
      return prev.map((row) => (keys.includes(rowKey(row)) ? { ...row, [batchField]: value } : row));
    });
    setBatchOpen(false);
    setBatchValue("");
  }

  async function validateBeforeCommit() {
    setSaving(true);
    setMessage("");
    setCommitResult(null);
    setCommitScope(null);
    try {
      const scope = buildCommitScope(rows, selectedRows);
      if (!scope.commitRows.length) {
        setMessage("请选择需要录入排仓的提单。");
        return;
      }
      await apiClient.put("/warehouse-planner/draft", { rows });
      const result = await apiClient.post<WarehousePlannerValidateResult>("/warehouse-planner/validate", { rows: scope.commitRows });
      setCommitScope(scope);
      setValidationResult(result);
      setRowErrors(Object.fromEntries(result.results.filter((item) => item.status === "invalid").map((item) => [`${item.source_type}:${item.source_id}`, item])));
      setValidationOpen(true);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "校验排仓数据失败。");
    } finally {
      setSaving(false);
    }
  }

  async function commitRows(mode: "all_or_none" | "success_only") {
    const scope = commitScope;
    if (!scope) {
      setMessage("请先校验需要录入排仓的提单。");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const result = await apiClient.post<WarehousePlannerCommitResult>("/warehouse-planner/commit", { rows: scope.commitRows, mode });
      const nextRows = scope.selectedOnly
        ? mergeCommitRemainingRows(scope.allRows, scope.commitKeys, result.remaining_rows || [])
        : normalizeBoardGroups(result.remaining_rows || []);
      await apiClient.put("/warehouse-planner/draft", { rows: nextRows });
      setCommitResult(result);
      setRows(nextRows);
      setSelectedRows(new Set());
      setRowErrors(Object.fromEntries(result.results.filter((item) => item.status === "failed").map((item) => [`${item.source_type}:${item.source_id}`, item])));
      await loadAll();
      setMessage(`录入完成：成功 ${result.success_count} 条，失败 ${result.failed_count} 条。`);
      setCommitScope(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "录入排仓失败。");
    } finally {
      setSaving(false);
    }
  }

  async function clearDraft() {
    if (!window.confirm("确认清空当前排仓编辑区草稿吗？")) return;
    await apiClient.delete<void>("/warehouse-planner/draft");
    setRows([]);
    setSelectedRows(new Set());
    setRowErrors({});
    setMessage("排仓编辑区已清空。");
  }

  async function exportDraft() {
    await apiClient.put("/warehouse-planner/draft", { rows });
    const { blob, filename } = await apiClient.download("/warehouse-planner/draft/export");
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "排仓编辑区.xlsx";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }

  async function uploadPlannerImportFile(file: File | null | undefined) {
    if (!file) return;
    setPlannerImportOpen(true);
    setUploadingPlannerImport(true);
    setPlannerImportError("");
    setPlannerImportResult(null);
    setMessage("");
    try {
      const formData = new FormData();
      formData.append("file", file);
      const result = await apiClient.postForm<WarehousePlannerBulkImportResult>("/warehouse-planner/bulk-import", formData);
      setPlannerImportResult(result);
      setRows((prev) => {
        const existing = new Set(prev.map(rowKey));
        const additions = result.rows
          .filter((row) => !existing.has(rowKey(row)))
          .map((row) => ({ ...row, planning_channel: activePlannerChannel }));
        return normalizeBoardGroups([...prev, ...additions]);
      });
      setMessage(`批量导入完成：导入 ${result.imported_count} 行，跳过 ${result.skipped_count} 行，提示 ${result.warnings.length} 条。`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "批量导入排仓草稿失败。";
      setPlannerImportError(errorMessage);
      setMessage(errorMessage);
    } finally {
      setUploadingPlannerImport(false);
    }
  }

  function renderSelectValue(value?: number | null) {
    return value === null || value === undefined ? CLEAR_VALUE : String(value);
  }

  const plannerColumnDefinitions: Record<PlannerColumnKey, PlannerTableColumn> = {
    source: {
      key: "source",
      label: PLANNER_COLUMN_LABELS.source,
      render: ({ row, error }) => (
        <TD>
          <div className="font-medium text-slate-900">{sourceLabel(row.source_type)}</div>
          {error ? <div className="mt-1 text-xs text-red-600">{error.errors.map((item) => item.message).join("；")}</div> : null}
        </TD>
      )
    },
    carrier_agent: {
      key: "carrier_agent",
      label: PLANNER_COLUMN_LABELS.carrier_agent,
      render: ({ row, key }) => (
        <TD>
          <Select value={renderSelectValue(row.carrier_agent_id)} onValueChange={(value) => updateRow(key, { carrier_agent_id: value === CLEAR_VALUE ? null : Number(value) })}>
            <SelectTrigger className="h-9 min-w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={CLEAR_VALUE}>未选择</SelectItem>
              {agents.map((agent) => <SelectItem key={agent.id} value={String(agent.id)}>{agent.agent_name}</SelectItem>)}
            </SelectContent>
          </Select>
        </TD>
      )
    },
    planned_flight_no: {
      key: "planned_flight_no",
      label: PLANNER_COLUMN_LABELS.planned_flight_no,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-28" value={row.planned_flight_no || ""} onChange={(event) => updateRow(key, { planned_flight_no: event.target.value })} /></TD>
      )
    },
    waybill_no: {
      key: "waybill_no",
      label: PLANNER_COLUMN_LABELS.waybill_no,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-36" value={row.waybill_no || ""} onChange={(event) => updateRow(key, { waybill_no: event.target.value })} /></TD>
      )
    },
    outbound_date: {
      key: "outbound_date",
      label: PLANNER_COLUMN_LABELS.outbound_date,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-36" type="date" value={row.outbound_date || ""} onChange={(event) => updateRow(key, { outbound_date: event.target.value || null })} /></TD>
      )
    },
    receipts: {
      key: "receipts",
      label: PLANNER_COLUMN_LABELS.receipts,
      render: ({ row, key }) => (
        <TD>
          <div className="flex min-w-56 flex-wrap gap-1">
            {(row.receipt_ids || []).map((receiptId) => {
              const receipt = receiptMap.get(receiptId);
              return (
                <span
                  key={receiptId}
                  title={receipt?.uploaded_at ? `上传时间：${formatDateTime(receipt.uploaded_at)}` : undefined}
                >
                  <Badge variant="default" className="gap-1">
                    {receipt?.warehouse_no || `#${receiptId}`}
                    <button type="button" onClick={() => updateRow(key, { receipt_ids: row.receipt_ids.filter((id) => id !== receiptId) })}>×</button>
                  </Badge>
                </span>
              );
            })}
            {!row.receipt_ids?.length ? <span className="text-xs text-slate-400">拖入入仓号</span> : null}
          </div>
        </TD>
      )
    },
    receipt_summary: {
      key: "receipt_summary",
      label: PLANNER_COLUMN_LABELS.receipt_summary,
      render: ({ row }) => {
        const summary = receiptSummary(row, receiptMap);
        if (!summary.hasReceipt) {
          return <TD><span className="text-xs text-slate-400">-</span></TD>;
        }
        return (
          <TD>
            <div className="min-w-56 space-y-1">
              <div className="flex flex-wrap gap-1">
                <Badge variant="gray">总方数 {formatDecimal(summary.totalVolume)}</Badge>
                <Badge variant="gray">总重量 {formatDecimal(summary.totalWeight)}</Badge>
                <Badge variant="gray">总密度 {summary.density === null ? "-" : formatDecimal(summary.density)}</Badge>
              </div>
              {summary.missingCount > 0 ? (
                <div className="text-[11px] text-amber-600">
                  部分入仓号未加载（{summary.missingCount} 个）
                </div>
              ) : null}
            </div>
          </TD>
        );
      }
    },
    customs_staff: {
      key: "customs_staff",
      label: PLANNER_COLUMN_LABELS.customs_staff,
      render: ({ row, key }) => (
        <TD>
          <Select value={renderSelectValue(row.customs_staff_id)} onValueChange={(value) => updateRow(key, { customs_staff_id: value === CLEAR_VALUE ? null : Number(value) })}>
            <SelectTrigger className="h-9 min-w-36"><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value={CLEAR_VALUE}>未指定</SelectItem>
              {customsStaff.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.display_name || item.username}</SelectItem>)}
            </SelectContent>
          </Select>
        </TD>
      )
    },
    booked_volume: {
      key: "booked_volume",
      label: PLANNER_COLUMN_LABELS.booked_volume,
      render: ({ row, key, volumeSpan }) => {
        if (volumeSpan && !volumeSpan.render) return null;
        if (row.board_group_id && volumeSpan?.render) {
          return (
            <TD rowSpan={volumeSpan.rowSpan} className="bg-purple-50/70 align-top">
              <div className="min-w-36 space-y-2">
                <Input
                  className="h-9"
                  type="number"
                  step="0.001"
                  value={row.board_booked_volume ?? ""}
                  onChange={(event) => updateBoardGroup(row.board_group_id as string, { board_booked_volume: event.target.value, booked_volume: null })}
                />
                <div className="flex flex-wrap items-center gap-2 text-xs text-purple-700">
                  <span>同板 {volumeSpan.rowSpan} 票</span>
                  <button type="button" className="font-medium hover:underline" onClick={() => addSelectedRowsToBoardGroup(row.board_group_id as string)}>
                    加入选中
                  </button>
                </div>
              </div>
            </TD>
          );
        }
        return <TD><Input className="h-9 min-w-28" type="number" step="0.001" value={row.booked_volume ?? ""} onChange={(event) => updateRow(key, { booked_volume: event.target.value })} /></TD>;
      }
    },
    planned_flight_date: {
      key: "planned_flight_date",
      label: PLANNER_COLUMN_LABELS.planned_flight_date,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-36" type="date" value={row.planned_flight_date || ""} onChange={(event) => updateRow(key, { planned_flight_date: event.target.value || null })} /></TD>
      )
    },
    booked_weight: {
      key: "booked_weight",
      label: PLANNER_COLUMN_LABELS.booked_weight,
      render: ({ row, key, weightSpan }) => {
        if (weightSpan && !weightSpan.render) return null;
        if (row.board_group_id && weightSpan?.render) {
          return (
            <TD rowSpan={weightSpan.rowSpan} className="bg-purple-50/70 align-top">
              <Input
                className="h-9 min-w-28"
                type="number"
                step="0.001"
                value={row.board_booked_weight ?? ""}
                onChange={(event) => updateBoardGroup(row.board_group_id as string, { board_booked_weight: event.target.value, booked_weight: null })}
              />
            </TD>
          );
        }
        return <TD><Input className="h-9 min-w-28" type="number" step="0.001" value={row.booked_weight ?? ""} onChange={(event) => updateRow(key, { booked_weight: event.target.value })} /></TD>;
      }
    },
    density: {
      key: "density",
      label: PLANNER_COLUMN_LABELS.density,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-24" type="number" step="0.001" value={row.density ?? ""} onChange={(event) => updateRow(key, { density: event.target.value })} /></TD>
      )
    },
    quotation: {
      key: "quotation",
      label: PLANNER_COLUMN_LABELS.quotation,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-24" value={row.quotation || ""} onChange={(event) => updateRow(key, { quotation: event.target.value })} /></TD>
      )
    },
    include_tc: {
      key: "include_tc",
      label: PLANNER_COLUMN_LABELS.include_tc,
      render: ({ row, key }) => (
        <TD className="text-center"><input type="checkbox" checked={Boolean(row.include_tc)} onChange={(event) => updateRow(key, { include_tc: event.target.checked })} /></TD>
      )
    },
    departure_port: {
      key: "departure_port",
      label: PLANNER_COLUMN_LABELS.departure_port,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-24" value={row.departure_port || ""} onChange={(event) => updateRow(key, { departure_port: event.target.value })} /></TD>
      )
    },
    destination_port: {
      key: "destination_port",
      label: PLANNER_COLUMN_LABELS.destination_port,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-24" value={row.destination_port || ""} onChange={(event) => updateRow(key, { destination_port: event.target.value })} /></TD>
      )
    },
    planned_route_text: {
      key: "planned_route_text",
      label: PLANNER_COLUMN_LABELS.planned_route_text,
      render: ({ row, key }) => (
        <TD><Input className="h-9 min-w-40" value={row.planned_route_text || ""} onChange={(event) => updateRow(key, { planned_route_text: event.target.value })} /></TD>
      )
    },
    internal_remark: {
      key: "internal_remark",
      label: PLANNER_COLUMN_LABELS.internal_remark,
      render: ({ row, key }) => (
        <TD><Textarea className="min-h-20 min-w-56" value={row.internal_remark || ""} onChange={(event) => updateRow(key, { internal_remark: event.target.value })} /></TD>
      )
    },
    actions: {
      key: "actions",
      label: PLANNER_COLUMN_LABELS.actions,
      render: ({ row, key }) => (
        <TD>
          <div className="flex min-w-36 flex-wrap items-center gap-2">
            {row.board_group_id ? (
              <Button type="button" variant="secondary" size="sm" onClick={() => removeFromBoardGroup(key)}>
                移出板组
              </Button>
            ) : null}
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => moveRowOrGroupToChannel(key, activePlannerChannel === "AMS" ? "LHR" : "AMS")}
            >
              移到 {activePlannerChannel === "AMS" ? "LHR" : "AMS"}
            </Button>
            <Button variant="danger" size="sm" onClick={() => removeRow(key)}><Trash2 className="h-4 w-4" /></Button>
          </div>
        </TD>
      )
    }
  };

  const orderedPlannerColumns = plannerColumnOrder.map((column) => plannerColumnDefinitions[column]);

  return (
    <>
      <input
        ref={plannerImportInputRef}
        type="file"
        accept=".xlsx"
        className="hidden"
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          void uploadPlannerImportFile(file);
        }}
      />
      <PageHeader
        title="排仓编辑器"
        description="把正式提单和预排仓放在同一个工作台中安排出仓与入仓号。"
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <a href="/templates/waybill-bulk-import-template.xlsx" download="批量上传提单号_模板.xlsx">
                <Download className="h-4 w-4" />
                下载模板
              </a>
            </Button>
            <Button variant="secondary" disabled={uploadingPlannerImport} onClick={() => plannerImportInputRef.current?.click()}>
              <Upload className="h-4 w-4" />
              {uploadingPlannerImport ? "上传中..." : "批量上传"}
            </Button>
            <Button variant="secondary" onClick={() => void loadAll()}>
              <RefreshCw className="h-4 w-4" />
              刷新
            </Button>
            <Button variant="secondary" onClick={() => setRightPanelVisible((prev) => !prev)}>
              {rightPanelVisible ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
              {rightPanelVisible ? "隐藏右栏" : "显示右栏"}
            </Button>
            <Button variant="secondary" onClick={() => void exportDraft()}>
              <Download className="h-4 w-4" />
              导出 Excel
            </Button>
            <Button variant="danger" onClick={() => void clearDraft()}>
              <Trash2 className="h-4 w-4" />
              清空草稿
            </Button>
          </div>
        }
      />
      {message ? <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div> : null}
      <div ref={plannerLayoutRef} className={cn("grid min-w-0 gap-4 xl:flex xl:items-start xl:gap-0", !rightPanelVisible && "xl:block")}>
        <div
          className="min-w-0"
          style={rightPanelVisible ? { flexBasis: `${mainPanePercent}%`, flexGrow: 0, flexShrink: 1 } : undefined}
        >
          <Panel
            className="min-w-0 overflow-hidden"
            title="排仓编辑区"
            action={
              <div className="flex flex-wrap items-center justify-end gap-2">
                <span className="text-sm text-slate-500">已选 {selectedRowCount} 条</span>
                <span className="text-sm text-slate-500">当前 {activePlannerChannel}: {activeRows.length} 条</span>
                <Button variant="secondary" onClick={resetPlannerColumnOrder}>
                  <RotateCcw className="h-4 w-4" />
                  恢复默认列
                </Button>
                <Button variant="secondary" disabled={activeSelectedRows.length < 2} onClick={mergeSelectedRowsAsBoard}>
                  <ListPlus className="h-4 w-4" />
                  合并选中为板
                </Button>
                <Button variant="secondary" disabled={!selectedRowCount} onClick={() => setBatchOpen(true)}>
                  <ListPlus className="h-4 w-4" />
                  批量编辑
                </Button>
                <Button disabled={!rows.length || saving} onClick={() => void validateBeforeCommit()}>
                  <Save className="h-4 w-4" />
                  录入排仓
                </Button>
              </div>
            }
          >
          <div className="mb-3 grid max-w-sm grid-cols-2 gap-2">
            {PLANNER_CHANNELS.map((channel) => (
              <Button
                key={channel}
                type="button"
                variant={activePlannerChannel === channel ? "default" : "secondary"}
                onClick={() => setActivePlannerChannel(channel)}
              >
                {channel}（{channelRows[channel].length}）
              </Button>
            ))}
          </div>
          <div
            className="min-h-64 min-w-0 rounded-md border border-dashed border-slate-300 bg-slate-50/50 p-2"
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDropIntoRows}
          >
            {activeRows.length ? (
              <div className="w-full max-w-full overflow-x-auto rounded-md border border-slate-200 bg-white">
                <Table className="min-w-[2320px]">
                  <THead>
                    <TR>
                      <TH className="w-10" />
                      <TH className="w-10"><input type="checkbox" checked={activeRows.length > 0 && activeSelectedRows.length === activeRows.length} onChange={(event) => toggleActiveChannelSelection(event.target.checked)} /></TH>
                      {orderedPlannerColumns.map((column) => (
                        <TH
                          key={column.key}
                          draggable
                          className={cn(
                            "cursor-grab select-none whitespace-nowrap active:cursor-grabbing",
                            draggingPlannerColumn === column.key && "bg-purple-50 text-purple-700"
                          )}
                          title="拖动调整列顺序"
                          onDragStart={(event) => {
                            event.dataTransfer.effectAllowed = "move";
                            event.dataTransfer.setData("text/plain", column.key);
                            setDraggingPlannerColumn(column.key);
                          }}
                          onDragOver={(event) => event.preventDefault()}
                          onDrop={(event) => handlePlannerColumnDrop(event, column.key)}
                          onDragEnd={() => setDraggingPlannerColumn(null)}
                        >
                          {column.label}
                        </TH>
                      ))}
                    </TR>
                  </THead>
                  <TBody>
                    {activeRows.map((row) => {
                      const key = rowKey(row);
                      const error = rowErrors[key];
                      return (
                        <TR
                          key={key}
                          className={cn(error && "bg-red-50", rowSortDragKey === key && "opacity-50")}
                          onDragOver={(event) => event.preventDefault()}
                          onDrop={(event) => onPlannerRowDrop(event, row)}
                        >
                          <TD>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              className="h-7 w-7 cursor-grab text-slate-400 active:cursor-grabbing"
                              draggable
                              aria-label="拖动排序排仓条目"
                              onDragStart={(event) => onPlannerRowSortDragStart(event, row)}
                              onDragEnd={() => setRowSortDragKey(null)}
                            >
                              <GripVertical className="h-4 w-4" />
                            </Button>
                          </TD>
                          <TD><input type="checkbox" checked={selectedRows.has(key)} onChange={(event) => setSelectedRows((prev) => {
                            const next = new Set(prev);
                            if (event.target.checked) next.add(key);
                            else next.delete(key);
                            return next;
                          })} /></TD>
                          {orderedPlannerColumns.map((column) => (
                            <Fragment key={column.key}>
                              {column.render({ row, key, error, volumeSpan: activeVolumeSpans.get(key), weightSpan: activeWeightSpans.get(key) })}
                            </Fragment>
                          ))}
                        </TR>
                      );
                    })}
                  </TBody>
                </Table>
              </div>
            ) : (
              <EmptyState title="暂无排仓条目" description="从右侧待排仓提单多选后拖入这里，或点击加入排仓。" />
            )}
          </div>
          </Panel>
        </div>

        {rightPanelVisible ? (
          <>
            <button
              type="button"
              aria-label="拖动调整排仓编辑区和排仓侧栏宽度"
              className={cn(
                "hidden h-[calc(100vh-96px)] w-3 shrink-0 cursor-col-resize items-stretch justify-center rounded-sm transition hover:bg-slate-100 xl:flex",
                resizingSplit && "bg-slate-100"
              )}
              onPointerDown={(event) => {
                event.preventDefault();
                setResizingSplit(true);
              }}
            >
              <span className="my-1 w-px rounded-full bg-slate-300" />
            </button>
            <div
              className="min-w-0 xl:min-w-[280px]"
              style={{ flexBasis: `${100 - mainPanePercent}%`, flexGrow: 1, flexShrink: 1 }}
            >
              <div className="sticky top-20 h-[calc(100vh-96px)] space-y-3 overflow-hidden">
                <Panel title="排仓侧栏">
              <div className="mb-3 grid grid-cols-2 gap-2">
                <Button variant={rightPanelMode === "candidates" ? "default" : "secondary"} onClick={() => setRightPanelMode("candidates")}>待排仓提单</Button>
                <Button variant={rightPanelMode === "receipts" ? "default" : "secondary"} onClick={() => setRightPanelMode("receipts")}>未绑定箱号数据</Button>
              </div>
              {rightPanelMode === "candidates" ? (
                <div className="space-y-3">
                  <Button className="w-full" disabled={!selectedCandidateItems().length} onClick={() => addCandidates(selectedCandidateItems())}>
                    <ListPlus className="h-4 w-4" />
                    加入排仓
                  </Button>
                  <div className="max-h-[calc(100vh-260px)] space-y-2 overflow-y-auto pr-1">
                    {allCandidates.map((item) => {
                      const key = rowKey(item);
                      const added = rowKeySet.has(key);
                      const selected = selectedCandidates.has(key);
                      return (
                        <div
                          key={key}
                          draggable
                          onDragStart={(event) => onCandidateDragStart(event, item)}
                          className={cn("rounded-md border bg-white p-3 text-sm", added ? "border-slate-200 opacity-60" : selected ? "border-purple-300 bg-purple-50" : "border-slate-200")}
                        >
                          <label className="flex items-start gap-2">
                            <input
                              type="checkbox"
                              disabled={added}
                              checked={selected}
                              onChange={(event) => setSelectedCandidates((prev) => {
                                const next = new Set(prev);
                                if (event.target.checked) next.add(key);
                                else next.delete(key);
                                return next;
                              })}
                            />
                            <span className="min-w-0 flex-1">
                              <span className="flex items-center gap-2 font-semibold text-slate-900">
                                <GripVertical className="h-4 w-4 text-slate-400" />
                                {item.label}
                                <Badge variant={item.source_type === "waybill" ? "purple" : "amber"}>{sourceLabel(item.source_type)}</Badge>
                                {added ? <Badge variant="gray">已加入</Badge> : null}
                              </span>
                              <span className="mt-1 grid gap-0.5 text-xs text-slate-500">
                                <span>航代：{item.carrier_agent?.agent_name || "-"}</span>
                                <span>出仓：{formatOutboundDate(item.outbound_date) || "-"} / 起飞：{compact(item.planned_flight_date)}</span>
                                <span>方数：{formatDecimal(item.booked_volume)} / 入仓号：{item.receipts?.length || 0}</span>
                              </span>
                            </span>
                          </label>
                        </div>
                      );
                    })}
                    {!allCandidates.length ? <EmptyState title="暂无待排仓提单" description="当前没有满足条件的正式提单或预排仓。" /> : null}
                  </div>
                </div>
              ) : (
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-2">
                    <Button className="h-8 text-xs" variant={receiptViewMode === "list" ? "default" : "secondary"} onClick={() => setReceiptViewMode("list")}>
                      操作列表
                    </Button>
                    <Button className="h-8 text-xs" variant={receiptViewMode === "summary" ? "default" : "secondary"} onClick={() => setReceiptViewMode("summary")}>
                      入仓号总览
                    </Button>
                  </div>
                  {receiptViewMode === "list" ? (
                    <div className="max-h-[calc(100vh-268px)] space-y-2 overflow-y-auto pr-1">
                      {(candidates?.unbound_receipts || []).map((receipt) => {
                        const selected = selectedReceipts.has(receipt.id);
                        const assigned = assignedReceiptIds.has(receipt.id);
                        return (
                          <div
                            key={receipt.id}
                            draggable
                            onDragStart={(event) => onReceiptDragStart(event, receipt)}
                            onDragOver={(event) => {
                              if (receiptSortDragId !== null) {
                                event.preventDefault();
                                event.dataTransfer.dropEffect = "move";
                              }
                            }}
                            onDrop={(event) => {
                              if (receiptSortDragId !== null) {
                                event.preventDefault();
                                movePlannerReceiptBefore(receiptSortDragId, receipt.id);
                                setReceiptSortDragId(null);
                              }
                            }}
                            className={cn(
                              "rounded-md border p-3 text-sm transition-colors",
                              assigned ? "border-slate-200 bg-slate-100 text-slate-500" : "border-slate-200 bg-white",
                              selected && "border-purple-300 ring-1 ring-purple-200"
                            )}
                          >
                            <label className="flex items-start gap-2">
                              <input
                                type="checkbox"
                                checked={selected}
                                onChange={(event) => toggleReceiptSelection(receipt.id, event.target.checked)}
                              />
                              <span className="min-w-0 flex-1">
                                <span className={cn("flex items-center gap-2 font-semibold", assigned ? "text-slate-500" : "text-slate-900")}>
                                  <span
                                    role="button"
                                    tabIndex={0}
                                    draggable={!receiptOrderSaving}
                                    className="inline-flex h-6 w-6 cursor-grab items-center justify-center rounded text-slate-400 hover:bg-slate-100 active:cursor-grabbing"
                                    title="拖动排序"
                                    onMouseDown={(event) => event.stopPropagation()}
                                    onClick={(event) => {
                                      event.preventDefault();
                                      event.stopPropagation();
                                    }}
                                    onDragStart={(event) => onReceiptSortDragStart(event, receipt)}
                                    onDragEnd={() => setReceiptSortDragId(null)}
                                  >
                                    <GripVertical className="h-4 w-4" />
                                  </span>
                                  {receipt.source_file_name || receipt.warehouse_no}
                                  {assigned ? <Badge variant="gray">已在编辑区</Badge> : null}
                                </span>
                                <span className="mt-1 flex flex-wrap gap-1">
                                  {channelTags(receipt.channel_tags).map((tag) => <Badge key={tag} variant="amber">{tag}</Badge>)}
                                </span>
                                <span className="mt-1 grid gap-0.5 text-xs text-slate-500">
                                  <span>入仓号：{receipt.warehouse_no}</span>
                                  <span>上传：{formatDateTime(receipt.uploaded_at)}</span>
                                  <span>箱数：{receipt.box_count ?? 0} / 件数：{compact(receipt.total_quantity)}</span>
                                  <span>重量：{formatDecimal(receipt.total_weight)} / 方数：{formatDecimal(receipt.total_volume)}</span>
                                  {(receipt.general_cargo_count ?? 0) > 0 ? <span>普货：{receipt.general_cargo_count}件</span> : null}
                                  <span>密度：{formatReceiptDensity(receipt)}</span>
                                </span>
                              </span>
                            </label>
                          </div>
                        );
                      })}
                      {!candidates?.unbound_receipts.length ? <EmptyState title="暂无未绑定入仓号" description="未绑定箱号模块上传后会显示在这里。" /> : null}
                    </div>
                  ) : (
                    <div className="max-h-[calc(100vh-268px)] overflow-y-auto pr-1">
                      {candidates?.unbound_receipts.length ? (
                        <div className="grid grid-cols-[repeat(auto-fit,minmax(138px,1fr))] gap-2">
                          {candidates.unbound_receipts.map((receipt) => {
                            const selected = selectedReceipts.has(receipt.id);
                            const assigned = assignedReceiptIds.has(receipt.id);
                            const fileName = receipt.source_file_name || receipt.warehouse_no;
                            return (
                              <div
                                key={receipt.id}
                                draggable
                                onDragStart={(event) => onReceiptDragStart(event, receipt)}
                                onDragOver={(event) => {
                                  if (receiptSortDragId !== null) {
                                    event.preventDefault();
                                    event.dataTransfer.dropEffect = "move";
                                  }
                                }}
                                onDrop={(event) => {
                                  if (receiptSortDragId !== null) {
                                    event.preventDefault();
                                    movePlannerReceiptBefore(receiptSortDragId, receipt.id);
                                    setReceiptSortDragId(null);
                                  }
                                }}
                                className={cn(
                                  "rounded-md border p-2 text-xs transition-colors",
                                  assigned ? "border-slate-200 bg-slate-100 text-slate-500" : "border-slate-200 bg-white",
                                  selected && "border-purple-300 ring-1 ring-purple-200"
                                )}
                              >
                                <label className="block">
                                  <span className="flex items-start gap-2">
                                    <input
                                      className="mt-0.5"
                                      type="checkbox"
                                      checked={selected}
                                      onChange={(event) => toggleReceiptSelection(receipt.id, event.target.checked)}
                                    />
                                    <span className="min-w-0 flex-1">
                                      <span className={cn("flex min-w-0 items-center gap-1 font-semibold", assigned ? "text-slate-500" : "text-slate-900")}>
                                        <span
                                          role="button"
                                          tabIndex={0}
                                          draggable={!receiptOrderSaving}
                                          className="inline-flex h-5 w-5 shrink-0 cursor-grab items-center justify-center rounded text-slate-400 hover:bg-slate-100 active:cursor-grabbing"
                                          title="拖动排序"
                                          onMouseDown={(event) => event.stopPropagation()}
                                          onClick={(event) => {
                                            event.preventDefault();
                                            event.stopPropagation();
                                          }}
                                          onDragStart={(event) => onReceiptSortDragStart(event, receipt)}
                                          onDragEnd={() => setReceiptSortDragId(null)}
                                        >
                                          <GripVertical className="h-3.5 w-3.5" />
                                        </span>
                                        <span className="truncate" title={fileName}>{fileName}</span>
                                        {assigned ? <Badge variant="gray">已在编辑区</Badge> : null}
                                      </span>
                                      <span className="mt-2 grid grid-cols-2 gap-x-2 gap-y-1 text-slate-500">
                                        <span>箱数 {receipt.box_count ?? 0}</span>
                                        <span>件数 {compact(receipt.total_quantity)}</span>
                                        <span>重量 {formatDecimal(receipt.total_weight)}</span>
                                        <span>方数 {formatDecimal(receipt.total_volume)}</span>
                                        {(receipt.general_cargo_count ?? 0) > 0 ? <span>普货 {receipt.general_cargo_count}件</span> : <span>普货 -</span>}
                                        <span>密度 {formatReceiptDensity(receipt)}</span>
                                      </span>
                                      <span className="mt-1 block text-slate-400">上传 {formatDateTime(receipt.uploaded_at)}</span>
                                    </span>
                                  </span>
                                </label>
                              </div>
                            );
                          })}
                        </div>
                      ) : (
                        <EmptyState title="暂无未绑定入仓号" description="未绑定箱号模块上传后会显示在这里。" />
                      )}
                    </div>
                  )}
                </div>
              )}
                </Panel>
              </div>
            </div>
          </>
        ) : null}
      </div>

      <Dialog open={batchOpen} onOpenChange={setBatchOpen}>
        <DialogContent>
          <DialogTitle>批量编辑</DialogTitle>
          <div className="mt-3 grid gap-3">
            <div className="text-sm text-slate-600">将 {selectedRowCount} 条排仓记录的同一字段改为相同值。</div>
            <Select value={batchField} onValueChange={(value) => { setBatchField(value as PlannerField); setBatchValue(""); }}>
              <SelectTrigger><SelectValue /></SelectTrigger>
              <SelectContent>{BATCH_FIELDS.map((item) => <SelectItem key={item.key} value={item.key}>{item.label}</SelectItem>)}</SelectContent>
            </Select>
            {(() => {
              const field = BATCH_FIELDS.find((item) => item.key === batchField);
              if (field?.kind === "select" && batchField === "carrier_agent_id") {
                return (
                  <Select value={batchValue || CLEAR_VALUE} onValueChange={setBatchValue}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={CLEAR_VALUE}>清空</SelectItem>
                      {agents.map((agent) => <SelectItem key={agent.id} value={String(agent.id)}>{agent.agent_name}</SelectItem>)}
                    </SelectContent>
                  </Select>
                );
              }
              if (field?.kind === "select" && batchField === "customs_staff_id") {
                return (
                  <Select value={batchValue || CLEAR_VALUE} onValueChange={setBatchValue}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value={CLEAR_VALUE}>清空</SelectItem>
                      {customsStaff.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.display_name || item.username}</SelectItem>)}
                    </SelectContent>
                  </Select>
                );
              }
              if (field?.kind === "boolean") {
                return (
                  <Select value={batchValue || "false"} onValueChange={setBatchValue}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="true">是</SelectItem>
                      <SelectItem value="false">否</SelectItem>
                    </SelectContent>
                  </Select>
                );
              }
              return <Input type={field?.kind === "number" ? "number" : field?.kind === "date" ? "date" : "text"} step="0.001" value={batchValue} onChange={(event) => setBatchValue(event.target.value)} />;
            })()}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setBatchOpen(false)}>取消</Button>
            <Button onClick={applyBatchEdit}>应用到已选</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={plannerImportOpen} onOpenChange={setPlannerImportOpen}>
        <DialogContent className="w-[min(900px,calc(100vw-32px))]">
          <DialogTitle>批量上传排仓草稿</DialogTitle>
          <div className="mt-3 space-y-4 text-sm">
            {uploadingPlannerImport ? (
              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-slate-600">正在解析上传文件...</div>
            ) : null}
            {plannerImportError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700">{plannerImportError}</div>
            ) : null}
            {plannerImportResult ? (
              <>
                <div className="grid gap-2 sm:grid-cols-4">
                  <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                    <div className="text-xs text-slate-500">文件</div>
                    <div className="mt-1 font-medium text-slate-900">{plannerImportResult.file_name}</div>
                  </div>
                  <div className="rounded-md border border-green-200 bg-green-50 px-3 py-2 text-green-700">
                    <div className="text-xs">导入</div>
                    <div className="mt-1 font-semibold">{plannerImportResult.imported_count} 行</div>
                  </div>
                  <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                    <div className="text-xs text-slate-500">跳过空行</div>
                    <div className="mt-1 font-semibold text-slate-900">{plannerImportResult.skipped_count} 行</div>
                  </div>
                  <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-amber-700">
                    <div className="text-xs">提示</div>
                    <div className="mt-1 font-semibold">{plannerImportResult.warnings.length} 条</div>
                  </div>
                </div>
                <div>
                  <div className="mb-2 font-medium text-slate-900">已加入编辑区</div>
                  <div className="max-h-44 overflow-auto rounded-md border border-slate-200">
                    <Table>
                      <THead><TR><TH>来源</TH><TH>提单号</TH><TH>航代</TH><TH>起飞日期</TH></TR></THead>
                      <TBody>
                        {plannerImportResult.rows.map((row) => (
                          <TR key={`${row.source_type}-${row.source_id}`}>
                            <TD>{sourceLabel(row.source_type)}</TD>
                            <TD>{compact(row.waybill_no) || "-"}</TD>
                            <TD>{agents.find((agent) => agent.id === row.carrier_agent_id)?.agent_name || "-"}</TD>
                            <TD>{compact(row.planned_flight_date) || "-"}</TD>
                          </TR>
                        ))}
                        {!plannerImportResult.rows.length ? (
                          <TR><TD colSpan={4} className="text-center text-slate-400">没有可导入行</TD></TR>
                        ) : null}
                      </TBody>
                    </Table>
                  </div>
                </div>
                {plannerImportResult.warnings.length ? (
                  <div>
                    <div className="mb-2 font-medium text-amber-700">需要补充或确认的字段</div>
                    <div className="max-h-44 overflow-auto rounded-md border border-amber-200">
                      <Table>
                        <THead><TR><TH>行号</TH><TH>字段</TH><TH>原值</TH><TH>原因</TH></TR></THead>
                        <TBody>
                          {plannerImportResult.warnings.map((item, index) => (
                            <TR key={`${item.row_number}-${item.field}-${index}`}>
                              <TD>{item.row_number}</TD>
                              <TD>{item.field}</TD>
                              <TD>{compact(item.raw_value) || "-"}</TD>
                              <TD>{item.message}</TD>
                            </TR>
                          ))}
                        </TBody>
                      </Table>
                    </div>
                  </div>
                ) : null}
                {plannerImportResult.errors.length ? (
                  <div>
                    <div className="mb-2 font-medium text-red-700">未导入错误</div>
                    <div className="max-h-36 overflow-auto rounded-md border border-red-200">
                      <Table>
                        <THead><TR><TH>行号</TH><TH>提单号</TH><TH>原因</TH></TR></THead>
                        <TBody>
                          {plannerImportResult.errors.map((item, index) => (
                            <TR key={`${item.row_number || "file"}-${index}`}>
                              <TD>{item.row_number ?? "-"}</TD>
                              <TD>{compact(item.waybill_no) || "-"}</TD>
                              <TD>{item.message}</TD>
                            </TR>
                          ))}
                        </TBody>
                      </Table>
                    </div>
                  </div>
                ) : null}
              </>
            ) : null}
          </div>
          <div className="mt-5 flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setPlannerImportOpen(false)}>关闭</Button>
            <Button disabled={uploadingPlannerImport} onClick={() => plannerImportInputRef.current?.click()}>
              继续上传
            </Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={validationOpen} onOpenChange={setValidationOpen}>
        <DialogContent className="w-[min(900px,calc(100vw-32px))]">
          <DialogTitle>录入排仓校验</DialogTitle>
          {validationResult ? (
            <div className="mt-3 space-y-4 text-sm">
              <div className="rounded-md border border-slate-200 bg-slate-50 px-3 py-2">
                可写入 {validationResult.valid_count} 条，失败 {validationResult.invalid_count} 条。
              </div>
              <div className="max-h-80 overflow-auto rounded-md border border-slate-200">
                <Table>
                  <THead><TR><TH>来源</TH><TH>提单号</TH><TH>状态</TH><TH>原因</TH></TR></THead>
                  <TBody>
                    {validationResult.results.map((item) => (
                      <TR key={`${item.source_type}-${item.source_id}`}>
                        <TD>{sourceLabel(item.source_type)}</TD>
                        <TD>{compact(item.waybill_no) || `#${item.source_id}`}</TD>
                        <TD>{item.status === "valid" ? <Badge variant="green">可写入</Badge> : <Badge variant="red">失败</Badge>}</TD>
                        <TD>{item.errors.map((error) => `${error.field ? `${error.field}: ` : ""}${error.message}`).join("；")}</TD>
                      </TR>
                    ))}
                  </TBody>
                </Table>
              </div>
              {commitResult ? (
                <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-blue-700">
                  写入结果：成功 {commitResult.success_count} 条，失败 {commitResult.failed_count} 条。
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" disabled={saving} onClick={() => setValidationOpen(false)}>全部取消</Button>
            {validationResult?.invalid_count ? (
              <Button disabled={saving || !validationResult.valid_count} onClick={() => void commitRows("success_only")}>
                只写入成功项
              </Button>
            ) : (
              <Button disabled={saving || !validationResult?.valid_count} onClick={() => void commitRows("all_or_none")}>
                确认全部写入
              </Button>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
