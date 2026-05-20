export type RoleCode = "admin" | "route_staff" | "customer_service" | "customs_staff";

export type LifecycleStatus =
  | "created"
  | "waiting_monitor"
  | "monitoring"
  | "warehouse_received"
  | "loaded"
  | "departed"
  | "arrived"
  | "pickup_notified"
  | "picked_up"
  | "closed"
  | "voided";

export type AlertLevel = "info" | "warning" | "critical";
export type AlertStatus = "active" | "acknowledged" | "resolved" | "ignored";
export type QueryStatus = "success" | "failed" | "partial_success";

export interface PageResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface Me {
  id: number;
  username: string;
  display_name?: string | null;
  roles: RoleCode[];
}

export interface Role {
  id: number;
  code: RoleCode;
  name: string;
  description?: string | null;
}

export interface User {
  id: number;
  username: string;
  display_name?: string | null;
  email?: string | null;
  phone?: string | null;
  is_active: boolean;
  is_superuser: boolean;
  last_login_at?: string | null;
  last_seen_at?: string | null;
  roles: Role[];
  created_at: string;
  updated_at: string;
}

export interface WaybillPlan {
  id: number;
  planned_flight_no?: string | null;
  planned_flight_date?: string | null;
  planned_destination?: string | null;
  planned_route_text?: string | null;
}

export interface Waybill {
  id: number;
  waybill_no: string;
  carrier_prefix?: string | null;
  carrier_code?: string | null;
  destination_port?: string | null;
  agent?: string | null;
  carrier_agent_id?: number | null;
  carrier_agent?: CarrierAgent | null;
  warehouse_no?: string | null;
  consignee?: string | null;
  document_operator_id?: number | null;
  route_staff_id?: number | null;
  data_charge?: string | number | null;
  delivery_time?: string | null;
  document_cutoff_time?: string | null;
  booked_weight?: string | number | null;
  booked_volume?: string | number | null;
  density?: string | number | null;
  quotation?: string | number | null;
  include_tc: boolean;
  warehouse_data_remark?: string | null;
  notify_pickup: boolean;
  pickup_time?: string | null;
  internal_remark?: string | null;
  customer_remark?: string | null;
  air_freight_cost?: string | number | null;
  payment_date?: string | null;
  lifecycle_status: LifecycleStatus;
  alert_level?: AlertLevel | null;
  monitor_enabled: boolean;
  first_monitor_at?: string | null;
  last_query_at?: string | null;
  next_query_at?: string | null;
  consecutive_query_failures: number;
  plan?: WaybillPlan | null;
  created_at: string;
  updated_at: string;
}

export interface Alert {
  id: number;
  waybill_id: number;
  alert_type: string;
  alert_level: AlertLevel;
  title: string;
  description?: string | null;
  old_value?: string | null;
  new_value?: string | null;
  status: AlertStatus;
  acknowledged_by?: number | null;
  acknowledged_at?: string | null;
  resolved_by?: number | null;
  resolved_at?: string | null;
  created_at: string;
  updated_at: string;
}

export interface Carrier {
  id: number;
  carrier_code: string;
  carrier_name: string;
  carrier_name_en?: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CarrierAgent {
  id: number;
  carrier_code: string;
  agent_name: string;
  contact_person?: string | null;
  contact_phone?: string | null;
  enabled: boolean;
  remark?: string | null;
  created_at: string;
  updated_at: string;
}

export interface CarrierPrefixMapping {
  id: number;
  prefix: string;
  carrier_code: string;
  adapter_code: string;
  query_method: "protocol" | "playwright" | "hybrid";
  enabled: boolean;
  remark?: string | null;
  created_at: string;
  updated_at: string;
}

export interface OfficialInfo {
  id: number;
  waybill_id: number;
  official_waybill_no?: string | null;
  carrier_text?: string | null;
  route_text?: string | null;
  goods_name?: string | null;
  total_pieces?: number | null;
  total_weight?: string | number | null;
  total_volume?: string | number | null;
  raw_data: Record<string, unknown>;
}

export interface OfficialFlightSegment {
  id: number;
  waybill_id: number;
  booking_no?: string | null;
  route_text?: string | null;
  segment_order: number;
  departure_airport?: string | null;
  arrival_airport?: string | null;
  flight_no?: string | null;
  flight_date?: string | null;
  pieces?: number | null;
  weight?: string | number | null;
  volume?: string | number | null;
  booking_type?: string | null;
  raw_data: Record<string, unknown>;
}

export interface StatusEvent {
  id: number;
  waybill_id: number;
  event_time_local?: string | null;
  event_time_text?: string | null;
  event_city?: string | null;
  airport_code?: string | null;
  flight_no?: string | null;
  status_text: string;
  normalized_event_type: string;
  pieces?: number | null;
  weight?: string | number | null;
  raw_data: Record<string, unknown>;
}

export interface AssemblyEvent {
  id: number;
  waybill_id: number;
  event_time_local?: string | null;
  event_time_text?: string | null;
  event_city?: string | null;
  status_text: string;
  uld_no?: string | null;
  pieces?: number | null;
  weight?: string | number | null;
  raw_data: Record<string, unknown>;
}

export interface QuerySnapshot {
  id: number;
  waybill_id: number;
  carrier_code?: string | null;
  adapter_code?: string | null;
  query_method?: string | null;
  query_status: QueryStatus;
  raw_response?: Record<string, unknown> | null;
  raw_text?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  started_at?: string | null;
  finished_at?: string | null;
  queried_at: string;
}

export interface OnlineUser {
  id: number;
  username: string;
  display_name?: string | null;
  last_seen_at?: string | null;
}

export interface DailyOnlineStat {
  user_id: number;
  stat_date: string;
  total_online_seconds: number;
}

export interface AuditLog {
  id: number;
  user_id?: number | null;
  action: string;
  target_type?: string | null;
  target_id?: number | null;
  before_data?: Record<string, unknown> | null;
  after_data?: Record<string, unknown> | null;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
}

export interface LookupOfficialInfo {
  official_waybill_no?: string | null;
  carrier_text?: string | null;
  route_text?: string | null;
  goods_name?: string | null;
  total_pieces?: number | null;
  total_weight?: string | number | null;
  total_volume?: string | number | null;
}

export interface LookupFlightSegment {
  booking_no?: string | null;
  route_text?: string | null;
  departure_airport?: string | null;
  arrival_airport?: string | null;
  flight_no?: string | null;
  flight_date?: string | null;
  pieces?: number | null;
  weight?: string | number | null;
  volume?: string | number | null;
  booking_type?: string | null;
}

export interface LookupStatusEvent {
  event_time_local?: string | null;
  event_time_text?: string | null;
  event_city?: string | null;
  flight_no?: string | null;
  status_text: string;
  normalized_event_type: string;
  pieces?: number | null;
  weight?: string | number | null;
}

export interface LookupAssemblyEvent {
  event_time_local?: string | null;
  event_time_text?: string | null;
  event_city?: string | null;
  status_text: string;
  uld_no?: string | null;
  pieces?: number | null;
  weight?: string | number | null;
}

export interface WaybillLookupResponse {
  waybill_no: string;
  status: QueryStatus;
  carrier_code?: string | null;
  adapter_code?: string | null;
  query_method?: string | null;
  error_code?: string | null;
  error_message?: string | null;
  official_info?: LookupOfficialInfo | null;
  flight_segments: LookupFlightSegment[];
  status_events: LookupStatusEvent[];
  assembly_events: LookupAssemblyEvent[];
  raw_response?: Record<string, unknown> | null;
}
