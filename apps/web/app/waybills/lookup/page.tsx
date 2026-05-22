"use client";

import { useEffect, useMemo, useState } from "react";
import { Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient, ApiError } from "@/lib/client-api";
import { carrierAdapterLabels, carrierAdapterOptions } from "@/lib/constants";
import { compact, computeRatio, formatDateTime } from "@/lib/utils";
import type { Carrier, CarrierPrefixMapping, WaybillLookupResponse } from "@/lib/types";

const DEFAULT_ADAPTER_CODE = "general_adapter";

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

function hasDetailedTimes(segment: WaybillLookupResponse["flight_segments"][number]) {
  return Boolean(
    segment.departure_planned_time ||
      segment.departure_actual_time ||
      segment.arrival_planned_time ||
      segment.arrival_actual_time
  );
}

function extractCarrierPrefix(value: string) {
  const digits = value.replace(/\D/g, "");
  return digits.length >= 3 ? digits.slice(0, 3) : "";
}

export default function WaybillLookupPage() {
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<WaybillLookupResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [mappings, setMappings] = useState<CarrierPrefixMapping[]>([]);
  const [configError, setConfigError] = useState<string | null>(null);
  const [adapterOverride, setAdapterOverride] = useState<{ prefix: string; adapterCode: string } | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadCarrierConfig() {
      setConfigError(null);
      try {
        const [carrierList, mappingList] = await Promise.all([
          apiClient.get<Carrier[]>("/carriers"),
          apiClient.get<CarrierPrefixMapping[]>("/carrier-prefix-mappings")
        ]);
        if (cancelled) return;
        setCarriers(carrierList);
        setMappings(mappingList);
      } catch (err) {
        if (cancelled) return;
        const message = err instanceof ApiError ? err.message : err instanceof Error ? err.message : "配置加载失败";
        setConfigError(message || "配置加载失败");
      }
    }

    loadCarrierConfig();
    return () => {
      cancelled = true;
    };
  }, []);

  const carrierByCode = useMemo(() => {
    const items = new Map<string, Carrier>();
    carriers.forEach((carrier) => items.set(carrier.carrier_code, carrier));
    return items;
  }, [carriers]);

  const mappingByPrefix = useMemo(() => {
    const items = new Map<string, CarrierPrefixMapping>();
    mappings.forEach((mapping) => {
      if (mapping.enabled) items.set(mapping.prefix, mapping);
    });
    return items;
  }, [mappings]);

  const detectedPrefix = useMemo(() => extractCarrierPrefix(input), [input]);
  const detectedMapping = detectedPrefix ? mappingByPrefix.get(detectedPrefix) : undefined;
  const detectedCarrier = detectedMapping ? carrierByCode.get(detectedMapping.carrier_code) : undefined;
  const suggestedAdapterCode = detectedMapping?.adapter_code || DEFAULT_ADAPTER_CODE;
  const activeAdapterCode =
    adapterOverride?.prefix === detectedPrefix ? adapterOverride.adapterCode : suggestedAdapterCode;
  const selectedAdapterLabel = carrierAdapterLabels[activeAdapterCode] || activeAdapterCode;

  async function submit() {
    const value = input.trim();
    if (!value) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await apiClient.post<WaybillLookupResponse>("/waybills/lookup", {
        waybill_no: value,
        adapter_code: activeAdapterCode
      });
      setResult(res);
      if (res.status !== "success") {
        setError(res.error_message || res.error_code || "查询失败");
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : err instanceof Error ? err.message : "查询失败";
      setError(message || "查询失败");
    } finally {
      setLoading(false);
    }
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") submit();
  }

  const canShowDetails = result?.status === "success" || result?.status === "partial_success";
  const isPartial = result?.status === "partial_success";

  return (
    <>
      <PageHeader
        title="提单速查"
        description="输入提单号直接查询承运人官网数据，结果仅供查看，不会创建提单，也不会写入数据库"
      />
      <Panel title="查询">
        <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(240px,320px)_auto]">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">提单号</label>
            <Input
              placeholder="例如 784-83707805 或 78483707805"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={onKeyDown}
              disabled={loading}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-600">查询适配器</label>
            <Select
              value={activeAdapterCode}
              onValueChange={(value) => setAdapterOverride({ prefix: detectedPrefix, adapterCode: value })}
              disabled={loading}
            >
              <SelectTrigger>
                <SelectValue placeholder="选择适配器" />
              </SelectTrigger>
              <SelectContent>
                {carrierAdapterOptions.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <Button onClick={submit} disabled={!input.trim() || loading} className="self-end">
            <Search className="h-4 w-4" />
            {loading ? "查询中..." : "查询"}
          </Button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-600">
          {detectedPrefix ? (
            <Badge variant={detectedMapping ? "blue" : "amber"}>前缀 {detectedPrefix}</Badge>
          ) : (
            <Badge variant="gray">等待输入前三位前缀</Badge>
          )}
          <span>
            {detectedMapping
              ? `识别航司：${detectedMapping.carrier_code}${
                  detectedCarrier ? ` · ${detectedCarrier.carrier_name}` : ""
                }`
              : detectedPrefix
                ? "未配置前缀，默认通用适配器"
                : "输入或粘贴提单号后自动识别"}
          </span>
          <span className="text-slate-400">/</span>
          <span>当前适配器：{selectedAdapterLabel}</span>
        </div>
        {configError ? (
          <div className="mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700">
            航司配置加载失败，适配器默认使用通用查询。{configError}
          </div>
        ) : null}
        {error ? (
          <div
            className={
              isPartial
                ? "mt-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-700"
                : "mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700"
            }
          >
            {error}
            {result?.error_code ? (
              <span className={isPartial ? "ml-2 text-xs text-amber-600" : "ml-2 text-xs text-red-500"}>
                ({result.error_code})
              </span>
            ) : null}
          </div>
        ) : null}
        {result && result.status === "success" ? (
          <div className="mt-3 rounded-md border border-green-200 bg-green-50 px-3 py-2 text-sm text-green-700">
            查询成功：{result.waybill_no}
            {result.carrier_code ? <span className="ml-2 text-xs text-green-600">({result.carrier_code})</span> : null}
          </div>
        ) : null}
      </Panel>

      {result && canShowDetails ? (
        <>
          <Panel title="官方提单信息" className="mt-4">
            {result.official_info ? (
              <FieldGrid
                items={[
                  ["官方提单号", result.official_info.official_waybill_no],
                  ["承运人", result.official_info.carrier_text],
                  ["航程", result.official_info.route_text],
                  ["货物品名", result.official_info.goods_name],
                  ["总件数", result.official_info.total_pieces],
                  ["总重量", result.official_info.total_weight],
                  ["总体积", result.official_info.total_volume],
                  ["密度", computeRatio(result.official_info.total_weight, result.official_info.total_volume)]
                ]}
              />
            ) : (
              <EmptyState title="暂无官方提单信息" description="官网未返回提单概要数据。" />
            )}
          </Panel>

          <Panel title="官方订舱航段" className="mt-4">
            {result.flight_segments.length ? (
              <Table>
                <THead>
                  <TR>
                    <TH>序号</TH>
                    <TH>订舱号</TH>
                    <TH>航班</TH>
                    <TH>航班日期</TH>
                    <TH>出发</TH>
                    <TH>到达</TH>
                    <TH className="border-l border-slate-200">起飞计划</TH>
                    <TH>起飞实际</TH>
                    <TH className="border-l border-slate-200">到达计划</TH>
                    <TH>到达实际</TH>
                    <TH className="border-l border-slate-200">件 / 重 / 方</TH>
                    <TH>精确时间</TH>
                  </TR>
                </THead>
                <TBody>
                  {result.flight_segments.map((item, index) => (
                    <TR key={`${item.flight_no || "seg"}-${index}`}>
                      <TD>{index + 1}</TD>
                      <TD>{compact(item.booking_no)}</TD>
                      <TD>{compact(item.flight_no)}</TD>
                      <TD>{compact(item.flight_date)}</TD>
                      <TD>{compact(item.departure_airport)}</TD>
                      <TD>{compact(item.arrival_airport)}</TD>
                      <TD className="border-l border-slate-100">{formatDateTime(item.departure_planned_time)}</TD>
                      <TD>{formatDateTime(item.departure_actual_time)}</TD>
                      <TD className="border-l border-slate-100">{formatDateTime(item.arrival_planned_time)}</TD>
                      <TD>{formatDateTime(item.arrival_actual_time)}</TD>
                      <TD className="border-l border-slate-100">
                        {compact(item.pieces)} / {compact(item.weight)} / {compact(item.volume)}
                      </TD>
                      <TD>
                        <Badge variant={hasDetailedTimes(item) ? "green" : "amber"}>
                          {hasDetailedTimes(item) ? "已返回" : "未返回"}
                        </Badge>
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : (
              <EmptyState title="暂无官方航段" description="官网未返回订舱航段数据。" />
            )}
          </Panel>

          <Panel title="货物状态事件" className="mt-4">
            {result.status_events.length ? (
              <Table>
                <THead>
                  <TR>
                    <TH>时间</TH>
                    <TH>城市</TH>
                    <TH>航班</TH>
                    <TH>状态</TH>
                    <TH>类型</TH>
                    <TH>件 / 重</TH>
                  </TR>
                </THead>
                <TBody>
                  {result.status_events.map((item, index) => (
                    <TR key={`${item.event_time_text || index}-${index}`}>
                      <TD>{formatDateTime(item.event_time_local) || compact(item.event_time_text)}</TD>
                      <TD>{compact(item.event_city)}</TD>
                      <TD>{compact(item.flight_no)}</TD>
                      <TD>{item.status_text}</TD>
                      <TD>
                        <Badge>{item.normalized_event_type}</Badge>
                      </TD>
                      <TD>
                        {compact(item.pieces)} / {compact(item.weight)}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : (
              <EmptyState title="暂无状态事件" description="官网未返回货物状态时间线。" />
            )}
          </Panel>

          <Panel title="货物组装事件" className="mt-4">
            {result.assembly_events.length ? (
              <Table>
                <THead>
                  <TR>
                    <TH>时间</TH>
                    <TH>城市</TH>
                    <TH>状态</TH>
                    <TH>板号</TH>
                    <TH>件 / 重</TH>
                  </TR>
                </THead>
                <TBody>
                  {result.assembly_events.map((item, index) => (
                    <TR key={`${item.event_time_text || index}-${index}`}>
                      <TD>{formatDateTime(item.event_time_local) || compact(item.event_time_text)}</TD>
                      <TD>{compact(item.event_city)}</TD>
                      <TD>{item.status_text}</TD>
                      <TD>{compact(item.uld_no)}</TD>
                      <TD>
                        {compact(item.pieces)} / {compact(item.weight)}
                      </TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : (
              <EmptyState title="暂无组装事件" description="官网未返回 ULD 装板信息。" />
            )}
          </Panel>
        </>
      ) : null}
    </>
  );
}
