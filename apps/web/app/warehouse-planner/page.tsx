"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type DragEvent } from "react";
import { Download, EyeOff, GripVertical, ListPlus, PanelRightClose, PanelRightOpen, RefreshCw, Save, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { cn, compact, formatOutboundDate } from "@/lib/utils";
import type {
  CarrierAgent,
  User,
  WarehousePlannerCandidate,
  WarehousePlannerCandidates,
  WarehousePlannerCommitResult,
  WarehousePlannerRow,
  WarehousePlannerRowResult,
  WarehousePlannerValidateResult,
  WarehouseReceipt
} from "@/lib/types";

type RightPanelMode = "candidates" | "receipts";
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
  | "planned_route_text";

const CLEAR_VALUE = "__clear__";
const CANDIDATE_DRAG_TYPE = "application/x-warehouse-planner-candidates";
const RECEIPT_DRAG_TYPE = "application/x-warehouse-planner-receipts";

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
  { key: "planned_route_text", label: "航程", kind: "text" }
];

function rowKey(row: Pick<WarehousePlannerRow, "source_type" | "source_id">) {
  return `${row.source_type}:${row.source_id}`;
}

function candidateToRow(item: WarehousePlannerCandidate): WarehousePlannerRow {
  return {
    source_type: item.source_type,
    source_id: item.source_id,
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
    source_updated_at: item.source_updated_at
  };
}

function formatDecimal(value?: string | number | null) {
  if (value === null || value === undefined || value === "") return "-";
  const num = Number(value);
  if (!Number.isFinite(num)) return compact(value);
  return num.toFixed(3).replace(/\.?0+$/, "");
}

function sourceLabel(value: WarehousePlannerRow["source_type"]) {
  return value === "waybill" ? "正式提单" : "预排仓";
}

function channelTags(tags?: string[] | null) {
  return (tags || []).filter(Boolean);
}

