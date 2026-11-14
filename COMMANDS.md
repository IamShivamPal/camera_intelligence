# Camera Intelligence — Unified Command & Operations Reference

This document serves as the master command cheat-sheet and runbook for **Camera Intelligence**. It covers the backend, frontend, database, Docker, virtual environments, and AI engine evaluation scripts.

You can run commands using the master automation script [run.ps1](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/run.ps1) or directly in your shell.

---

## 1. Quick Start with the Master Runner (`run.ps1`)

Run from the project root (`C:\Users\PC\Desktop\Shivam\camera_intelligence`):

```powershell
# Display help and all available commands
.\run.ps1 help

# Check system status (virtual environments, database, migrations)
.\run.ps1 status

# Start the FastAPI backend server (http://127.0.0.1:8000)
.\run.ps1 backend

# Start the React/Vite frontend (http://localhost:5173)
.\run.ps1 frontend

# Test PostgreSQL database connectivity and show table inventory
.\run.ps1 db-check

# Run Alembic migrations to head
.\run.ps1 migrate

# Check current Alembic migration version
.\run.ps1 migrate-status

# Bootstrap initial super_admin user
.\run.ps1 seed-admin
```

---

## 2. Virtual Environments & Shell Activation

This project maintains **two isolated virtual environments**:
- **`server/.venv`**: Backend (FastAPI, SQLAlchemy 2.x, psycopg 3, Alembic, pwdlib/Argon2).
- **`ai_engine/.venv`**: AI Engine (PyTorch, CUDA, ONNX Runtime, RetinaFace, AuraFace, YOLO).

> **Never mix dependencies across environments.**

### Backend Virtual Environment (`server/.venv`)
```powershell
# PowerShell Activation:
.\server\.venv\Scripts\Activate.ps1

# CMD Activation:
server\.venv\Scripts\activate.bat

# Direct Execution (without activating):
.\server\.venv\Scripts\python.exe <script.py>
```

### AI Engine Virtual Environment (`ai_engine/.venv`)
```powershell
# PowerShell Activation:
.\ai_engine\.venv\Scripts\Activate.ps1

# CMD Activation:
ai_engine\.venv\Scripts\activate.bat

# Direct Execution (without activating):
.\ai_engine\.venv\Scripts\python.exe <script.py>
```

---

## 3. Backend Commands (FastAPI + Uvicorn)

### Start Development Server (Auto-reload on code change)
```powershell
# Via runner script:
.\run.ps1 backend

# Direct command:
.\server\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir server --reload --host 127.0.0.1 --port 8000
```
- **API Base:** `http://127.0.0.1:8000`
- **Interactive OpenAPI Docs (Swagger UI):** `http://127.0.0.1:8000/docs`
- **Alternative Redoc:** `http://127.0.0.1:8000/redoc`

### Start Production Server (Multi-worker)
```powershell
.\run.ps1 backend-prod

# Direct command (4 workers):
.\server\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000 --workers 4
```

### Health Endpoints Verification
```powershell
# Via runner script:
.\run.ps1 backend-health

# Manual HTTP requests:
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/health/database
```

---

## 4. Frontend Commands (React + Vite in `client/`)

### Initialize Frontend (when starting Phase 3)
```powershell
cd client
npm create vite@latest . -- --template react-ts
npm install
cd ..
```

### Run Frontend Development Server
```powershell
# Via runner script:
.\run.ps1 frontend

# Direct command:
cd client
npm run dev
```
- **Frontend URL:** `http://localhost:5173`

### Build Production Bundle
```powershell
# Via runner script:
.\run.ps1 frontend-build

# Direct command:
cd client
npm run build
```

---

## 5. Database & Migration Commands (PostgreSQL & Alembic)

All Alembic commands MUST point to `server/alembic.ini` and execute using `server/.venv`:

### Database Connectivity Check
```powershell
.\run.ps1 db-check
```

### Apply Migrations
```powershell
# Via runner script:
.\run.ps1 migrate

# Direct command:
.\server\.venv\Scripts\alembic.exe -c server/alembic.ini upgrade head
```

