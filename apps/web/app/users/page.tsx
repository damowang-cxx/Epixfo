"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { Pencil, Trash2, UserPlus, X } from "lucide-react";
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

const routeStaffManagedRoles: RoleCode[] = ["customer_service", "customs_staff"];

function userRoleCodes(user: User) {
  return user.roles.map((item) => item.code);
}

function isRouteStaffManageable(user: User) {
  const roles = userRoleCodes(user);
  return roles.length > 0 && roles.every((role) => routeStaffManagedRoles.includes(role));
}

function firstEditableRole(user: User, fallback: RoleCode) {
  return userRoleCodes(user)[0] || fallback;
}

export default function UsersPage() {
  const { hasRole, user: currentUser } = useAuth();
  const isAdmin = hasRole("admin");
  const [users, setUsers] = useState<User[]>([]);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [role, setRole] = useState<RoleCode>("customer_service");
  const [editingUser, setEditingUser] = useState<User | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [statusUpdatingId, setStatusUpdatingId] = useState<number | null>(null);
  const [deletingUserId, setDeletingUserId] = useState<number | null>(null);

  const creatableRoles = useMemo(() => {
    if (isAdmin) return roleOptions;
    return roleOptions.filter((item) => routeStaffManagedRoles.includes(item.value));
  }, [isAdmin]);

  const load = useCallback(() => {
    apiClient.get<User[]>("/users").then(setUsers).catch((exc) => setError(exc instanceof Error ? exc.message : "读取用户失败"));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  function resetForm() {
    setUsername("");
    setPassword("");
    setDisplayName("");
    setEmail("");
    setPhone("");
    setRole("customer_service");
    setEditingUser(null);
  }

  function startEdit(user: User) {
    setEditingUser(user);
    setUsername(user.username);
    setPassword("");
    setDisplayName(user.display_name || "");
    setEmail(user.email || "");
    setPhone(user.phone || "");
    setRole(firstEditableRole(user, "customer_service"));
    setError("");
  }

  function canManageUser(user: User) {
    return isAdmin || isRouteStaffManageable(user);
  }

  function canDeleteUser(user: User) {
    return user.id !== currentUser?.id && canManageUser(user);
  }

  async function saveUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    setSaving(true);
    try {
      const payload = {
        username,
        display_name: displayName || null,
        email: email || null,
        phone: phone || null,
        role_codes: [role],
        ...(password ? { password } : {})
      };
      if (editingUser) {
        await apiClient.patch<User>(`/users/${editingUser.id}`, payload);
      } else {
        await apiClient.post<User>("/users", { ...payload, password });
      }
      resetForm();
      load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : editingUser ? "保存用户失败" : "创建用户失败");
    } finally {
      setSaving(false);
    }
  }

  async function setActive(id: number, active: boolean) {
    setError("");
    setStatusUpdatingId(id);
    try {
      await apiClient.post<User>(`/users/${id}/${active ? "enable" : "disable"}`);
      load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "更新用户状态失败");
    } finally {
      setStatusUpdatingId(null);
    }
  }

  async function deleteUser(user: User) {
    if (!window.confirm(`确认删除用户 ${user.username}？删除后不可恢复。`)) {
      return;
    }
    setError("");
    setDeletingUserId(user.id);
    try {
      await apiClient.delete<void>(`/users/${user.id}`);
      if (editingUser?.id === user.id) {
        resetForm();
      }
      load();
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "删除用户失败");
    } finally {
      setDeletingUserId(null);
    }
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
                {users.map((user) => {
                  const manageable = canManageUser(user);
                  return (
                    <TR key={user.id}>
                      <TD className="font-medium">{user.username}</TD>
                      <TD>{user.display_name || "-"}</TD>
                      <TD>
                        <div className="flex flex-wrap gap-1">
                          {user.roles.map((item) => <Badge key={item.code}>{roleLabels[item.code]}</Badge>)}
                        </div>
                      </TD>
                      <TD>
                        <Button
                          variant="secondary"
                          size="sm"
                          className={user.is_active ? "border-emerald-200 bg-emerald-50 text-emerald-700 hover:bg-emerald-100" : "border-slate-300 bg-slate-50 text-slate-500 hover:bg-slate-100"}
                          disabled={!manageable || statusUpdatingId === user.id}
                          onClick={() => setActive(user.id, !user.is_active)}
                          aria-label={`${user.is_active ? "停用" : "启用"}用户 ${user.username}`}
                        >
                          {user.is_active ? "启用" : "停用"}
                        </Button>
                      </TD>
                      <TD>{formatDateTime(user.last_seen_at)}</TD>
                      <TD>
                        {manageable ? (
                          <div className="flex flex-wrap gap-2">
                            <Button type="button" variant="ghost" size="sm" onClick={() => startEdit(user)}>
                              <Pencil className="h-4 w-4" />
                              编辑
                            </Button>
                            {canDeleteUser(user) ? (
                              <Button
                                type="button"
                                variant="danger"
                                size="sm"
                                onClick={() => deleteUser(user)}
                                disabled={deletingUserId === user.id}
                              >
                                <Trash2 className="h-4 w-4" />
                                删除
                              </Button>
                            ) : null}
                          </div>
                        ) : (
                          <span className="text-xs text-slate-400">只读</span>
                        )}
                      </TD>
                    </TR>
                  );
                })}
              </TBody>
            </Table>
          ) : (
            <EmptyState title="暂无用户" description="创建用户后会显示在这里。" />
          )}
        </Panel>
        <Panel
          title={editingUser ? "编辑用户" : "新建用户"}
          action={
            editingUser ? (
              <Button type="button" variant="ghost" size="sm" onClick={resetForm}>
                <X className="h-4 w-4" />
                取消编辑
              </Button>
            ) : null
          }
        >
          <form onSubmit={saveUser} className="space-y-3">
            <div className="space-y-1.5">
              <Label htmlFor="username">用户名</Label>
              <Input id="username" value={username} onChange={(event) => setUsername(event.target.value)} required />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="password">{editingUser ? "新密码" : "密码"}</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required={!editingUser}
                minLength={6}
                placeholder={editingUser ? "不修改请留空" : undefined}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="display_name">显示名</Label>
              <Input id="display_name" value={displayName} onChange={(event) => setDisplayName(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="email">邮箱</Label>
              <Input id="email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="phone">电话</Label>
              <Input id="phone" value={phone} onChange={(event) => setPhone(event.target.value)} />
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
            <Button className="w-full" disabled={saving}>
              <UserPlus className="h-4 w-4" />
              {editingUser ? "保存用户" : "创建用户"}
            </Button>
          </form>
        </Panel>
      </div>
    </>
  );
}
