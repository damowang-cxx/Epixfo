"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Save } from "lucide-react";
import type { FormEvent } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/client-api";
import { formatPlannedFlightInfo } from "@/lib/planned-flight";
import type { CarrierAgent, Consignee, ConsigneeContact, User, Waybill } from "@/lib/types";

type FormState = {
  waybill_no: string;
  departure_port: string;
  destination_port: string;
  carrier_agent_id: string;
  warehouse_no: string;
  consignee_contact_id: string;
  customs_staff_id: string;
  planned_flight_info: string;
  planned_destination: string;
  planned_route_text: string;
  booked_weight: string;
  booked_volume: string;
  density: string;
  quotation: string;
  air_freight_cost: string;
  other_charge: string;
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

type TextFieldKey = Exclude<keyof FormState, "include_tc" | "notify_pickup">;

type FieldMeta = {
  key: TextFieldKey;
  label: string;
  type?: string;
  readonlyOnEdit?: boolean;
  requiredOnCreate?: boolean;
};

const fields: FieldMeta[] = [
  { key: "waybill_no", label: "提单号", readonlyOnEdit: true, requiredOnCreate: true },
  { key: "departure_port", label: "始发港", requiredOnCreate: true },
  { key: "destination_port", label: "目的港", requiredOnCreate: true },
  { key: "warehouse_no", label: "入仓号" },
  { key: "planned_flight_info", label: "计划航班信息", requiredOnCreate: true },
  { key: "planned_destination", label: "计划目的港" },
  { key: "planned_route_text", label: "人工计划航程", requiredOnCreate: true },
  { key: "booked_weight", label: "订舱重量", type: "number", requiredOnCreate: true },
  { key: "booked_volume", label: "订舱方数", type: "number", requiredOnCreate: true },
  { key: "density", label: "密度", type: "number" },
  { key: "quotation", label: "报价", requiredOnCreate: true },
  { key: "air_freight_cost", label: "航空费", type: "number" },
  { key: "other_charge", label: "其他费用", type: "number" },
  { key: "payment_date", label: "付款日期", type: "date" },
  { key: "data_charge", label: "做数据收费", type: "number" },
  { key: "delivery_time", label: "交货时间", type: "datetime-local" },
  { key: "document_cutoff_time", label: "截单时间", type: "datetime-local" },
  { key: "pickup_time", label: "提取时间", type: "datetime-local" }
];

const requiredFieldLabels = fields
  .filter((field) => field.requiredOnCreate)
  .reduce<Record<string, string>>((acc, field) => {
    acc[field.key] = field.label;
    return acc;
  }, {});

function dateTimeInput(value?: string | null) {
  if (!value) return "";
  return value.slice(0, 16);
}

function initialState(waybill?: Waybill): FormState {
  return {
    waybill_no: waybill?.waybill_no || "",
    departure_port: waybill?.departure_port || "",
    destination_port: waybill?.destination_port || "",
    carrier_agent_id: waybill?.carrier_agent_id?.toString() || "",
    warehouse_no: waybill?.warehouse_no || "",
    consignee_contact_id: waybill?.consignee_contact_id?.toString() || "",
    customs_staff_id: waybill?.customs_staff_id?.toString() || "",
    planned_flight_info: formatPlannedFlightInfo(waybill?.plan),
    planned_destination: waybill?.plan?.planned_destination || "",
    planned_route_text: waybill?.plan?.planned_route_text || "",
    booked_weight: waybill?.booked_weight?.toString() || "",
    booked_volume: waybill?.booked_volume?.toString() || "",
    density: waybill?.density?.toString() || "",
    quotation: waybill?.quotation?.toString() || "",
    air_freight_cost: waybill?.air_freight_cost?.toString() || "",
    other_charge: waybill?.other_charge?.toString() || "",
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
    if (key === "carrier_agent_id" || key === "consignee_contact_id" || key === "customs_staff_id") {
      payload[key] = value === "" ? null : Number(value);
      return;
    }
    payload[key] = value === "" ? null : value;
  });
  return payload;
}

function validateCreateRequired(state: FormState) {
  const errors: string[] = [];
  Object.entries(requiredFieldLabels).forEach(([key, label]) => {
    const value = state[key as TextFieldKey];
    if (typeof value !== "string" || value.trim() === "") {
      errors.push(`${label}为必填信息`);
    }
  });
  ["booked_weight", "booked_volume"].forEach((key) => {
    const value = state[key as TextFieldKey].trim();
    if (value !== "" && Number.isNaN(Number(value))) {
      errors.push(`${requiredFieldLabels[key]}必须是有效数字`);
    }
  });
  return errors;
}

function isRequiredOnCurrentForm(field: FieldMeta, editing: boolean) {
  return !editing && Boolean(field.requiredOnCreate);
}

function RequiredLabel({ field, editing }: { field: FieldMeta; editing: boolean }) {
  return (
    <Label htmlFor={field.key}>
      {field.label}
      {isRequiredOnCurrentForm(field, editing) ? (
        <span className="ml-1 text-red-600" aria-label="必填">
          *
        </span>
      ) : null}
    </Label>
  );
}

