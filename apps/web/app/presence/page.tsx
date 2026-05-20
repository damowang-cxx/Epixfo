"use client";

import { useCallback, useEffect, useState } from "react";
import { Activity, Clock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { apiClient } from "@/lib/client-api";
import { formatDateTime } from "@/lib/utils";
import type { DailyOnlineStat, OnlineUser } from "@/lib/types";

function formatSeconds(seconds: number) {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  return `${hours}小时 ${minutes}分钟`;
}

export default function PresencePage() {
  const [onlineUsers, setOnlineUsers] = useState<OnlineUser[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("");
  const [stats, setStats] = useState<DailyOnlineStat[]>([]);
  const [message, setMessage] = useState("");

  const loadOnlineUsers = useCallback(() => {
    apiClient.get<OnlineUser[]>("/presence/online-users").then(setOnlineUsers);
  }, []);

  useEffect(() => {
    loadOnlineUsers();
  }, [loadOnlineUsers]);

  async function sendHeartbeat() {
    await apiClient.post<{ user_id: number; last_seen_at: string }>("/presence/heartbeat");
    setMessage("已发送当前账号心跳。");
    loadOnlineUsers();
  }

  async function loadStats() {
    if (!selectedUserId) return;
    const data = await apiClient.get<DailyOnlineStat[]>(`/presence/users/${selectedUserId}/daily-stats`);
    setStats(data);
  }

  return (
    <>
      <PageHeader
        title="在线状态"
        description="查看当前在线用户和每日在线时长"
        action={
          <Button onClick={sendHeartbeat}>
            <Activity className="h-4 w-4" />
            发送心跳
          </Button>
        }
      />
      {message ? <div className="mb-4 rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">{message}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[1fr_420px]">
        <Panel title="在线用户">
          {onlineUsers.length ? (
            <Table>
              <THead><TR><TH>用户ID</TH><TH>用户名</TH><TH>显示名</TH><TH>状态</TH><TH>最后心跳</TH></TR></THead>
              <TBody>
                {onlineUsers.map((user) => (
                  <TR key={user.id}>
                    <TD>{user.id}</TD>
                    <TD className="font-medium">{user.username}</TD>
                    <TD>{user.display_name || "-"}</TD>
                    <TD><Badge variant="green">在线</Badge></TD>
                    <TD>{formatDateTime(user.last_seen_at)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState title="暂无在线用户" description="用户最近 3 分钟内发送心跳后会显示为在线。" />
          )}
        </Panel>
        <Panel title="每日在线时长">
          <div className="mb-4 grid gap-2 sm:grid-cols-[1fr_96px]">
            <div className="space-y-1.5">
              <Label htmlFor="selected_user_id">用户ID</Label>
              <Input id="selected_user_id" value={selectedUserId} onChange={(event) => setSelectedUserId(event.target.value)} placeholder="例如 1" />
            </div>
            <div className="flex items-end">
              <Button className="w-full" variant="secondary" onClick={loadStats}>
                <Clock className="h-4 w-4" />
                查询
              </Button>
            </div>
          </div>
          {stats.length ? (
            <Table>
              <THead><TR><TH>日期</TH><TH>在线时长</TH></TR></THead>
              <TBody>
                {stats.map((item) => (
                  <TR key={`${item.user_id}-${item.stat_date}`}>
                    <TD>{item.stat_date}</TD>
                    <TD>{formatSeconds(item.total_online_seconds)}</TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState title="暂无统计" description="输入用户ID后可查看每日在线时长。" />
          )}
        </Panel>
      </div>
    </>
  );
}
