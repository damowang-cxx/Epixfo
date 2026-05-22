"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Plus, Save, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import { apiClient } from "@/lib/client-api";
import { carrierAdapterLabels, carrierAdapterOptions, carrierAdapterQueryMethods } from "@/lib/constants";
import type { Carrier, CarrierAgent, CarrierPrefixMapping } from "@/lib/types";

type EditingRowId = number | "new" | null;

type MappingDraft = {
  prefix: string;
  carrierCode: string;
  carrierName: string;
  carrierNameEn: string;
  adapterCode: string;
  enabled: boolean;
  remark: string;
};

type AgentDraft = {
  carrierCode: string;
  agentName: string;
  contactPerson: string;
  contactPhone: string;
  contactEmails: string;
  enabled: boolean;
  remark: string;
};

function emptyMappingDraft(): MappingDraft {
  return {
    prefix: "",
    carrierCode: "",
    carrierName: "",
    carrierNameEn: "",
    adapterCode: "general_adapter",
    enabled: true,
    remark: ""
  };
}

function mappingDraftFromItem(item: CarrierPrefixMapping, carrier?: Carrier): MappingDraft {
  return {
    prefix: item.prefix,
    carrierCode: item.carrier_code,
    carrierName: carrier?.carrier_name || "",
    carrierNameEn: carrier?.carrier_name_en || "",
    adapterCode: item.adapter_code,
    enabled: item.enabled,
    remark: item.remark || ""
  };
}

function emptyAgentDraft(carriers: Carrier[]): AgentDraft {
  const firstCarrier = carriers.find((carrier) => carrier.enabled) || carriers[0];
  return {
    carrierCode: firstCarrier?.carrier_code || "",
    agentName: "",
    contactPerson: "",
    contactPhone: "",
    contactEmails: "",
    enabled: true,
    remark: ""
  };
}

function agentDraftFromItem(item: CarrierAgent): AgentDraft {
  return {
    carrierCode: item.carrier_code,
    agentName: item.agent_name,
    contactPerson: item.contact_person || "",
    contactPhone: item.contact_phone || "",
    contactEmails: item.contact_emails || "",
    enabled: item.enabled,
    remark: item.remark || ""
  };
}

function errorMessage(error: unknown, fallback: string) {
  return error instanceof Error ? error.message : fallback;
}

