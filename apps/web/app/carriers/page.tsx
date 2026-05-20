"use client";

import { useCallback, useEffect, useState } from "react";
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
import type { Carrier, CarrierAgent, CarrierPrefixMapping } from "@/lib/types";

type QueryMethod = "protocol" | "playwright" | "hybrid";

export default function CarriersPage() {
  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [mappings, setMappings] = useState<CarrierPrefixMapping[]>([]);
  const [agents, setAgents] = useState<CarrierAgent[]>([]);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [carrierCode, setCarrierCode] = useState("CZ");
  const [prefix, setPrefix] = useState("");
  const [adapterCode, setAdapterCode] = useState("cz_adapter");
  const [queryMethod, setQueryMethod] = useState<QueryMethod>("hybrid");
  const [enabled, setEnabled] = useState(true);
  const [remark, setRemark] = useState("");
  const [newCarrierCode, setNewCarrierCode] = useState("");
  const [newCarrierName, setNewCarrierName] = useState("");
  const [newCarrierNameEn, setNewCarrierNameEn] = useState("");
  const [editingAgentId, setEditingAgentId] = useState<number | null>(null);
  const [agentCarrierCode, setAgentCarrierCode] = useState("");
  const [agentName, setAgentName] = useState("");
  const [agentContactPerson, setAgentContactPerson] = useState("");
  const [agentContactPhone, setAgentContactPhone] = useState("");
  const [agentEnabled, setAgentEnabled] = useState(true);
  const [agentRemark, setAgentRemark] = useState("");

  const load = useCallback(() => {
    apiClient.get<Carrier[]>("/carriers").then(setCarriers);
    apiClient.get<CarrierPrefixMapping[]>("/carrier-prefix-mappings").then(setMappings);
    apiClient.get<CarrierAgent[]>("/carrier-agents").then(setAgents);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function resetMappingForm() {
    setEditingId(null);
    setPrefix("");
    setCarrierCode("CZ");
    setAdapterCode("cz_adapter");
    setQueryMethod("hybrid");
    setEnabled(true);
    setRemark("");
  }

  function editMapping(item: CarrierPrefixMapping) {
    setEditingId(item.id);
    setPrefix(item.prefix);
    setCarrierCode(item.carrier_code);
    setAdapterCode(item.adapter_code);
    setQueryMethod(item.query_method);
    setEnabled(item.enabled);
    setRemark(item.remark || "");
  }

  async function saveMapping(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (editingId) {
      await apiClient.patch<CarrierPrefixMapping>(`/carrier-prefix-mappings/${editingId}`, {
        carrier_code: carrierCode,
        adapter_code: adapterCode,
        query_method: queryMethod,
        enabled,
        remark: remark || null
      });
    } else {
      await apiClient.post<CarrierPrefixMapping>("/carrier-prefix-mappings", {
        prefix,
        carrier_code: carrierCode,
        adapter_code: adapterCode,
        query_method: queryMethod,
        enabled,
        remark: remark || null
      });
    }
    resetMappingForm();
    load();
  }

  async function createCarrier(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await apiClient.post<Carrier>("/carriers", {
      carrier_code: newCarrierCode,
      carrier_name: newCarrierName,
      carrier_name_en: newCarrierNameEn || null,
      enabled: true
    });
    setNewCarrierCode("");
    setNewCarrierName("");
    setNewCarrierNameEn("");
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
      <PageHeader title="航司配置" description="维护航司和运单前三位前缀映射" />
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel title="前缀映射">
          <Table>
            <THead><TR><TH>前缀</TH><TH>航司</TH><TH>适配器</TH><TH>方式</TH><TH>状态</TH><TH>操作</TH></TR></THead>
            <TBody>
              {mappings.map((item) => (
                <TR key={item.id}>
                  <TD className="font-medium">{item.prefix}</TD>
                  <TD>{item.carrier_code}</TD>
                  <TD>{item.adapter_code}</TD>
                  <TD>{item.query_method}</TD>
                  <TD><Badge variant={item.enabled ? "green" : "gray"}>{item.enabled ? "启用" : "停用"}</Badge></TD>
                  <TD>
                    <Button variant="ghost" size="sm" onClick={() => editMapping(item)}>
                      <Pencil className="h-4 w-4" />
                      编辑
                    </Button>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Panel>
        <Panel title={editingId ? "编辑映射" : "新建映射"}>
          <form onSubmit={saveMapping} className="space-y-3">
            <div className="space-y-1.5">
              <Label>前缀</Label>
              <Input value={prefix} onChange={(event) => setPrefix(event.target.value)} required readOnly={Boolean(editingId)} />
            </div>
            <div className="space-y-1.5">
              <Label>航司代码</Label>
              <Input value={carrierCode} onChange={(event) => setCarrierCode(event.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>适配器</Label>
              <Input value={adapterCode} onChange={(event) => setAdapterCode(event.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label>查询方式</Label>
              <Select value={queryMethod} onValueChange={(value) => setQueryMethod(value as QueryMethod)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="protocol">protocol</SelectItem>
                  <SelectItem value="playwright">playwright</SelectItem>
                  <SelectItem value="hybrid">hybrid</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label>备注</Label>
              <Input value={remark} onChange={(event) => setRemark(event.target.value)} />
            </div>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input type="checkbox" className="h-4 w-4 rounded border-slate-300" checked={enabled} onChange={(event) => setEnabled(event.target.checked)} />
              启用映射
            </label>
            <div className="flex gap-2">
              <Button className="flex-1">
                <Save className="h-4 w-4" />
                保存映射
              </Button>
              {editingId ? <Button type="button" variant="secondary" onClick={resetMappingForm}>取消</Button> : null}
            </div>
          </form>
        </Panel>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel title="航司列表">
          <Table>
            <THead><TR><TH>代码</TH><TH>名称</TH><TH>英文名</TH><TH>状态</TH></TR></THead>
            <TBody>
              {carriers.map((item) => (
                <TR key={item.id}>
                  <TD className="font-medium">{item.carrier_code}</TD>
                  <TD>{item.carrier_name}</TD>
                  <TD>{item.carrier_name_en || "-"}</TD>
                  <TD><Badge variant={item.enabled ? "green" : "gray"}>{item.enabled ? "启用" : "停用"}</Badge></TD>
                </TR>
              ))}
            </TBody>
          </Table>
        </Panel>
        <Panel title="新建航司">
          <form onSubmit={createCarrier} className="space-y-3">
            <div className="space-y-1.5"><Label>航司代码</Label><Input value={newCarrierCode} onChange={(event) => setNewCarrierCode(event.target.value)} required /></div>
            <div className="space-y-1.5"><Label>中文名称</Label><Input value={newCarrierName} onChange={(event) => setNewCarrierName(event.target.value)} required /></div>
            <div className="space-y-1.5"><Label>英文名称</Label><Input value={newCarrierNameEn} onChange={(event) => setNewCarrierNameEn(event.target.value)} /></div>
            <Button className="w-full">
              <Plus className="h-4 w-4" />
              创建航司
            </Button>
          </form>
        </Panel>
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel title="航司代理">
          <Table>
            <THead><TR><TH>航司</TH><TH>代理名</TH><TH>联系人</TH><TH>电话</TH><TH>状态</TH><TH>操作</TH></TR></THead>
            <TBody>
              {agents.map((item) => (
                <TR key={item.id}>
                  <TD className="font-medium">{item.carrier_code}</TD>
                  <TD>{item.agent_name}</TD>
                  <TD>{item.contact_person || "-"}</TD>
                  <TD>{item.contact_phone || "-"}</TD>
                  <TD><Badge variant={item.enabled ? "green" : "gray"}>{item.enabled ? "启用" : "停用"}</Badge></TD>
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
                      <SelectItem key={c.carrier_code} value={c.carrier_code}>{c.carrier_code} · {c.carrier_name}</SelectItem>
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
