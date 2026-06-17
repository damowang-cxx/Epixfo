"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Ban, Download, Pencil, Play, Trash2, Upload, UserCheck } from "lucide-react";
import { AlertLevelBadge, LifecycleBadge } from "@/components/ui/status-badge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { CargoBoxesTable } from "@/components/waybills/cargo-boxes-table";
import { WaybillForm } from "@/components/waybills/waybill-form";
import { WarehouseFileUploadButton } from "@/components/waybills/warehouse-file-upload-button";
import { useAuth } from "@/components/layout/auth-provider";
import { apiClient } from "@/lib/client-api";
import { compact, computeRatio, formatDateTime, formatOutboundDate } from "@/lib/utils";
import { carrierAdapterTypeLabels, lifecycleLabels } from "@/lib/constants";
import { formatPlannedFlightInfo } from "@/lib/planned-flight";
import { formatWarehouseUploadMessage } from "@/lib/warehouse-upload";
import type {
  Alert,
  AssemblyEvent,
  CargoBox,
  LifecycleStatus,
  OfficialFlightSegment,
  OfficialInfo,
  QuerySnapshot,
  StatusEvent,
  User,
  Waybill,
  WaybillAirlineFile
} from "@/lib/types";

const statusOptions: LifecycleStatus[] = [
  "created",
  "waiting_monitor",
  "monitoring",
  "warehouse_received",
  "loaded",
  "departed",
  "arrived",
  "pickup_notified",
  "picked_up",
  "voided"
];

const customsUploadAvailableStatuses: LifecycleStatus[] = [
  "warehouse_received",
  "loaded",
  "departed",
  "arrived",
  "pickup_notified",
  "picked_up"
];

function FieldGrid({ items }: { items: Array<[string, unknown]> }) {
  return (
    <div className="grid gap-3 text-sm md:grid-cols-4">
      {items.map(([label, value]) => (
        <div key={label} className="rounded-md border border-slate-100 p-3">
          <div className="text-xs text-slate-500">{label}</div>
          <div className="mt-1 font-medium text-slate-800">{compact(value)}</div>
        </div>
      ))}
    </div>
  );
}

function userDisplayName(user?: Waybill["customs_staff"]) {
  if (!user) return "";
  return user.display_name || user.username;
}