### Check Current Migration Revision & Heads
```powershell
# Via runner script:
.\run.ps1 migrate-status

# Direct commands:
.\server\.venv\Scripts\alembic.exe -c server/alembic.ini current
.\server\.venv\Scripts\alembic.exe -c server/alembic.ini heads
```

### Generate a New Auto-Detected Migration
```powershell
# Via runner script:
.\run.ps1 migrate-create "add_new_feature_tables"

# Direct command:
.\server\.venv\Scripts\alembic.exe -c server/alembic.ini revision --autogenerate -m "add_new_feature_tables"
```

### View Migration History
```powershell
.\run.ps1 migrate-history

# Direct command:
.\server\.venv\Scripts\alembic.exe -c server/alembic.ini history --verbose
```

---

## 6. Administrative Bootstrap (`super_admin`)

### Run Super Admin Bootstrap
```powershell
# Interactive mode (prompts for email & masked password):
.\run.ps1 seed-admin

# Direct execution with parameters:
.\server\.venv\Scripts\python.exe server/scripts/bootstrap_admin.py --email admin@cameraintelligence.com --password "YourStrongPassword!"

# Environment variable mode (CI/CD / Docker):
$env:BOOTSTRAP_SUPERADMIN_EMAIL = "admin@cameraintelligence.com"
$env:BOOTSTRAP_SUPERADMIN_PASSWORD = "YourStrongPassword!"
.\run.ps1 seed-admin
```

### Check Super Admin Status in Database
```powershell
.\run.ps1 seed-status
```

### Run Authentication & Authorization API Test Suite
```powershell
# Via runner script:
.\run.ps1 test-auth

# Direct:
.\server\.venv\Scripts\python.exe tests/test_auth_api.py -v
```

---

## 7. Authentication Endpoints Reference (`/api/v1/auth`)

- **`POST /api/v1/auth/login`**: Authenticate with JSON `{"email": "...", "password": "..."}` -> returns JWT `access_token`, `expires_in`, `expires_at`, and `user` profile.
- **`GET /api/v1/auth/me`**: Authenticated profile with `Authorization: Bearer <token>`.
- **`POST /api/v1/auth/logout`**: Stateless logout confirmation.
- **Interactive API Documentation:** Available at `http://127.0.0.1:8000/docs`.

---

## 8. Management APIs Reference (`/api/v1/`)

### Location APIs (`/api/v1/locations`)
- **`GET /api/v1/locations`**: List accessible locations (scoped by user assignment, global for `super_admin`).
- **`POST /api/v1/locations`**: Create location (requires `super_admin`).
- **`GET /api/v1/locations/{id}`**: Get location details including department, employee, and camera counts.
- **`PATCH /api/v1/locations/{id}`**: Update location address, timezone, or name (`super_admin` or assigned `location_admin`).
- **`DELETE /api/v1/locations/{id}`**: Soft-deactivate location (`is_active=False`).

### Department APIs (`/api/v1/departments`)
- **`GET /api/v1/departments`**: List departments across accessible locations (optional `?location_id=`, `?is_active=`).
- **`POST /api/v1/departments`**: Create department within a location (enforces unique name & code per location).
- **`GET /api/v1/departments/{id}`**: Get department details.
- **`PATCH /api/v1/departments/{id}`**: Update department name, code, or status.
- **`DELETE /api/v1/departments/{id}`**: Soft-deactivate department (`is_active=False`).

### Employee Job Role APIs (`/api/v1/roles`)
- **`GET /api/v1/roles`**: List all available employee job roles.
- **`POST /api/v1/roles`**: Create employee job role (unique name).
- **`GET /api/v1/roles/{id}`**: Get role details.

### Employee APIs (`/api/v1/employees`)
- **`GET /api/v1/employees`**: List employees with pagination (`page`, `size`) and filtering (`location_id`, `department_id`, `is_active`, `enrollment_status`, `search`).
- **`POST /api/v1/employees`**: Create employee (validates unique `employee_code` & `email`, department/location consistency, role IDs, location permissions).
- **`GET /api/v1/employees/{id}`**: Get employee details (safely omits credentials and biometric vectors).
- **`PATCH /api/v1/employees/{id}`**: Update employee details (validates cross-location transfer permissions).
- **`DELETE /api/v1/employees/{id}`**: Soft-deactivate employee (`is_active=False`).
- **`POST /api/v1/employees/{id}/roles`**: Assign role to employee.
- **`DELETE /api/v1/employees/{id}/roles/{role_id}`**: Remove assigned role from employee.

