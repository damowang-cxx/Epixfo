"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, ClipboardList, RadioTower, Users } from "lucide-react";
import { AlertLevelBadge, LifecycleBadge } from "@/components/ui/status-badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Panel } from "@/components/ui/panel";
import { PageHeader } from "@/components/ui/page-header";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { formatDateTime } from "@/lib/utils";
import type { Alert, OnlineUser, PageResponse, Waybill } from "@/lib/types";

export default function DashboardPage() {
  const [waybills, setWaybills] = useState<PageResponse<Waybill> | null>(null);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);

  useEffect(() => {
    apiClient.get<PageResponse<Waybill>>("/waybills?page_size=5").then(setWaybills).catch(() => undefined);
    apiClient.get<Alert[]>("/alerts?status=active").then(setAlerts).catch(() => undefined);
    apiClient.get<OnlineUser[]>("/presence/online-users").then(setOnlineUsers).catch(() => undefined);
  }, []);

  const cards = [
    { label: "运单总数", value: waybills?.total ?? "-", icon: ClipboardList, href: "/waybills" },
    { label: "活动异常", value: alerts.length, icon: AlertTriangle, href: "/alerts" },
    { label: "在线用户", value: onlineUsers.length, icon: Users, href: "/presence" },
    { label: "监控任务", value: "手动", icon: RadioTower, href: "/monitor" }
  ];

  return (
    <>
      <PageHeader title="总览" description="航空头程运单监控系统运行概况" />
      <div className="grid gap-4 md:grid-cols-4">
        {cards.map((card) => {
          const Icon = card.icon;
          return (
            <Link key={card.label} href={card.href} className="rounded-md border border-slate-200 bg-white p-4 hover:border-purple-300">
              <div className="flex items-center justify-between">
                <div className="text-sm text-slate-500">{card.label}</div>
                <Icon className="h-4 w-4 text-purple-700" />
              </div>
              <div className="mt-3 text-2xl font-semibold text-slate-950">{card.value}</div>
            </Link>
          );
        })}
      </div>
      <div className="mt-4 grid gap-4 xl:grid-cols-2">
        <Panel title="最近运单" action={<Button asChild variant="secondary" size="sm"><Link href="/waybills">查看全部</Link></Button>}>
          {(waybills?.items || []).length ? (
            <Table>
              <THead>
                <TR>
                  <TH>运单号</TH>
                  <TH>目的港</TH>
                  <TH>生命周期</TH>
                  <TH>下次查询</TH>
                </TR>
              </THead>
              <TBody>
                {(waybills?.items || []).map((item) => (
                  <TR key={item.id}>
                    <TD className="font-medium"><Link href={`/waybills/${item.id}`}>{item.waybill_no}</Link></TD>
                    <TD>{item.destination_port || "-"}</TD>
                    <TD><LifecycleBadge value={item.lifecycle_status} /></TD>
                    <TD>{formatDateTime(item.next_query_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState title="暂无运单" description="创建第一票运单后，这里会显示最新记录。" />
          )}
        </Panel>
        <Panel title="活动异常" action={<Button asChild variant="secondary" size="sm"><Link href="/alerts">处理异常</Link></Button>}>
          {alerts.length ? (
            <Table>
              <THead>
                <TR>
                  <TH>标题</TH>
                  <TH>等级</TH>
                  <TH>类型</TH>
                  <TH>时间</TH>
                </TR>
              </THead>
              <TBody>
                {alerts.slice(0, 5).map((item) => (
                  <TR key={item.id}>
                    <TD className="font-medium">{item.title}</TD>
                    <TD><AlertLevelBadge value={item.alert_level} /></TD>
                    <TD>{item.alert_type}</TD>
                    <TD>{formatDateTime(item.created_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState title="暂无活动异常" description="当前没有需要处理的系统异常。" />
          )}
        </Panel>
      </div>
    </>
  );
}
