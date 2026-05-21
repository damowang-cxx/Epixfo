"use client";

import { useCallback, useEffect, useState } from "react";
import { CheckCircle2, Eye, ShieldCheck } from "lucide-react";
import { AlertLevelBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { compact, formatDateTime } from "@/lib/utils";
import type { Alert, AlertStatus } from "@/lib/types";

export default function AlertsPage() {
  const [status, setStatus] = useState<AlertStatus | "all">("active");
  const [items, setItems] = useState<Alert[]>([]);

  const load = useCallback(() => {
    apiClient.get<Alert[]>(`/alerts${status === "all" ? "" : `?status=${status}`}`).then(setItems);
  }, [status]);

  useEffect(() => {
    load();
  }, [load]);

  async function transition(id: number, action: "acknowledge" | "resolve" | "ignore") {
    await apiClient.post<Alert>(`/alerts/${id}/${action}`);
    load();
  }

  return (
    <>
      <PageHeader title="异常中心" description="处理提单查询、航班变化和官方数据差异异常" />
      <Panel>
        <div className="mb-4 w-48">
          <Select value={status} onValueChange={(value) => setStatus(value as AlertStatus | "all")}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="active">活动异常</SelectItem>
              <SelectItem value="acknowledged">已确认</SelectItem>
              <SelectItem value="resolved">已解决</SelectItem>
              <SelectItem value="ignored">已忽略</SelectItem>
              <SelectItem value="all">全部</SelectItem>
            </SelectContent>
          </Select>
        </div>
        {items.length ? (
          <Table>
            <THead>
              <TR><TH>标题</TH><TH>提单ID</TH><TH>类型</TH><TH>等级</TH><TH>状态</TH><TH>描述</TH><TH>时间</TH><TH>操作</TH></TR>
            </THead>
            <TBody>
              {items.map((item) => (
                <TR key={item.id}>
                  <TD className="font-medium">{item.title}</TD>
                  <TD>{item.waybill_id}</TD>
                  <TD>{item.alert_type}</TD>
                  <TD><AlertLevelBadge value={item.alert_level} /></TD>
                  <TD>{item.status}</TD>
                  <TD>{compact(item.description)}</TD>
                  <TD>{formatDateTime(item.created_at)}</TD>
                  <TD>
                    <div className="flex flex-wrap gap-1">
                      <Button variant="secondary" size="sm" onClick={() => transition(item.id, "acknowledge")}>
                        <Eye className="h-4 w-4" />
                        确认
                      </Button>
                      <Button variant="secondary" size="sm" onClick={() => transition(item.id, "resolve")}>
                        <CheckCircle2 className="h-4 w-4" />
                        解决
                      </Button>
                      <Button variant="ghost" size="sm" onClick={() => transition(item.id, "ignore")}>
                        <ShieldCheck className="h-4 w-4" />
                        忽略
                      </Button>
                    </div>
                  </TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ) : (
          <EmptyState title="暂无异常" description="当前筛选条件下没有异常记录。" />
        )}
      </Panel>
    </>
  );
}
