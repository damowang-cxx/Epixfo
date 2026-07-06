"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Check, Download, Pencil, Plus, RotateCcw, Search, Trash2, Upload, X } from "lucide-react";
import { AlertLevelBadge, LifecycleBadge, LIFECYCLE_VARIANT, type LifecycleBadgeVariant } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/components/layout/auth-provider";
import { apiClient } from "@/lib/client-api";
import { LIFECYCLE_ORDER, lifecycleLabels } from "@/lib/constants";
import { formatPlannedFlightInfo } from "@/lib/planned-flight";
import { cn, compact, formatDateTime, formatOutboundDate } from "@/lib/utils";
import type {
  CarrierAgent,
  Consignee,
  ConsigneeContact,
  LifecycleStatus,
  PageResponse,
  TableColumnPreference,
  User,
  WaybillBulkDeleteRequest,
  WaybillBulkDeleteResult,
  WaybillAirlineFileBatchUploadResult,
  WaybillBulkInlineUpdateRequest,
  WaybillBulkInlineUpdateResult,
  WaybillInlineUpdateField,
  WaybillInlineUpdateValue,
  Waybill
} from "@/lib/types";

const lifecycleOptions: Array<{ value: LifecycleStatus | "all"; label: string }> = [
  { value: "all", label: "全部状态" },
  ...LIFECYCLE_ORDER.map((status) => ({ value: status as LifecycleStatus, label: lifecycleLabels[status] }))
];

interface StatusCount {
  status: LifecycleStatus;
  count: number;
}

const BULK_CLEAR_VALUE = "__clear__";

type BulkUpdateFieldKind = "select" | "date" | "text" | "number" | "boolean";
type InlineDraftChanges = Partial<Record<WaybillInlineUpdateField, WaybillInlineUpdateValue>>;
type DraftChanges = Record<number, InlineDraftChanges>;
type CellErrorField = WaybillInlineUpdateField | "_row" | "_delete";
type CellErrors = Record<number, Partial<Record<CellErrorField, string>>>;

const BULK_UPDATE_FIELDS: Array<{
  key: WaybillInlineUpdateField;
  label: string;
  kind: BulkUpdateFieldKind;
  placeholder?: string;
}> = [
  { key: "waybill_no", label: "提单号", kind: "text" },
  { key: "consignee_contact_id", label: "收件人", kind: "select" },
  { key: "booked_volume", label: "订舱方数", kind: "number" },
  { key: "booked_weight", label: "订舱重量", kind: "number" },
  { key: "density", label: "密度", kind: "number" },
  { key: "quotation", label: "报价", kind: "text" },
  { key: "include_tc", label: "含T", kind: "boolean" },
  { key: "customs_staff_id", label: "指定清关人员", kind: "select" },
  { key: "carrier_agent_id", label: "航代", kind: "select" },
  { key: "outbound_date", label: "出仓日期", kind: "date" },
  { key: "planned_flight_no", label: "计划航班号", kind: "text" },
  { key: "planned_flight_date", label: "约定航班起飞日期", kind: "date" }
];

const WAYBILL_TABLE_KEY = "waybills:list";

const DEFAULT_WAYBILL_COLUMN_ORDER = [
  "waybill_no",
  "consignee",
  "booked_volume",
  "booked_weight",
  "density",
  "quotation",
  "include_tc",
  "customs_staff",
  "customs_data",
  "internal_remark",
  "agent",
  "warehouse",
  "outbound_date",
  "departure_port",
  "destination_port",
  "planned_flight",
  "planned_flight_date",
  "official_estimated_flight_date",
  "lifecycle",
  "alert"
] as const;

type WaybillColumnKey = (typeof DEFAULT_WAYBILL_COLUMN_ORDER)[number];

const WAYBILL_COLUMN_LABELS: Record<WaybillColumnKey, string> = {
  waybill_no: "提单号",
  consignee: "收件人",
  booked_volume: "订舱方数/板总方数",
  booked_weight: "订舱重量",
  density: "密度",
  quotation: "报价",
  include_tc: "含T",
  customs_staff: "指定清关人员",
  customs_data: "清关资料",
  internal_remark: "内部备注",
  agent: "航代",
  warehouse: "入仓号/入仓文件",
  outbound_date: "出仓日期",
  departure_port: "始发港",
  destination_port: "目的港",
  planned_flight: "计划航班",
  planned_flight_date: "约定航班起飞日期",
  official_estimated_flight_date: "官方预计航班日期",
  lifecycle: "生命周期",
  alert: "异常"
};

function normalizeWaybillColumnOrder(order?: string[] | null): WaybillColumnKey[] {
  const validColumns = new Set<string>(DEFAULT_WAYBILL_COLUMN_ORDER);
  const seen = new Set<string>();
  const normalized: WaybillColumnKey[] = [];
  for (const column of order || []) {
    if (!validColumns.has(column) || seen.has(column)) continue;
    seen.add(column);
    normalized.push(column as WaybillColumnKey);
  }
  for (const column of DEFAULT_WAYBILL_COLUMN_ORDER) {
    if (!seen.has(column)) normalized.push(column);
  }
  return normalized;
}

