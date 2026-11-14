# Camera Intelligence — Complete Backend API Reference

**Document ID:** `docs/handover/API_REFERENCE.md`  
**Base URL:** `http://127.0.0.1:8000`  
**API Prefix:** `/api/v1`  
**Documentation Endpoints:** Interactive Swagger UI at `/docs` | OpenAPI JSON at `/openapi.json` | Redoc at `/redoc`  
**Authentication Scheme:** HTTP Bearer Header (`Authorization: Bearer <JWT_ACCESS_TOKEN>`)  

---

## 1. System Health Endpoints

### 1.1 Root Status
- **Method & Path:** `GET /`
- **Purpose:** Service liveness check.
- **Required Role:** Public (None).
- **Response:** `{"app": "Camera Intelligence", "version": "1.0.0", "status": "running"}` (200 OK).

### 1.2 Health Check
- **Method & Path:** `GET /health`
- **Purpose:** API health verification.
- **Required Role:** Public (None).
- **Response:** `{"status": "ok", "app_name": "Camera Intelligence", "app_env": "development"}` (200 OK).

### 1.3 Database Connection Health
- **Method & Path:** `GET /health/database`
- **Purpose:** Verify live PostgreSQL connectivity.
- **Required Role:** Public (None).
- **Response:** `{"database": "healthy", "database_name": "camera_intelligence"}` (200 OK).
- **Error Response:** `503 Service Unavailable` if database connection fails.

---

## 2. Authentication APIs (`/api/v1/auth`)

### 2.1 User Login
- **Method & Path:** `POST /api/v1/auth/login`
- **Purpose:** Authenticate user with credentials and issue JWT access token.
- **Required Role:** Public.
- **Request Body:**
  ```json
  {
    "email": "admin@cameraintelligence.com",
    "password": "SecretPassword123!"
  }
  ```
