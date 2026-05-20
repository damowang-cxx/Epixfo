"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { UserPlus } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PageHeader } from "@/components/ui/page-header";
import { Panel } from "@/components/ui/panel";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useAuth } from "@/components/layout/auth-provider";
import { roleLabels, roleOptions } from "@/lib/constants";
import { apiClient } from "@/lib/client-api";
import { formatDateTime } from "@/lib/utils";
import type { RoleCode, User } from "@/lib/types";

export default function UsersPage() {
  const { hasRole } = useAuth();
  const [users, setUsers] = useState<User[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [role, setRole] = useState<RoleCode>("customer_service");
  const [error, setError] = useState("");

  const creatableRoles = useMemo(() => {
    if (hasRole("admin")) return roleOptions;
    return roleOptions.filter((item) => item.value === "customer_service" || item.value === "customs_staff");
  }, [hasRole]);

  const load = useCallback(() => {
    apiClient.get<User[]>("/users").then(setUsers).catch((exc) => setError(exc instanceof Error ? exc.message : "读取用户失败"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function createUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    try {
      await apiClient.post<User>("/users", {
        username,
        password,
        display_name: displayName || null,
        role_codes: [role]
      });
      setUsername("");
      setPassword("");
      setDisplayName("");
      load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "创建用户失败");
    }
  }

  async function setActive(id: number, active: boolean) {
    await apiClient.post<User>(`/users/${id}/${active ? "enable" : "disable"}`);
    load();
  }

  return (
    <>
      <PageHeader title="用户管理" description="维护系统用户和角色" />
      {error ? <div className="mb-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</div> : null}
      <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
        <Panel title="用户列表">
          {users.length ? (
            <Table>
              <THead><TR><TH>用户名</TH><TH>姓名</TH><TH>角色</TH><TH>状态</TH><TH>最后在线</TH><TH>操作</TH></TR></THead>
              <TBody>
                {users.map((user) => (
                  <TR key={user.id}>
                    <TD className="font-medium">{user.username}</TD>
                    <TD>{user.display_name || "-"}</TD>
                    <TD>
                      <div className="flex flex-wrap gap-1">
                        {user.roles.map((item) => <Badge key={item.code}>{roleLabels[item.code]}</Badge>)}
                      </div>
                    </TD>
                    <TD>{user.is_active ? "启用" : "停用"}</TD>
                    <TD>{formatDateTime(user.last_seen_at)}</TD>
                    <TD>
                      <Button variant="secondary" size="sm" onClick={() => setActive(user.id, !user.is_active)}>
                        {user.is_active ? "停用" : "启用"}
                      </Button>
                    </TD>
                  </TR>
                ))}
              </TBody>
            </Table>
          ) : (
            <EmptyState title="暂无用户" description="创建用户后会显示在这里。" />
          )}
        </Panel>
        <Panel title="新建用户">
          <form onSubmit={createUser} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="username">用户名</Label>
              <Input id="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">密码</Label>
              <Input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} required minLength={6} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="display_name">显示名</Label>
              <Input id="display_name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label>角色</Label>
              <Select value={role} onValueChange={(value) => setRole(value as RoleCode)}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  {creatableRoles.map((item) => <SelectItem key={item.value} value={item.value}>{item.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <Button className="w-full">
              <UserPlus className="h-4 w-4" />
              创建用户
            </Button>
          </form>
        </Panel>
      </div>
    </>
  );
}
