"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Save } from "lucide-react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel } from "@/components/ui/panel";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/client-api";
import type { Waybill } from "@/lib/types";

type FormState = {
  waybill_no: string;
  destination_port: string;
  agent: string;
  warehouse_no: string;
  consignee: string;
  planned_flight_no: string;
  planned_flight_date: string;
  planned_destination: string;
  planned_route_text: string;
  booked_weight: string;
  booked_volume: string;
  density: string;
  quotation: string;
  air_freight_cost: string;
  payment_date: string;
  data_charge: string;
  delivery_time: string;
  document_cutoff_time: string;
  pickup_time: string;
  include_tc: boolean;
  notify_pickup: boolean;
  warehouse_data_remark: string;
  customer_remark: string;
  internal_remark: string;
};

const fields: Array<{ key: keyof FormState; label: string; type?: string; readonlyOnEdit?: boolean }> = [
  { key: "waybill_no", label: "运单号", readonlyOnEdit: true },
  { key: "destination_port", label: "目的港" },
  { key: "agent", label: "航代" },
  { key: "warehouse_no", label: "入仓号" },
  { key: "consignee", label: "收货人" },
  { key: "planned_flight_no", label: "计划航班号" },
  { key: "planned_flight_date", label: "计划航班日期", type: "date" },
  { key: "planned_destination", label: "计划目的港" },
  { key: "planned_route_text", label: "人工计划航程" },
  { key: "booked_weight", label: "订舱重量", type: "number" },
  { key: "booked_volume", label: "订舱方数", type: "number" },
  { key: "density", label: "密度", type: "number" },
  { key: "quotation", label: "报价", type: "number" },
  { key: "air_freight_cost", label: "航空费", type: "number" },
  { key: "payment_date", label: "付款日期", type: "date" },
  { key: "data_charge", label: "做数据收费", type: "number" },
  { key: "delivery_time", label: "交货时间", type: "datetime-local" },
  { key: "document_cutoff_time", label: "截单时间", type: "datetime-local" },
  { key: "pickup_time", label: "提取时间", type: "datetime-local" }
];

function dateTimeInput(value?: string | null) {
  if (!value) return "";
  return value.slice(0, 16);
}

function initialState(waybill?: Waybill): FormState {
  return {
    waybill_no: waybill?.waybill_no || "",
    destination_port: waybill?.destination_port || "",
    agent: waybill?.agent || "",
    warehouse_no: waybill?.warehouse_no || "",
    consignee: waybill?.consignee || "",
    planned_flight_no: waybill?.plan?.planned_flight_no || "",
    planned_flight_date: waybill?.plan?.planned_flight_date || "",
    planned_destination: waybill?.plan?.planned_destination || "",
    planned_route_text: waybill?.plan?.planned_route_text || "",
    booked_weight: waybill?.booked_weight?.toString() || "",
    booked_volume: waybill?.booked_volume?.toString() || "",
    density: waybill?.density?.toString() || "",
    quotation: waybill?.quotation?.toString() || "",
    air_freight_cost: waybill?.air_freight_cost?.toString() || "",
    payment_date: waybill?.payment_date || "",
    data_charge: waybill?.data_charge?.toString() || "",
    delivery_time: dateTimeInput(waybill?.delivery_time),
    document_cutoff_time: dateTimeInput(waybill?.document_cutoff_time),
    pickup_time: dateTimeInput(waybill?.pickup_time),
    include_tc: Boolean(waybill?.include_tc),
    notify_pickup: Boolean(waybill?.notify_pickup),
    warehouse_data_remark: waybill?.warehouse_data_remark || "",
    customer_remark: waybill?.customer_remark || "",
    internal_remark: waybill?.internal_remark || ""
  };
}

function payloadFromState(state: FormState, editing: boolean) {
  const payload: Record<string, string | number | boolean | null> = {};
  Object.entries(state).forEach(([key, value]) => {
    if (editing && key === "waybill_no") return;
    payload[key] = value === "" ? null : value;
  });
  return payload;
}

export function WaybillForm({ waybill }: { waybill?: Waybill }) {
  const router = useRouter();
  const editing = Boolean(waybill);
  const [state, setState] = useState<FormState>(() => initialState(waybill));
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSaving(true);
    setError("");
    try {
      const payload = payloadFromState(state, editing);
      const result = editing
        ? await apiClient.patch<Waybill>(`/waybills/${waybill!.id}`, payload)
        : await apiClient.post<Waybill>("/waybills", payload);
      router.push(`/waybills/${result.id}`);
      router.refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <Panel title="基础与计划信息">
        <div className="grid gap-4 md:grid-cols-3">
          {fields.map((field) => (
            <div key={field.key} className="space-y-1.5">
              <Label htmlFor={field.key}>{field.label}</Label>
              <Input
                id={field.key}
                type={field.type || "text"}
                value={state[field.key] as string}
                readOnly={editing && field.readonlyOnEdit}
                onChange={(event) => setState((prev) => ({ ...prev, [field.key]: event.target.value }))}
                required={field.key === "waybill_no"}
                step={field.type === "number" ? "0.001" : undefined}
              />
            </div>
          ))}
        </div>
        <div className="mt-4 flex flex-wrap gap-6 text-sm text-slate-700">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={state.include_tc}
              onChange={(event) => setState((prev) => ({ ...prev, include_tc: event.target.checked }))}
            />
            是否含 TC
          </label>
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={state.notify_pickup}
              onChange={(event) => setState((prev) => ({ ...prev, notify_pickup: event.target.checked }))}
            />
            通知提取
          </label>
        </div>
      </Panel>
      <Panel title="备注">
        <div className="grid gap-4 md:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor="warehouse_data_remark">入仓数据</Label>
            <Textarea
              id="warehouse_data_remark"
              value={state.warehouse_data_remark}
              onChange={(event) => setState((prev) => ({ ...prev, warehouse_data_remark: event.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="customer_remark">客服可见备注</Label>
            <Textarea
              id="customer_remark"
              value={state.customer_remark}
              onChange={(event) => setState((prev) => ({ ...prev, customer_remark: event.target.value }))}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="internal_remark">内部备注</Label>
            <Textarea
              id="internal_remark"
              value={state.internal_remark}
              onChange={(event) => setState((prev) => ({ ...prev, internal_remark: event.target.value }))}
            />
          </div>
        </div>
      </Panel>
      {error ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
      <div className="flex justify-end">
        <Button disabled={saving}>
          <Save className="h-4 w-4" />
          {saving ? "保存中..." : "保存运单"}
        </Button>
      </div>
    </form>
  );
}
