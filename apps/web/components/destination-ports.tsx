"use client";

import { useCallback, useEffect, useState } from "react";
import { CircleAlert, Plus } from "lucide-react";
import type { WarehouseReceipt } from "@/lib/types";
import { apiClient } from "@/lib/client-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export function useDestinationPorts() {
  const [ports, setPorts] = useState<string[]>([]);
  const [error, setError] = useState("");
  const reload = useCallback(async () => {
    try {
      const items = await apiClient.get<{ code: string }[]>("/destination-ports");
      setPorts(items.map((item) => item.code));
      setError("");
    } catch (error) {
      setError(error instanceof Error ? error.message : "目的港加载失败");
    }
  }, []);
  useEffect(() => {
    const timer = window.setTimeout(() => { void reload(); }, 0);
    return () => window.clearTimeout(timer);
  }, [reload]);
  return { ports, error, reload };
}

export function DestinationPortSelect({ ports, value, onChange, id, emptyLabel = "选择目的港", disabled = false }: {
  ports: string[]; value: string; onChange: (value: string) => void;
  id?: string; emptyLabel?: string; disabled?: boolean;
}) {
  return <Select value={value || "__none__"} onValueChange={(value) => onChange(value === "__none__" ? "" : value)} disabled={disabled}>
    <SelectTrigger id={id} aria-label="目的港"><SelectValue placeholder={emptyLabel} /></SelectTrigger>
    <SelectContent>
      <SelectItem value="__none__">{emptyLabel}</SelectItem>
      {value && !ports.includes(value) ? <SelectItem value={value}>{value}（未配置）</SelectItem> : null}
      {ports.map((code) => <SelectItem key={code} value={code}>{code}</SelectItem>)}
    </SelectContent>
  </Select>;
}

export function DestinationPortManager() {
  const { ports, error: loadError, reload } = useDestinationPorts();
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  async function add() {
    const value = code.trim().toUpperCase();
    if (!/^[A-Z0-9]{3,16}$/.test(value)) { setError("请输入 3～16 位字母或数字目的港代码"); return; }
    setSaving(true);
    setError("");
    try {
      await apiClient.post("/destination-ports", { code: value });
      setCode("");
      await reload();
    } catch (error) { setError(error instanceof Error ? error.message : "目的港添加失败"); }
    finally { setSaving(false); }
  }
  return <Panel title="目的港管理" className="mb-4">
    <div className="flex flex-wrap items-center gap-3">
      {ports.map((port) => <span key={port} className="font-medium">{port}</span>)}
      <Input aria-label="新增目的港代码" placeholder="目的港代码" className="w-40" maxLength={16} value={code}
        disabled={saving} onChange={(event) => setCode(event.target.value.toUpperCase())}
        onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); void add(); } }} />
      <Button type="button" size="icon" title="增加目的港" aria-label="增加目的港" disabled={saving} onClick={() => void add()}><Plus className="h-4 w-4" /></Button>
    </div>
    {error || loadError ? <p role="alert" className="mt-2 text-sm text-red-700">{error || loadError}</p> : null}
  </Panel>;
}

export function receiptDestinationPorts(receipt: WarehouseReceipt): string[] {
  return receipt.destination_ports ?? receipt.destination_ports_override ?? receipt.channel_tags ?? [];
}

export function ReceiptDestinationEditor({ receipt, ports, onSaved }: {
  receipt: WarehouseReceipt; ports: string[]; onSaved: (receipt: WarehouseReceipt) => void;
}) {
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const destinations = receiptDestinationPorts(receipt);
  const override = receipt.destination_ports_override;
  const value = override == null ? "__auto__" : override[0] || "__none__";
  async function save(value: string) {
    setSaving(true);
    setError("");
    try {
      const result = await apiClient.patch<WarehouseReceipt>(`/warehouse-receipts/${receipt.id}/destination`, {
        destination_ports: value === "__auto__" ? null : value === "__none__" ? [] : [value]
      });
      onSaved(result);
    } catch (error) { setError(error instanceof Error ? error.message : "目的港保存失败"); }
    finally { setSaving(false); }
  }
  return <div className="min-w-0" onClick={(event) => event.stopPropagation()}>
    <div className="flex items-center gap-1">
      {!destinations.length ? <span title="请为该文件选择目的港归属" aria-label="缺少目的港归属"><CircleAlert className="h-4 w-4 shrink-0 text-amber-600" /></span> : null}
      <Select value={value} onValueChange={(value) => void save(value)} disabled={saving}>
        <SelectTrigger className="h-8 w-48" aria-label={`${receipt.warehouse_no} 目的港归属`}><SelectValue /></SelectTrigger>
        <SelectContent>
          <SelectItem value="__auto__">自动识别：{(receipt.channel_tags || []).join(" / ") || "未识别"}</SelectItem>
          <SelectItem value="__none__">未归属</SelectItem>
          {ports.map((port) => <SelectItem key={port} value={port}>{port}</SelectItem>)}
        </SelectContent>
      </Select>
    </div>
    {error ? <p role="alert" className="mt-1 max-w-64 text-xs text-red-700">{error}</p> : null}
  </div>;
}
