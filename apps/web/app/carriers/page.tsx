"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Save } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { carrierAdapterLabels, carrierAdapterOptions, carrierAdapterQueryMethods } from "@/lib/constants";
import type { Carrier, CarrierAgent, CarrierPrefixMapping } from "@/lib/types";

export default function CarriersPage() {
  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [mappings, setMappings] = useState<CarrierPrefixMapping[]>([]);
  const [agents, setAgents] = useState<CarrierAgent[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [prefix, setPrefix] = useState("");
  const [carrierCode, setCarrierCode] = useState("CZ");
  const [carrierName, setCarrierName] = useState("");
  const [carrierNameEn, setCarrierNameEn] = useState("");
  const [adapterCode, setAdapterCode] = useState("cz_adapter");
  const [enabled, setEnabled] = useState(true);
  const [remark, setRemark] = useState("");
  const [editingAgentId, setEditingAgentId] = useState<number | null>(null);
  const [agentCarrierCode, setAgentCarrierCode] = useState("");
  const [agentName, setAgentName] = useState("");
  const [agentContactPerson, setAgentContactPerson] = useState("");
  const [agentContactPhone, setAgentContactPhone] = useState("");
  const [agentEnabled, setAgentEnabled] = useState(true);
  const [agentRemark, setAgentRemark] = useState("");

  const carrierByCode = useMemo(() => {
    return new Map(carriers.map((carrier) => [carrier.carrier_code, carrier]));
  }, [carriers]);

  const load = useCallback(() => {
    apiClient.get<Carrier[]>("/carriers").then(setCarriers);
    apiClient.get<CarrierPrefixMapping[]>("/carrier-prefix-mappings").then(setMappings);
    apiClient.get<CarrierAgent[]>("/carrier-agents").then(setAgents);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function resetCarrierForm() {
    setEditingId(null);
    setPrefix("");
    setCarrierCode("CZ");
    setCarrierName("");
    setCarrierNameEn("");
    setAdapterCode("cz_adapter");
    setEnabled(true);
    setRemark("");
  }

  function editCarrierConfig(item: CarrierPrefixMapping) {
    const carrier = carrierByCode.get(item.carrier_code);
    setEditingId(item.id);
    setPrefix(item.prefix);
    setCarrierCode(item.carrier_code);
    setCarrierName(carrier?.carrier_name || "");
    setCarrierNameEn(carrier?.carrier_name_en || "");
    setAdapterCode(item.adapter_code);
    setEnabled(item.enabled);
    setRemark(item.remark || "");
  }

  async function saveCarrierConfig(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const normalizedPrefix = prefix.trim();
    const normalizedCarrierCode = carrierCode.trim().toUpperCase();
    const normalizedAdapterCode = adapterCode.trim();
    const queryMethod = carrierAdapterQueryMethods[normalizedAdapterCode] || "hybrid";
    const existingCarrier = carrierByCode.get(normalizedCarrierCode);

    if (existingCarrier) {
      await apiClient.patch<Carrier>(`/carriers/${normalizedCarrierCode}`, {
        carrier_name: carrierName,
        carrier_name_en: carrierNameEn || null,
        enabled: true
      });
    } else {
      await apiClient.post<Carrier>("/carriers", {
        carrier_code: normalizedCarrierCode,
        carrier_name: carrierName,
        carrier_name_en: carrierNameEn || null,
        enabled: true
      });
    }

    if (editingId) {
      await apiClient.patch<CarrierPrefixMapping>(`/carrier-prefix-mappings/${editingId}`, {
        carrier_code: normalizedCarrierCode,
        adapter_code: normalizedAdapterCode,
        query_method: queryMethod,
        enabled,
        remark: remark || null
      });
    } else {
      await apiClient.post<CarrierPrefixMapping>("/carrier-prefix-mappings", {
        prefix: normalizedPrefix,
        carrier_code: normalizedCarrierCode,
        adapter_code: normalizedAdapterCode,
        query_method: queryMethod,
        enabled,
        remark: remark || null
      });
    }

    resetCarrierForm();
    load();
  }

  function resetAgentForm() {
    setEditingAgentId(null);
    setAgentCarrierCode(carriers[0]?.carrier_code || "");
    setAgentName("");
    setAgentContactPerson("");
    setAgentContactPhone("");
    setAgentEnabled(true);
    setAgentRemark("");
  }

  function editAgent(item: CarrierAgent) {
    setEditingAgentId(item.id);
    setAgentCarrierCode(item.carrier_code);
    setAgentName(item.agent_name);
    setAgentContactPerson(item.contact_person || "");
    setAgentContactPhone(item.contact_phone || "");
    setAgentEnabled(item.enabled);
    setAgentRemark(item.remark || "");
  }

  async function saveAgent(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingAgentId) {
      await apiClient.patch<CarrierAgent>(`/carrier-agents/${editingAgentId}`, {
        agent_name: agentName,
        contact_person: agentContactPerson || null,
        contact_phone: agentContactPhone || null,
        enabled: agentEnabled,
        remark: agentRemark || null
      });
    } else {
      await apiClient.post<CarrierAgent>("/carrier-agents", {
        carrier_code: agentCarrierCode,
        agent_name: agentName,
        contact_person: agentContactPerson || null,
        contact_phone: agentContactPhone || null,
        enabled: agentEnabled,
        remark: agentRemark || null
      });
    }
    resetAgentForm();
    load();
  }

  return (
    <>
      <PageHeader title="航司配置" description="维护提单前三位前缀对应的航司识别规则和航司代理信息" />
      <div className="grid gap-4 xl:grid-cols-[1fr_400px]">
        <Panel title="航司识别配置">
          <Table>
            <THead>
              <TR>
                <TH>前缀</TH>
                <TH>航司代码</TH>
                <TH>航司名称</TH>
                <TH>英文名</TH>
                <TH>适配器</TH>
                <TH>状态</TH>
                <TH>操作</TH>
              </TR>
            </THead>
            <TBody>
              {mappings.map((item) => {
                const carrier = carrierByCode.get(item.carrier_code);
                return (
                  <TR key={item.id}>
                    <TD className="font-medium">{item.prefix}</TD>
                    <TD>{item.carrier_code}</TD>
                    <TD>{carrier?.carrier_name || "-"}</TD>
                    <TD>{carrier?.carrier_name_en || "-"}</TD>
                    <TD>{carrierAdapterLabels[item.adapter_code] || item.adapter_code}</TD>
                    <TD>
                      <Badge variant={item.enabled ? "green" : "gray"}>
                        {item.enabled ? "启用" : "停用"}
                      </Badge>
                    </TD>
                    <TD>
                      <Button variant="ghost" size="sm" onClick={() => editCarrierConfig(item)}>
                        <Pencil className="h-4 w-4" />
                        编辑
                      </Button>
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        </Panel>
        <Panel title={editingId ? "编辑航司" : "新建航司"}>
          <form onSubmit={saveCarrierConfig} className="space-y-3">
            <div className="space-y-1.5">
              <Label>提单前缀</Label>
              <Input value={prefix} onChange={(event) => setPrefix(event.target.value)} required readOnly={Boolean(editingId)} />
            </div>
            <div className="space-y-1.5">
              <Label>航司代码</Label>
              <Input value={carrierCode} onChange={(event) => setCarrierCode(event.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>航司名称</Label>
              <Input value={carrierName} onChange={(event) => setCarrierName(event.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>英文名称</Label>
              <Input value={carrierNameEn} onChange={(event) => setCarrierNameEn(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>适配器</Label>
              <Select value={adapterCode} onValueChange={setAdapterCode}>
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
            <div className="space-y-1.5">
              <Label>备注</Label>
              <Input value={remark} onChange={(event) => setRemark(event.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
              启用识别配置
            </label>
            <div className="flex gap-2">
              <Button className="flex-1">
                {editingId ? <Save className="h-4 w-4" /> : <Plus className="h-4 w-4" />}
                {editingId ? "保存航司" : "创建航司"}
              </Button>
              {editingId ? <Button type="button" variant="secondary" onClick={resetCarrierForm}>取消</Button> : null}
            </div>
          </form>
        </Panel>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_400px]">
        <Panel title="航司代理">
          <Table>
            <THead>
              <TR>
                <TH>航司</TH>
                <TH>代理名</TH>
                <TH>联系人</TH>
                <TH>电话</TH>
                <TH>状态</TH>
                <TH>操作</TH>
              </TR>
            </THead>
            <TBody>
              {agents.map((item) => (
                <TR key={item.id}>
                  <TD className="font-medium">{item.carrier_code}</TD>
                  <TD>{item.agent_name}</TD>
                  <TD>{item.contact_person || "-"}</TD>
                  <TD>{item.contact_phone || "-"}</TD>
                  <TD>
                    <Badge variant={item.enabled ? "green" : "gray"}>
                      {item.enabled ? "启用" : "停用"}
                    </Badge>
                  </TD>
                  <TD>
                    <Button variant="ghost" size="sm" onClick={() => editAgent(item)}>
                      <Pencil className="h-4 w-4" />
                      编辑
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Panel>
        <Panel title={editingAgentId ? "编辑代理" : "新建代理"}>
          <form onSubmit={saveAgent} className="space-y-3">
            <div className="space-y-1.5">
              <Label>航司</Label>
              {editingAgentId ? (
                <Input value={agentCarrierCode} readOnly />
              ) : (
                <Select value={agentCarrierCode} onValueChange={setAgentCarrierCode}>
                  <SelectTrigger><SelectValue placeholder="选择航司" /></SelectTrigger>
                  <SelectContent>
                    {carriers.filter((c) => c.enabled).map((c) => (
                      <SelectItem key={c.carrier_code} value={c.carrier_code}>{c.carrier_code} / {c.carrier_name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
            <div className="space-y-1.5">
              <Label>代理名</Label>
              <Input value={agentName} onChange={(event) => setAgentName(event.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>联系人</Label>
              <Input value={agentContactPerson} onChange={(event) => setAgentContactPerson(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>联系电话</Label>
              <Input value={agentContactPhone} onChange={(event) => setAgentContactPhone(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>备注</Label>
              <Input value={agentRemark} onChange={(event) => setAgentRemark(event.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-slate-300"
                checked={agentEnabled}
                onChange={(event) => setAgentEnabled(event.target.checked)}
              />
              启用代理
            </label>
            <div className="flex gap-2">
              <Button className="flex-1" disabled={!agentCarrierCode || !agentName}>
                <Save className="h-4 w-4" />
                保存代理
              </Button>
              {editingAgentId ? <Button type="button" variant="secondary" onClick={resetAgentForm}>取消</Button> : null}
            </div>
          </form>
        </Panel>
      </div>
    </>
  );
}