function reorderWaybillColumns(
  order: WaybillColumnKey[],
  draggedKey: WaybillColumnKey,
  targetKey: WaybillColumnKey,
  insertAfter: boolean,
): WaybillColumnKey[] {
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

interface WaybillColumnRenderArgs {
  item: Waybill;
  boardSpan: number;
  shouldRenderBoardCells: boolean;
}

interface WaybillTableColumn {
  key: WaybillColumnKey;
  label: string;
  render: (args: WaybillColumnRenderArgs) => ReactNode;
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

function userDisplayName(user?: Waybill["customs_staff"]) {
  if (!user) return "";
  return user.display_name || user.username;
}

function InternalRemarkCell({
  item,
  disabled,
  onSave
}: {
  item: Waybill;
  disabled: boolean;
  onSave: (item: Waybill, value: string | null) => Promise<void>;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(item.internal_remark || "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  async function save() {
    setSaving(true);
    setError("");
    try {
      await onSave(item, draft.trim() ? draft.trim() : null);
      setEditing(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败。");
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="min-w-64">
      {editing ? (
        <div className="space-y-2">
          <Textarea className="min-h-20" value={draft} disabled={disabled || saving} onChange={(event) => setDraft(event.target.value)} />
          <div className="flex items-center gap-1">
            <Button type="button" variant="ghost" size="icon" className="h-7 w-7" disabled={disabled || saving} onClick={() => void save()} aria-label={`保存提单 ${item.waybill_no} 内部备注`}>
              <Check className="h-4 w-4 text-emerald-600" />
            </Button>
            <Button type="button" variant="ghost" size="icon" className="h-7 w-7" disabled={saving} onClick={() => { setDraft(item.internal_remark || ""); setError(""); setEditing(false); }} aria-label={`取消编辑提单 ${item.waybill_no} 内部备注`}>
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      ) : (
        <div className="flex items-start justify-between gap-2">
          <div className="whitespace-pre-wrap text-sm text-slate-700">{compact(item.internal_remark)}</div>
          <Button type="button" variant="ghost" size="icon" className="h-7 w-7 shrink-0" disabled={disabled} onClick={() => { setDraft(item.internal_remark || ""); setError(""); setEditing(true); }} aria-label={`编辑提单 ${item.waybill_no} 内部备注`}>
            <Pencil className="h-4 w-4" />
          </Button>
        </div>
      )}
      {error ? <div className="mt-1 text-xs text-red-600">{error}</div> : null}
    </div>
  );
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

function currentMonthValue() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
}

function parseMonthValue(value: string) {
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  if (!Number.isInteger(year) || !Number.isInteger(month) || month < 1 || month > 12) return null;
  return { year, month };
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

export default function WaybillsPage() {
  const { user, hasRole } = useAuth();
  const router = useRouter();
  const airlineFileInputRef = useRef<HTMLInputElement | null>(null);
  const canBulkEditWaybills = hasRole("admin") || hasRole("route_staff");
  const canRequestCustomsAccess = hasRole("customs_staff") && !hasRole("admin") && !hasRole("route_staff");
  const [data, setData] = useState<PageResponse<Waybill> | null>(null);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [waybillNo, setWaybillNo] = useState("");
  const [carrierCode, setCarrierCode] = useState("");
  const [destinationPort, setDestinationPort] = useState("");
  const [plannedFlightNo, setPlannedFlightNo] = useState("");
  const [lifecycleStatus, setLifecycleStatus] = useState<LifecycleStatus | "all">("all");
  const [page, setPage] = useState(1);
  const [message, setMessage] = useState("");
  const [generalCargoMonth, setGeneralCargoMonth] = useState(currentMonthValue);
  const [exportingGeneralCargo, setExportingGeneralCargo] = useState(false);
  const [airlineUploading, setAirlineUploading] = useState(false);
  const [airlineUploadResult, setAirlineUploadResult] = useState<WaybillAirlineFileBatchUploadResult | null>(null);
  const [columnOrder, setColumnOrder] = useState<WaybillColumnKey[]>(() => normalizeWaybillColumnOrder());
  const [draggingColumn, setDraggingColumn] = useState<WaybillColumnKey | null>(null);
  const [accessWaybillNo, setAccessWaybillNo] = useState("");
  const [requestingAccess, setRequestingAccess] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [draftChanges, setDraftChanges] = useState<DraftChanges>({});
  const [pendingDeleteIds, setPendingDeleteIds] = useState<number[]>([]);
  const [cellErrors, setCellErrors] = useState<CellErrors>({});
  const [savingInlineChanges, setSavingInlineChanges] = useState(false);
  const [selectedWaybillIds, setSelectedWaybillIds] = useState<number[]>([]);
  const [bulkEditOpen, setBulkEditOpen] = useState(false);
  const [bulkEditField, setBulkEditField] = useState<WaybillInlineUpdateField>("outbound_date");
  const [bulkEditValue, setBulkEditValue] = useState("");
  const [bulkEditSaving, setBulkEditSaving] = useState(false);
  const [bulkEditResult, setBulkEditResult] = useState<{ success_count: number } | null>(null);
  const [agents, setAgents] = useState<CarrierAgent[]>([]);
  const [consignees, setConsignees] = useState<Consignee[]>([]);
  const [contacts, setContacts] = useState<ConsigneeContact[]>([]);
  const [users, setUsers] = useState<User[]>([]);

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
    if (!canBulkEditWaybills) return;
    Promise.all([
      apiClient.get<CarrierAgent[]>("/carrier-agents"),
      apiClient.get<Consignee[]>("/consignees"),
      apiClient.get<ConsigneeContact[]>("/consignee-contacts"),
      apiClient.get<User[]>("/users")
    ])
      .then(([agentRows, consigneeRows, contactRows, userRows]) => {
        setAgents(agentRows);
        setConsignees(consigneeRows);
        setContacts(contactRows);
        setUsers(userRows);
      })
      .catch(() => undefined);
  }, [canBulkEditWaybills]);

  useEffect(() => {
    if (!user?.id) {
      return;
    }
    let cancelled = false;
    apiClient
      .get<TableColumnPreference>(`/user-preferences/table-columns/${encodeURIComponent(WAYBILL_TABLE_KEY)}`)
      .then((preference) => {
        if (!cancelled) setColumnOrder(normalizeWaybillColumnOrder(preference.column_order));
      })
      .catch(() => {
        if (!cancelled) setColumnOrder(normalizeWaybillColumnOrder());
      });
    return () => {
      cancelled = true;
    };
  }, [user?.id]);

  const saveColumnOrder = useCallback(async (nextOrder: WaybillColumnKey[]) => {
    try {
      await apiClient.put<TableColumnPreference>(
        `/user-preferences/table-columns/${encodeURIComponent(WAYBILL_TABLE_KEY)}`,
        { column_order: nextOrder }
      );
    } catch (error) {
      setMessage(error instanceof Error ? `列顺序保存失败：${error.message}` : "列顺序保存失败。");
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadCounts();
  }, [data, loadCounts]);

  const totalCount = useMemo(() => Object.values(counts).reduce((a, b) => a + b, 0), [counts]);
  const currentPageIds = useMemo(() => (data?.items || []).map((item) => item.id), [data?.items]);
  const selectedIdSet = useMemo(() => new Set(selectedWaybillIds), [selectedWaybillIds]);
  const pendingDeleteIdSet = useMemo(() => new Set(pendingDeleteIds), [pendingDeleteIds]);
  const hasPendingListChanges = Object.keys(draftChanges).length > 0 || pendingDeleteIds.length > 0;
  const selectedWaybills = useMemo(
    () => (data?.items || []).filter((item) => selectedIdSet.has(item.id)),
    [data?.items, selectedIdSet]
  );
  const allCurrentPageSelected = currentPageIds.length > 0 && currentPageIds.every((id) => selectedIdSet.has(id));
  const someCurrentPageSelected = currentPageIds.some((id) => selectedIdSet.has(id));
  const consigneeNameById = useMemo(() => new Map(consignees.map((item) => [item.id, item.name])), [consignees]);
  const enabledAgents = useMemo(() => agents.filter((item) => item.enabled), [agents]);
  const enabledContacts = useMemo(() => contacts.filter((item) => item.enabled), [contacts]);
  const enabledCustomsUsers = useMemo(
    () => users.filter((item) => item.is_active && item.roles.some((role) => role.code === "customs_staff")),
    [users]
  );
  const selectedBulkField = useMemo(
    () => BULK_UPDATE_FIELDS.find((item) => item.key === bulkEditField) || BULK_UPDATE_FIELDS[0],
    [bulkEditField]
  );
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
    if (!confirmAndDiscardEditChanges()) return;
    setPage(1);
    load();
  }

  function selectStatus(status: LifecycleStatus | "all") {
    if (!confirmAndDiscardEditChanges()) return;
    setLifecycleStatus(status);
    setPage(1);
  }

  function handleColumnDrop(event: DragEvent<HTMLTableCellElement>, targetKey: WaybillColumnKey) {
    event.preventDefault();
    if (!draggingColumn || draggingColumn === targetKey) {
      setDraggingColumn(null);
      return;
    }
    const rect = event.currentTarget.getBoundingClientRect();
    const insertAfter = event.clientX > rect.left + rect.width / 2;
    const nextOrder = reorderWaybillColumns(columnOrder, draggingColumn, targetKey, insertAfter);
    setColumnOrder(nextOrder);
    setDraggingColumn(null);
    void saveColumnOrder(nextOrder);
  }

  function resetColumnOrder() {
    const nextOrder = normalizeWaybillColumnOrder();
    setColumnOrder(nextOrder);
    setMessage("已恢复默认列顺序。");
    void saveColumnOrder([]);
  }

  function toggleCurrentPageSelection(checked: boolean) {
    setSelectedWaybillIds(checked ? currentPageIds : []);
  }

  function toggleWaybillSelection(id: number, checked: boolean) {
    setSelectedWaybillIds((prev) => {
      if (checked) {
        return prev.includes(id) ? prev : [...prev, id];
      }
      return prev.filter((item) => item !== id);
    });
  }

  function openBulkEditDialog() {
    if (!editMode || selectedWaybillIds.length === 0) return;
    setBulkEditValue("");
    setBulkEditResult(null);
    setBulkEditOpen(true);
  }

  function normalizeInlineValue(field: WaybillInlineUpdateField, rawValue: string | number | boolean | null): WaybillInlineUpdateValue {
    if (field === "include_tc") return Boolean(rawValue);
    if (typeof rawValue === "string") {
      const trimmed = rawValue.trim();
      return trimmed === "" ? null : trimmed;
    }
    return rawValue;
  }

  function getBaseInlineValue(item: Waybill, field: WaybillInlineUpdateField): WaybillInlineUpdateValue {
    if (field === "planned_flight_no") return item.plan?.planned_flight_no || null;
    if (field === "planned_flight_date") return item.plan?.planned_flight_date || null;
    if (field === "consignee_contact_id") return item.consignee_contact_id ?? null;
    if (field === "carrier_agent_id") return item.carrier_agent_id ?? null;
    if (field === "customs_staff_id") return item.customs_staff_id ?? null;
    return item[field] as WaybillInlineUpdateValue;
  }

  function getDraftValue(item: Waybill, field: WaybillInlineUpdateField): WaybillInlineUpdateValue {
    const draft = draftChanges[item.id]?.[field];
    return draft !== undefined ? draft : getBaseInlineValue(item, field);
  }

  function valuesEqual(left: WaybillInlineUpdateValue, right: WaybillInlineUpdateValue) {
    return String(left ?? "") === String(right ?? "");
  }

  function clearCellError(ids: number[], field: CellErrorField) {
    setCellErrors((prev) => {
      const next = { ...prev };
      for (const id of ids) {
        if (!next[id]) continue;
        const row = { ...next[id] };
        delete row[field];
        delete row._row;
        next[id] = row;
      }
      return next;
    });
  }

  function stageDraftChange(item: Waybill, field: WaybillInlineUpdateField, value: WaybillInlineUpdateValue, syncBoard = false) {
    const normalizedValue = normalizeInlineValue(field, value);
    const targetItems =
      syncBoard && item.board_id
        ? (data?.items || []).filter((row) => row.board_id === item.board_id)
        : [item];
    const targetIds = targetItems.map((row) => row.id);
    setDraftChanges((prev) => {
      const next: DraftChanges = { ...prev };
      for (const row of targetItems) {
        const baseValue = getBaseInlineValue(row, field);
        const rowDraft = { ...(next[row.id] || {}) };
        if (valuesEqual(baseValue, normalizedValue)) {
          delete rowDraft[field];
        } else {
          rowDraft[field] = normalizedValue;
        }
        if (Object.keys(rowDraft).length === 0) {
          delete next[row.id];
        } else {
          next[row.id] = rowDraft;
        }
      }
      return next;
    });
    clearCellError(targetIds, field);
  }

  function discardEditChanges() {
    setDraftChanges({});
    setPendingDeleteIds([]);
    setCellErrors({});
    setSelectedWaybillIds([]);
    setBulkEditResult(null);
    setMessage("");
  }

  function confirmAndDiscardEditChanges() {
    if (hasPendingListChanges && !window.confirm("确认放弃当前未保存的修改吗？")) return false;
    discardEditChanges();
    return true;
  }

  function enterEditMode() {
    setEditMode(true);
    setMessage("");
  }

  function cancelEditMode() {
    if (!confirmAndDiscardEditChanges()) return;
    setEditMode(false);
  }

  function togglePendingDelete(item: Waybill) {
    setPendingDeleteIds((prev) => (prev.includes(item.id) ? prev.filter((id) => id !== item.id) : [...prev, item.id]));
    clearCellError([item.id], "_delete");
  }

  function stageSelectedForDelete() {
    if (selectedWaybillIds.length === 0) return;
    setPendingDeleteIds((prev) => Array.from(new Set([...prev, ...selectedWaybillIds])));
    setSelectedWaybillIds([]);
  }

  function normalizeBulkEditValue(): WaybillInlineUpdateValue {
    if (selectedBulkField.kind === "select") {
      return bulkEditValue === "" || bulkEditValue === BULK_CLEAR_VALUE ? null : Number(bulkEditValue);
    }
    if (selectedBulkField.kind === "boolean") {
      return bulkEditValue === "true";
    }
    if (selectedBulkField.kind === "date") {
      return bulkEditValue || null;
    }
    const trimmed = bulkEditValue.trim();
    return trimmed === "" ? null : trimmed;
  }

  async function submitBulkEdit() {
    if (!editMode || selectedWaybillIds.length === 0 || bulkEditSaving) return;
    const value = normalizeBulkEditValue();
    setBulkEditSaving(true);
    setBulkEditResult(null);
    try {
      const selectedRows = (data?.items || []).filter((item) => selectedIdSet.has(item.id));
      const affectedIds = new Set<number>();
      for (const item of selectedRows) {
        const syncBoard = (bulkEditField === "consignee_contact_id" || bulkEditField === "booked_volume") && Boolean(item.board_id);
        const targets = syncBoard ? (data?.items || []).filter((row) => row.board_id === item.board_id) : [item];
        targets.forEach((row) => affectedIds.add(row.id));
        stageDraftChange(item, bulkEditField, value, syncBoard);
      }
      setBulkEditResult({ success_count: affectedIds.size });
      setMessage(`已应用到草稿：${affectedIds.size} 票。点击“确认修改”后才会保存。`);
      setBulkEditOpen(false);
    } finally {
      setBulkEditSaving(false);
    }
  }

  function buildInlineUpdatePayload(): WaybillBulkInlineUpdateRequest {
    const updates = Object.entries(draftChanges)
      .map(([id, changes]) => ({
        waybill_id: Number(id),
        changes
      }))
      .filter((item) => !pendingDeleteIdSet.has(item.waybill_id) && Object.keys(item.changes).length > 0);
    return { updates };
  }

  async function submitInlineChanges() {
    if (!hasPendingListChanges || savingInlineChanges) return;
    setSavingInlineChanges(true);
    setMessage("");
    setCellErrors({});
    const updatePayload = buildInlineUpdatePayload();
    const deletePayload: WaybillBulkDeleteRequest = { waybill_ids: pendingDeleteIds };
    try {
      const [updateResult, deleteResult] = await Promise.all([
        updatePayload.updates.length > 0
          ? apiClient.patch<WaybillBulkInlineUpdateResult>("/waybills/bulk-inline-update", updatePayload)
          : Promise.resolve<WaybillBulkInlineUpdateResult>({
              success_count: 0,
              failed_count: 0,
              updated_waybills: [],
              errors: []
            }),
        deletePayload.waybill_ids.length > 0
          ? apiClient.post<WaybillBulkDeleteResult>("/waybills/bulk-delete", deletePayload)
          : Promise.resolve<WaybillBulkDeleteResult>({
              success_count: 0,
              failed_count: 0,
              deleted_waybills: [],
              errors: []
            })
      ]);
      const updatedMap = new Map(updateResult.updated_waybills.map((item) => [item.id, item]));
      const deletedIds = new Set(deleteResult.deleted_waybills.map((item) => item.id));
      setData((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items
                .filter((item) => !deletedIds.has(item.id))
                .map((item) => updatedMap.get(item.id) || item),
              total: Math.max(0, prev.total - deletedIds.size)
            }
          : prev
      );
      setDraftChanges((prev) => {
        const next = { ...prev };
        updateResult.updated_waybills.forEach((item) => delete next[item.id]);
        deletedIds.forEach((id) => delete next[id]);
        return next;
      });
      setPendingDeleteIds((prev) => prev.filter((id) => !deletedIds.has(id)));
      setSelectedWaybillIds((prev) => prev.filter((id) => !deletedIds.has(id)));
      const nextErrors: CellErrors = {};
      updateResult.errors.forEach((item) => {
        const field = (item.field as CellErrorField | undefined) || "_row";
        nextErrors[item.waybill_id] = {
          ...(nextErrors[item.waybill_id] || {}),
          [field]: item.message
        };
      });
      deleteResult.errors.forEach((item) => {
        nextErrors[item.id] = {
          ...(nextErrors[item.id] || {}),
          _delete: item.message
        };
      });
      setCellErrors(nextErrors);
      const failedCount = updateResult.failed_count + deleteResult.failed_count;
      const successCount = updateResult.success_count + deleteResult.success_count;
      if (failedCount === 0) {
        discardEditChanges();
        setEditMode(false);
        setMessage(`确认修改完成：成功 ${successCount} 项。`);
      } else {
        setMessage(`确认修改完成：成功 ${successCount} 项，失败 ${failedCount} 项。失败项已保留在编辑态。`);
      }
      loadCounts();
      load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认修改失败。");
    } finally {
      setSavingInlineChanges(false);
    }
  }

  async function requestCustomsAccess() {
    const waybillNo = accessWaybillNo.trim();
    if (!waybillNo) {
      setMessage("请输入需要申请查看的提单号。");
      return;
    }
    setRequestingAccess(true);
    setMessage("");
    try {
      const result = await apiClient.post<Waybill>("/waybills/access-requests", { waybill_no: waybillNo });
      setMessage(`已获得提单 ${result.waybill_no} 的查看权限。`);
      setAccessWaybillNo("");
      router.push(`/waybills/${result.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "申请查看提单失败。");
    } finally {
      setRequestingAccess(false);
    }
  }

  async function exportMonthlyGeneralCargo() {
    const selectedMonth = parseMonthValue(generalCargoMonth);
    if (!selectedMonth) {
      setMessage("请选择需要导出的月份。");
      return;
    }

    setExportingGeneralCargo(true);
    setMessage("");
    try {
      const { blob, filename } = await apiClient.download(
        `/waybills/general-cargo-export?year=${selectedMonth.year}&month=${selectedMonth.month}`
      );
      downloadBlob(blob, filename || `${selectedMonth.year}年${selectedMonth.month}月普货汇总.xlsx`);
      setMessage(`${selectedMonth.year}年${selectedMonth.month}月普货汇总已导出。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出普货汇总失败。");
    } finally {
      setExportingGeneralCargo(false);
    }
  }

  async function uploadAirlineFiles(files: FileList | null) {
    if (!files || files.length === 0) return;
    if (!canBulkEditWaybills) return;

    const formData = new FormData();
    Array.from(files).forEach((file) => formData.append("files", file));
    setAirlineUploading(true);
    setMessage("");
    try {
      const result = await apiClient.postForm<WaybillAirlineFileBatchUploadResult>("/waybills/airline-files/batch", formData);
      setAirlineUploadResult(result);
      setMessage(`提单文件上传完成：成功 ${result.success_count} 个，失败 ${result.failed_count} 个。`);
      load();
      loadCounts();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "提单文件上传失败。");
    } finally {
      setAirlineUploading(false);
      if (airlineFileInputRef.current) airlineFileInputRef.current.value = "";
    }
  }

  function renderBulkEditValueInput() {
    const fieldId = "bulk-edit-value";
    if (selectedBulkField.kind === "date") {
      return (
        <Input
          id={fieldId}
          type="date"
          value={bulkEditValue}
          onChange={(event) => setBulkEditValue(event.target.value)}
        />
      );
    }

    if (bulkEditField === "customs_staff_id") {
      return (
        <Select value={bulkEditValue || BULK_CLEAR_VALUE} onValueChange={setBulkEditValue}>
          <SelectTrigger id={fieldId}>
            <SelectValue placeholder="选择清关人员" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={BULK_CLEAR_VALUE}>清空</SelectItem>
            {enabledCustomsUsers.map((item) => (
              <SelectItem key={item.id} value={String(item.id)}>
                {item.display_name || item.username}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }

    if (bulkEditField === "carrier_agent_id") {
      return (
        <Select value={bulkEditValue || BULK_CLEAR_VALUE} onValueChange={setBulkEditValue}>
          <SelectTrigger id={fieldId}>
            <SelectValue placeholder="选择航代" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={BULK_CLEAR_VALUE}>清空</SelectItem>
            {enabledAgents.map((item) => (
              <SelectItem key={item.id} value={String(item.id)}>
                {item.agent_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      );
    }

    if (bulkEditField === "consignee_contact_id") {
      return (
        <Select value={bulkEditValue || BULK_CLEAR_VALUE} onValueChange={setBulkEditValue}>
          <SelectTrigger id={fieldId}>
            <SelectValue placeholder="选择收件人" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={BULK_CLEAR_VALUE}>清空</SelectItem>
            {enabledContacts.map((item) => {
              const company = consigneeNameById.get(item.consignee_id) || "?";
              const addr = (item.address || "").split("\n")[0].slice(0, 30);
              return (
                <SelectItem key={item.id} value={String(item.id)}>
                  [{company}] {item.name} {addr ? `- ${addr}` : ""}
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
      );
    }

    if (selectedBulkField.kind === "boolean") {
      return (
        <Select value={bulkEditValue || "false"} onValueChange={setBulkEditValue}>
          <SelectTrigger id={fieldId}>
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="true">含T</SelectItem>
            <SelectItem value="false">不含T</SelectItem>
          </SelectContent>
        </Select>
      );
    }

    return (
      <Input
        id={fieldId}
        type={selectedBulkField.kind === "number" ? "number" : "text"}
        step={selectedBulkField.kind === "number" ? "0.001" : undefined}
        value={bulkEditValue}
        placeholder={selectedBulkField.placeholder || "留空保存为清空"}
        onChange={(event) => setBulkEditValue(event.target.value)}
      />
    );
  }

  function getCellError(item: Waybill, field: CellErrorField) {
    return cellErrors[item.id]?.[field];
  }

  function renderCellError(item: Waybill, field: CellErrorField) {
    const error = getCellError(item, field);
    return error ? <div className="mt-1 text-xs text-red-600">{error}</div> : null;
  }

  function renderInlineText(item: Waybill, field: WaybillInlineUpdateField, options?: { type?: "text" | "number" | "date"; syncBoard?: boolean }) {
    const value = getDraftValue(item, field);
    return (
      <div className="min-w-32">
        <Input
          type={options?.type || "text"}
          step={options?.type === "number" ? "0.001" : undefined}
          value={String(value ?? "")}
          disabled={pendingDeleteIdSet.has(item.id)}
          onChange={(event) => stageDraftChange(item, field, event.target.value, options?.syncBoard)}
        />
        {renderCellError(item, field)}
      </div>
    );
  }

  function renderCarrierAgentSelect(item: Waybill) {
    const value = getDraftValue(item, "carrier_agent_id");
    return (
      <div className="min-w-44">
        <Select
          value={value == null ? BULK_CLEAR_VALUE : String(value)}
          disabled={pendingDeleteIdSet.has(item.id)}
          onValueChange={(nextValue) =>
            stageDraftChange(item, "carrier_agent_id", nextValue === BULK_CLEAR_VALUE ? null : Number(nextValue))
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="选择航代" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={BULK_CLEAR_VALUE}>清空</SelectItem>
            {enabledAgents.map((agent) => (
              <SelectItem key={agent.id} value={String(agent.id)}>
                {agent.agent_name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {renderCellError(item, "carrier_agent_id")}
      </div>
    );
  }

  function renderContactSelect(item: Waybill, syncBoard = false) {
    const value = getDraftValue(item, "consignee_contact_id");
    return (
      <div className="min-w-56">
        <Select
          value={value == null ? BULK_CLEAR_VALUE : String(value)}
          disabled={pendingDeleteIdSet.has(item.id)}
          onValueChange={(nextValue) =>
            stageDraftChange(item, "consignee_contact_id", nextValue === BULK_CLEAR_VALUE ? null : Number(nextValue), syncBoard)
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="选择收件人" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={BULK_CLEAR_VALUE}>清空</SelectItem>
            {enabledContacts.map((contact) => {
              const company = consigneeNameById.get(contact.consignee_id) || "?";
              const addr = (contact.address || "").split("\n")[0].slice(0, 30);
              return (
                <SelectItem key={contact.id} value={String(contact.id)}>
                  [{company}] {contact.name} {addr ? `- ${addr}` : ""}
                </SelectItem>
              );
            })}
          </SelectContent>
        </Select>
        {renderCellError(item, "consignee_contact_id")}
      </div>
    );
  }

  function renderCustomsStaffSelect(item: Waybill) {
    const value = getDraftValue(item, "customs_staff_id");
    return (
      <div className="min-w-44">
        <Select
          value={value == null ? BULK_CLEAR_VALUE : String(value)}
          disabled={pendingDeleteIdSet.has(item.id)}
          onValueChange={(nextValue) =>
            stageDraftChange(item, "customs_staff_id", nextValue === BULK_CLEAR_VALUE ? null : Number(nextValue))
          }
        >
          <SelectTrigger>
            <SelectValue placeholder="选择清关人员" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={BULK_CLEAR_VALUE}>清空</SelectItem>
            {enabledCustomsUsers.map((customsUser) => (
              <SelectItem key={customsUser.id} value={String(customsUser.id)}>
                {customsUser.display_name || customsUser.username}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        {renderCellError(item, "customs_staff_id")}
      </div>
    );
  }

  async function saveInternalRemark(item: Waybill, value: string | null) {
    setMessage("");
    const updated = await apiClient.patch<Waybill>(`/waybills/${item.id}`, { internal_remark: value });
    setData((current) =>
      current
        ? {
            ...current,
            items: current.items.map((row) => (row.id === updated.id ? updated : row))
          }
        : current
    );
  }

  const columnDefinitions: Record<WaybillColumnKey, WaybillTableColumn> = {
      waybill_no: {
        key: "waybill_no",
        label: WAYBILL_COLUMN_LABELS.waybill_no,
        render: ({ item }) => (
          <TD className="font-medium">
            {editMode ? (
              <>
                {renderInlineText(item, "waybill_no")}
                {renderCellError(item, "_row")}
                {renderCellError(item, "_delete")}
              </>
            ) : (
              <Link
                href={`/waybills/${item.id}`}
                className="inline-flex rounded px-1 py-0.5 font-semibold text-purple-700 underline-offset-2 hover:bg-purple-50 hover:text-purple-900 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-purple-300"
              >
                {item.waybill_no}
              </Link>
            )}
          </TD>
        )
      },
      consignee: {
        key: "consignee",
        label: WAYBILL_COLUMN_LABELS.consignee,
        render: ({ item, boardSpan, shouldRenderBoardCells }) =>
          shouldRenderBoardCells ? (
            <TD rowSpan={boardSpan} className="align-middle">
              {editMode ? renderContactSelect(item, Boolean(item.board_id)) : item.board ? compact(item.board.consignee_text) : compact(item.consignee)}
            </TD>
          ) : null
      },
      booked_volume: {
        key: "booked_volume",
        label: WAYBILL_COLUMN_LABELS.booked_volume,
        render: ({ item, boardSpan, shouldRenderBoardCells }) =>
          shouldRenderBoardCells ? (
            <TD rowSpan={boardSpan} className="align-middle">
              {editMode ? renderInlineText(item, "booked_volume", { type: "number", syncBoard: Boolean(item.board_id) }) : item.board ? compact(item.board.total_booked_volume) : compact(item.booked_volume)}
            </TD>
          ) : null
      },
      booked_weight: {
        key: "booked_weight",
        label: WAYBILL_COLUMN_LABELS.booked_weight,
        render: ({ item }) => <TD>{editMode ? renderInlineText(item, "booked_weight", { type: "number" }) : compact(item.booked_weight)}</TD>
      },
      density: {
        key: "density",
        label: WAYBILL_COLUMN_LABELS.density,
        render: ({ item }) => <TD>{editMode ? renderInlineText(item, "density", { type: "number" }) : compact(item.density)}</TD>
      },
      quotation: {
        key: "quotation",
        label: WAYBILL_COLUMN_LABELS.quotation,
        render: ({ item }) => <TD>{editMode ? renderInlineText(item, "quotation") : compact(item.quotation)}</TD>
      },
      include_tc: {
        key: "include_tc",
        label: WAYBILL_COLUMN_LABELS.include_tc,
        render: ({ item }) => (
          <TD>
            {editMode ? (
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300"
                checked={Boolean(getDraftValue(item, "include_tc"))}
                disabled={pendingDeleteIdSet.has(item.id)}
                onChange={(event) => stageDraftChange(item, "include_tc", event.target.checked)}
                aria-label={`设置提单 ${item.waybill_no} 是否含T`}
              />
            ) : item.include_tc ? (
              <Check className="h-4 w-4 text-emerald-600" aria-label="含T" />
            ) : null}
          </TD>
        )
      },
      customs_staff: {
        key: "customs_staff",
        label: WAYBILL_COLUMN_LABELS.customs_staff,
        render: ({ item }) => <TD>{editMode ? renderCustomsStaffSelect(item) : compact(userDisplayName(item.customs_staff))}</TD>
      },
      customs_data: {
        key: "customs_data",
        label: WAYBILL_COLUMN_LABELS.customs_data,
        render: ({ item }) => (
          <TD>
            {item.customs_data_uploaded_at ? (
              <span className="text-emerald-700">已上传 {formatDateTime(item.customs_data_uploaded_at)}</span>
            ) : (
              <span className="text-amber-700">待上传</span>
            )}
          </TD>
        )
      },
      internal_remark: {
        key: "internal_remark",
        label: WAYBILL_COLUMN_LABELS.internal_remark,
        render: ({ item }) => (
          <TD>
            <InternalRemarkCell item={item} disabled={pendingDeleteIdSet.has(item.id)} onSave={saveInternalRemark} />
          </TD>
        )
      },
      agent: {
        key: "agent",
        label: WAYBILL_COLUMN_LABELS.agent,
        render: ({ item }) => <TD>{editMode ? renderCarrierAgentSelect(item) : compact(item.agent)}</TD>
      },
      warehouse: {
        key: "warehouse",
        label: WAYBILL_COLUMN_LABELS.warehouse,
        render: ({ item }) => (
          <TD>
            <div className="flex min-w-40 flex-col items-start gap-1">
              {item.warehouse_no ? <span className="font-medium text-slate-800">{item.warehouse_no}</span> : <span className="text-slate-400">-</span>}
            </div>
          </TD>
        )
      },
      outbound_date: {
        key: "outbound_date",
        label: WAYBILL_COLUMN_LABELS.outbound_date,
        render: ({ item }) => <TD>{editMode ? renderInlineText(item, "outbound_date", { type: "date" }) : compact(formatOutboundDate(item.outbound_date))}</TD>
      },
      departure_port: {
        key: "departure_port",
        label: WAYBILL_COLUMN_LABELS.departure_port,
        render: ({ item }) => <TD>{compact(item.departure_port)}</TD>
      },
      destination_port: {
        key: "destination_port",
        label: WAYBILL_COLUMN_LABELS.destination_port,
        render: ({ item }) => <TD>{compact(item.destination_port)}</TD>
      },
      planned_flight: {
        key: "planned_flight",
        label: WAYBILL_COLUMN_LABELS.planned_flight,
        render: ({ item }) => <TD>{editMode ? renderInlineText(item, "planned_flight_no") : compact(formatPlannedFlightInfo(item.plan))}</TD>
      },
      planned_flight_date: {
        key: "planned_flight_date",
        label: WAYBILL_COLUMN_LABELS.planned_flight_date,
        render: ({ item }) => <TD>{editMode ? renderInlineText(item, "planned_flight_date", { type: "date" }) : compact(item.plan?.planned_flight_date)}</TD>
      },
      official_estimated_flight_date: {
        key: "official_estimated_flight_date",
        label: WAYBILL_COLUMN_LABELS.official_estimated_flight_date,
        render: ({ item }) => <TD>{item.official_estimated_flight_date || ""}</TD>
      },
      lifecycle: {
        key: "lifecycle",
        label: WAYBILL_COLUMN_LABELS.lifecycle,
        render: ({ item }) => (
          <TD>
            <LifecycleBadge value={item.lifecycle_status} />
          </TD>
        )
      },
      alert: {
        key: "alert",
        label: WAYBILL_COLUMN_LABELS.alert,
        render: ({ item }) => (
          <TD>
            <AlertLevelBadge value={item.alert_level} />
          </TD>
        )
      }
    };

  const visibleColumnOrder = canBulkEditWaybills ? columnOrder : columnOrder.filter((key) => key !== "internal_remark");
  const orderedColumns = visibleColumnOrder.map((key) => columnDefinitions[key]);

  return (
    <>
      <PageHeader
        title="提单管理"
        description="录入、筛选、追踪航空头程提单"
        action={
          <div className="flex flex-wrap gap-2">
            {canBulkEditWaybills ? (
              <>
                <input
                  ref={airlineFileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  multiple
                  className="hidden"
                  onChange={(event) => void uploadAirlineFiles(event.target.files)}
                />
                <Button type="button" variant="secondary" disabled={airlineUploading} onClick={() => airlineFileInputRef.current?.click()}>
                  <Upload className="h-4 w-4" />
                  {airlineUploading ? "上传中..." : "上传提单文件"}
                </Button>
              </>
            ) : null}
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
      {canRequestCustomsAccess ? (
        <Panel title="申请查看提单" className="mb-4">
          <div className="flex flex-wrap gap-2">
            <Input
              className="max-w-sm"
              placeholder="输入提单号"
              value={accessWaybillNo}
              onChange={(event) => setAccessWaybillNo(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  void requestCustomsAccess();
                }
              }}
            />
            <Button type="button" disabled={requestingAccess} onClick={() => void requestCustomsAccess()}>
              申请查看提单
            </Button>
          </div>
        </Panel>
      ) : null}
      <Panel
        title="状态总览"
        action={
          canBulkEditWaybills ? (
            <div className="flex flex-wrap items-center justify-end gap-2 py-2">
              <Input
                type="month"
                value={generalCargoMonth}
                onChange={(event) => setGeneralCargoMonth(event.target.value)}
                className="h-8 w-36"
                aria-label="普货汇总导出月份"
              />
              <Button type="button" variant="secondary" size="sm" disabled={exportingGeneralCargo} onClick={() => void exportMonthlyGeneralCargo()}>
                <Download className="h-4 w-4" />
                {exportingGeneralCargo ? "导出中..." : "本月普货导出"}
              </Button>
            </div>
          ) : null
        }
      >
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
          <Input
            placeholder="提单号"
            value={waybillNo}
            onChange={(event) => {
              setSelectedWaybillIds([]);
              setWaybillNo(event.target.value);
            }}
          />
          <Input
            placeholder="航司代码"
            value={carrierCode}
            onChange={(event) => {
              setSelectedWaybillIds([]);
              setCarrierCode(event.target.value);
            }}
          />
          <Input
            placeholder="目的港"
            value={destinationPort}
            onChange={(event) => {
              setSelectedWaybillIds([]);
              setDestinationPort(event.target.value);
            }}
          />
          <Input
            placeholder="计划航班"
            value={plannedFlightNo}
            onChange={(event) => {
              setSelectedWaybillIds([]);
              setPlannedFlightNo(event.target.value);
            }}
          />
          <Select
            value={lifecycleStatus}
            onValueChange={(value) => {
              if (!confirmAndDiscardEditChanges()) return;
              setLifecycleStatus(value as LifecycleStatus | "all");
            }}
          >
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
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            {editMode && canBulkEditWaybills ? (
              <>
                <span className="text-sm text-slate-600">
                  已选 {selectedWaybillIds.length} 票
                  {pendingDeleteIds.length > 0 ? `，待删除 ${pendingDeleteIds.length} 票` : ""}
                </span>
                <Button type="button" size="sm" disabled={selectedWaybillIds.length === 0} onClick={openBulkEditDialog}>
                  <Pencil className="h-4 w-4" />
                  批量编辑
                </Button>
                <Button type="button" variant="ghost" size="sm" disabled={selectedWaybillIds.length === 0} onClick={stageSelectedForDelete}>
                  <Trash2 className="h-4 w-4 text-red-600" />
                  批量删除
                </Button>
                <Button type="button" size="sm" disabled={!hasPendingListChanges || savingInlineChanges} onClick={() => void submitInlineChanges()}>
                  {savingInlineChanges ? "保存中..." : "确认修改"}
                </Button>
                <Button type="button" variant="secondary" size="sm" onClick={cancelEditMode}>
                  取消修改
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedWaybillIds([])}>
                  取消选择
                </Button>
              </>
            ) : null}
          </div>
          <div className="flex flex-wrap gap-2">
            {canBulkEditWaybills && !editMode ? (
              <Button type="button" variant="secondary" size="sm" onClick={enterEditMode}>
                <Pencil className="h-4 w-4" />
                编辑
              </Button>
            ) : null}
            <Button type="button" variant="secondary" size="sm" onClick={resetColumnOrder}>
              <RotateCcw className="h-4 w-4" />
              恢复默认列顺序
            </Button>
          </div>
        </div>
        <Table>
          <THead>
            <TR>
              {editMode && canBulkEditWaybills ? (
                <TH className="w-10">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-slate-300"
                    checked={allCurrentPageSelected}
                    ref={(element) => {
                      if (element) element.indeterminate = someCurrentPageSelected && !allCurrentPageSelected;
                    }}
                    onChange={(event) => toggleCurrentPageSelection(event.target.checked)}
                    aria-label="选择当前页提单"
                  />
                </TH>
              ) : null}
              {orderedColumns.map((column) => (
                <TH
                  key={column.key}
                  draggable
                  onDragStart={(event) => {
                    setDraggingColumn(column.key);
                    event.dataTransfer.effectAllowed = "move";
                    event.dataTransfer.setData("text/plain", column.key);
                  }}
                  onDragOver={(event) => {
                    event.preventDefault();
                    event.dataTransfer.dropEffect = "move";
                  }}
                  onDrop={(event) => handleColumnDrop(event, column.key)}
                  onDragEnd={() => setDraggingColumn(null)}
                  className={cn(
                    "cursor-move select-none transition",
                    draggingColumn === column.key && "bg-purple-50 text-purple-700"
                  )}
                  title="拖动列标题调整顺序"
                >
                  {column.label}
                </TH>
              ))}
              {editMode && canBulkEditWaybills ? <TH>操作</TH> : null}
            </TR>
          </THead>
          <TBody>
            {(data?.items || []).map((item, index) => {
              const boardSpan = boardRowSpans.get(index) || 0;
              const shouldRenderBoardCells = !item.board_id || boardSpan > 0;
              const isPendingDelete = pendingDeleteIdSet.has(item.id);
              return (
              <TR
                key={item.id}
                className={cn(
                  item.lifecycle_status === "picked_up" &&
                    "[&_td]:text-slate-400 [&_td_*]:text-slate-400",
                  isPendingDelete && "[&_td]:bg-red-50 [&_td]:text-slate-400 [&_td_*]:text-slate-400"
                )}
              >
                {editMode && canBulkEditWaybills ? (
                  <TD>
                    <input
                      type="checkbox"
                      className="h-4 w-4 rounded border-slate-300"
                      checked={selectedIdSet.has(item.id)}
                      onChange={(event) => toggleWaybillSelection(item.id, event.target.checked)}
                      aria-label={`选择提单 ${item.waybill_no}`}
                    />
                  </TD>
                ) : null}
                {orderedColumns.map((column) => (
                  <Fragment key={column.key}>
                    {column.render({ item, boardSpan, shouldRenderBoardCells })}
                  </Fragment>
                ))}
                {editMode && canBulkEditWaybills ? (
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => togglePendingDelete(item)}
                        aria-label={`${isPendingDelete ? "取消删除" : "删除"}提单 ${item.waybill_no}`}
                      >
                        <Trash2 className="h-4 w-4 text-red-600" />
                        {isPendingDelete ? "取消删除" : "删除"}
                      </Button>
                    </div>
                  </TD>
                ) : null}
              </TR>
              );
            })}
          </TBody>
        </Table>
        <div className="mt-4 flex items-center justify-between text-sm text-slate-500">
          <span>共 {data?.total ?? 0} 条</span>
          <div className="flex gap-2">
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() => {
                if (!confirmAndDiscardEditChanges()) return;
                setPage((prev) => prev - 1);
              }}
            >
              上一页
            </Button>
            <Button
              variant="secondary"
              size="sm"
              disabled={!data || page * data.page_size >= data.total}
              onClick={() => {
                if (!confirmAndDiscardEditChanges()) return;
                setPage((prev) => prev + 1);
              }}
            >
              下一页
            </Button>
          </div>
        </div>
      </Panel>
      <Dialog open={Boolean(airlineUploadResult)} onOpenChange={(open) => !open && setAirlineUploadResult(null)}>
        <DialogContent className="w-[min(900px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">提单文件上传结果</DialogTitle>
          {airlineUploadResult ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <section className="rounded-md border border-emerald-200 bg-emerald-50/60">
                <div className="border-b border-emerald-200 px-3 py-2 text-sm font-medium text-emerald-900">
                  成功绑定 {airlineUploadResult.success_count} 个
                </div>
                <div className="max-h-72 overflow-auto divide-y divide-emerald-100">
                  {airlineUploadResult.successes.map((item, index) => (
                    <div key={`${item.file_name}-${index}`} className="space-y-1 px-3 py-2 text-sm">
                      <div className="font-medium text-slate-900">{item.file_name}</div>
                      <div className="text-slate-700">
                        提单 {item.waybill_no}
                        {item.replaced_existing ? "，已替换旧文件" : ""}
                      </div>
                      <div className="text-xs text-slate-500">
                        识别方式：{item.extraction_method === "ocr" ? "OCR" : "文本层"}
                      </div>
                    </div>
                  ))}
                  {airlineUploadResult.successes.length === 0 ? (
                    <div className="px-3 py-8 text-center text-sm text-slate-500">没有成功绑定的文件</div>
                  ) : null}
                </div>
              </section>
              <section className="rounded-md border border-rose-200 bg-rose-50/60">
                <div className="border-b border-rose-200 px-3 py-2 text-sm font-medium text-rose-900">
                  失败 {airlineUploadResult.failed_count} 个
                </div>
                <div className="max-h-72 overflow-auto divide-y divide-rose-100">
                  {airlineUploadResult.failures.map((item, index) => (
                    <div key={`${item.file_name}-${index}`} className="space-y-1 px-3 py-2 text-sm">
                      <div className="font-medium text-slate-900">{item.file_name}</div>
                      <div className="text-rose-700">{item.message}</div>
                      {item.extracted_waybill_no ? (
                        <div className="text-xs text-slate-500">识别结果：{item.extracted_waybill_no}</div>
                      ) : null}
                    </div>
                  ))}
                  {airlineUploadResult.failures.length === 0 ? (
                    <div className="px-3 py-8 text-center text-sm text-slate-500">没有失败文件</div>
                  ) : null}
                </div>
              </section>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
      <Dialog
        open={bulkEditOpen}
        onOpenChange={(open) => {
          setBulkEditOpen(open);
          if (!open) {
            setBulkEditResult(null);
          }
        }}
      >
        <DialogContent className="w-[min(880px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">批量编辑提单</DialogTitle>
          <div className="grid gap-4 lg:grid-cols-[1fr_1fr]">
            <section className="space-y-4">
              <div className="space-y-1.5">
                <Label htmlFor="bulk-edit-field">修改字段</Label>
                <Select
                  value={bulkEditField}
                  onValueChange={(value) => {
                    setBulkEditField(value as WaybillInlineUpdateField);
                    setBulkEditValue("");
                    setBulkEditResult(null);
                  }}
                >
                  <SelectTrigger id="bulk-edit-field">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {BULK_UPDATE_FIELDS.map((item) => (
                      <SelectItem key={item.key} value={item.key}>
                        {item.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="bulk-edit-value">统一修改为</Label>
                {renderBulkEditValueInput()}
                <p className="text-xs text-slate-500">下拉字段选择“清空”，文本或日期留空，都会保存为空值。</p>
              </div>
              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => setBulkEditOpen(false)}>
                  取消
                </Button>
                <Button type="button" disabled={bulkEditSaving || selectedWaybillIds.length === 0} onClick={() => void submitBulkEdit()}>
                  {bulkEditSaving ? "应用中..." : "应用到草稿"}
                </Button>
              </div>
            </section>
            <section className="space-y-3">
              <div className="rounded-md border border-slate-200">
                <div className="border-b border-slate-200 px-3 py-2 text-sm font-medium text-slate-800">
                  已选提单（{selectedWaybillIds.length}）
                </div>
                <div className="max-h-48 overflow-auto">
                  <Table>
                    <THead>
                      <TR>
                        <TH>提单号</TH>
                        <TH>生命周期</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {selectedWaybills.map((item) => (
                        <TR key={item.id}>
                          <TD className="font-medium">{item.waybill_no}</TD>
                          <TD>
                            <LifecycleBadge value={item.lifecycle_status} />
                          </TD>
                        </TR>
                      ))}
                      {selectedWaybills.length === 0 ? (
                        <TR>
                          <TD colSpan={2} className="py-6 text-center text-slate-500">
                            暂无当前页选中提单
                          </TD>
                        </TR>
                      ) : null}
                    </TBody>
                  </Table>
                </div>
              </div>
              {bulkEditResult ? (
                <div className="rounded-md border border-slate-200">
                  <div className="border-b border-slate-200 px-3 py-2 text-sm font-medium text-slate-800">
                    已应用到草稿：{bulkEditResult.success_count} 票
                  </div>
                  <div className="px-3 py-3 text-sm text-slate-600">批量编辑只修改当前草稿，点击列表上方“确认修改”后才会写入系统。</div>
                </div>
              ) : null}
            </section>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