### Run Automated Management Tests
```powershell
# Via runner script:
.\run.ps1 test-management

# Direct command:
.\server\.venv\Scripts\python.exe tests/test_management_apis.py -v
```

---

## 9. Camera Management & Configuration APIs (`/api/v1/cameras`)

### Camera Endpoints Reference
- **`GET /api/v1/cameras`**: List accessible cameras with pagination (`page`, `size`) and filtering (`location_id`, `camera_role`, `stream_type`, `connection_status`, `is_active`, `search`).
- **`POST /api/v1/cameras`**: Register camera (enforces unique `camera_code`, location existence and authorization, rejects inline RTSP credentials).
- **`GET /api/v1/cameras/{id}`**: Get camera details with location name, associated workstation zones, detection event count, and alert count.
- **`PATCH /api/v1/cameras/{id}`**: Update camera configuration (validates unique code, location transfer permissions, and attached zone consistency).
- **`DELETE /api/v1/cameras/{id}`**: Soft-deactivate camera (`is_active=False`).
- **`POST /api/v1/cameras/{id}/zones/{zone_id}`**: Associate existing workstation zone with camera (validates that camera and zone belong to the same location).
- **`GET /api/v1/cameras/{id}/zones`**: List workstation zones linked to camera.

### RTSP Credential Security Architecture
- Plaintext passwords or inline credentials (e.g., `user:pass@host`) are strictly forbidden in `stream_secret_ref` and rejected by validation.
- API responses never expose credentials or sensitive stream tokens.
- Secret references point to external vaults/secret managers (`stream_secret_ref: str`).

### Run Camera Test Suite
```powershell
# Via runner script:
.\run.ps1 test-cameras

# Direct command:
.\server\.venv\Scripts\python.exe tests/test_camera_apis.py -v
```

---

## 10. Workstation Zone & Location Schedule APIs

### Workstation Zone Endpoints (`/api/v1/zones`)
- **`GET /api/v1/zones`**: List accessible zones (paginated; filters: `location_id`, `camera_id`, `assigned_employee_id`, `is_active`, `search`).
- **`POST /api/v1/zones`**: Create workstation zone (validates normalized polygon coordinates `[[x, y], ...]`, minimum 3 distinct vertices, camera location consistency, inactivity threshold).
- **`GET /api/v1/zones/{zone_id}`**: Get zone details (camera, employee, department, location).
- **`PATCH /api/v1/zones/{zone_id}`**: Update zone configuration.
- **`DELETE /api/v1/zones/{zone_id}`**: Soft-deactivate zone (`is_active=False`).
- **`POST /api/v1/zones/{zone_id}/assign-employee`**: Assign employee to zone (enforces location consistency).
- **`DELETE /api/v1/zones/{zone_id}/assign-employee`**: Remove assigned employee.

### Location Schedule Endpoints (`/api/v1/locations/{location_id}/schedules`)
- **`GET /api/v1/locations/{location_id}/schedules`**: Retrieve weekly operating schedules for location (timezone-aware).
- **`POST /api/v1/locations/{location_id}/schedules`**: Create daily operating schedule (enforces unique day per location, grace minutes >= 0).
- **`GET /api/v1/locations/{location_id}/schedules/{day}`**: Retrieve single day schedule (accepts 0-6 or name e.g. "Monday").
- **`PATCH /api/v1/locations/{location_id}/schedules/{day}`**: Update daily operating hours / grace period.
- **`DELETE /api/v1/locations/{location_id}/schedules/{day}`**: Remove daily schedule entry.

### Run Zone & Schedule Test Suite
```powershell
# Via runner script:
.\run.ps1 test-zones

# Direct command:
.\server\.venv\Scripts\python.exe tests/test_zone_and_schedule_apis.py -v
```

---

## 11. Face Enrollment & Biometric Template APIs

