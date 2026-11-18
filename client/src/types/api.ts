export interface User {
  id: number
  email: string
  full_name: string
  system_role: 'super_admin' | 'location_admin' | 'operator' | 'viewer'
  is_active: boolean
  employee_id?: number | null
  last_login_at?: string | null
  created_at: string
}

export interface LoginRequest {
  email: string
  password: string
}

export interface TokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  expires_at: string
  user: User
}

export interface Location {
  id: number
  name: string
  address?: string | null
  timezone: string
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface LocationDetail extends Location {
  department_count: number
  employee_count: number
  camera_count: number
}

export interface LocationCreatePayload {
  name: string
  address?: string | null
  timezone?: string
  is_active?: boolean
}

export interface LocationUpdatePayload {
  name?: string
  address?: string | null
  timezone?: string
  is_active?: boolean
}

export interface LocationSchedule {
  id: number
  location_id: number
  day_of_week: number
  day_name: string
  is_working_day: boolean
  open_time?: string | null
  close_time?: string | null
  after_hours_grace_minutes: number
  is_overnight: boolean
  created_at: string
  updated_at: string
}

export interface LocationScheduleListResponse {
  location_id: number
  location_name: string
  timezone: string
  schedules: LocationSchedule[]
}

export interface LocationScheduleCreatePayload {
  day_of_week: number
  is_working_day: boolean
  open_time?: string | null
  close_time?: string | null
  after_hours_grace_minutes?: number
}

export interface LocationScheduleUpdatePayload {
  is_working_day?: boolean
  open_time?: string | null
  close_time?: string | null
  after_hours_grace_minutes?: number
}

export interface Department {
  id: number
  name: string
  code?: string | null
  location_id: number
  is_active: boolean
  employee_count?: number
  created_at: string
  updated_at: string
}

export type CameraRole = 'entry_exit' | 'workstation' | 'perimeter' | 'general'
export type StreamType = 'rtsp' | 'webcam' | 'file' | 'onvif'
export type ConnectionStatus = 'online' | 'offline' | 'degraded' | 'unknown'

export interface Camera {
  id: number
  camera_code: string
  name: string
  location_id: number
  camera_role: CameraRole
  stream_type: StreamType
  stream_secret_ref?: string | null
  connection_status: ConnectionStatus
  last_heartbeat_at?: string | null
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface WorkstationZoneSummary {
  id: number
  zone_code: string
  name: string
  location_id: number
  camera_id: number
  is_active: boolean
}

export interface CameraDetail extends Camera {
  location_name?: string | null
  workstation_zones: WorkstationZoneSummary[]
  detection_event_count: number
  alert_count: number
}

export interface CameraCreatePayload {
  name: string
  camera_code: string
  location_id: number
  camera_role: CameraRole
  stream_type: StreamType
  stream_secret_ref?: string | null
  connection_status?: ConnectionStatus
  is_active?: boolean
}

export interface CameraUpdatePayload {
  name?: string
  camera_code?: string
  location_id?: number
  camera_role?: CameraRole
  stream_type?: StreamType
  stream_secret_ref?: string | null
  connection_status?: ConnectionStatus
  is_active?: boolean
}

export interface CameraQueryParams {
  page?: number
  size?: number
  location_id?: number
  camera_role?: string
  stream_type?: string
  connection_status?: string
  is_active?: boolean
  search?: string
}

export interface WorkstationZone {
  id: number
  zone_code: string
  name: string
  location_id: number
  camera_id: number
  polygon_points: [number, number][]
  assigned_employee_id?: number | null
  department_id?: number | null
  inactivity_threshold_seconds: number
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface WorkstationZoneDetail extends WorkstationZone {
  location_name?: string | null
  camera_name?: string | null
  camera_code?: string | null
  assigned_employee_name?: string | null
  department_name?: string | null
}

export interface WorkstationZoneCreatePayload {
  zone_code: string
  name: string
  location_id: number
  camera_id: number
  polygon_points: [number, number][]
  assigned_employee_id?: number | null
  department_id?: number | null
  inactivity_threshold_seconds?: number
  is_active?: boolean
}

export interface WorkstationZoneUpdatePayload {
  name?: string
  zone_code?: string
  camera_id?: number
  polygon_points?: [number, number][]
  assigned_employee_id?: number | null
  department_id?: number | null
  inactivity_threshold_seconds?: number
  is_active?: boolean
}

export interface WorkstationZoneQueryParams {
  page?: number
  size?: number
  location_id?: number
  camera_id?: number
  assigned_employee_id?: number
  is_active?: boolean
  search?: string
}

export interface DetectionEvent {
  id: number
  camera_id: number
  location_id: number
  event_type:
    | 'employee_recognized'
    | 'unknown_person'
    | 'workstation_active'
    | 'workstation_idle'
    | 'after_hours_employee'
    | 'after_hours_intrusion'
    | 'guest_entry'
    | 'guest_exit'
  occurred_at: string
  confidence?: number | null
  employee_id?: number | null
  workstation_zone_id?: number | null
  tracker_id?: string | null
  metadata_json?: Record<string, any> | null
  created_at?: string
}

export interface Alert {
  id: number
  location_id: number
  camera_id?: number | null
  alert_type: string
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  status: 'open' | 'acknowledged' | 'resolved' | 'false_positive'
  title: string
  description?: string | null
  created_at: string
  updated_at?: string
}

export type EnrollmentStatus = 'pending' | 'enrolled' | 'needs_re_enroll' | 'revoked'

export interface Role {
  id: number
  name: string
  code: string
  description?: string | null
  is_active: boolean
  created_at?: string
  updated_at?: string
}

export interface Employee {
  id: number
  employee_code: string
  full_name: string
  email?: string | null
  department_id?: number | null
  location_id?: number | null
  enrollment_status: EnrollmentStatus
  is_active: boolean
  created_at: string
  updated_at: string
  roles: Role[]
}

export interface EmployeeDetail extends Employee {
  department_name?: string | null
  location_name?: string | null
}

export interface EmployeeCreatePayload {
  employee_code: string
  full_name: string
  email?: string | null
  department_id?: number | null
  location_id?: number | null
  enrollment_status?: EnrollmentStatus
  is_active?: boolean
  role_ids?: number[]
}

export interface EmployeeUpdatePayload {
  full_name?: string
  email?: string | null
  department_id?: number | null
  location_id?: number | null
  enrollment_status?: EnrollmentStatus
  is_active?: boolean
  role_ids?: number[]
}

export interface EmployeeQueryParams {
  page?: number
  size?: number
  location_id?: number
  department_id?: number
  is_active?: boolean
  enrollment_status?: string
  search?: string
}

export interface FaceEnrollment {
  id: number
  employee_id: number
  is_template: boolean
  model_name: string
  model_version: string
  sample_count: number
  quality_score?: number | null
  source_image_ref?: string | null
  enrolled_by_user_id?: number | null
  is_active: boolean
  created_at: string
  updated_at: string
  embedding_dim: number
}

export interface FaceEnrollmentDetail extends FaceEnrollment {
  employee_code?: string | null
  employee_name?: string | null
  location_id?: number | null
  location_name?: string | null
  department_name?: string | null
  enrolled_by_user_name?: string | null
}

export interface FaceEnrollmentCreatePayload {
  embedding: number[]
  model_name?: string
  model_version?: string
  is_template?: boolean
  sample_count?: number
  quality_score?: number | null
  source_image_ref?: string | null
  is_active?: boolean
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface HealthCheckResponse {
  status: string
  application: string
  environment: string
  version: string
}
