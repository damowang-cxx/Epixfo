"use client";

import { useCallback, useEffect, useState } from "react";
import { ShieldCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { compact, formatDateTime } from "@/lib/utils";
import type { AuditLog } from "@/lib/types";

export default function AuditLogsPage() {
  const [items, setItems] = useState<AuditLog[]>([]);

  const load = useCallback(() => {
    apiClient.get<AuditLog[]>("/audit-logs?limit=100").then(setItems);
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <>
      <PageHeader
        title="审计日志"
        description="查看用户关键操作记录"
        action={
          <Button variant="secondary" onClick={load}>
            <ShieldCheck className="h-4 w-4" />
            刷新
          </Button>
        }
      />
      <Panel>
        {items.length ? (
          <Table>
            <THead><TR><TH>时间</TH><TH>用户ID</TH><TH>动作</TH><TH>对象</TH><TH>对象ID</TH><TH>IP</TH><TH>User-Agent</TH></TR></THead>
            <TBody>
              {items.map((item) => (
                <TR key={item.id}>
                  <TD>{formatDateTime(item.created_at)}</TD>
                  <TD>{compact(item.user_id)}</TD>
                  <TD className="font-medium">{item.action}</TD>
                  <TD>{compact(item.target_type)}</TD>
                  <TD>{compact(item.target_id)}</TD>
                  <TD>{compact(item.ip_address)}</TD>
                  <TD className="max-w-[360px] truncate">{compact(item.user_agent)}</TD>
                </TR>
              ))}
            </TBody>
          </Table>
        ) : (
          <EmptyState title="暂无审计日志" description="发生登录、运单、异常等操作后会写入记录。" />
        )}
      </Panel>
    </>
  );
}
