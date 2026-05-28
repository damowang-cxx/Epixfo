"use client";

import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type DragEvent, type ReactNode } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Download, Pencil, Plus, RotateCcw, Search, Trash2, Upload } from "lucide-react";
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
import { WarehouseFileUploadButton } from "@/components/waybills/warehouse-file-upload-button";
import { apiClient } from "@/lib/client-api";
import { LIFECYCLE_ORDER, lifecycleLabels } from "@/lib/constants";
import { formatPlannedFlightInfo } from "@/lib/planned-flight";
import { cn, compact, formatDateTime, formatOutboundDate } from "@/lib/utils";
import { formatWarehouseUploadMessage } from "@/lib/warehouse-upload";
import type {
  CarrierAgent,
  Consignee,
  ConsigneeContact,
  LifecycleStatus,
  PageResponse,
  TableColumnPreference,
  User,
  WaybillBulkImportResult,
  WaybillBulkUpdateField,
  WaybillBulkUpdateRequest,
  WaybillBulkUpdateResult,
  WarehouseFileUploadResult,
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

type BulkUpdateFieldKind = "select" | "date" | "text" | "textarea";

const BULK_UPDATE_FIELDS: Array<{
  key: WaybillBulkUpdateField;
  label: string;
  kind: BulkUpdateFieldKind;
  placeholder?: string;
}> = [
  { key: "customs_staff_id", label: "指定清关人员", kind: "select" },
  { key: "outbound_date", label: "出仓日期", kind: "date" },
  { key: "carrier_agent_id", label: "航代", kind: "select" },
  { key: "consignee_contact_id", label: "收件人", kind: "select" },
  { key: "departure_port", label: "始发港", kind: "text" },
  { key: "destination_port", label: "目的港", kind: "text" },
  { key: "planned_flight_info", label: "计划航班信息", kind: "text", placeholder: "QR8943/01" },
  { key: "planned_route_text", label: "人工计划航程", kind: "text" },
  { key: "warehouse_data_remark", label: "入仓数据备注", kind: "textarea" },
  { key: "customer_remark", label: "客户备注", kind: "textarea" },
  { key: "internal_remark", label: "内部备注", kind: "textarea" }
];

const WAYBILL_TABLE_KEY = "waybills:list";

const DEFAULT_WAYBILL_COLUMN_ORDER = [
  "waybill_no",
  "consignee",
  "booked_volume",
  "customs_staff",
  "customs_data",
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
  customs_staff: "指定清关人员",
  customs_data: "清关资料",
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
  const { user, hasRole } = useAuth();
  const router = useRouter();
  const canDeleteWaybills = hasRole("admin") || hasRole("route_staff");
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
  const [columnOrder, setColumnOrder] = useState<WaybillColumnKey[]>(() => normalizeWaybillColumnOrder());
  const [draggingColumn, setDraggingColumn] = useState<WaybillColumnKey | null>(null);
  const [deletingWaybillId, setDeletingWaybillId] = useState<number | null>(null);
  const [accessWaybillNo, setAccessWaybillNo] = useState("");
  const [requestingAccess, setRequestingAccess] = useState(false);
  const bulkImportInputRef = useRef<HTMLInputElement>(null);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const [uploadingBulkImport, setUploadingBulkImport] = useState(false);
  const [bulkImportResult, setBulkImportResult] = useState<WaybillBulkImportResult | null>(null);
  const [bulkImportError, setBulkImportError] = useState("");
  const [selectedWaybillIds, setSelectedWaybillIds] = useState<number[]>([]);
  const [bulkEditOpen, setBulkEditOpen] = useState(false);
  const [bulkEditField, setBulkEditField] = useState<WaybillBulkUpdateField>("outbound_date");
  const [bulkEditValue, setBulkEditValue] = useState("");
  const [bulkEditSaving, setBulkEditSaving] = useState(false);
  const [bulkEditResult, setBulkEditResult] = useState<WaybillBulkUpdateResult | null>(null);
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
    setSelectedWaybillIds([]);
    setPage(1);
    load();
  }

  function selectStatus(status: LifecycleStatus | "all") {
    setSelectedWaybillIds([]);
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
    if (selectedWaybillIds.length === 0) return;
    setBulkEditValue("");
    setBulkEditResult(null);
    setBulkEditOpen(true);
  }

  function normalizeBulkEditValue(): string | number | null {
    if (selectedBulkField.kind === "select") {
      return bulkEditValue === "" || bulkEditValue === BULK_CLEAR_VALUE ? null : Number(bulkEditValue);
    }
    if (selectedBulkField.kind === "date") {
      return bulkEditValue || null;
    }
    const trimmed = bulkEditValue.trim();
    return trimmed === "" ? null : trimmed;
  }

  function applyBulkUpdateToLocalRow(item: Waybill, field: WaybillBulkUpdateField, value: string | number | null): Waybill {
    if (field === "carrier_agent_id") {
      const agent = typeof value === "number" ? agents.find((row) => row.id === value) : undefined;
      return {
        ...item,
        carrier_agent_id: agent?.id ?? null,
        carrier_agent: agent ?? null,
        agent: agent?.agent_name ?? null
      };
    }
    if (field === "consignee_contact_id") {
      const contact = typeof value === "number" ? contacts.find((row) => row.id === value) : undefined;
      const company = contact ? consigneeNameById.get(contact.consignee_id) : null;
      return {
        ...item,
        consignee_contact_id: contact?.id ?? null,
        consignee_contact: contact ?? null,
        consignee: contact ? compact(company ? `${company} ${contact.name}` : contact.name) : null
      };
    }
    if (field === "customs_staff_id") {
      const customsUser = typeof value === "number" ? users.find((row) => row.id === value) : undefined;
      return {
        ...item,
        customs_staff_id: customsUser?.id ?? null,
        customs_staff: customsUser
          ? {
              id: customsUser.id,
              username: customsUser.username,
              display_name: customsUser.display_name,
              is_active: customsUser.is_active
            }
          : null
      };
    }
    if (field === "planned_route_text") {
      return {
        ...item,
        plan: item.plan ? { ...item.plan, planned_route_text: value as string | null } : item.plan
      };
    }
    if (field === "planned_flight_info") {
      return item;
    }
    return { ...item, [field]: value } as Waybill;
  }

  async function submitBulkEdit() {
    if (selectedWaybillIds.length === 0 || bulkEditSaving) return;
    const value = normalizeBulkEditValue();
    const payload: WaybillBulkUpdateRequest = {
      waybill_ids: selectedWaybillIds,
      field: bulkEditField,
      value
    };
    setBulkEditSaving(true);
    setBulkEditResult(null);
    setMessage("");
    try {
      const result = await apiClient.patch<WaybillBulkUpdateResult>("/waybills/bulk-update", payload);
      setBulkEditResult(result);
      const updatedIds = new Set(result.updated_waybills.map((item) => item.id));
      if (updatedIds.size > 0) {
        setData((prev) =>
          prev
            ? {
                ...prev,
                items: prev.items.map((item) =>
                  updatedIds.has(item.id) ? applyBulkUpdateToLocalRow(item, bulkEditField, value) : item
                )
              }
            : prev
        );
        setSelectedWaybillIds((prev) => prev.filter((id) => !updatedIds.has(id)));
        load();
        loadCounts();
      }
      setMessage(`批量编辑完成：成功 ${result.success_count} 票，失败 ${result.failed_count} 票。`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "批量编辑失败。");
    } finally {
      setBulkEditSaving(false);
    }
  }

  const handleUploadSuccess = useCallback((result: WarehouseFileUploadResult) => {
    setMessage(formatWarehouseUploadMessage(result));
    load();
    loadCounts();
  }, [load, loadCounts]);

  async function uploadWaybillImportFile(file: File | null | undefined) {
    if (!file) return;
    setBulkImportOpen(true);
    setUploadingBulkImport(true);
    setBulkImportError("");
    setMessage("");
    setBulkImportResult(null);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const result = await apiClient.postForm<WaybillBulkImportResult>("/waybills/bulk-import", formData);
      setBulkImportResult(result);
      setMessage(`批量导入完成：成功 ${result.created_count} 票，失败 ${result.errors.length} 行。`);
      load();
      loadCounts();
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : "批量导入提单失败。";
      setBulkImportError(errorMessage);
      setMessage(errorMessage);
    } finally {
      setUploadingBulkImport(false);
    }
  }

  async function deleteWaybill(item: Waybill) {
    if (!window.confirm(`确认删除提单 ${item.waybill_no} 吗？删除后不可恢复，关联的入仓箱号会转为未绑定。`)) return;
    setDeletingWaybillId(item.id);
    setMessage("");
    try {
      await apiClient.delete<void>(`/waybills/${item.id}`);
      const shouldMoveToPreviousPage = (data?.items.length || 0) <= 1 && page > 1;
      setData((prev) =>
        prev
          ? {
              ...prev,
              items: prev.items.filter((row) => row.id !== item.id),
              total: Math.max(0, prev.total - 1)
            }
          : prev
      );
      setMessage(`提单 ${item.waybill_no} 已删除。`);
      if (shouldMoveToPreviousPage) {
        setPage((prev) => Math.max(1, prev - 1));
      } else {
        load();
      }
      loadCounts();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除提单失败。");
    } finally {
      setDeletingWaybillId(null);
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
                [{item.carrier_code}] {item.agent_name}
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

    if (selectedBulkField.kind === "textarea") {
      return (
        <Textarea
          id={fieldId}
          value={bulkEditValue}
          placeholder="留空保存为清空"
          onChange={(event) => setBulkEditValue(event.target.value)}
        />
      );
    }

    return (
      <Input
        id={fieldId}
        value={bulkEditValue}
        placeholder={selectedBulkField.placeholder || "留空保存为清空"}
        onChange={(event) => setBulkEditValue(event.target.value)}
      />
    );
  }

  const columnDefinitions = useMemo<Record<WaybillColumnKey, WaybillTableColumn>>(
    () => ({
      waybill_no: {
        key: "waybill_no",
        label: WAYBILL_COLUMN_LABELS.waybill_no,
        render: ({ item }) => (
          <TD className="font-medium">
            <Link
              href={`/waybills/${item.id}`}
              className="text-purple-700 underline-offset-2 hover:text-purple-900 hover:underline"
            >
              {item.waybill_no}
            </Link>
          </TD>
        )
      },
      consignee: {
        key: "consignee",
        label: WAYBILL_COLUMN_LABELS.consignee,
        render: ({ item, boardSpan, shouldRenderBoardCells }) =>
          shouldRenderBoardCells ? (
            <TD rowSpan={boardSpan} className="align-middle">
              {item.board ? compact(item.board.consignee_text) : compact(item.consignee)}
            </TD>
          ) : null
      },
      booked_volume: {
        key: "booked_volume",
        label: WAYBILL_COLUMN_LABELS.booked_volume,
        render: ({ item, boardSpan, shouldRenderBoardCells }) =>
          shouldRenderBoardCells ? (
            <TD rowSpan={boardSpan} className="align-middle">
              {item.board ? compact(item.board.total_booked_volume) : compact(item.booked_volume)}
            </TD>
          ) : null
      },
      customs_staff: {
        key: "customs_staff",
        label: WAYBILL_COLUMN_LABELS.customs_staff,
        render: ({ item }) => <TD>{compact(userDisplayName(item.customs_staff))}</TD>
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
      agent: {
        key: "agent",
        label: WAYBILL_COLUMN_LABELS.agent,
        render: ({ item }) => <TD>{compact(item.agent)}</TD>
      },
      warehouse: {
        key: "warehouse",
        label: WAYBILL_COLUMN_LABELS.warehouse,
        render: ({ item }) => (
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
        )
      },
      outbound_date: {
        key: "outbound_date",
        label: WAYBILL_COLUMN_LABELS.outbound_date,
        render: ({ item }) => <TD>{compact(formatOutboundDate(item.outbound_date))}</TD>
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
        render: ({ item }) => <TD>{compact(formatPlannedFlightInfo(item.plan))}</TD>
      },
      planned_flight_date: {
        key: "planned_flight_date",
        label: WAYBILL_COLUMN_LABELS.planned_flight_date,
        render: ({ item }) => <TD>{compact(item.plan?.planned_flight_date)}</TD>
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
    }),
    [handleUploadSuccess]
  );

  const orderedColumns = useMemo(
    () => columnOrder.map((key) => columnDefinitions[key]),
    [columnDefinitions, columnOrder]
  );

  return (
    <>
      <input
        ref={bulkImportInputRef}
        type="file"
        accept=".xlsx"
        className="hidden"
        onChange={(event) => {
          const file = event.currentTarget.files?.[0];
          event.currentTarget.value = "";
          void uploadWaybillImportFile(file);
        }}
      />
      <PageHeader
        title="提单管理"
        description="录入、筛选、追踪航空头程提单"
        action={
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" onClick={() => setBulkImportOpen(true)}>
              <Upload className="h-4 w-4" />
              批量上传提单
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
              setSelectedWaybillIds([]);
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
            {canBulkEditWaybills && selectedWaybillIds.length > 0 ? (
              <>
                <span className="text-sm text-slate-600">已选 {selectedWaybillIds.length} 票</span>
                <Button type="button" size="sm" onClick={openBulkEditDialog}>
                  <Pencil className="h-4 w-4" />
                  批量编辑
                </Button>
                <Button type="button" variant="ghost" size="sm" onClick={() => setSelectedWaybillIds([])}>
                  取消选择
                </Button>
              </>
            ) : null}
          </div>
          <Button type="button" variant="secondary" size="sm" onClick={resetColumnOrder}>
            <RotateCcw className="h-4 w-4" />
            恢复默认列顺序
          </Button>
        </div>
        <Table>
          <THead>
            <TR>
              {canBulkEditWaybills ? (
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
                {canBulkEditWaybills ? (
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
            <Button
              variant="secondary"
              size="sm"
              disabled={page <= 1}
              onClick={() => {
                setSelectedWaybillIds([]);
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
                setSelectedWaybillIds([]);
                setPage((prev) => prev + 1);
              }}
            >
              下一页
            </Button>
          </div>
        </div>
      </Panel>
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
                    setBulkEditField(value as WaybillBulkUpdateField);
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
                  {bulkEditSaving ? "保存中..." : "确认保存"}
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
                    保存结果：成功 {bulkEditResult.success_count} 票，失败 {bulkEditResult.failed_count} 票
                  </div>
                  <div className="max-h-48 overflow-auto">
                    <Table>
                      <THead>
                        <TR>
                          <TH>提单号</TH>
                          <TH>原因</TH>
                        </TR>
                      </THead>
                      <TBody>
                        {bulkEditResult.errors.map((item) => (
                          <TR key={item.id}>
                            <TD>{item.waybill_no || item.id}</TD>
                            <TD className="text-red-700">{item.message}</TD>
                          </TR>
                        ))}
                        {bulkEditResult.errors.length === 0 ? (
                          <TR>
                            <TD colSpan={2} className="py-6 text-center text-emerald-700">
                              全部保存成功
                            </TD>
                          </TR>
                        ) : null}
                      </TBody>
                    </Table>
                  </div>
                </div>
              ) : null}
            </section>
          </div>
        </DialogContent>
      </Dialog>
      <Dialog open={bulkImportOpen} onOpenChange={setBulkImportOpen}>
        <DialogContent className="w-[min(980px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">批量上传提单</DialogTitle>
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap items-center justify-between gap-2 rounded-md border border-slate-200 bg-slate-50 p-3">
              <div className="flex flex-wrap gap-2">
                <Button asChild variant="secondary">
                  <a href="/templates/waybill-bulk-import-template.xlsx" download="批量上传提单号_模板.xlsx">
                    <Download className="h-4 w-4" />
                    下载模板
                  </a>
                </Button>
                <Button type="button" disabled={uploadingBulkImport} onClick={() => bulkImportInputRef.current?.click()}>
                  <Upload className="h-4 w-4" />
                  {uploadingBulkImport ? "上传中..." : "上传文件"}
                </Button>
              </div>
              <div className="flex gap-3 text-xs text-slate-600">
                <span>成功 {bulkImportResult?.created_count ?? 0}</span>
                <span>失败 {bulkImportResult?.errors.length ?? 0}</span>
                <span>跳过 {bulkImportResult?.skipped_count ?? 0}</span>
              </div>
            </div>
            {bulkImportError ? (
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700">{bulkImportError}</div>
            ) : null}
            <div className="grid gap-4 xl:grid-cols-2">
              <section className="space-y-2">
                <div className="font-medium text-slate-800">上传成功</div>
                <div className="max-h-80 overflow-auto rounded-md border border-slate-200">
                  <Table>
                    <THead>
                      <TR>
                        <TH>序号</TH>
                        <TH>提单号</TH>
                        <TH>操作</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {(bulkImportResult?.created_waybills || []).map((item, index) => (
                        <TR key={item.id}>
                          <TD>{index + 1}</TD>
                          <TD className="font-medium">{item.waybill_no}</TD>
                          <TD>
                            <Link
                              href={`/waybills/${item.id}`}
                              className="text-purple-700 underline-offset-2 hover:text-purple-900 hover:underline"
                              onClick={() => setBulkImportOpen(false)}
                            >
                              打开
                            </Link>
                          </TD>
                        </TR>
                      ))}
                      {!bulkImportResult?.created_waybills.length ? (
                        <TR>
                          <TD colSpan={3} className="py-6 text-center text-slate-500">
                            暂无成功数据
                          </TD>
                        </TR>
                      ) : null}
                    </TBody>
                  </Table>
                </div>
              </section>
              <section className="space-y-2">
                <div className="font-medium text-red-700">上传失败</div>
                <div className="max-h-80 overflow-auto rounded-md border border-red-200">
                  <Table>
                    <THead>
                      <TR>
                        <TH>行号</TH>
                        <TH>提单号</TH>
                        <TH>原因</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {(bulkImportResult?.errors || []).map((item) => (
                        <TR key={`${item.row_number}-${item.waybill_no || ""}`}>
                          <TD>{item.row_number}</TD>
                          <TD>{item.waybill_no || ""}</TD>
                          <TD>{item.message}</TD>
                        </TR>
                      ))}
                      {!bulkImportResult?.errors.length ? (
                        <TR>
                          <TD colSpan={3} className="py-6 text-center text-slate-500">
                            暂无失败数据
                          </TD>
                        </TR>
                      ) : null}
                    </TBody>
                  </Table>
                </div>
              </section>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