- **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOi...",
    "token_type": "bearer",
    "expires_in": 3600,
    "expires_at": "2026-11-14T12:35:00Z",
    "user": {
      "id": 1,
      "email": "admin@cameraintelligence.com",
      "full_name": "System Administrator",
      "system_role": "super_admin",
      "is_active": true,
      "employee_id": null,
      "last_login_at": "2026-11-14T11:35:00Z",
      "created_at": "2026-11-13T12:08:10Z"
    }
  }
  ```
- **Error Responses:**
  - `401 Unauthorized`: Invalid email or password.
  - `403 Forbidden`: User account is deactivated (`is_active=False`).

### 2.2 Current User Profile
- **Method & Path:** `GET /api/v1/auth/me`
- **Purpose:** Return authenticated user profile and assigned locations.
- **Required Role:** Any active authenticated user (`viewer` or higher).
- **Response (200 OK):** `UserProfileResponse` with `assigned_location_ids`.
- **Error Response:** `401 Unauthorized` if token missing or expired.

### 2.3 User Logout
- **Method & Path:** `POST /api/v1/auth/logout`
- **Purpose:** Stateless logout confirmation.
- **Required Role:** Any authenticated user.
- **Response (200 OK):** `{"message": "Logged out successfully"}`.

---

## 3. Location Management APIs (`/api/v1/locations`)

### 3.1 List Accessible Locations
- **Method & Path:** `GET /api/v1/locations`
- **Purpose:** List facilities accessible to the current user. `super_admin` sees all; other roles see only assigned locations.
- **Required Role:** `viewer` or higher.
- **Response (200 OK):** Array of `LocationResponse`.

### 3.2 Create Location
- **Method & Path:** `POST /api/v1/locations`
- **Purpose:** Register a new facility.
- **Required Role:** `super_admin`.
- **Request Body:**
  ```json
  {
    "name": "New York Headquarters",
    "address": "350 5th Ave, New York, NY",
    "timezone": "America/New_York",
    "is_active": true
  }
  ```
- **Response (201 Created):** `LocationResponse`.
- **Error Response:** `409 Conflict` if location name already exists.

### 3.3 Get Location Details
- **Method & Path:** `GET /api/v1/locations/{location_id}`
- **Purpose:** Retrieve detailed location info including department, employee, and camera counts.
- **Required Role:** `viewer` with location authorization.
- **Response (200 OK):** `LocationDetailResponse`.
- **Error Responses:** `404 Not Found`, `403 Forbidden` if unauthorized.

### 3.4 Update Location
- **Method & Path:** `PATCH /api/v1/locations/{location_id}`
- **Purpose:** Update location name, address, timezone, or active status.
- **Required Role:** `super_admin` or assigned `location_admin`.
- **Response (200 OK):** `LocationResponse`.

### 3.5 Deactivate Location
- **Method & Path:** `DELETE /api/v1/locations/{location_id}`
- **Purpose:** Soft-deactivate location (`is_active=False`).
- **Required Role:** `super_admin` or assigned `location_admin`.
- **Response (200 OK):** `LocationResponse`.

---

## 4. Department APIs (`/api/v1/departments`)

- **`GET /api/v1/departments`**: List departments across accessible locations (query parameters: `location_id`, `is_active`). Requires `viewer`.
- **`POST /api/v1/departments`**: Create department within a location. Requires `super_admin` or assigned `location_admin`. Enforces unique `name` and `code` per facility.
- **`GET /api/v1/departments/{department_id}`**: Get department details. Requires `viewer` with location access.
- **`PATCH /api/v1/departments/{department_id}`**: Update department. Requires `super_admin` or assigned `location_admin`.
- **`DELETE /api/v1/departments/{department_id}`**: Soft-deactivate department. Requires `super_admin` or assigned `location_admin`.

---

## 5. Employee Job Role APIs (`/api/v1/roles`)

- **`GET /api/v1/roles`**: List all employee job titles / roles. Requires `viewer`.
- **`POST /api/v1/roles`**: Create employee job role. Requires `super_admin`.
- **`GET /api/v1/roles/{role_id}`**: Get role details. Requires `viewer`.

---

## 6. Employee Management APIs (`/api/v1/employees`)

- **`GET /api/v1/employees`**: List employees with pagination (`page`, `size`) and filtering (`location_id`, `department_id`, `is_active`, `enrollment_status`, `search`). Requires `viewer`.
- **`POST /api/v1/employees`**: Create employee. Requires `super_admin` or assigned `location_admin`. Validates unique `employee_code` & `email`, department location consistency, and initial enrollment status (`pending`).
- **`GET /api/v1/employees/{employee_id}`**: Retrieve employee profile. Biometric vectors and credentials strictly omitted. Requires `viewer`.
- **`PATCH /api/v1/employees/{employee_id}`**: Update employee profile. Validates cross-location transfer permissions. Requires `super_admin` or assigned `location_admin`.
- **`DELETE /api/v1/employees/{employee_id}`**: Soft-deactivate employee (`is_active=False`). Requires `super_admin` or assigned `location_admin`.
- **`POST /api/v1/employees/{employee_id}/roles`**: Assign job role to employee. Requires `super_admin` or assigned `location_admin`.
- **`DELETE /api/v1/employees/{employee_id}/roles/{role_id}`**: Remove assigned job role. Requires `super_admin` or assigned `location_admin`.

---

## 7. Camera Management APIs (`/api/v1/cameras`)

- **`GET /api/v1/cameras`**: List accessible cameras with pagination and filters (`location_id`, `camera_role`, `stream_type`, `connection_status`, `is_active`, `search`). Requires `viewer`.
- **`POST /api/v1/cameras`**: Register camera. Requires `super_admin` or assigned `location_admin`. Enforces unique `camera_code`, location access, and **strictly rejects inline RTSP credentials**.
- **`GET /api/v1/cameras/{camera_id}`**: Retrieve camera details, attached workstation zones, and event counts. Requires `viewer`.
- **`PATCH /api/v1/cameras/{camera_id}`**: Update camera configuration. Cannot move camera to another facility while zones are attached. Requires `super_admin` or assigned `location_admin`.
- **`DELETE /api/v1/cameras/{camera_id}`**: Soft-deactivate camera (`is_active=False`). Requires `super_admin` or assigned `location_admin`.
- **`POST /api/v1/cameras/{camera_id}/zones/{zone_id}`**: Link workstation zone to camera. Enforces same location consistency. Requires `super_admin` or assigned `location_admin`.
- **`GET /api/v1/cameras/{camera_id}/zones`**: List zones linked to camera. Requires `viewer`.

---

## 8. Workstation Zone APIs (`/api/v1/zones`)

- **`GET /api/v1/zones`**: List zones with pagination and filters (`location_id`, `camera_id`, `assigned_employee_id`, `is_active`, `search`). Requires `viewer`.
- **`POST /api/v1/zones`**: Create workstation zone. Requires `super_admin` or assigned `location_admin`. Validates polygon has $\ge 3$ distinct vertices with points normalized in $[0.0, 1.0]$. Inactivity threshold must be $> 0$.
- **`GET /api/v1/zones/{zone_id}`**: Retrieve zone details. Requires `viewer`.
- **`PATCH /api/v1/zones/{zone_id}`**: Update zone configuration. Requires `super_admin` or assigned `location_admin`.
- **`DELETE /api/v1/zones/{zone_id}`**: Soft-deactivate zone. Requires `super_admin` or assigned `location_admin`.
- **`POST /api/v1/zones/{zone_id}/assign-employee`**: Assign employee to workstation. Enforces that employee and zone belong to the same facility. Requires `super_admin` or assigned `location_admin`.
- **`DELETE /api/v1/zones/{zone_id}/assign-employee`**: Unassign employee from zone. Requires `super_admin` or assigned `location_admin`.

---

## 9. Location Schedule APIs (`/api/v1/locations/{location_id}/schedules`)

- **`GET /api/v1/locations/{location_id}/schedules`**: Retrieve weekly operating schedules (Monday=0..Sunday=6). Requires `viewer`.
- **`POST /api/v1/locations/{location_id}/schedules`**: Create daily schedule. Day must be 0–6; grace period $\ge 0$. Enforces unique day per facility. Requires `super_admin` or assigned `location_admin`.
- **`GET /api/v1/locations/{location_id}/schedules/{day}`**: Retrieve single day schedule. Accepts integer 0–6 or weekday name. Requires `viewer`.
- **`PATCH /api/v1/locations/{location_id}/schedules/{day}`**: Update daily operating hours. Requires `super_admin` or assigned `location_admin`.
- **`DELETE /api/v1/locations/{location_id}/schedules/{day}`**: Delete schedule entry. Requires `super_admin` or assigned `location_admin`.

---

## 10. Face Enrollment APIs

- **`POST /api/v1/employees/{employee_id}/face-enrollments`**: Enroll 512D AuraFace template. Validates length=512, no NaN/Inf, and $L_2$-norm $\|v\|_2 \in [0.95, 1.05]$. Enforces unique active template. Updates `employee.enrollment_status = 'enrolled'`. Requires `super_admin` or assigned `location_admin`.
- **`GET /api/v1/employees/{employee_id}/face-enrollments`**: List template metadata for employee. **Raw embedding vectors are strictly excluded**. Requires `viewer`.
- **`GET /api/v1/face-enrollments/{embedding_id}`**: Retrieve detailed template metadata and employee info. Requires `viewer`.
- **`DELETE /api/v1/face-enrollments/{embedding_id}`**: Soft-deactivate template (`is_active=False`, `is_template=False`). If employee has no remaining active templates, transitions status to `'needs_re_enroll'`. Requires `super_admin` or assigned `location_admin`.
- **`POST /api/v1/face-enrollments/{embedding_id}/set-primary`**: Promote embedding to active primary template; demotes existing primary template in a single atomic transaction. Requires `super_admin` or assigned `location_admin`.

---

## 11. Detection Event APIs (`/api/v1/events`)

- **`POST /api/v1/events`**: Ingest detection event. Validates event type against check constraint, bounds confidence $[0.0, 1.0]$, verifies camera and employee/zone location consistency. Automatically starts/links facility presence sessions on entry/exit cameras, updates workstation presence, links guest visits, and raises critical alerts on after-hours intrusions. Requires `super_admin`, `location_admin`, or `operator`.
- **`GET /api/v1/events`**: List detection events with pagination (`page`, `size`) and filtering (`location_id`, `camera_id`, `employee_id`, `event_type`, `workstation_zone_id`, `tracker_id`, `from_time`, `to_time`). Requires `viewer`.
- **`GET /api/v1/events/{event_id}`**: Retrieve comprehensive event telemetry with joined location, camera, and employee names. Requires `viewer`.

---

## 12. Security & Operational Alert APIs (`/api/v1/alerts`)

- **`GET /api/v1/alerts`**: List alerts with pagination and triage filters (`location_id`, `camera_id`, `employee_id`, `workstation_zone_id`, `alert_type`, `severity`, `status`, `from_time`, `to_time`). Requires `viewer`.
- **`POST /api/v1/alerts`**: Create an alert. Validates location consistency with optional camera/employee/zone. Initial status is `'open'`. Requires `super_admin`, `location_admin`, or `operator`.
- **`GET /api/v1/alerts/{alert_id}`**: Retrieve alert details with audit user emails and timestamps. Requires `viewer`.
- **`POST /api/v1/alerts/{alert_id}/acknowledge`**: Acknowledge an open alert. Records `acknowledged_by_user_id` and timestamp. Rejects already acknowledged or resolved alerts (`400`). Requires `super_admin`, `location_admin`, or `operator`.
- **`POST /api/v1/alerts/{alert_id}/resolve`**: Resolve an alert. Accepts optional `resolution_notes` and boolean `is_false_positive` (transitions to `'resolved'` or `'false_positive'`). Rejects already closed alerts (`400`). Requires `super_admin`, `location_admin`, or `operator`.
- **`PATCH /api/v1/alerts/{alert_id}`**: Update permitted metadata (`title`, `description`, `severity`, `resolution_notes`). Protected fields (`status`, `acknowledged_at`, `resolved_at`) cannot be modified via PATCH. Requires `super_admin`, `location_admin`, or `operator`.