function channelTags(tags?: string[] | null) {
  return (tags || []).filter(Boolean);
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

export default function WaybillDetailPage() {
  const params = useParams<{ id: string }>();
  const router = useRouter();
  const id = Array.isArray(params.id) ? params.id[0] : params.id;
  const airlineFileInputRef = useRef<HTMLInputElement | null>(null);
  const { hasRole } = useAuth();
  const isAdmin = hasRole("admin");
  const isRouteStaff = hasRole("route_staff");
  const isCustomsStaff = hasRole("customs_staff");
  const canEditBoxes = isAdmin || isRouteStaff;
  const canDeleteWaybill = canEditBoxes;
  const canConfirmCustomsUpload = isAdmin || isRouteStaff || isCustomsStaff;
  const canRevokeCustomsUpload = isAdmin || isRouteStaff;
  const [waybill, setWaybill] = useState<Waybill | null>(null);
  const [officialInfo, setOfficialInfo] = useState<OfficialInfo | null>(null);
  const [segments, setSegments] = useState<OfficialFlightSegment[]>([]);
  const [events, setEvents] = useState<StatusEvent[]>([]);
  const [assemblies, setAssemblies] = useState<AssemblyEvent[]>([]);
  const [boxes, setBoxes] = useState<CargoBox[]>([]);
  const [snapshots, setSnapshots] = useState<QuerySnapshot[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [users, setUsers] = useState<User[]>([]);
  const [manualStatus, setManualStatus] = useState<LifecycleStatus>("created");
  const [message, setMessage] = useState("");
  const [customsStaffSaving, setCustomsStaffSaving] = useState(false);
  const [airlineFileUploading, setAirlineFileUploading] = useState(false);
  const [airlineFileDeleting, setAirlineFileDeleting] = useState(false);
  const [airlineFileDownloading, setAirlineFileDownloading] = useState(false);

  const load = useCallback(() => {
    if (!id) return;
    apiClient.get<Waybill>(`/waybills/${id}`).then((data) => {
      setWaybill(data);
      setManualStatus(data.lifecycle_status);
    });
    apiClient.get<OfficialInfo | null>(`/waybills/${id}/official-info`).then(setOfficialInfo).catch(() => setOfficialInfo(null));
    apiClient.get<OfficialFlightSegment[]>(`/waybills/${id}/official-flight-segments`).then(setSegments);
    apiClient.get<StatusEvent[]>(`/waybills/${id}/status-events`).then(setEvents);
    apiClient.get<AssemblyEvent[]>(`/waybills/${id}/assembly-events`).then(setAssemblies);
    apiClient.get<CargoBox[]>(`/waybills/${id}/boxes`).then(setBoxes);
    apiClient.get<QuerySnapshot[]>(`/waybills/${id}/query-snapshots`).then(setSnapshots);
    apiClient.get<Alert[]>(`/waybills/${id}/alerts`).then(setAlerts);
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!canEditBoxes) return;
    apiClient.get<User[]>("/users").then(setUsers).catch(() => setUsers([]));
  }, [canEditBoxes]);

  const boxGroups = useMemo(() => {
    const groups = new Map<
      string,
      {
        key: string;
        receiptId?: number | null;
        warehouseNo?: string | null;
        totalQuantity?: number | null;
        totalWeight?: string | number | null;
        totalVolume?: string | number | null;
        weightVolumeRatio?: string | number | null;
        uploadedAt?: string | null;
        channelTags: string[];
        boxes: CargoBox[];
      }
    >();
    for (const box of boxes) {
      const receipt = box.warehouse_receipt;
      const key = receipt?.id ? String(receipt.id) : "none";
      if (!groups.has(key)) {
        groups.set(key, {
          key,
          receiptId: receipt?.id,
          warehouseNo: receipt?.warehouse_no || waybill?.warehouse_no,
          totalQuantity: receipt?.total_quantity,
          totalWeight: receipt?.total_weight,
          totalVolume: receipt?.total_volume,
          weightVolumeRatio: receipt?.weight_volume_ratio,
          uploadedAt: receipt?.uploaded_at,
          channelTags: channelTags(receipt?.channel_tags),
          boxes: []
        });
      }
      groups.get(key)?.boxes.push(box);
    }
    return Array.from(groups.values());
  }, [boxes, waybill?.warehouse_no]);

  async function triggerQuery() {
    if (!id) return;
    await apiClient.post<QuerySnapshot>(`/waybills/${id}/trigger-query`);
    setMessage("已触发查询。本期 CZ 适配器会返回未配置真实查询的占位失败结果。");
    load();
  }

  async function updateManualStatus() {
    if (!id || !manualStatus) return;
    await apiClient.post<Waybill>(`/waybills/${id}/manual-status`, { lifecycle_status: manualStatus });
    setMessage("生命周期已手动更新。");
    load();
  }

  async function voidWaybill() {
    if (!id) return;
    await apiClient.post<Waybill>(`/waybills/${id}/void`);
    setMessage("提单已作废。");
    load();
  }

  async function deleteWaybill() {
    if (!id || !waybill) return;
    if (!window.confirm(`确认删除提单 ${waybill.waybill_no} 吗？删除后不可恢复，关联的入仓箱号会转为未绑定。`)) return;
    try {
      await apiClient.delete<void>(`/waybills/${id}`);
      router.push("/waybills");
      router.refresh();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除提单失败。");
    }
  }

  if (!waybill) return <div className="text-sm text-slate-500">正在加载提单...</div>;

  const visibleCustomsUsers = users.filter(
    (user) =>
      user.roles.some((role) => role.code === "customs_staff") &&
      (user.is_active || waybill.customs_staff_id === user.id)
  );

  async function exportCustomsData() {
    if (!id || !waybill) return;
    try {
      const { blob, filename } = await apiClient.download(`/waybills/${id}/customs-export`);
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = filename || `清关数据_${waybill.waybill_no}.xlsx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "导出清关数据失败。");
    }
  }

  async function confirmCustomsUpload() {
    if (!id) return;
    try {
      const updated = await apiClient.post<Waybill>(`/waybills/${id}/customs-upload-confirm`);
      setWaybill(updated);
      setMessage("已记录清关资料上传确认。");
      load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认清关资料上传失败。");
    }
  }

  async function revokeCustomsUpload() {
    if (!id || !window.confirm("确认撤销清关资料上传记录吗？")) return;
    try {
      const updated = await apiClient.delete<Waybill>(`/waybills/${id}/customs-upload-confirm`);
      setWaybill(updated);
      setMessage("已撤销清关资料上传确认。");
      load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "撤销清关资料上传确认失败。");
    }
  }

  async function updateCustomsStaff(value: string) {
    if (!id) return;
    setCustomsStaffSaving(true);
    setMessage("");
    try {
      const customsStaffId = value === "__none__" ? null : Number(value);
      const updated = await apiClient.patch<Waybill>(`/waybills/${id}`, { customs_staff_id: customsStaffId });
      setWaybill(updated);
      setMessage(customsStaffId ? "指定清关人员已更新。" : "已清空指定清关人员。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "更新指定清关人员失败。");
    } finally {
      setCustomsStaffSaving(false);
    }
  }

  async function uploadAirlineFile(files: FileList | null) {
    const file = files?.[0];
    if (!id || !file || !canEditBoxes) return;
    const formData = new FormData();
    formData.append("file", file);
    setAirlineFileUploading(true);
    setMessage("");
    try {
      const uploaded = await apiClient.postForm<WaybillAirlineFile>(`/waybills/${id}/airline-file`, formData);
      setWaybill((current) => (current ? { ...current, airline_file: uploaded } : current));
      setMessage("航司对接文件已上传。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "航司对接文件上传失败。");
    } finally {
      setAirlineFileUploading(false);
      if (airlineFileInputRef.current) airlineFileInputRef.current.value = "";
    }
  }

  async function downloadAirlineFile() {
    if (!id || !waybill?.airline_file) return;
    setAirlineFileDownloading(true);
    setMessage("");
    try {
      const { blob, filename } = await apiClient.download(`/waybills/${id}/airline-file/download`);
      downloadBlob(blob, filename || waybill.airline_file.original_file_name || `airline-file-${waybill.waybill_no}.pdf`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "航司对接文件下载失败。");
    } finally {
      setAirlineFileDownloading(false);
    }
  }

  async function deleteAirlineFile() {
    if (!id || !waybill?.airline_file || !canEditBoxes) return;
    if (!window.confirm("确认删除当前航司对接文件？")) return;
    setAirlineFileDeleting(true);
    setMessage("");
    try {
      await apiClient.delete<void>(`/waybills/${id}/airline-file`);
      setWaybill((current) => (current ? { ...current, airline_file: null } : current));
      setMessage("航司对接文件已删除。");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "航司对接文件删除失败。");
    } finally {
      setAirlineFileDeleting(false);
    }
  }

  return (
    <>
      <PageHeader
        title={`提单 ${waybill.waybill_no}`}
        description="查看生命周期、官方事件、查询快照和异常"
        action={
          <div className="flex flex-wrap gap-2">
            <Button asChild variant="secondary">
              <Link href="/waybills">
                <Pencil className="h-4 w-4" />
                返回列表
              </Link>
            </Button>
            <Button asChild variant="secondary">
              <Link href={`/waybills/${id}/edit`}>
                <Pencil className="h-4 w-4" />
                编辑
              </Link>
            </Button>
            <Button onClick={triggerQuery}>
              <Play className="h-4 w-4" />
              触发查询
            </Button>
            <Button variant="secondary" onClick={exportCustomsData}>
              <Download className="h-4 w-4" />
              清关数据导出
            </Button>
            {canConfirmCustomsUpload &&
            customsUploadAvailableStatuses.includes(waybill.lifecycle_status) &&
            !waybill.customs_data_uploaded_at ? (
              <Button variant="secondary" onClick={confirmCustomsUpload}>
                已上传清关资料
              </Button>
            ) : null}
            {canRevokeCustomsUpload && waybill.customs_data_uploaded_at ? (
              <Button variant="ghost" onClick={revokeCustomsUpload}>
                撤销清关确认
              </Button>
            ) : null}
            {isAdmin ? (
              <Button variant="danger" onClick={voidWaybill}>
                <Ban className="h-4 w-4" />
                作废
              </Button>
            ) : null}
            {canDeleteWaybill ? (
              <Button variant="danger" onClick={deleteWaybill}>
                <Trash2 className="h-4 w-4" />
                删除
              </Button>
            ) : null}
          </div>
        }
      />
      {message ? <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div> : null}
      <div className="mb-4 grid gap-4 md:grid-cols-3">
        <Panel><div className="text-xs text-slate-500">生命周期</div><div className="mt-2"><LifecycleBadge value={waybill.lifecycle_status} /></div></Panel>
        <Panel><div className="text-xs text-slate-500">异常等级</div><div className="mt-2"><AlertLevelBadge value={waybill.alert_level} /></div></Panel>
        <Panel><div className="text-xs text-slate-500">航司</div><div className="mt-2 text-sm font-semibold">{compact(waybill.carrier_code)}</div></Panel>
      </div>
      <Tabs defaultValue="base">
        <TabsList>
          <TabsTrigger value="base">基础信息</TabsTrigger>
          <TabsTrigger value="official">官方信息</TabsTrigger>
          <TabsTrigger value="events">状态事件</TabsTrigger>
          <TabsTrigger value="snapshots">查询快照</TabsTrigger>
          <TabsTrigger value="alerts">异常</TabsTrigger>
          <TabsTrigger value="edit">编辑</TabsTrigger>
        </TabsList>
        <TabsContent value="base">
          <Panel
            title="提单信息"
            action={
              <div className="flex flex-wrap items-center justify-end gap-2 py-1">
                <input
                  ref={airlineFileInputRef}
                  type="file"
                  accept="application/pdf,.pdf"
                  className="hidden"
                  onChange={(event) => void uploadAirlineFile(event.target.files)}
                />
                {waybill.airline_file ? (
                  <Button type="button" variant="secondary" size="sm" disabled={airlineFileDownloading} onClick={() => void downloadAirlineFile()}>
                    <Download className="h-4 w-4" />
                    {airlineFileDownloading ? "下载中..." : "下载航司对接文件"}
                  </Button>
                ) : null}
                {canEditBoxes ? (
                  <Button type="button" variant="secondary" size="sm" disabled={airlineFileUploading} onClick={() => airlineFileInputRef.current?.click()}>
                    <Upload className="h-4 w-4" />
                    {airlineFileUploading ? "上传中..." : waybill.airline_file ? "替换航司对接文件" : "上传航司对接文件"}
                  </Button>
                ) : null}
                {canEditBoxes && waybill.airline_file ? (
                  <Button type="button" variant="ghost" size="sm" disabled={airlineFileDeleting} onClick={() => void deleteAirlineFile()}>
                    <Trash2 className="h-4 w-4 text-red-600" />
                    {airlineFileDeleting ? "删除中..." : "删除"}
                  </Button>
                ) : null}
              </div>
            }
          >
            <FieldGrid
              items={[
                ["始发港", waybill.departure_port],
                ["目的港", waybill.destination_port],
                ["航代", waybill.agent],
                ["入仓号", waybill.warehouse_no],
                [
                  "航司对接文件",
                  waybill.airline_file
                    ? `${waybill.airline_file.original_file_name}（${formatDateTime(waybill.airline_file.uploaded_at)}）`
                    : "未上传"
                ],
                ["出仓日期", formatOutboundDate(waybill.outbound_date)],
                ["收货人", waybill.consignee],
                ["指定清关人员", userDisplayName(waybill.customs_staff)],
                [
                  "清关资料",
                  waybill.customs_data_uploaded_at
                    ? `已上传 ${formatDateTime(waybill.customs_data_uploaded_at)}${
                        userDisplayName(waybill.customs_data_uploaded_by_user)
                          ? `（${userDisplayName(waybill.customs_data_uploaded_by_user)}）`
                          : ""
                      }`
                    : "待上传"
                ],
                ["计划航班", formatPlannedFlightInfo(waybill.plan)],
                ["计划日期", waybill.plan?.planned_flight_date],
                ["计划航程", waybill.plan?.planned_route_text],
                ["订舱重量", waybill.booked_weight],
                ["订舱方数", waybill.booked_volume],
                ["密度", waybill.density],
                ["报价", waybill.quotation],
                ["航空费", waybill.air_freight_cost],
                ["其他费用", waybill.other_charge],
                ["付款日期", waybill.payment_date],
                ["做数据收费", waybill.data_charge],
                ["客服备注", waybill.customer_remark],
                ["内部备注", waybill.internal_remark]
              ]}
            />
            {isAdmin ? (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Select value={manualStatus} onValueChange={(value) => setManualStatus(value as LifecycleStatus)}>
                  <SelectTrigger className="w-56"><SelectValue /></SelectTrigger>
                  <SelectContent>
                    {statusOptions.map((status) => (
                      <SelectItem key={status} value={status}>{lifecycleLabels[status]}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button variant="secondary" onClick={updateManualStatus}>手动更新状态</Button>
              </div>
            ) : null}
          </Panel>
          <Panel
            title="入仓货物明细"
            className="mt-4"
            action={
              canEditBoxes ? (
                <div className="flex flex-wrap items-center justify-end gap-2 py-1">
                  <Select
                    value={waybill.customs_staff_id ? String(waybill.customs_staff_id) : undefined}
                    onValueChange={(value) => void updateCustomsStaff(value)}
                    disabled={customsStaffSaving}
                  >
                    <SelectTrigger className="w-52 border-purple-200 bg-purple-50 text-purple-800">
                      <UserCheck className="mr-2 h-4 w-4 shrink-0" />
                      <SelectValue placeholder="指定清关人员" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="__none__">不指定清关人员</SelectItem>
                      {visibleCustomsUsers.map((user) => (
                        <SelectItem key={user.id} value={String(user.id)}>
                          {user.display_name || user.username}
                          {!user.is_active ? "（已停用）" : ""}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <WarehouseFileUploadButton
                    waybillId={waybill.id}
                    label={waybill.warehouse_no ? "上传新入仓文件" : "上传入仓文件"}
                    onUploaded={(result) => {
                      setMessage(formatWarehouseUploadMessage(result));
                      load();
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
                        <span>入仓号：{group.warehouseNo || "未归属入仓号"}</span>
                        {group.channelTags.map((tag) => (
                          <Badge key={tag} variant="amber">
                            {tag}
                          </Badge>
                        ))}
                      </div>
                      <div className="flex flex-wrap gap-3 text-xs text-slate-600">
                        <span>箱数 {group.boxes.length}</span>
                        <span>总数量 {compact(group.totalQuantity)}</span>
                        <span>总重量 {compact(group.totalWeight)}</span>
                        <span>总方数 {compact(group.totalVolume)}</span>
                        <span>重量/方 {compact(group.weightVolumeRatio)}</span>
                        <span>上传 {formatDateTime(group.uploadedAt)}</span>
                      </div>
                    </div>
                    <div className="p-3">
                      <CargoBoxesTable
                        boxes={group.boxes}
                        waybillId={waybill.id}
                        warehouseNo={group.warehouseNo}
                        warehouseReceiptId={group.receiptId}
                        allowCreate={group.warehouseNo === waybill.warehouse_no}
                        readonly={!canEditBoxes}
                        onBoxUpdated={(updated) => {
                          setBoxes((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
                          setMessage("外箱条码已更新。");
                        }}
                        onBoxDeleted={(boxId) => {
                          setBoxes((prev) => prev.filter((item) => item.id !== boxId));
                        }}
                        onChanged={() => {
                          setMessage("箱号绑定已更新。");
                          load();
                        }}
                        onError={setMessage}
                        onMessage={setMessage}
                      />
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <CargoBoxesTable
                boxes={[]}
                waybillId={waybill.id}
                warehouseNo={waybill.warehouse_no}
                readonly={!canEditBoxes}
                onChanged={() => {
                  setMessage("箱号绑定已更新。");
                  load();
                }}
                onError={setMessage}
                onMessage={setMessage}
              />
            )}
          </Panel>
        </TabsContent>
        <TabsContent value="official">
          <Panel title="官方提单信息">
            <FieldGrid
              items={[
                ["官方提单号", officialInfo?.official_waybill_no],
                ["承运人", officialInfo?.carrier_text],
                ["航程", officialInfo?.route_text],
                ["货物品名", officialInfo?.goods_name],
                ["总件数", officialInfo?.total_pieces],
                ["总重量", officialInfo?.total_weight],
                ["总体积", officialInfo?.total_volume],
                ["比例", computeRatio(officialInfo?.total_weight, officialInfo?.total_volume)]
              ]}
            />
          </Panel>
          <Panel title="官方订舱航段" className="mt-4">
            {segments.length ? (
              <Table>
                <THead>
                  <TR>
                    <TH rowSpan={2}>序号</TH>
                    <TH rowSpan={2}>订舱号</TH>
                    <TH rowSpan={2}>航班</TH>
                    <TH rowSpan={2}>日期</TH>
                    <TH rowSpan={2}>出发</TH>
                    <TH rowSpan={2}>到达</TH>
                    <TH colSpan={2} className="border-l border-slate-200 text-center">起飞时间</TH>
                    <TH colSpan={2} className="border-l border-slate-200 text-center">到达时间</TH>
                    <TH rowSpan={2} className="border-l border-slate-200">件/重/体</TH>
                  </TR>
                  <TR>
                    <TH className="border-l border-slate-200">计划</TH>
                    <TH>实际</TH>
                    <TH className="border-l border-slate-200">计划</TH>
                    <TH>实际</TH>
                  </TR>
                </THead>
                <TBody>
                  {segments.map((item) => (
                    <TR key={item.id}>
                      <TD>{item.segment_order}</TD>
                      <TD>{compact(item.booking_no)}</TD>
                      <TD>{compact(item.flight_no)}</TD>
                      <TD>{compact(item.flight_date)}</TD>
                      <TD>{compact(item.departure_airport)}</TD>
                      <TD>{compact(item.arrival_airport)}</TD>
                      <TD className="border-l border-slate-100">{formatDateTime(item.departure_planned_time)}</TD>
                      <TD>{formatDateTime(item.departure_actual_time)}</TD>
                      <TD className="border-l border-slate-100">{formatDateTime(item.arrival_planned_time)}</TD>
                      <TD>{formatDateTime(item.arrival_actual_time)}</TD>
                      <TD className="border-l border-slate-100">{compact(item.pieces)} / {compact(item.weight)} / {compact(item.volume)}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : <EmptyState title="暂无官方航段" description="真实航司查询接入后会写入订舱航段。" />}
          </Panel>
        </TabsContent>
        <TabsContent value="events">
          <Panel title="货物状态事件">
            {events.length ? (
              <Table><THead><TR><TH>时间</TH><TH>城市</TH><TH>航班</TH><TH>状态</TH><TH>类型</TH><TH>件/重</TH></TR></THead>
                <TBody>{events.map((item) => <TR key={item.id}><TD>{formatDateTime(item.event_time_local) || item.event_time_text}</TD><TD>{compact(item.event_city)}</TD><TD>{compact(item.flight_no)}</TD><TD>{item.status_text}</TD><TD><Badge>{item.normalized_event_type}</Badge></TD><TD>{compact(item.pieces)} / {compact(item.weight)}</TD></TR>)}</TBody>
              </Table>
            ) : <EmptyState title="暂无状态事件" description="官方货物状态解析后会形成时间线。" />}
          </Panel>
          <Panel title="货物组装事件" className="mt-4">
            {assemblies.length ? (
              <Table><THead><TR><TH>时间</TH><TH>城市</TH><TH>状态</TH><TH>板号</TH><TH>件/重</TH></TR></THead>
                <TBody>{assemblies.map((item) => <TR key={item.id}><TD>{formatDateTime(item.event_time_local) || item.event_time_text}</TD><TD>{compact(item.event_city)}</TD><TD>{item.status_text}</TD><TD>{compact(item.uld_no)}</TD><TD>{compact(item.pieces)} / {compact(item.weight)}</TD></TR>)}</TBody>
              </Table>
            ) : <EmptyState title="暂无组装事件" description="如 PMC 板号等信息会显示在这里。" />}
          </Panel>
        </TabsContent>
        <TabsContent value="snapshots">
          <Panel title="查询快照">
            <div className="mb-4 grid gap-3 text-sm md:grid-cols-3">
              <div className="rounded-md border border-slate-100 p-3">
                <div className="text-xs text-slate-500">首次监控</div>
                <div className="mt-1 font-medium text-slate-800">{formatDateTime(waybill.first_monitor_at)}</div>
              </div>
              <div className="rounded-md border border-slate-100 p-3">
                <div className="text-xs text-slate-500">最近查询</div>
                <div className="mt-1 font-medium text-slate-800">{formatDateTime(waybill.last_query_at)}</div>
              </div>
              <div className="rounded-md border border-slate-100 p-3">
                <div className="text-xs text-slate-500">下次查询</div>
                <div className="mt-1 font-medium text-slate-800">{formatDateTime(waybill.next_query_at)}</div>
              </div>
            </div>
            {snapshots.length ? (
              <Table><THead><TR><TH>时间</TH><TH>状态</TH><TH>适配器</TH><TH>类型</TH><TH>错误码</TH><TH>错误信息</TH></TR></THead>
                <TBody>{snapshots.map((item) => <TR key={item.id}><TD>{formatDateTime(item.queried_at)}</TD><TD>{item.query_status}</TD><TD>{compact(item.adapter_code)}</TD><TD>{item.adapter_type ? <Badge variant={item.adapter_type === "general" ? "blue" : "gray"}>{carrierAdapterTypeLabels[item.adapter_type] || item.adapter_type}</Badge> : "-"}</TD><TD>{compact(item.error_code)}</TD><TD>{compact(item.error_message)}</TD></TR>)}</TBody>
              </Table>
            ) : <EmptyState title="暂无查询快照" description="手动触发或调度执行后会记录查询结果。" />}
          </Panel>
        </TabsContent>
        <TabsContent value="alerts">
          <Panel title="异常列表">
            {alerts.length ? (
              <Table><THead><TR><TH>标题</TH><TH>类型</TH><TH>等级</TH><TH>状态</TH><TH>新值</TH><TH>时间</TH></TR></THead>
                <TBody>{alerts.map((item) => <TR key={item.id}><TD>{item.title}</TD><TD>{item.alert_type}</TD><TD><AlertLevelBadge value={item.alert_level} /></TD><TD>{item.status}</TD><TD>{compact(item.new_value)}</TD><TD>{formatDateTime(item.created_at)}</TD></TR>)}</TBody>
              </Table>
            ) : <EmptyState title="暂无异常" description="这票提单当前没有异常记录。" />}
          </Panel>
        </TabsContent>
        <TabsContent value="edit">
          <WaybillForm waybill={waybill} />
        </TabsContent>
      </Tabs>
    </>
  );
}