### Face Enrollment Endpoints Reference
- **`POST /api/v1/employees/{employee_id}/face-enrollments`**: Enroll a 512D face template or biometric sample for an employee. Validates 512-dimension vector, numeric finite values (no NaN/Inf), and L2 unit normalization ($0.95 \le \|v\|_2 \le 1.05$). Enforces active template uniqueness per model/version and automatically transitions employee status (`enrolled`).
- **`GET /api/v1/employees/{employee_id}/face-enrollments`**: List enrollment metadata for an employee (paginated; filters: `is_template`, `is_active`, `model_name`). Excludes raw embedding vectors.
- **`GET /api/v1/face-enrollments/{embedding_id}`**: Retrieve detailed template metadata, quality scores, model version, and employee information. Excludes raw vectors.
- **`DELETE /api/v1/face-enrollments/{embedding_id}`**: Soft-deactivate a biometric template (`is_active=False`, `is_template=False`). If the employee has no remaining active templates, transitions `employee.enrollment_status` to `'needs_re_enroll'`.
- **`POST /api/v1/face-enrollments/{embedding_id}/set-primary`**: Promote an existing active embedding to the primary template for its model/version, demoting any existing primary template within a single atomic transaction.

### Biometric Security & Privacy Architecture
- **Vector Sanitization:** Public schemas (`FaceEnrollmentResponse`, `FaceEnrollmentDetailResponse`) omit raw 512-dimensional vector floats and raw images from all API responses and logs.
- **Strict Vector Validation:** Requires exactly 512 dimensions, all finite numbers (no NaN or $\pm\infty$), and unit L2-norm ($0.95 \le \|v\|_2 \le 1.05$).
- **Partial Unique Index Guard:** Protects against duplicate active templates per `(employee_id, model_name, model_version)` via PostgreSQL partial index `uq_active_employee_template`.
- **Role & Location Scoping:**
  - `super_admin`: Global access across all locations and employees.
  - `location_admin`: Can enroll, list, and manage templates only for employees assigned to their accessible locations.
  - `operator` / `viewer`: Read-only access to metadata for assigned locations; all write/modification attempts return HTTP 403 Forbidden.

### Run Face Enrollment Test Suite
```powershell
# Via runner script:
.\run.ps1 test-enrollment

# Direct command:
.\server\.venv\Scripts\python.exe tests/test_face_enrollment_apis.py -v
```

---

## 12. Event Logging, Detection Telemetry & Alert APIs

### Detection Event Endpoints (`/api/v1/events`)
- **`POST /api/v1/events`**: Ingest an AI detection event (e.g. from YOLO, RetinaFace, ByteTrack, or stream analyzer). Validates event type against check constraint (`employee_recognized`, `unknown_person`, `workstation_active`, `workstation_idle`, `after_hours_employee`, `after_hours_intrusion`, `guest_entry`, `guest_exit`). Validates confidence bounds $[0.0, 1.0]$. Enforces location consistency: camera and employee/zone must belong to the same location.
- **`GET /api/v1/events`**: List detection events with pagination (`page`, `size`) and filtering (`location_id`, `camera_id`, `employee_id`, `event_type`, `workstation_zone_id`, `tracker_id`, `from_time`, `to_time`). Non-super-admin users are automatically scoped to authorized locations.
- **`GET /api/v1/events/{event_id}`**: Retrieve comprehensive event details with joined camera, employee, zone, and location details.

### Security & Operational Alert Endpoints (`/api/v1/alerts`)
- **`GET /api/v1/alerts`**: List operational and security alerts (paginated; filters: `location_id`, `camera_id`, `employee_id`, `workstation_zone_id`, `alert_type`, `severity`, `status`, `from_time`, `to_time`).
- **`POST /api/v1/alerts`**: Create an alert (requires `super_admin`, `location_admin`, or `operator`). Validates location authorization and consistency with linked entities.
- **`GET /api/v1/alerts/{alert_id}`**: Retrieve detailed alert information including audit trails (`acknowledged_by`, `resolved_by`, timestamps, notes).
- **`POST /api/v1/alerts/{alert_id}/acknowledge`**: Acknowledge an open alert. Records user ID and timestamp. Rejects invalid transitions (e.g. from resolved/false_positive).
- **`POST /api/v1/alerts/{alert_id}/resolve`**: Resolve an open or acknowledged alert. Supports setting `status` to `'resolved'` or `'false_positive'` with resolution notes.
- **`PATCH /api/v1/alerts/{alert_id}`**: Update permitted non-protected alert fields (`title`, `description`, `severity`, `resolution_notes`). Protected fields (`status`, `acknowledged_at`, `resolved_at`) cannot be modified via PATCH.

