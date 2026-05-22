"use client";

import { Fragment, useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Clock, RefreshCw, Users, Wifi, WifiOff } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { roleLabels } from "@/lib/constants";
import { apiClient } from "@/lib/client-api";
import { cn, formatDateTime } from "@/lib/utils";
import type { PresenceSessionStatus, PresenceUserSession, PresenceUserStatus } from "@/lib/types";

const REFRESH_INTERVAL_MS = 30_000;

const statusLabels: Record<PresenceUserStatus["status"], string> = {
  online: "在线",
  offline: "离线",
  disabled: "停用"
};

const sessionStatusLabels: Record<PresenceSessionStatus, string> = {
  online: "在线中",
  logged_out: "正常退出",
  timeout: "超时离线"
};

function formatDuration(seconds: number) {
  if (seconds < 60) return `${seconds} 秒`;
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const parts = [];
  if (days) parts.push(`${days} 天`);
  if (hours) parts.push(`${hours} 小时`);
  parts.push(`${minutes} 分钟`);
  return parts.join(" ");
}

function formatAge(seconds?: number | null) {
  if (seconds === null || seconds === undefined) return "-";
  if (seconds < 60) return `${seconds} 秒前`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)} 分钟前`;
  return `${Math.floor(seconds / 3600)} 小时前`;
}

function StatusBadge({ status }: { status: PresenceUserStatus["status"] }) {
  const variant = status === "online" ? "green" : status === "disabled" ? "gray" : "amber";
  return <Badge variant={variant}>{statusLabels[status]}</Badge>;
}

function SessionStatusBadge({ status }: { status: PresenceSessionStatus }) {
  const variant = status === "online" ? "green" : status === "timeout" ? "amber" : "gray";
  return <Badge variant={variant}>{sessionStatusLabels[status]}</Badge>;
}

export default function PresencePage() {
  const [users, setUsers] = useState<PresenceUserStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sessionUser, setSessionUser] = useState<PresenceUserStatus | null>(null);
  const [sessions, setSessions] = useState<PresenceUserSession[]>([]);
  const [sessionLoading, setSessionLoading] = useState(false);
  const [sessionError, setSessionError] = useState("");
  const rowRefs = useRef(new Map<number, HTMLTableRowElement>());
  const rowPositions = useRef(new Map<number, number>());

  const loadUsers = useCallback(async () => {
    try {
      const data = await apiClient.get<PresenceUserStatus[]>("/presence/users");
      setUsers(data);
      setError("");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "读取用户在线状态失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const initialTimer = window.setTimeout(() => {
      void loadUsers();
    }, 0);
    const timer = window.setInterval(() => {
      void loadUsers();
    }, REFRESH_INTERVAL_MS);
    return () => {
      window.clearTimeout(initialTimer);
      window.clearInterval(timer);
    };
  }, [loadUsers]);

  useLayoutEffect(() => {
    const previous = rowPositions.current;
    const next = new Map<number, number>();
    rowRefs.current.forEach((node, id) => {
      const top = node.getBoundingClientRect().top;
      next.set(id, top);
      const oldTop = previous.get(id);
      if (oldTop === undefined) return;
      const delta = oldTop - top;
      if (!delta) return;
      node.style.transform = `translateY(${delta}px)`;
      node.style.transition = "transform 0s";
      window.requestAnimationFrame(() => {
        node.style.transform = "";
        node.style.transition = "transform 260ms ease";
      });
    });
    rowPositions.current = next;
  }, [users]);

  async function openSessions(user: PresenceUserStatus) {
    setSessionUser(user);
    setSessions([]);
    setSessionError("");
    setSessionLoading(true);
    try {
      const data = await apiClient.get<PresenceUserSession[]>(`/presence/users/${user.id}/sessions?days=30`);
      setSessions(data);
    } catch (exc) {
      setSessionError(exc instanceof Error ? exc.message : "读取上线时段失败");
    } finally {
      setSessionLoading(false);
    }
  }

  const onlineUsers = users.filter((user) => user.online);
  const offlineUsers = users.filter((user) => !user.online);
  const onlineCount = onlineUsers.length;
  const offlineCount = users.filter((user) => user.status === "offline").length;
  const disabledCount = users.filter((user) => user.status === "disabled").length;

  return (
    <>
      <PageHeader
        title="在线状态"
        description="按权限和实时在线状态查看系统用户"
        action={
          <Button variant="secondary" onClick={() => void loadUsers()}>
            <RefreshCw className="h-4 w-4" />
            刷新
          </Button>
        }
      />
      {error ? <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
      <div className="mb-4 grid gap-4 md:grid-cols-3">
        <Panel className="border-emerald-100" title="在线用户">
          <div className="flex items-center justify-between">
            <div className="text-3xl font-semibold text-slate-950">{onlineCount}</div>
            <Wifi className="h-5 w-5 text-emerald-600" />
          </div>
        </Panel>
        <Panel className="border-amber-100" title="离线用户">
          <div className="flex items-center justify-between">
            <div className="text-3xl font-semibold text-slate-950">{offlineCount}</div>
            <WifiOff className="h-5 w-5 text-amber-600" />
          </div>
        </Panel>
        <Panel title="停用用户">
          <div className="flex items-center justify-between">
            <div className="text-3xl font-semibold text-slate-950">{disabledCount}</div>
            <Users className="h-5 w-5 text-slate-500" />
          </div>
        </Panel>
      </div>

      <Panel title="用户列表">
        {users.length ? (
          <Table>
            <THead>
              <TR>
                <TH>用户</TH>
                <TH>权限</TH>
                <TH>状态</TH>
                <TH>最后在线</TH>
                <TH>最后登录</TH>
                <TH>心跳间隔</TH>
              </TR>
            </THead>
            <TBody>
              {[
                { key: "online", label: "在线用户", count: onlineUsers.length, rows: onlineUsers },
                { key: "offline", label: "离线用户", count: offlineUsers.length, rows: offlineUsers }
              ].map((section) => (
                <Fragment key={section.key}>
                  <TR key={`${section.key}-header`} className="bg-slate-50 hover:bg-slate-50">
                    <TD colSpan={6} className="h-9 text-xs font-semibold text-slate-500">
                      {section.label} · {section.count}
                    </TD>
                  </TR>
                  {section.rows.map((user) => (
                    <TR
                      key={user.id}
                      ref={(node) => {
                        if (node) rowRefs.current.set(user.id, node);
                        else rowRefs.current.delete(user.id);
                      }}
                      className={cn("bg-white transition-colors", user.online && "bg-emerald-50/40")}
                    >
                      <TD>
                        <button
                          type="button"
                          onClick={() => void openSessions(user)}
                          className="text-left font-medium text-purple-800 hover:text-purple-950 hover:underline"
                        >
                          {user.display_name || user.username}
                        </button>
                        <div className="text-xs text-slate-500">{user.username}</div>
                      </TD>
                      <TD>
                        <div className="flex flex-wrap gap-1">
                          {user.roles.length ? (
                            user.roles.map((role) => <Badge key={role.code}>{roleLabels[role.code] || role.code}</Badge>)
                          ) : user.primary_role ? (
                            <Badge>{roleLabels[user.primary_role] || user.primary_role}</Badge>
                          ) : (
                            <Badge variant="gray">无角色</Badge>
                          )}
                        </div>
                      </TD>
                      <TD><StatusBadge status={user.status} /></TD>
                      <TD>{formatDateTime(user.last_seen_at)}</TD>
                      <TD>{formatDateTime(user.last_login_at)}</TD>
                      <TD>{formatAge(user.last_seen_age_seconds)}</TD>
                    </TR>
                  ))}
                </Fragment>
              ))}
            </TBody>
          </Table>
        ) : loading ? (
          <div className="py-10 text-center text-sm text-slate-500">正在加载用户状态...</div>
        ) : (
          <EmptyState title="暂无用户" description="创建用户后会显示在这里。" />
        )}
      </Panel>

      <Dialog
        open={Boolean(sessionUser)}
        onOpenChange={(open) => {
          if (!open) {
            setSessionUser(null);
            setSessions([]);
            setSessionError("");
          }
        }}
      >
        <DialogContent className="w-[min(920px,calc(100vw-32px))]">
          <DialogTitle className="text-base font-semibold text-slate-950">
            {sessionUser ? `${sessionUser.display_name || sessionUser.username} 的上线时段` : "上线时段"}
          </DialogTitle>
          <div className="mt-1 flex items-center gap-2 text-sm text-slate-500">
            <Clock className="h-4 w-4" />
            最近 30 天
          </div>
          {sessionError ? <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{sessionError}</div> : null}
          <div className="mt-4">
            {sessions.length ? (
              <Table>
                <THead>
                  <TR>
                    <TH>开始时间</TH>
                    <TH>结束时间</TH>
                    <TH>持续时长</TH>
                    <TH>状态</TH>
                    <TH>IP</TH>
                    <TH>客户端</TH>
                  </TR>
                </THead>
                <TBody>
                  {sessions.map((item) => (
                    <TR key={item.id}>
                      <TD>{formatDateTime(item.login_at)}</TD>
                      <TD>{item.status === "online" ? "在线中" : formatDateTime(item.effective_logout_at || item.logout_at)}</TD>
                      <TD>{formatDuration(item.duration_seconds)}</TD>
                      <TD><SessionStatusBadge status={item.status} /></TD>
                      <TD>{item.ip_address || "-"}</TD>
                      <TD className="max-w-[260px] truncate" title={item.user_agent || undefined}>{item.user_agent || "-"}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            ) : sessionLoading ? (
              <div className="py-10 text-center text-sm text-slate-500">正在加载上线时段...</div>
            ) : (
              <EmptyState title="暂无上线时段" description="该用户最近 30 天暂无登录记录。" />
            )}
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
