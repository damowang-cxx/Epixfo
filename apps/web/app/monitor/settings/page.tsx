"use client";

import { useEffect, useState } from "react";
import { Play, Save } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { apiClient } from "@/lib/client-api";
import { carrierAdapterOptions } from "@/lib/constants";
import { formatDateTime } from "@/lib/utils";
import type { AutoFlightQuerySettings } from "@/lib/types";

type SettingsDraft = {
  fallbackEnabled: boolean;
  fallbackAdapterCode: string;
  queryIntervalHours: string;
  scanLimit: string;
};

function draftFromSettings(settings: AutoFlightQuerySettings): SettingsDraft {
  return {
    fallbackEnabled: settings.fallback_enabled,
    fallbackAdapterCode: settings.fallback_adapter_code,
    queryIntervalHours: String(settings.query_interval_hours),
    scanLimit: String(settings.scan_limit)
  };
}

export default function AutoFlightQuerySettingsPage() {
  const [settings, setSettings] = useState<AutoFlightQuerySettings | null>(null);
  const [draft, setDraft] = useState<SettingsDraft | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [processed, setProcessed] = useState<number | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function loadSettings() {
      setLoading(true);
      setError("");
      try {
        const result = await apiClient.get<AutoFlightQuerySettings>("/monitor/settings");
        if (cancelled) return;
        setSettings(result);
        setDraft(draftFromSettings(result));
      } catch (exc) {
        if (cancelled) return;
        setError(exc instanceof Error ? exc.message : "设置加载失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadSettings();
    return () => {
      cancelled = true;
    };
  }, []);

  async function save() {
    if (!draft) return;
    setSaving(true);
    setError("");
    setMessage("");
    try {
      const result = await apiClient.patch<AutoFlightQuerySettings>("/monitor/settings", {
        fallback_enabled: draft.fallbackEnabled,
        fallback_adapter_code: draft.fallbackAdapterCode,
        query_interval_hours: Number(draft.queryIntervalHours),
        scan_limit: Number(draft.scanLimit)
      });
      setSettings(result);
      setDraft(draftFromSettings(result));
      setMessage("自动查询设置已保存");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }

  async function runMonitor() {
    const limit = draft?.scanLimit || settings?.scan_limit || 50;
    setRunning(true);
    setError("");
    setProcessed(null);
    try {
      const result = await apiClient.post<{ processed: number }>(
        `/monitor/due-waybills/run?limit=${encodeURIComponent(limit)}`
      );
      setProcessed(result.processed);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "扫描失败");
    } finally {
      setRunning(false);
    }
  }

  const disabled = loading || saving || !draft;

  return (
    <>
      <PageHeader title="自动航班查询设置" description="管理提单自动查询调度和默认适配器失败后的兜底流程" />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_360px]">
        <Panel title="查询流程">
          {draft ? (
            <div className="grid gap-4 lg:grid-cols-2">
              <label className="flex min-h-9 items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={draft.fallbackEnabled}
                  onChange={(event) => setDraft({ ...draft, fallbackEnabled: event.target.checked })}
                  disabled={disabled}
                  className="h-4 w-4 rounded border-slate-300"
                />
                默认适配器失败后启用通用查询
              </label>
              <div className="space-y-1.5">
                <Label htmlFor="fallback-adapter">兜底适配器</Label>
                <Select
                  value={draft.fallbackAdapterCode}
                  onValueChange={(value) => setDraft({ ...draft, fallbackAdapterCode: value })}
                  disabled={disabled || !draft.fallbackEnabled}
                >
                  <SelectTrigger id="fallback-adapter">
                    <SelectValue />
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
                <Label htmlFor="query-interval">查询间隔（小时）</Label>
                <Input
                  id="query-interval"
                  type="number"
                  min={1}
                  max={24}
                  value={draft.queryIntervalHours}
                  onChange={(event) => setDraft({ ...draft, queryIntervalHours: event.target.value })}
                  disabled={disabled}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="scan-limit">单轮扫描上限</Label>
                <Input
                  id="scan-limit"
                  type="number"
                  min={1}
                  max={500}
                  value={draft.scanLimit}
                  onChange={(event) => setDraft({ ...draft, scanLimit: event.target.value })}
                  disabled={disabled}
                />
              </div>
              <div className="lg:col-span-2">
                <Button onClick={save} disabled={disabled}>
                  <Save className="h-4 w-4" />
                  {saving ? "保存中..." : "保存设置"}
                </Button>
              </div>
            </div>
          ) : (
            <div className="text-sm text-slate-500">{loading ? "正在加载..." : "暂无设置"}</div>
          )}
        </Panel>

        <div className="space-y-4">
          <Panel title="当前状态">
            <div className="space-y-3 text-sm text-slate-700">
              <div className="flex items-center justify-between">
                <span>后台调度</span>
                <Badge variant={settings?.scheduler_process_enabled ? "green" : "amber"}>
                  {settings?.scheduler_process_enabled ? "已启用" : "进程开关关闭"}
                </Badge>
              </div>
              <div className="flex items-center justify-between">
                <span>调度扫描间隔</span>
                <span>{settings ? `${settings.scheduler_interval_seconds} 秒` : "-"}</span>
              </div>
              <div className="flex items-center justify-between">
                <span>首次自动查询</span>
                <span>计划航班日期前 3 天</span>
              </div>
              <div className="flex items-center justify-between">
                <span>更新时间</span>
                <span>{formatDateTime(settings?.updated_at)}</span>
              </div>
            </div>
          </Panel>

          <Panel title="手动扫描">
            <div className="space-y-3">
              <Button variant="secondary" onClick={runMonitor} disabled={running || !draft}>
                <Play className="h-4 w-4" />
                {running ? "扫描中..." : "运行扫描"}
              </Button>
              {processed !== null ? (
                <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                  本次处理 {processed} 票到期提单。
                </div>
              ) : null}
            </div>
          </Panel>
        </div>
      </div>
      {message ? <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{message}</div> : null}
      {error ? <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
    </>
  );
}