### Ephemeral Tracking & Data Privacy Architecture
- **Ephemeral Stream Tracker IDs:** Tracking IDs from ByteTrack (`tracker_id`) are accepted for stream telemetry continuity but are **strictly ephemeral** and never treated as employee identities.
- **Visual Privacy:** Raw video frames and images are never stored in the database. `snapshot_ref` holds external storage URI references only.
- **Automated Lifecycle Integration:**
  - Recognition on entry/exit cameras automatically starts/links facility `PresenceSession`.
  - Workstation active/idle events update workstation presence tracking.
  - Guest entry/exit events track `GuestVisit` status.
  - Critical anomalies (`after_hours_intrusion`, `after_hours_employee`) automatically spawn open security alerts.

### Run Detection Event & Alert Test Suites
```powershell
# Via runner script:
.\run.ps1 test-events
.\run.ps1 test-alerts

# Direct commands:
.\server\.venv\Scripts\python.exe tests/test_event_apis.py -v
.\server\.venv\Scripts\python.exe tests/test_alert_apis.py -v

# Run all test suites:
.\run.ps1 test-all
```

---

## 13. AI Engine Commands (`ai_engine/.venv`)

Run these using `ai_engine/.venv`:

### Face Recognition Evaluation
```powershell
.\run.ps1 ai-eval

# Direct:
.\ai_engine\.venv\Scripts\python.exe tests/evaluate_face_recognition.py
```

### Build Employee Templates (AuraFace 512D)
```powershell
.\run.ps1 ai-templates

# Direct:
.\ai_engine\.venv\Scripts\python.exe tests/build_employee_templates.py
```

### Detection Test (YOLO / RetinaFace)
```powershell
.\run.ps1 ai-test-det

# Direct:
.\ai_engine\.venv\Scripts\python.exe tests/test_detection.py
```

### Face Alignment Test
```powershell
.\run.ps1 ai-align

# Direct:
.\ai_engine\.venv\Scripts\python.exe tests/test_face_alignment.py
```

---

## 14. Docker Commands

### Standalone PostgreSQL Container (if not using local Windows PostgreSQL service)
```powershell
# Start PostgreSQL 16 container on port 5432:
.\run.ps1 docker-pg-start

# Manual command:
docker run --name camera_intelligence_pg `
  -e POSTGRES_USER=postgres `
  -e POSTGRES_PASSWORD=postgres `
  -e POSTGRES_DB=camera_intelligence `
  -p 5432:5432 `
  -d postgres:16-alpine

# Stop and remove PostgreSQL container:
.\run.ps1 docker-pg-stop
```

### Full-Stack Docker Compose (Future production/containerized setups)
```powershell
# Start all containers in background:
.\run.ps1 docker-up
# Or: docker compose up -d

# Stop all containers:
.\run.ps1 docker-down
# Or: docker compose down

# Tail logs:
.\run.ps1 docker-logs
# Or: docker compose logs -f
```

---

## 15. Troubleshooting & Common Issues

### 1. PowerShell Script Execution Policy
If PowerShell blocks running `.\run.ps1` with an execution policy error:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### 2. `ModuleNotFoundError: No module named 'psycopg'`
- **Cause:** Running `alembic` or `python` using the global system Python instead of `server/.venv`.
- **Fix:** Always use `.\server\.venv\Scripts\alembic.exe -c server/alembic.ini ...` or run `.\run.ps1 migrate`.

### 3. Port Conflicts (`8000` or `5432` already in use)
- To check what is listening on port 8000:
  ```powershell
  Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
  ```
- To check what is listening on port 5432:
  ```powershell
  Get-NetTCPConnection -LocalPort 5432 -ErrorAction SilentlyContinue
  ```

