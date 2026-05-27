"use client";

import Image from "next/image";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity,
  AlertTriangle,
  Archive,
  CalendarClock,
  ClipboardList,
  Home,
  Layers,
  LogOut,
  PackageCheck,
  PanelLeftClose,
  PanelLeftOpen,
  Plane,
  RadioTower,
  Search,
  Settings,
  ShieldCheck,
  Users
} from "lucide-react";
import { useEffect, useState, useSyncExternalStore, type ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { AuthProvider, useAuth } from "@/components/layout/auth-provider";
import { roleLabels } from "@/lib/constants";
import { apiClient } from "@/lib/client-api";
import { cn } from "@/lib/utils";
import type { Alert, RoleCode } from "@/lib/types";

const HEARTBEAT_INTERVAL_MS = 30_000;
const CUSTOMS_ALERT_POLL_INTERVAL_MS = 60_000;
const SIDEBAR_COLLAPSED_STORAGE_KEY = "epixfo.sidebarCollapsed";
const SIDEBAR_COLLAPSED_EVENT = "epixfo:sidebar-collapsed-change";
const DISMISSED_CUSTOMS_ALERTS_STORAGE_KEY = "epixfo.dismissedCustomsUploadAlerts";

const navItems: Array<{
  href: string;
  label: string;
  icon: typeof Home;
  roles?: RoleCode[];
}> = [
  { href: "/", label: "总览", icon: Home },
  { href: "/waybills", label: "提单管理", icon: ClipboardList },
  { href: "/prebookings", label: "预排仓", icon: CalendarClock, roles: ["admin", "route_staff"] },
  { href: "/boards", label: "板号管理", icon: Layers, roles: ["admin", "route_staff"] },
  { href: "/warehouse-receipts", label: "未绑定箱号", icon: Archive, roles: ["admin", "route_staff"] },
  { href: "/waybills/lookup", label: "提单速查", icon: Search, roles: ["admin", "route_staff"] },
  { href: "/alerts", label: "异常中心", icon: AlertTriangle },
  { href: "/carriers", label: "航司配置", icon: Plane, roles: ["admin", "route_staff"] },
  { href: "/consignees", label: "收件人管理", icon: PackageCheck, roles: ["admin", "route_staff"] },
  { href: "/users", label: "用户管理", icon: Users, roles: ["admin", "route_staff"] },
  { href: "/presence", label: "在线状态", icon: Activity, roles: ["admin"] },
  { href: "/monitor", label: "监控任务", icon: RadioTower, roles: ["admin"] },
  { href: "/monitor/settings", label: "自动航班查询设置", icon: Settings, roles: ["admin"] },
  { href: "/audit-logs", label: "审计日志", icon: ShieldCheck, roles: ["admin"] }
];

function canSee(userRoles: RoleCode[], allowed?: RoleCode[]) {
  if (!allowed) return true;
  return allowed.some((role) => userRoles.includes(role));
}

function canSeeCustomsUploadAlerts(userRoles: RoleCode[]) {
  return userRoles.some((role) => role === "admin" || role === "route_staff" || role === "customs_staff");
}

function readDismissedCustomsAlerts() {
  if (typeof window === "undefined") return new Set<number>();
  try {
    const raw = window.localStorage.getItem(DISMISSED_CUSTOMS_ALERTS_STORAGE_KEY);
    const ids = raw ? (JSON.parse(raw) as unknown) : [];
    return new Set(Array.isArray(ids) ? ids.filter((id): id is number => typeof id === "number") : []);
  } catch {
    return new Set<number>();
  }
}

function writeDismissedCustomsAlerts(ids: Set<number>) {
  try {
    window.localStorage.setItem(DISMISSED_CUSTOMS_ALERTS_STORAGE_KEY, JSON.stringify([...ids]));
  } catch {
    // Dismissal is local UI state only.
  }
}

function readSidebarCollapsedPreference() {
  if (typeof window === "undefined") return false;
  try {
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

function writeSidebarCollapsedPreference(value: boolean) {
  try {
    window.localStorage.setItem(SIDEBAR_COLLAPSED_STORAGE_KEY, String(value));
    window.dispatchEvent(new Event(SIDEBAR_COLLAPSED_EVENT));
  } catch {
    // Layout preference is nice-to-have; the UI should still toggle even if storage is unavailable.
  }
}

function subscribeSidebarCollapsedPreference(callback: () => void) {
  if (typeof window === "undefined") return () => {};
  window.addEventListener("storage", callback);
  window.addEventListener(SIDEBAR_COLLAPSED_EVENT, callback);
  return () => {
    window.removeEventListener("storage", callback);
    window.removeEventListener(SIDEBAR_COLLAPSED_EVENT, callback);
  };
}

function pickActiveHref(items: typeof navItems, pathname: string): string | null {
  // Match by longest prefix so /waybills/lookup wins over /waybills.
  const matches = items.filter((item) =>
    item.href === "/" ? pathname === "/" : pathname === item.href || pathname.startsWith(item.href + "/")
  );
  if (matches.length === 0) return null;
  return matches.reduce((longest, item) => (item.href.length > longest.href.length ? item : longest)).href;
}

function NavLink({
  href,
  label,
  icon: Icon,
  active,
  collapsed = false
}: (typeof navItems)[number] & { active: boolean; collapsed?: boolean }) {
  return (
    <Link
      href={href}
      title={label}
      aria-label={label}
      className={cn(
        "flex h-9 shrink-0 items-center rounded-md text-sm text-slate-700 transition-colors hover:bg-slate-100",
        collapsed ? "w-9 justify-center px-0" : "gap-2 px-3",
        active && "bg-purple-50 font-medium text-purple-800"
      )}
    >
      <Icon className="h-4 w-4 shrink-0" />
      {collapsed ? null : <span className="truncate">{label}</span>}
    </Link>
  );
}

function ShellContent({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, loading, logout } = useAuth();
  const sidebarCollapsed = useSyncExternalStore(
    subscribeSidebarCollapsedPreference,
    readSidebarCollapsedPreference,
    () => false
  );
  const [customsAlerts, setCustomsAlerts] = useState<Alert[]>([]);

  useEffect(() => {
    if (!loading && !user && pathname !== "/login") {
      router.replace("/login");
    }
  }, [loading, pathname, router, user]);

  useEffect(() => {
    if (!user || pathname === "/login") return;

    let stopped = false;
    const sendHeartbeat = async () => {
      if (stopped || document.hidden) return;
      try {
        await apiClient.post<{ user_id: number; last_seen_at: string }>("/presence/heartbeat");
      } catch {
        // Heartbeats are best-effort; normal API calls still handle auth redirects.
      }
    };

    const handleVisibility = () => {
      if (!document.hidden) void sendHeartbeat();
    };

    void sendHeartbeat();
    const timer = window.setInterval(() => {
      void sendHeartbeat();
    }, HEARTBEAT_INTERVAL_MS);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      stopped = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [pathname, user]);

  useEffect(() => {
    if (!user || pathname === "/login" || !canSeeCustomsUploadAlerts(user.roles)) {
      return;
    }

    let stopped = false;
    const loadAlerts = async () => {
      if (stopped || document.hidden) return;
      try {
        const items = await apiClient.get<Alert[]>(
          "/alerts?status=active&alert_type=customs_data_not_uploaded_after_departure"
        );
        const dismissed = readDismissedCustomsAlerts();
        setCustomsAlerts(items.filter((item) => !dismissed.has(item.id)));
      } catch {
        setCustomsAlerts([]);
      }
    };
    const handleVisibility = () => {
      if (!document.hidden) void loadAlerts();
    };

    void loadAlerts();
    const timer = window.setInterval(() => {
      void loadAlerts();
    }, CUSTOMS_ALERT_POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      stopped = true;
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [pathname, user]);

  if (pathname === "/login") return <>{children}</>;
  if (loading) return <div className="grid min-h-screen place-items-center text-sm text-slate-500">正在加载系统...</div>;
  if (!user) return null;

  const visibleNav = navItems.filter((item) => canSee(user.roles, item.roles));
  const activeHref = pickActiveHref(visibleNav, pathname);
  const activeCustomsAlert = canSeeCustomsUploadAlerts(user.roles) ? customsAlerts[0] : undefined;

  function toggleSidebarCollapsed() {
    writeSidebarCollapsedPreference(!sidebarCollapsed);
  }

  function dismissCustomsAlert(alertId: number) {
    const dismissed = readDismissedCustomsAlerts();
    dismissed.add(alertId);
    writeDismissedCustomsAlerts(dismissed);
    setCustomsAlerts((items) => items.filter((item) => item.id !== alertId));
  }

  return (
    <div className="min-h-screen bg-slate-100">
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-20 hidden flex-col border-r border-slate-200 bg-white transition-all duration-200 md:flex",
          sidebarCollapsed ? "w-16" : "w-60"
        )}
      >
        <div className={cn("flex h-16 items-center justify-center border-b border-slate-200 px-3", sidebarCollapsed && "px-2")}>
          <Link
            href="/"
            className={cn(
              "flex min-w-0 items-center justify-center overflow-hidden rounded-md transition-all",
              sidebarCollapsed ? "h-9 w-9 bg-purple-700 text-sm font-bold text-white" : "w-full"
            )}
            title="元大物流 Yuanda Cargo Logistics"
            aria-label="返回总览"
          >
            {sidebarCollapsed ? (
              <span>YD</span>
            ) : (
              <Image
                src="/logo.png"
                alt="元大物流 Yuanda Cargo Logistics"
                width={800}
                height={200}
                priority
                className="h-10 w-auto"
              />
            )}
          </Link>
        </div>
        <nav className={cn("flex-1 space-y-1 overflow-y-auto", sidebarCollapsed ? "p-2" : "p-3")}>
          {visibleNav.map((item) => (
            <NavLink key={item.href} {...item} active={item.href === activeHref} collapsed={sidebarCollapsed} />
          ))}
        </nav>
        <div className={cn("border-t border-slate-200", sidebarCollapsed ? "p-2" : "p-3")}>
          <Button
            type="button"
            variant="ghost"
            size={sidebarCollapsed ? "icon" : "default"}
            className={cn(sidebarCollapsed ? "h-9 w-9" : "w-full justify-start")}
            onClick={toggleSidebarCollapsed}
            title={sidebarCollapsed ? "展开导航" : "收起导航"}
            aria-label={sidebarCollapsed ? "展开导航" : "收起导航"}
          >
            {sidebarCollapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
            {sidebarCollapsed ? null : <span>收起导航</span>}
          </Button>
        </div>
      </aside>
      <div className={cn("transition-[padding] duration-200", sidebarCollapsed ? "md:pl-16" : "md:pl-60")}>
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white">
          <div className="flex h-14 items-center justify-between gap-3 px-4 md:px-5">
            <div className="min-w-0 text-sm font-medium text-slate-700">物流航空头程提单监控后台</div>
            <div className="flex items-center gap-3">
              <div className="hidden items-center gap-1 sm:flex">
                {user.roles.map((role) => (
                  <Badge key={role} variant={role === "admin" ? "red" : "default"}>
                    {roleLabels[role] || role}
                  </Badge>
                ))}
              </div>
              <div className="max-w-32 truncate text-sm text-slate-700">{user.display_name || user.username}</div>
              <Button variant="ghost" size="icon" onClick={logout} aria-label="退出登录">
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          </div>
          <nav className="flex gap-1 overflow-x-auto border-t border-slate-100 px-2 py-2 md:hidden">
            {visibleNav.map((item) => (
              <NavLink key={item.href} {...item} active={item.href === activeHref} />
            ))}
          </nav>
        </header>
        <main className="p-4 md:p-5">{children}</main>
      </div>
      <Dialog
        open={Boolean(activeCustomsAlert)}
        onOpenChange={(open) => {
          if (!open && activeCustomsAlert) dismissCustomsAlert(activeCustomsAlert.id);
        }}
      >
        <DialogContent className="w-[min(520px,calc(100vw-32px))]">
          <DialogTitle className="pr-10 text-base font-semibold text-slate-900">清关资料未上传</DialogTitle>
          {activeCustomsAlert ? (
            <div className="space-y-4 text-sm text-slate-700">
              <p>{activeCustomsAlert.description || "提单已起飞，但系统尚未确认清关资料已上传到清关行。"}</p>
              <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-red-700">
                提单号：{activeCustomsAlert.waybill_no || activeCustomsAlert.waybill_id}
              </div>
              {customsAlerts.length > 1 ? (
                <p className="text-xs text-slate-500">还有 {customsAlerts.length - 1} 条同类异常等待处理。</p>
              ) : null}
              <div className="flex justify-end gap-2">
                <Button type="button" variant="secondary" onClick={() => dismissCustomsAlert(activeCustomsAlert.id)}>
                  稍后处理
                </Button>
                <Button asChild>
                  <Link
                    href={`/waybills/${activeCustomsAlert.waybill_id}`}
                    onClick={() => dismissCustomsAlert(activeCustomsAlert.id)}
                  >
                    查看提单
                  </Link>
                </Button>
              </div>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </div>
  );
}

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ShellContent>{children}</ShellContent>
    </AuthProvider>
  );
}