export default function WarehousePlannerPage() {
  const saveTimerRef = useRef<number | null>(null);
  const [rows, setRows] = useState<WarehousePlannerRow[]>([]);
  const [loadedDraft, setLoadedDraft] = useState(false);
  const [selectedRows, setSelectedRows] = useState<Set<string>>(new Set());
  const [candidates, setCandidates] = useState<WarehousePlannerCandidates | null>(null);
  const [selectedCandidates, setSelectedCandidates] = useState<Set<string>>(new Set());
  const [selectedReceipts, setSelectedReceipts] = useState<Set<number>>(new Set());
  const [rightPanelMode, setRightPanelMode] = useState<RightPanelMode>("candidates");
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
  const [rowErrors, setRowErrors] = useState<Record<string, WarehousePlannerRowResult>>({});

  const allCandidates = useMemo(
    () => [...(candidates?.waybills || []), ...(candidates?.prebookings || [])],
    [candidates]
  );
  const rowKeySet = useMemo(() => new Set(rows.map(rowKey)), [rows]);
  const selectedRowKeys = useMemo(() => [...selectedRows], [selectedRows]);
  const selectedRowCount = selectedRows.size;
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
    setRows(draft.rows || []);
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

  function updateRow(key: string, changes: Partial<WarehousePlannerRow>) {
    setRows((prev) => prev.map((row) => (rowKey(row) === key ? { ...row, ...changes } : row)));
    setRowErrors((prev) => {
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }

  function removeRow(key: string) {
    setRows((prev) => prev.filter((row) => rowKey(row) !== key));
    setSelectedRows((prev) => {
      const next = new Set(prev);
      next.delete(key);
      return next;
    });
  }

  function addCandidates(items: WarehousePlannerCandidate[]) {
    setRows((prev) => {
      const existing = new Set(prev.map(rowKey));
      const additions = items.map(candidateToRow).filter((row) => !existing.has(rowKey(row)));
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

  function onDropIntoRows(event: DragEvent<HTMLDivElement>) {
    const raw = event.dataTransfer.getData(CANDIDATE_DRAG_TYPE);
    if (!raw) return;
    event.preventDefault();
    const keys = JSON.parse(raw) as string[];
    addCandidates(allCandidates.filter((item) => keys.includes(rowKey(item))));
  }

  function onDropReceipts(event: DragEvent<HTMLDivElement>, targetKey?: string) {
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
    setRows((prev) => prev.map((row) => (keys.includes(rowKey(row)) ? { ...row, [batchField]: value } : row)));
    setBatchOpen(false);
    setBatchValue("");
  }

  async function validateBeforeCommit() {
    setSaving(true);
    setMessage("");
    setCommitResult(null);
    try {
      await apiClient.put("/warehouse-planner/draft", { rows });
      const result = await apiClient.post<WarehousePlannerValidateResult>("/warehouse-planner/validate", { rows });
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
    setSaving(true);
    setMessage("");
    try {
      const result = await apiClient.post<WarehousePlannerCommitResult>("/warehouse-planner/commit", { rows, mode });
      setCommitResult(result);
      setRows(result.remaining_rows || []);
      setSelectedRows(new Set());
      setRowErrors(Object.fromEntries(result.results.filter((item) => item.status === "failed").map((item) => [`${item.source_type}:${item.source_id}`, item])));
      await loadAll();
      setMessage(`录入完成：成功 ${result.success_count} 条，失败 ${result.failed_count} 条。`);
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

  function renderSelectValue(value?: number | null) {
    return value === null || value === undefined ? CLEAR_VALUE : String(value);
  }

  return (
    <>
      <PageHeader
        title="排仓编辑器"
        description="把正式提单和预排仓放在同一个工作台中安排出仓与入仓号。"
        action={
          <div className="flex flex-wrap gap-2">
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
      <div className={cn("grid min-w-0 gap-4", rightPanelVisible ? "xl:grid-cols-[minmax(0,1fr)_360px]" : "xl:grid-cols-1")}>
        <Panel
          className="min-w-0 overflow-hidden"
          title="排仓编辑区"
          action={
            <div className="flex flex-wrap items-center justify-end gap-2">
              <span className="text-sm text-slate-500">已选 {selectedRowCount} 条</span>
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
          <div
            className="min-h-64 min-w-0 rounded-md border border-dashed border-slate-300 bg-slate-50/50 p-2"
            onDragOver={(event) => event.preventDefault()}
            onDrop={onDropIntoRows}
          >
            {rows.length ? (
              <div className="w-full max-w-full overflow-x-auto rounded-md border border-slate-200 bg-white">
                <Table className="min-w-[1900px]">
                  <THead>
                    <TR>
                      <TH className="w-10"><input type="checkbox" checked={rows.length > 0 && selectedRows.size === rows.length} onChange={(event) => setSelectedRows(event.target.checked ? new Set(rows.map(rowKey)) : new Set())} /></TH>
                      <TH>来源</TH>
                      <TH>航代</TH>
                      <TH>计划航班</TH>
                      <TH>提单号</TH>
                      <TH>出仓日期</TH>
                      <TH>入仓号/入仓文件</TH>
                      <TH>指定清关人员</TH>
                      <TH>订舱方数/板总方数</TH>
                      <TH>约定航班起飞日期</TH>
                      <TH>订舱重量</TH>
                      <TH>密度</TH>
                      <TH>报价</TH>
                      <TH>含T</TH>
                      <TH>始发港</TH>
                      <TH>目的港</TH>
                      <TH>航程</TH>
                      <TH>操作</TH>
                    </TR>
                  </THead>
                  <TBody>
                    {rows.map((row) => {
                      const key = rowKey(row);
                      const error = rowErrors[key];
                      return (
                        <TR
                          key={key}
                          className={cn(error && "bg-red-50")}
                          onDragOver={(event) => event.preventDefault()}
                          onDrop={(event) => onDropReceipts(event, key)}
                        >
                          <TD><input type="checkbox" checked={selectedRows.has(key)} onChange={(event) => setSelectedRows((prev) => {
                            const next = new Set(prev);
                            if (event.target.checked) next.add(key);
                            else next.delete(key);
                            return next;
                          })} /></TD>
                          <TD>
                            <div className="font-medium text-slate-900">{sourceLabel(row.source_type)}</div>
                            {error ? <div className="mt-1 text-xs text-red-600">{error.errors.map((item) => item.message).join("；")}</div> : null}
                          </TD>
                          <TD>
                            <Select value={renderSelectValue(row.carrier_agent_id)} onValueChange={(value) => updateRow(key, { carrier_agent_id: value === CLEAR_VALUE ? null : Number(value) })}>
                              <SelectTrigger className="h-9 min-w-36"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value={CLEAR_VALUE}>未选择</SelectItem>
                                {agents.map((agent) => <SelectItem key={agent.id} value={String(agent.id)}>{agent.agent_name}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </TD>
                          <TD><Input className="h-9 min-w-28" value={row.planned_flight_no || ""} onChange={(event) => updateRow(key, { planned_flight_no: event.target.value })} /></TD>
                          <TD><Input className="h-9 min-w-36" value={row.waybill_no || ""} onChange={(event) => updateRow(key, { waybill_no: event.target.value })} /></TD>
                          <TD><Input className="h-9 min-w-36" type="date" value={row.outbound_date || ""} onChange={(event) => updateRow(key, { outbound_date: event.target.value || null })} /></TD>
                          <TD>
                            <div className="flex min-w-56 flex-wrap gap-1">
                              {(row.receipt_ids || []).map((receiptId) => {
                                const receipt = receiptMap.get(receiptId);
                                return (
                                  <Badge key={receiptId} variant="default" className="gap-1">
                                    {receipt?.warehouse_no || `#${receiptId}`}
                                    <button type="button" onClick={() => updateRow(key, { receipt_ids: row.receipt_ids.filter((id) => id !== receiptId) })}>×</button>
                                  </Badge>
                                );
                              })}
                              {!row.receipt_ids?.length ? <span className="text-xs text-slate-400">拖入入仓号</span> : null}
                            </div>
                          </TD>
                          <TD>
                            <Select value={renderSelectValue(row.customs_staff_id)} onValueChange={(value) => updateRow(key, { customs_staff_id: value === CLEAR_VALUE ? null : Number(value) })}>
                              <SelectTrigger className="h-9 min-w-36"><SelectValue /></SelectTrigger>
                              <SelectContent>
                                <SelectItem value={CLEAR_VALUE}>未指定</SelectItem>
                                {customsStaff.map((item) => <SelectItem key={item.id} value={String(item.id)}>{item.display_name || item.username}</SelectItem>)}
                              </SelectContent>
                            </Select>
                          </TD>
                          <TD><Input className="h-9 min-w-28" type="number" step="0.001" value={row.booked_volume ?? ""} onChange={(event) => updateRow(key, { booked_volume: event.target.value })} /></TD>
                          <TD><Input className="h-9 min-w-36" type="date" value={row.planned_flight_date || ""} onChange={(event) => updateRow(key, { planned_flight_date: event.target.value || null })} /></TD>
                          <TD><Input className="h-9 min-w-28" type="number" step="0.001" value={row.booked_weight ?? ""} onChange={(event) => updateRow(key, { booked_weight: event.target.value })} /></TD>
                          <TD><Input className="h-9 min-w-24" type="number" step="0.001" value={row.density ?? ""} onChange={(event) => updateRow(key, { density: event.target.value })} /></TD>
                          <TD><Input className="h-9 min-w-24" value={row.quotation || ""} onChange={(event) => updateRow(key, { quotation: event.target.value })} /></TD>
                          <TD className="text-center"><input type="checkbox" checked={Boolean(row.include_tc)} onChange={(event) => updateRow(key, { include_tc: event.target.checked })} /></TD>
                          <TD><Input className="h-9 min-w-24" value={row.departure_port || ""} onChange={(event) => updateRow(key, { departure_port: event.target.value })} /></TD>
                          <TD><Input className="h-9 min-w-24" value={row.destination_port || ""} onChange={(event) => updateRow(key, { destination_port: event.target.value })} /></TD>
                          <TD><Input className="h-9 min-w-40" value={row.planned_route_text || ""} onChange={(event) => updateRow(key, { planned_route_text: event.target.value })} /></TD>
                          <TD><Button variant="danger" size="sm" onClick={() => removeRow(key)}><Trash2 className="h-4 w-4" /></Button></TD>
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

        {rightPanelVisible ? (
          <div className="sticky top-20 h-[calc(100vh-96px)] space-y-3 overflow-hidden">
            <Panel
              title="排仓侧栏"
              action={
                <Button variant="secondary" size="icon" onClick={() => setRightPanelVisible(false)}>
                  <EyeOff className="h-4 w-4" />
                </Button>
              }
            >
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
                <div className="max-h-[calc(100vh-220px)] space-y-2 overflow-y-auto pr-1">
                  {(candidates?.unbound_receipts || []).map((receipt) => {
                    const selected = selectedReceipts.has(receipt.id);
                    return (
                      <div
                        key={receipt.id}
                        draggable
                        onDragStart={(event) => onReceiptDragStart(event, receipt)}
                        className={cn("rounded-md border bg-white p-3 text-sm", selected ? "border-purple-300 bg-purple-50" : "border-slate-200")}
                      >
                        <label className="flex items-start gap-2">
                          <input
                            type="checkbox"
                            checked={selected}
                            onChange={(event) => setSelectedReceipts((prev) => {
                              const next = new Set(prev);
                              if (event.target.checked) next.add(receipt.id);
                              else next.delete(receipt.id);
                              return next;
                            })}
                          />
                          <span className="min-w-0 flex-1">
                            <span className="flex items-center gap-2 font-semibold text-slate-900">
                              <GripVertical className="h-4 w-4 text-slate-400" />
                              {receipt.source_file_name || receipt.warehouse_no}
                            </span>
                            <span className="mt-1 flex flex-wrap gap-1">
                              {channelTags(receipt.channel_tags).map((tag) => <Badge key={tag} variant="amber">{tag}</Badge>)}
                            </span>
                            <span className="mt-1 grid gap-0.5 text-xs text-slate-500">
                              <span>入仓号：{receipt.warehouse_no}</span>
                              <span>箱数：{receipt.box_count ?? 0} / 件数：{compact(receipt.total_quantity)}</span>
                              <span>重量：{formatDecimal(receipt.total_weight)} / 方数：{formatDecimal(receipt.total_volume)}</span>
                            </span>
                          </span>
                        </label>
                      </div>
                    );
                  })}
                  {!candidates?.unbound_receipts.length ? <EmptyState title="暂无未绑定入仓号" description="未绑定箱号模块上传后会显示在这里。" /> : null}
                </div>
              )}
            </Panel>
          </div>
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