export function WaybillForm({ waybill }: { waybill?: Waybill }) {
  const router = useRouter();
  const editing = Boolean(waybill);
  const [state, setState] = useState<FormState>(() => initialState(waybill));
  const [error, setError] = useState("");
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [agents, setAgents] = useState<CarrierAgent[]>([]);
  const [consignees, setConsignees] = useState<Consignee[]>([]);
  const [contacts, setContacts] = useState<ConsigneeContact[]>([]);
  const [users, setUsers] = useState<User[]>([]);

  useEffect(() => {
    apiClient.get<CarrierAgent[]>("/carrier-agents").then(setAgents).catch(() => setAgents([]));
    apiClient.get<Consignee[]>("/consignees").then(setConsignees).catch(() => setConsignees([]));
    apiClient.get<ConsigneeContact[]>("/consignee-contacts").then(setContacts).catch(() => setContacts([]));
    apiClient.get<User[]>("/users").then(setUsers).catch(() => setUsers([]));
  }, []);

  const visibleAgents = agents.filter((agent) => agent.enabled || state.carrier_agent_id === String(agent.id));
  const consigneeNameById = new Map(consignees.map((c) => [c.id, c.name]));
  const visibleContacts = contacts.filter((c) => c.enabled || state.consignee_contact_id === String(c.id));
  const visibleCustomsUsers = users.filter(
    (user) =>
      user.roles.some((role) => role.code === "customs_staff") &&
      (user.is_active || state.customs_staff_id === String(user.id))
  );

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (!editing) {
      const errors = validateCreateRequired(state);
      if (errors.length > 0) {
        setValidationErrors(errors);
        return;
      }
    }

    setSaving(true);
    try {
      const payload = payloadFromState(state, editing);
      const result = editing
        ? await apiClient.patch<Waybill>(`/waybills/${waybill!.id}`, payload)
        : await apiClient.post<Waybill>("/waybills", payload);
      router.push(`/waybills/${result.id}`);
      router.refresh();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "提交失败");
    } finally {
      setSaving(false);
    }
  }

  return (
    <>
      <form onSubmit={submit} className="space-y-4" noValidate>
        <Panel title="提单与计划信息">
          <div className="grid gap-4 md:grid-cols-3">
            {fields.map((field) => (
              field.key === "planned_destination" && !editing ? null : (
                <div key={field.key} className="space-y-1.5">
                  <RequiredLabel field={field} editing={editing} />
                  <div className={field.key === "quotation" ? "flex items-center gap-2" : undefined}>
                    <Input
                      id={field.key}
                      type={field.type || "text"}
                      placeholder={field.key === "planned_flight_info" ? "QR8943/01" : undefined}
                      value={state[field.key]}
                      readOnly={editing && field.readonlyOnEdit}
                      onChange={(event) => setState((prev) => ({ ...prev, [field.key]: event.target.value }))}
                      required={isRequiredOnCurrentForm(field, editing)}
                      aria-required={isRequiredOnCurrentForm(field, editing)}
                      step={field.type === "number" ? "0.001" : undefined}
                    />
                    {field.key === "quotation" ? (
                      <label className="flex h-10 shrink-0 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm text-slate-700">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300"
                          checked={state.include_tc}
                          onChange={(event) => setState((prev) => ({ ...prev, include_tc: event.target.checked }))}
                        />
                        含TC
                      </label>
                    ) : null}
                  </div>
                </div>
              )
            ))}
            <div className="space-y-1.5">
              <Label htmlFor="carrier_agent_id">航代</Label>
              <Select
                value={state.carrier_agent_id || "__none__"}
                onValueChange={(value) =>
                  setState((prev) => ({ ...prev, carrier_agent_id: value === "__none__" ? "" : value }))
                }
              >
                <SelectTrigger id="carrier_agent_id">
                  <SelectValue placeholder="选择航代" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">不指定</SelectItem>
                  {visibleAgents.map((agent) => (
                    <SelectItem key={agent.id} value={String(agent.id)}>
                      [{agent.carrier_code}] {agent.agent_name}
                      {!agent.enabled ? "（已停用）" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="consignee_contact_id">收货人</Label>
              <Select
                value={state.consignee_contact_id || "__none__"}
                onValueChange={(value) =>
                  setState((prev) => ({ ...prev, consignee_contact_id: value === "__none__" ? "" : value }))
                }
              >
                <SelectTrigger id="consignee_contact_id">
                  <SelectValue placeholder="选择收件人" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">不指定</SelectItem>
                  {visibleContacts.map((contact) => {
                    const company = consigneeNameById.get(contact.consignee_id) || "?";
                    const addr = (contact.address || "").split("\n")[0].slice(0, 30);
                    return (
                      <SelectItem key={contact.id} value={String(contact.id)}>
                        [{company}] {contact.name} {addr ? `- ${addr}` : ""}
                        {!contact.enabled ? "（已停用）" : ""}
                      </SelectItem>
                    );
                  })}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="customs_staff_id">指定清关人员</Label>
              <Select
                value={state.customs_staff_id || "__none__"}
                onValueChange={(value) =>
                  setState((prev) => ({ ...prev, customs_staff_id: value === "__none__" ? "" : value }))
                }
              >
                <SelectTrigger id="customs_staff_id">
                  <SelectValue placeholder="选择清关人员" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">不指定</SelectItem>
                  {visibleCustomsUsers.map((user) => (
                    <SelectItem key={user.id} value={String(user.id)}>
                      {user.display_name || user.username}
                      {!user.is_active ? "（已停用）" : ""}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="mt-4 flex flex-wrap gap-6 text-sm text-slate-700">
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
              <Label htmlFor="warehouse_data_remark">入仓数据备注</Label>
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
            {saving ? "提交中..." : editing ? "保存提单" : "新建提单"}
          </Button>
        </div>
      </form>

      <Dialog open={validationErrors.length > 0} onOpenChange={(open) => !open && setValidationErrors([])}>
        <DialogContent>
          <DialogTitle className="text-base font-semibold text-slate-900">必填信息缺失</DialogTitle>
          <div className="mt-3 rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">
            <p className="font-medium">请补充以下信息后再提交：</p>
            <ul className="mt-2 list-disc space-y-1 pl-5">
              {validationErrors.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="mt-4 flex justify-end">
            <Button type="button" onClick={() => setValidationErrors([])}>
              我知道了
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
