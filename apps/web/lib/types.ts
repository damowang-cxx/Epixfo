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

export interface TableColumnPreference {
  table_key: string;
  column_order: string[];
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

export interface UserSummary {
  id: number;
  username: string;
  display_name?: string | null;
  is_active: boolean;
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
  departure_port?: string | null;
  destination_port?: string | null;
  agent?: string | null;
  carrier_agent_id?: number | null;
  carrier_agent?: CarrierAgent | null;
  consignee_contact_id?: number | null;
  consignee_contact?: ConsigneeContact | null;
  board_id?: number | null;
  board?: BoardSummary | null;
  warehouse_no?: string | null;
  outbound_date?: string | null;
  consignee?: string | null;
  document_operator_id?: number | null;
  route_staff_id?: number | null;
  customs_staff_id?: number | null;
  customs_staff?: UserSummary | null;
  customs_data_uploaded_at?: string | null;
  customs_data_uploaded_by?: number | null;
  customs_data_uploaded_by_user?: UserSummary | null;
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
  other_charge?: string | number | null;
  payment_date?: string | null;
  lifecycle_status: LifecycleStatus;
  alert_level?: AlertLevel | null;
  monitor_enabled: boolean;
  first_monitor_at?: string | null;
  last_query_at?: string | null;
  next_query_at?: string | null;
  consecutive_query_failures: number;
  plan?: WaybillPlan | null;
  official_estimated_flight_date?: string | null;
  created_at: string;
  updated_at: string;
}

export interface BoardSummary {
  id: number;
  board_no: string;
  actual_board_no?: string | null;
  consignee_contact_id?: number | null;
  consignee_text?: string | null;
  member_count: number;
  total_booked_volume: string | number;
}

export interface BoardWaybill {
  id: number;
  waybill_no: string;
  consignee_contact_id?: number | null;
  consignee?: string | null;
  booked_volume?: string | number | null;
  lifecycle_status: LifecycleStatus;
}

export interface WaybillBoard extends BoardSummary {
  waybills: BoardWaybill[];
  created_at: string;
  updated_at: string;
}

export interface BoxDocument {
  id: number;
  file_name: string;
  file_path?: string | null;
  file_hash?: string | null;
  bound_waybill_id?: number | null;
  uploaded_by?: number | null;
  uploaded_at: string;
}

export interface CargoBox {
  id: number;
  box_no: string;
  document_id?: number | null;
  warehouse_receipt_id?: number | null;
  current_waybill_id?: number | null;
  warehouse_waybill_no?: string | null;
  goods_name?: string | null;
  quantity?: number | null;
  weight?: string | number | null;
  original_volume_info?: string | null;
  original_weight_volume_ratio?: string | null;
  volume?: string | number | null;
  weight_volume_ratio?: string | number | null;
  source_row_number?: number | null;
  status: string;
  is_general_cargo: boolean;
  never_bound_direct_upload: boolean;
  unbound_reason?: string | null;
  unbound_remark?: string | null;
  raw_data: Record<string, unknown>;
  document?: BoxDocument | null;
  warehouse_receipt?: WarehouseReceipt | null;
  items: CargoBoxItem[];
  created_at: string;
  updated_at: string;
}

export interface WarehouseReceipt {
  id: number;
  warehouse_no: string;
  waybill_id?: number | null;
  waybill_no?: string | null;
  prebooking_id?: number | null;
  prebooking_status?: string | null;
  prebooking_label?: string | null;
  source_document_id?: number | null;
  source_file_name?: string | null;
  uploaded_by?: number | null;
  total_quantity: number;
  total_weight?: string | number | null;
  total_volume?: string | number | null;
  weight_volume_ratio?: string | number | null;
  channel_tags: string[];
  box_count?: number;
  created_at: string;
  updated_at: string;
}

export type PrebookingStatus = "draft" | "converted" | "cancelled";

export interface WaybillPrebooking {
  id: number;
  status: PrebookingStatus;
  carrier_agent_id: number;
  carrier_agent?: CarrierAgent | null;
  agent?: string | null;
  planned_flight_date: string;
  outbound_date?: string | null;
  booked_volume: string | number;
  waybill_no?: string | null;
  departure_port?: string | null;
  destination_port?: string | null;
  planned_flight_no?: string | null;
  planned_route_text?: string | null;
  consignee?: string | null;
  consignee_contact_id?: number | null;
  consignee_contact?: ConsigneeContact | null;
  customs_staff_id?: number | null;
  customs_staff?: UserSummary | null;
  data_charge?: string | number | null;
  delivery_time?: string | null;
  document_cutoff_time?: string | null;
  booked_weight?: string | number | null;
  density?: string | number | null;
  quotation?: string | number | null;
  include_tc: boolean;
  warehouse_data_remark?: string | null;
  notify_pickup: boolean;
  pickup_time?: string | null;
  internal_remark?: string | null;
  customer_remark?: string | null;
  air_freight_cost?: string | number | null;
  other_charge?: string | number | null;
  payment_date?: string | null;
  converted_waybill_id?: number | null;
  converted_waybill?: Waybill | null;
  receipts: WarehouseReceipt[];
  created_at: string;
  updated_at: string;
}

export interface CargoBoxItem {
  id: number;
  box_id: number;
  document_id?: number | null;
  warehouse_waybill_no?: string | null;
  goods_name?: string | null;
  quantity?: number | null;
  weight?: string | number | null;
  source_row_number?: number | null;
  raw_data: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface WarehouseFileImportError {
  row_number: number;
  message: string;
}

export interface WarehouseBoxConflict {
  box_no: string;
  current_waybill_id?: number | null;
  current_waybill_no?: string | null;
  current_warehouse_no?: string | null;
  target_waybill_id: number;
  target_waybill_no: string;
  target_warehouse_no: string;
}

export interface WarehouseChannelReviewIssue {
  box_no: string;
  prefix: string;
  reason: string;
  message: string;
}

export interface WarehouseUploadIntegrityIssue {
  row_number: number;
  box_no: string;
  message: string;
}

export interface WarehouseChannelReview {
  detected_channel: "europe" | "uk" | "unknown" | "mixed";
  warnings: string[];
}

export interface WarehouseFileUploadResult {
  file_name: string;
  warehouse_no: string;
  document_id: number;
  success_count: number;
  skipped_count: number;
  errors: WarehouseFileImportError[];
  conflicts: WarehouseBoxConflict[];
  channel_review?: WarehouseChannelReview | null;
  channel_tags: string[];
  integrity_issues: WarehouseUploadIntegrityIssue[];
}

export type PlannerSourceType = "waybill" | "prebooking";
export type PlannerCommitMode = "all_or_none" | "success_only";

export interface WarehousePlannerRow {
  source_type: PlannerSourceType;
  source_id: number;
  waybill_no?: string | null;
  carrier_agent_id?: number | null;
  planned_flight_no?: string | null;
  planned_flight_date?: string | null;
  outbound_date?: string | null;
  receipt_ids: number[];
  customs_staff_id?: number | null;
  booked_volume?: string | number | null;
  booked_weight?: string | number | null;
  density?: string | number | null;
  quotation?: string | null;
  include_tc?: boolean | null;
  departure_port?: string | null;
  destination_port?: string | null;
  planned_route_text?: string | null;
  source_updated_at?: string | null;
}

export interface WarehousePlannerDraft {
  rows: WarehousePlannerRow[];
  updated_at?: string | null;
}

export interface WarehousePlannerCandidate {
  source_type: PlannerSourceType;
  source_id: number;
  label: string;
  waybill_no?: string | null;
  carrier_agent_id?: number | null;
  carrier_agent?: CarrierAgent | null;
  planned_flight_no?: string | null;
  planned_flight_date?: string | null;
  outbound_date?: string | null;
  receipts: WarehouseReceipt[];
  customs_staff_id?: number | null;
  customs_staff?: UserSummary | null;
  booked_volume?: string | number | null;
  booked_weight?: string | number | null;
  density?: string | number | null;
  quotation?: string | null;
  include_tc?: boolean | null;
  departure_port?: string | null;
  destination_port?: string | null;
  planned_route_text?: string | null;
  lifecycle_status?: string | null;
  source_updated_at: string;
}

export interface WarehousePlannerCandidates {
  waybills: WarehousePlannerCandidate[];
  prebookings: WarehousePlannerCandidate[];
  unbound_receipts: WarehouseReceipt[];
}

export interface WarehousePlannerRowError {
  field?: string | null;
  message: string;
}

export interface WarehousePlannerRowResult {
  source_type: PlannerSourceType;
  source_id: number;
  status: "valid" | "invalid" | "committed" | "failed";
  waybill_id?: number | null;
  waybill_no?: string | null;
  errors: WarehousePlannerRowError[];
}

export interface WarehousePlannerValidateResult {
  valid_count: number;
  invalid_count: number;
  results: WarehousePlannerRowResult[];
}

export interface WarehousePlannerCommitResult {
  success_count: number;
  failed_count: number;
  results: WarehousePlannerRowResult[];
  remaining_rows: WarehousePlannerRow[];
  skipped_due_to_all_or_none: boolean;
}

export interface WaybillBulkImportError {
  row_number: number;
  waybill_no?: string | null;
  message: string;
}

export interface WaybillBulkImportCreated {
  id: number;
  waybill_no: string;
}

export interface WaybillBulkImportResult {
  file_name: string;
  created_count: number;
  skipped_count: number;
  errors: WaybillBulkImportError[];
  created_waybills: WaybillBulkImportCreated[];
}

export type WaybillBulkUpdateField =
  | "customs_staff_id"
  | "outbound_date"
  | "carrier_agent_id"
  | "consignee_contact_id"
  | "departure_port"
  | "destination_port"
  | "planned_flight_info"
  | "planned_route_text"
  | "warehouse_data_remark"
  | "customer_remark"
  | "internal_remark";

export interface WaybillBulkUpdateRequest {
  waybill_ids: number[];
  field: WaybillBulkUpdateField;
  value: string | number | null;
}

export interface WaybillBulkUpdateItem {
  id: number;
  waybill_no: string;
}

export interface WaybillBulkUpdateError {
  id: number;
  waybill_no?: string | null;
  message: string;
}

export interface WaybillBulkUpdateResult {
  success_count: number;
  failed_count: number;
  updated_waybills: WaybillBulkUpdateItem[];
  errors: WaybillBulkUpdateError[];
}

export type WaybillInlineUpdateField =
  | "waybill_no"
  | "consignee_contact_id"
  | "booked_volume"
  | "booked_weight"
  | "density"
  | "quotation"
  | "include_tc"
  | "customs_staff_id"
  | "carrier_agent_id"
  | "outbound_date"
  | "planned_flight_no"
  | "planned_flight_date";

export type WaybillInlineUpdateValue = string | number | boolean | null;

export interface WaybillBulkInlineUpdateRequest {
  updates: Array<{
    waybill_id: number;
    changes: Partial<Record<WaybillInlineUpdateField, WaybillInlineUpdateValue>>;
  }>;
}

export interface WaybillBulkInlineUpdateError {
  waybill_id: number;
  waybill_no?: string | null;
  field?: string | null;
  message: string;
}

export interface WaybillBulkInlineUpdateResult {
  success_count: number;
  failed_count: number;
  updated_waybills: Waybill[];
  errors: WaybillBulkInlineUpdateError[];
}

export interface WaybillBulkDeleteRequest {
  waybill_ids: number[];
}

export interface WaybillBulkDeleteResult {
  success_count: number;
  failed_count: number;
  deleted_waybills: WaybillBulkUpdateItem[];
  errors: WaybillBulkUpdateError[];
}

export interface BoxBatchOperationResult {
  updated_count: number;
  boxes: CargoBox[];
}

export interface BoxVolumeRecalculationResult {
  target_volume: string | number;
  total_weight: string | number;
  original_total_volume: string | number;
  old_total_volume: string | number;
  fixed_total_volume: string | number;
  adjustable_total_volume: string | number;
  new_total_volume: string | number;
  adjusted: boolean;
  adjusted_box_count: number;
  fixed_box_count: number;
  boxes: CargoBox[];
}

export interface Alert {
  id: number;
  waybill_id: number;
  waybill_no?: string | null;
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

export interface Consignee {
  id: number;
  name: string;
  enabled: boolean;
  remark?: string | null;
  created_at: string;
  updated_at: string;
}

export interface ConsigneeContact {
  id: number;
  consignee_id: number;
  name: string;
  address?: string | null;
  email?: string | null;
  phone?: string | null;
  tax_info?: string | null;
  notify_info?: string | null;
  remark?: string | null;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ConsigneeNotifyParty {
  id: number;
  consignee_contact_id: number;
  name: string;
  address?: string | null;
  email?: string | null;
  phone?: string | null;
  tax_info?: string | null;
  remark?: string | null;
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
  contact_emails?: string | null;
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
  departure_planned_time?: string | null;
  departure_actual_time?: string | null;
  arrival_planned_time?: string | null;
  arrival_actual_time?: string | null;
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

export interface AutoFlightQuerySettings {
  fallback_enabled: boolean;
  fallback_adapter_code: string;
  query_interval_hours: number;
  scan_limit: number;
  scheduler_process_enabled: boolean;
  scheduler_interval_seconds: number;
  created_at?: string | null;
  updated_at?: string | null;
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

export type PresenceUserStatusCode = "online" | "offline" | "disabled";
export type PresenceSessionStatus = "online" | "logged_out" | "timeout";

export interface PresenceUserStatus {
  id: number;
  username: string;
  display_name?: string | null;
  is_active: boolean;
  roles: Role[];
  last_login_at?: string | null;
  last_seen_at?: string | null;
  last_seen_age_seconds?: number | null;
  online: boolean;
  status: PresenceUserStatusCode;
  primary_role?: RoleCode | null;
  role_rank: number;
}

export interface PresenceUserSession {
  id: number;
  login_at: string;
  logout_at?: string | null;
  effective_logout_at?: string | null;
  duration_seconds: number;
  status: PresenceSessionStatus;
  ip_address?: string | null;
  user_agent?: string | null;
}

export interface PresenceWaybillViewLog {
  id: number;
  user_id: number;
  waybill_id?: number | null;
  waybill_no: string;
  lifecycle_status?: LifecycleStatus | null;
  viewed_at: string;
  ip_address?: string | null;
  user_agent?: string | null;
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
  departure_planned_time?: string | null;
  departure_actual_time?: string | null;
  arrival_planned_time?: string | null;
  arrival_actual_time?: string | null;
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
