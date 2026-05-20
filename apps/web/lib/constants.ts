export const lifecycleLabels: Record<string, string> = {
  created: "已创建",
  waiting_monitor: "待监控",
  monitoring: "监控中",
  warehouse_received: "已入仓",
  loaded: "已装机",
  departed: "已起飞",
  arrived: "已到达",
  pickup_notified: "已通知提取",
  picked_up: "已提取",
  closed: "已结束",
  voided: "已作废"
};

export const alertLevelLabels: Record<string, string> = {
  info: "提示",
  warning: "警告",
  critical: "严重"
};

export const roleLabels: Record<string, string> = {
  admin: "管理员",
  route_staff: "航线排仓",
  customer_service: "客服",
  customs_staff: "出口报关"
};

export const roleOptions = [
  { value: "admin", label: "管理员" },
  { value: "route_staff", label: "航线排仓人员" },
  { value: "customer_service", label: "客服人员" },
  { value: "customs_staff", label: "出口报关人员" }
] as const;
