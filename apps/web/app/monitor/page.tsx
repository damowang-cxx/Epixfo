"use client";

import { useState } from "react";
import { Play, RadioTower } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { apiClient } from "@/lib/client-api";

export default function MonitorPage() {
  const [limit, setLimit] = useState("50");
  const [processed, setProcessed] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  async function runMonitor() {
    setRunning(true);
    setError("");
    try {
      const result = await apiClient.post<{ processed: number }>(`/monitor/due-waybills/run?limit=${encodeURIComponent(limit)}`);
      setProcessed(result.processed);
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "触发监控失败");
    } finally {
      setRunning(false);
    }
  }

  return (
    <>
      <PageHeader title="监控任务" description="手动触发到期提单扫描，便于本地验收和生产排查" />
      <div className="grid gap-4 lg:grid-cols-[420px_1fr]">
        <Panel title="手动扫描">
          <div className="space-y-4">
            <div className="space-y-1.5">
              <Label htmlFor="limit">单次处理上限</Label>
              <Input id="limit" type="number" min={1} max={500} value={limit} onChange={(event) => setLimit(event.target.value)} />
            </div>
            <Button onClick={runMonitor} disabled={running}>
              <Play className="h-4 w-4" />
              {running ? "扫描中..." : "运行扫描"}
            </Button>
            {processed !== null ? (
              <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
                本次处理 {processed} 票到期提单。
              </div>
            ) : null}
            {error ? <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
          </div>
        </Panel>
        <Panel title="调度说明">
          <div className="space-y-3 text-sm leading-6 text-slate-700">
            <div className="flex gap-2">
              <RadioTower className="mt-1 h-4 w-4 shrink-0 text-purple-700" />
              <p>后端调度由配置项 <span className="font-mono text-slate-900">ENABLE_MONITOR_SCHEDULER</span> 控制，可在自动航班查询设置中查看当前状态。</p>
            </div>
            <p>手动扫描会调用后端 <span className="font-mono text-slate-900">/monitor/due-waybills/run</span>，扫描 <span className="font-mono text-slate-900">next_query_at &lt;= now()</span> 的提单，并走同一套查询快照、生命周期和异常规则。</p>
          </div>
        </Panel>
      </div>
    </>
  );
}