export default function CarriersPage() {
  const [carriers, setCarriers] = useState<Carrier[]>([]);
  const [mappings, setMappings] = useState<CarrierPrefixMapping[]>([]);
  const [agents, setAgents] = useState<CarrierAgent[]>([]);
  const [editingMappingId, setEditingMappingId] = useState<EditingRowId>(null);
  const [carrierDraft, setCarrierDraft] = useState<MappingDraft>(() => emptyMappingDraft());
  const [mappingError, setMappingError] = useState("");
  const [savingMapping, setSavingMapping] = useState(false);
  const [editingAgentId, setEditingAgentId] = useState<EditingRowId>(null);
  const [agentDraft, setAgentDraft] = useState<AgentDraft>(() => emptyAgentDraft([]));
  const [agentError, setAgentError] = useState("");
  const [savingAgent, setSavingAgent] = useState(false);

  const carrierByCode = useMemo(() => {
    return new Map(carriers.map((carrier) => [carrier.carrier_code, carrier]));
  }, [carriers]);

  const carrierOptions = useMemo(() => {
    const items = new Map<string, { code: string; label: string; enabled: boolean }>();
    carriers.forEach((carrier) => {
      items.set(carrier.carrier_code, {
        code: carrier.carrier_code,
        label: `${carrier.carrier_code} / ${carrier.carrier_name}`,
        enabled: carrier.enabled
      });
    });
    mappings.forEach((mapping) => {
      if (!items.has(mapping.carrier_code)) {
        items.set(mapping.carrier_code, {
          code: mapping.carrier_code,
          label: mapping.carrier_code,
          enabled: mapping.enabled
        });
      }
    });
    agents.forEach((agent) => {
      if (!items.has(agent.carrier_code)) {
        items.set(agent.carrier_code, {
          code: agent.carrier_code,
          label: agent.carrier_code,
          enabled: agent.enabled
        });
      }
    });
    return Array.from(items.values()).sort((left, right) => left.code.localeCompare(right.code));
  }, [agents, carriers, mappings]);

  const load = useCallback(async () => {
    const results = await Promise.allSettled([
      apiClient.get<Carrier[]>("/carriers"),
      apiClient.get<CarrierPrefixMapping[]>("/carrier-prefix-mappings"),
      apiClient.get<CarrierAgent[]>("/carrier-agents")
    ]);
    if (results[0].status === "fulfilled") {
      setCarriers(results[0].value);
    } else {
      setMappingError(errorMessage(results[0].reason, "航司信息加载失败"));
    }
    if (results[1].status === "fulfilled") {
      setMappings(results[1].value);
    } else {
      setMappingError(errorMessage(results[1].reason, "航司识别配置加载失败"));
    }
    if (results[2].status === "fulfilled") {
      setAgents(results[2].value);
    } else {
      setAgentError(errorMessage(results[2].reason, "航代信息加载失败"));
    }
  }, []);

  useEffect(() => {
    let active = true;
    void Promise.allSettled([
      apiClient.get<Carrier[]>("/carriers"),
      apiClient.get<CarrierPrefixMapping[]>("/carrier-prefix-mappings"),
      apiClient.get<CarrierAgent[]>("/carrier-agents")
    ]).then((results) => {
      if (!active) return;
      if (results[0].status === "fulfilled") {
        setCarriers(results[0].value);
      } else {
        setMappingError(errorMessage(results[0].reason, "航司信息加载失败"));
      }
      if (results[1].status === "fulfilled") {
        setMappings(results[1].value);
      } else {
        setMappingError(errorMessage(results[1].reason, "航司识别配置加载失败"));
      }
      if (results[2].status === "fulfilled") {
        setAgents(results[2].value);
      } else {
        setAgentError(errorMessage(results[2].reason, "航代信息加载失败"));
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const mappingReady = Boolean(
    carrierDraft.prefix.trim() &&
      carrierDraft.carrierCode.trim() &&
      carrierDraft.carrierName.trim() &&
      carrierDraft.adapterCode.trim()
  );
  const agentReady = Boolean(agentDraft.carrierCode.trim() && agentDraft.agentName.trim());

  function startNewMapping() {
    setMappingError("");
    setEditingMappingId("new");
    setCarrierDraft(emptyMappingDraft());
  }

  function editMapping(item: CarrierPrefixMapping) {
    setMappingError("");
    setEditingMappingId(item.id);
    setCarrierDraft(mappingDraftFromItem(item, carrierByCode.get(item.carrier_code)));
  }

  function cancelMappingEdit() {
    setMappingError("");
    setEditingMappingId(null);
    setCarrierDraft(emptyMappingDraft());
  }

  async function saveMappingDraft() {
    if (!mappingReady || editingMappingId === null) return;
    setSavingMapping(true);
    setMappingError("");

    try {
      const normalizedPrefix = carrierDraft.prefix.trim();
      const normalizedCarrierCode = carrierDraft.carrierCode.trim().toUpperCase();
      const normalizedAdapterCode = carrierDraft.adapterCode.trim();
      const queryMethod = carrierAdapterQueryMethods[normalizedAdapterCode] || "hybrid";
      const existingCarrier = carrierByCode.get(normalizedCarrierCode);

      if (existingCarrier) {
        await apiClient.patch<Carrier>(`/carriers/${normalizedCarrierCode}`, {
          carrier_name: carrierDraft.carrierName.trim(),
          carrier_name_en: carrierDraft.carrierNameEn.trim() || null,
          enabled: true
        });
      } else {
        await apiClient.post<Carrier>("/carriers", {
          carrier_code: normalizedCarrierCode,
          carrier_name: carrierDraft.carrierName.trim(),
          carrier_name_en: carrierDraft.carrierNameEn.trim() || null,
          enabled: true
        });
      }

      if (editingMappingId === "new") {
        await apiClient.post<CarrierPrefixMapping>("/carrier-prefix-mappings", {
          prefix: normalizedPrefix,
          carrier_code: normalizedCarrierCode,
          adapter_code: normalizedAdapterCode,
          query_method: queryMethod,
          enabled: carrierDraft.enabled,
          remark: carrierDraft.remark.trim() || null
        });
      } else {
        await apiClient.patch<CarrierPrefixMapping>(`/carrier-prefix-mappings/${editingMappingId}`, {
          carrier_code: normalizedCarrierCode,
          adapter_code: normalizedAdapterCode,
          query_method: queryMethod,
          enabled: carrierDraft.enabled,
          remark: carrierDraft.remark.trim() || null
        });
      }

      cancelMappingEdit();
      await load();
    } catch (error) {
      setMappingError(errorMessage(error, "航司配置保存失败"));
    } finally {
      setSavingMapping(false);
    }
  }

  function startNewAgent() {
    setAgentError("");
    setEditingAgentId("new");
    const firstCarrier = carrierOptions.find((carrier) => carrier.enabled) || carrierOptions[0];
    setAgentDraft({
      ...emptyAgentDraft(carriers),
      carrierCode: firstCarrier?.code || ""
    });
  }

  function editAgent(item: CarrierAgent) {
    setAgentError("");
    setEditingAgentId(item.id);
    setAgentDraft(agentDraftFromItem(item));
  }

  function cancelAgentEdit() {
    setAgentError("");
    setEditingAgentId(null);
    const firstCarrier = carrierOptions.find((carrier) => carrier.enabled) || carrierOptions[0];
    setAgentDraft({
      ...emptyAgentDraft(carriers),
      carrierCode: firstCarrier?.code || ""
    });
  }

  async function saveAgentDraft() {
    if (!agentReady || editingAgentId === null) return;
    setSavingAgent(true);
    setAgentError("");

    try {
      if (editingAgentId === "new") {
        await apiClient.post<CarrierAgent>("/carrier-agents", {
          carrier_code: agentDraft.carrierCode,
          agent_name: agentDraft.agentName.trim(),
          contact_person: agentDraft.contactPerson.trim() || null,
          contact_phone: agentDraft.contactPhone.trim() || null,
          contact_emails: agentDraft.contactEmails.trim() || null,
          enabled: agentDraft.enabled,
          remark: agentDraft.remark.trim() || null
        });
      } else {
        await apiClient.patch<CarrierAgent>(`/carrier-agents/${editingAgentId}`, {
          agent_name: agentDraft.agentName.trim(),
          contact_person: agentDraft.contactPerson.trim() || null,
          contact_phone: agentDraft.contactPhone.trim() || null,
          contact_emails: agentDraft.contactEmails.trim() || null,
          enabled: agentDraft.enabled,
          remark: agentDraft.remark.trim() || null
        });
      }

      cancelAgentEdit();
      await load();
    } catch (error) {
      setAgentError(errorMessage(error, "航代保存失败"));
    } finally {
      setSavingAgent(false);
    }
  }

  function mappingDraftRow(key: string, prefixReadOnly: boolean) {
    return (
      <TR key={key} className="bg-slate-50 align-top hover:bg-slate-50">
        <TD>
          <Input
            value={carrierDraft.prefix}
            onChange={(event) => setCarrierDraft((prev) => ({ ...prev, prefix: event.target.value }))}
            readOnly={prefixReadOnly}
            className="w-24"
          />
        </TD>
        <TD>
          <Input
            value={carrierDraft.carrierCode}
            onChange={(event) => setCarrierDraft((prev) => ({ ...prev, carrierCode: event.target.value.toUpperCase() }))}
            className="w-24"
          />
        </TD>
        <TD>
          <Input
            value={carrierDraft.carrierName}
            onChange={(event) => setCarrierDraft((prev) => ({ ...prev, carrierName: event.target.value }))}
            className="w-36"
          />
        </TD>
        <TD>
          <Input
            value={carrierDraft.carrierNameEn}
            onChange={(event) => setCarrierDraft((prev) => ({ ...prev, carrierNameEn: event.target.value }))}
            className="w-44"
          />
        </TD>
        <TD>
          <Select
            value={carrierDraft.adapterCode}
            onValueChange={(value) => setCarrierDraft((prev) => ({ ...prev, adapterCode: value }))}
          >
            <SelectTrigger className="w-56">
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
        </TD>
        <TD>
          <label className="flex h-9 items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={carrierDraft.enabled}
              onChange={(event) => setCarrierDraft((prev) => ({ ...prev, enabled: event.target.checked }))}
            />
            启用
          </label>
        </TD>
        <TD>
          <Input
            value={carrierDraft.remark}
            onChange={(event) => setCarrierDraft((prev) => ({ ...prev, remark: event.target.value }))}
            className="w-48"
          />
        </TD>
        <TD>
          <div className="flex gap-2">
            <Button size="sm" onClick={saveMappingDraft} disabled={!mappingReady || savingMapping}>
              <Save className="h-4 w-4" />
              保存
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={cancelMappingEdit} disabled={savingMapping}>
              <X className="h-4 w-4" />
              取消
            </Button>
          </div>
        </TD>
      </TR>
    );
  }

  function agentDraftRow(key: string, carrierReadOnly: boolean) {
    return (
      <TR key={key} className="bg-slate-50 align-top hover:bg-slate-50">
        <TD>
          {carrierReadOnly ? (
            <Input value={agentDraft.carrierCode} readOnly className="w-28" />
          ) : (
            <Select
              value={agentDraft.carrierCode}
              onValueChange={(value) => setAgentDraft((prev) => ({ ...prev, carrierCode: value }))}
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder="选择航司" />
              </SelectTrigger>
              <SelectContent>
                {carrierOptions
                  .filter((carrier) => carrier.enabled)
                  .map((carrier) => (
                    <SelectItem key={carrier.code} value={carrier.code}>
                      {carrier.label}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          )}
        </TD>
        <TD>
          <Input
            value={agentDraft.agentName}
            onChange={(event) => setAgentDraft((prev) => ({ ...prev, agentName: event.target.value }))}
            className="w-40"
          />
        </TD>
        <TD>
          <Input
            value={agentDraft.contactPerson}
            onChange={(event) => setAgentDraft((prev) => ({ ...prev, contactPerson: event.target.value }))}
            className="w-32"
          />
        </TD>
        <TD>
          <Input
            value={agentDraft.contactPhone}
            onChange={(event) => setAgentDraft((prev) => ({ ...prev, contactPhone: event.target.value }))}
            className="w-36"
          />
        </TD>
        <TD>
          <Textarea
            value={agentDraft.contactEmails}
            onChange={(event) => setAgentDraft((prev) => ({ ...prev, contactEmails: event.target.value }))}
            placeholder={"每行一个邮箱\nabc@xx.com\ndef@yy.com"}
            rows={3}
            className="w-56"
          />
        </TD>
        <TD>
          <label className="flex h-9 items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              className="h-4 w-4 rounded border-slate-300"
              checked={agentDraft.enabled}
              onChange={(event) => setAgentDraft((prev) => ({ ...prev, enabled: event.target.checked }))}
            />
            启用
          </label>
        </TD>
        <TD>
          <Input
            value={agentDraft.remark}
            onChange={(event) => setAgentDraft((prev) => ({ ...prev, remark: event.target.value }))}
            className="w-48"
          />
        </TD>
        <TD>
          <div className="flex gap-2">
            <Button size="sm" onClick={saveAgentDraft} disabled={!agentReady || savingAgent}>
              <Save className="h-4 w-4" />
              保存
            </Button>
            <Button type="button" size="sm" variant="secondary" onClick={cancelAgentEdit} disabled={savingAgent}>
              <X className="h-4 w-4" />
              取消
            </Button>
          </div>
        </TD>
      </TR>
    );
  }

  return (
    <>
      <PageHeader title="航司配置" description="维护提单前三位前缀对应的航司识别规则和航司代理信息" />

      <Panel
        title="航司识别配置"
        action={
          <Button size="sm" onClick={startNewMapping} disabled={editingMappingId !== null || savingMapping}>
            <Plus className="h-4 w-4" />
            新建航司
          </Button>
        }
      >
        {mappingError ? (
          <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{mappingError}</div>
        ) : null}
        <Table>
          <THead>
            <TR>
              <TH>前缀</TH>
              <TH>航司代码</TH>
              <TH>航司名称</TH>
              <TH>英文名</TH>
              <TH>适配器</TH>
              <TH>状态</TH>
              <TH>备注</TH>
              <TH>操作</TH>
            </TR>
          </THead>
          <TBody>
            {editingMappingId === "new" ? mappingDraftRow("new-mapping", false) : null}
            {mappings.map((item) => {
              const carrier = carrierByCode.get(item.carrier_code);
              if (editingMappingId === item.id) {
                return mappingDraftRow(`mapping-${item.id}`, true);
              }
              return (
                <TR key={item.id}>
                  <TD className="font-medium">{item.prefix}</TD>
                  <TD>{item.carrier_code}</TD>
                  <TD>{carrier?.carrier_name || "-"}</TD>
                  <TD>{carrier?.carrier_name_en || "-"}</TD>
                  <TD>{carrierAdapterLabels[item.adapter_code] || item.adapter_code}</TD>
                  <TD>
                    <Badge variant={item.enabled ? "green" : "gray"}>{item.enabled ? "启用" : "停用"}</Badge>
                  </TD>
                  <TD>{item.remark || "-"}</TD>
                  <TD>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => editMapping(item)}
                      disabled={editingMappingId !== null || savingMapping}
                    >
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

      <Panel
        title="航司代理"
        className="mt-4"
        action={
          <Button size="sm" onClick={startNewAgent} disabled={editingAgentId !== null || savingAgent}>
            <Plus className="h-4 w-4" />
            新建航代
          </Button>
        }
      >
        {agentError ? (
          <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{agentError}</div>
        ) : null}
        <Table>
          <THead>
            <TR>
              <TH>航司</TH>
              <TH>代理名</TH>
              <TH>联系人</TH>
              <TH>电话</TH>
              <TH>邮箱</TH>
              <TH>状态</TH>
              <TH>备注</TH>
              <TH>操作</TH>
            </TR>
          </THead>
          <TBody>
            {editingAgentId === "new" ? agentDraftRow("new-agent", false) : null}
            {agents.map((item) => {
              if (editingAgentId === item.id) {
                return agentDraftRow(`agent-${item.id}`, true);
              }
              return (
                <TR key={item.id}>
                  <TD className="font-medium">{item.carrier_code}</TD>
                  <TD>{item.agent_name}</TD>
                  <TD>{item.contact_person || "-"}</TD>
                  <TD>{item.contact_phone || "-"}</TD>
                  <TD>
                    {item.contact_emails ? (
                      <div className="max-w-56 whitespace-pre-wrap break-all text-xs leading-5 text-slate-700">
                        {item.contact_emails}
                      </div>
                    ) : (
                      "-"
                    )}
                  </TD>
                  <TD>
                    <Badge variant={item.enabled ? "green" : "gray"}>{item.enabled ? "启用" : "停用"}</Badge>
                  </TD>
                  <TD>{item.remark || "-"}</TD>
                  <TD>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => editAgent(item)}
                      disabled={editingAgentId !== null || savingAgent}
                    >
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
    </>
  );
}
