<#
.SYNOPSIS
    Camera Intelligence — Master Development & Operations Controller

.DESCRIPTION
    Unified CLI script for running, testing, managing, and bootstrapping:
    - Backend (FastAPI, Uvicorn, health checks)
    - Frontend (React + Vite in client/)
    - Database (PostgreSQL connectivity, Alembic migrations, admin seed)
    - Virtual Environments (server/.venv and ai_engine/.venv)
    - AI Engine (Face recognition, RetinaFace, AuraFace evaluation)
    - Docker (Container lifecycle and local PostgreSQL container)

.USAGE
    .\run.ps1 <command> [arguments]
    Example: .\run.ps1 backend
    Example: .\run.ps1 db-check
    Example: .\run.ps1 migrate
    Example: .\run.ps1 seed-admin
    Example: .\run.ps1 help
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = "help",

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$ArgsList
)

$ErrorActionPreference = "Stop"

# Base directory paths
$RootDir = $PSScriptRoot
$ServerDir = Join-Path $RootDir "server"
$ClientDir = Join-Path $RootDir "client"
$AIEngineDir = Join-Path $RootDir "ai_engine"

# Virtual environment python and executable paths
$ServerPy = Join-Path $ServerDir ".venv\Scripts\python.exe"
$ServerAlembic = Join-Path $ServerDir ".venv\Scripts\alembic.exe"
$AIPy = Join-Path $AIEngineDir ".venv\Scripts\python.exe"

# Helper print functions
function Write-Header {
    param([string]$Text)
    Write-Host "`n========================================================" -ForegroundColor Cyan
    Write-Host "  $Text" -ForegroundColor Cyan -NoNewline
    Write-Host "`n========================================================" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "[OK] $Text" -ForegroundColor Green
}

function Write-Info {
    param([string]$Text)
    Write-Host "[INFO] $Text" -ForegroundColor Yellow
}

function Write-ErrorMsg {
    param([string]$Text)
    Write-Host "[ERROR] $Text" -ForegroundColor Red
}

# -------------------------------------------------------------
# COMMAND HANDLERS
# -------------------------------------------------------------

function Invoke-Help {
    Write-Header "Camera Intelligence — Master Command Runner"
    Write-Host "Usage: .\run.ps1 <command> [options]`n" -ForegroundColor White

    Write-Host "--- BACKEND COMMANDS ---" -ForegroundColor Yellow
    Write-Host "  backend               Start FastAPI Uvicorn dev server (http://127.0.0.1:8000)"
    Write-Host "  backend-prod          Start FastAPI Uvicorn production server (multiple workers)"
    Write-Host "  backend-health        Test backend health endpoints via curl / HTTP request"

    Write-Host "`n--- FRONTEND COMMANDS ---" -ForegroundColor Yellow
    Write-Host "  frontend              Start Vite dev server in client/ (http://localhost:5173)"
    Write-Host "  frontend-install      Install frontend packages (npm install in client/)"
    Write-Host "  frontend-build        Build production frontend bundle in client/"

    Write-Host "`n--- DATABASE & MIGRATIONS ---" -ForegroundColor Yellow
    Write-Host "  db-check              Test PostgreSQL connection and display public table inventory"
    Write-Host "  migrate               Apply all pending Alembic migrations (alembic upgrade head)"
    Write-Host "  migrate-status        Show current applied revision and head revision"
    Write-Host "  migrate-history       Display full Alembic revision history"
    Write-Host "  migrate-create <msg>  Generate a new auto-detected migration"

    Write-Host "`n--- AUTHENTICATION & BOOTSTRAP ---" -ForegroundColor Yellow
    Write-Host "  seed-admin            Bootstrap super_admin user (interactive, env vars, or flags)"
    Write-Host "  seed-status           Verify super_admin existence and active status in DB"
    Write-Host "  test-auth             Run complete authentication & authorization API test suite"
    Write-Host "  test-management       Run location, department & employee management API tests"
    Write-Host "  test-cameras          Run camera management & configuration API tests"
    Write-Host "  test-zones            Run workstation zone & location schedule API tests"
    Write-Host "  test-enrollment       Run face enrollment & biometric template API tests"
    Write-Host "  test-events           Run detection event & telemetry API tests"
    Write-Host "  test-alerts           Run security & operational alert API tests"
    Write-Host "  test-all              Run all backend automated test suites"

    Write-Host "`n--- VIRTUAL ENVIRONMENTS ---" -ForegroundColor Yellow
    Write-Host "  activate-backend      Show command to activate server/.venv in your shell"
    Write-Host "  activate-ai           Show command to activate ai_engine/.venv in your shell"
    Write-Host "  status                Inspect system environments, DB connection, and heads"

    Write-Host "`n--- AI ENGINE & EVALUATION ---" -ForegroundColor Yellow
    Write-Host "  ai-eval               Run face recognition verification evaluation script"
    Write-Host "  ai-templates          Run AuraFace employee template builder"
    Write-Host "  ai-test-det           Run YOLO / RetinaFace detection test script"
    Write-Host "  ai-align              Run face alignment script"

    Write-Host "`n--- DOCKER COMMANDS ---" -ForegroundColor Yellow
    Write-Host "  docker-up             Start docker compose services in background"
    Write-Host "  docker-down           Stop all docker compose services"
    Write-Host "  docker-logs           Tail docker compose logs"
    Write-Host "  docker-pg-start       Start standalone PostgreSQL container on port 5432"
    Write-Host "  docker-pg-stop        Stop standalone PostgreSQL container"
    Write-Host ""
}

function Invoke-Backend {
    Write-Header "Starting FastAPI Backend Server (Development Mode)"
    if (-not (Test-Path $ServerPy)) {
        Write-ErrorMsg "Backend virtual environment not found at server/.venv"
        exit 1
    }
    Write-Info "Server running at: http://127.0.0.1:8000"
    Write-Info "API Documentation: http://127.0.0.1:8000/docs"
    Write-Info "Press Ctrl+C to stop the server.`n"

    & $ServerPy -m uvicorn app.main:app --app-dir server --reload --host 127.0.0.1 --port 8000 @ArgsList
}

function Invoke-BackendProd {
    Write-Header "Starting FastAPI Backend Server (Production Mode)"
    if (-not (Test-Path $ServerPy)) {
        Write-ErrorMsg "Backend virtual environment not found at server/.venv"
        exit 1
    }
    Write-Info "Binding to 0.0.0.0:8000 with 4 workers..."
    & $ServerPy -m uvicorn app.main:app --app-dir server --host 0.0.0.0 --port 8000 --workers 4 @ArgsList
}

function Invoke-BackendHealth {
    Write-Header "Testing Backend Health Endpoints"
    $urls = @(
        "http://127.0.0.1:8000/",
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/health/database"
    )
    foreach ($u in $urls) {
        try {
            $resp = Invoke-RestMethod -Uri $u -Method Get -TimeoutSec 3
            Write-Success "$u -> $($resp | ConvertTo-Json -Compress)"
        } catch {
            Write-ErrorMsg "$u -> Unreachable or Error ($($_.Exception.Message))"
        }
    }
}

function Invoke-Frontend {
    Write-Header "Starting Frontend Vite Development Server"
    if (-not (Test-Path (Join-Path $ClientDir "package.json"))) {
        Write-Info "client/package.json not found yet."
        Write-Info "To initialize the React + Vite frontend, run:"
        Write-Host "  cd client`n  npm create vite@latest . -- --template react-ts`n  npm install" -ForegroundColor Cyan
        return
    }
    Set-Location $ClientDir
    try {
        npm run dev
    } finally {
        Set-Location $RootDir
    }
}

function Invoke-FrontendInstall {
    Write-Header "Installing Frontend Dependencies"
    if (-not (Test-Path (Join-Path $ClientDir "package.json"))) {
        Write-ErrorMsg "client/package.json not found."
        return
    }
    Set-Location $ClientDir
    try {
        npm install
        Write-Success "Frontend dependencies installed."
    } finally {
        Set-Location $RootDir
    }
}

function Invoke-FrontendBuild {
    Write-Header "Building Frontend Production Bundle"
    Set-Location $ClientDir
    try {
        npm run build
        Write-Success "Frontend production build complete."
    } finally {
        Set-Location $RootDir
    }
}

function Invoke-DbCheck {
    Write-Header "Checking PostgreSQL Database Connectivity & Tables"
    if (-not (Test-Path $ServerPy)) {
        Write-ErrorMsg "Backend venv not found."
        exit 1
    }
    $code = @"
import sys
sys.path.insert(0, 'server')
from sqlalchemy import text
from app.database.session import engine

try:
    with engine.connect() as conn:
        res = conn.execute(text('SELECT 1')).scalar()
        db_name = engine.url.database
        host = engine.url.host
        port = engine.url.port
        print(f'[OK] Connected to PostgreSQL: {host}:{port}/{db_name}')
        tables = [r[0] for r in conn.execute(text(\"SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name\"))]
        print(f'[OK] Total public schema tables: {len(tables)}')
        for t in tables:
            print(f'     - {t}')
        if 'alembic_version' in tables:
            rev = conn.execute(text('SELECT version_num FROM alembic_version')).scalar()
            print(f'[OK] Current Alembic revision: {rev}')
except Exception as e:
    print(f'[ERROR] Failed to connect to database: {e}')
    sys.exit(1)
"@
    & $ServerPy -c $code
}

function Invoke-Migrate {
    Write-Header "Applying Alembic Migrations (upgrade head)"
    if (-not (Test-Path $ServerAlembic)) {
        Write-ErrorMsg "Alembic not found in server/.venv"
        exit 1
    }
    & $ServerAlembic -c server/alembic.ini upgrade head
    Write-Success "Migration upgrade head completed."
}

function Invoke-MigrateStatus {
    Write-Header "Checking Alembic Revision Status"
    Write-Info "Current Database Revision:"
    & $ServerAlembic -c server/alembic.ini current
    Write-Info "`nActive Migration Heads:"
    & $ServerAlembic -c server/alembic.ini heads
}

function Invoke-MigrateHistory {
    Write-Header "Alembic Revision History"
    & $ServerAlembic -c server/alembic.ini history --verbose
}

function Invoke-MigrateCreate {
    param([string]$Message)
    if (-not $Message) {
        $Message = Read-Host "Enter migration description message"
    }
    if (-not $Message) {
        Write-ErrorMsg "Migration message cannot be empty."
        return
    }
    Write-Header "Creating New Migration: '$Message'"
    & $ServerAlembic -c server/alembic.ini revision --autogenerate -m "$Message"
}

function Invoke-SeedAdmin {
    Write-Header "Running Administrative Bootstrap"
    $scriptPath = Join-Path $ServerDir "scripts\bootstrap_admin.py"
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "bootstrap_admin.py not found at $scriptPath"
        return
    }
    & $ServerPy $scriptPath @ArgsList
}

function Invoke-SeedStatus {
    Write-Header "Verifying Super Admin User in Database"
    $code = @"
import sys
sys.path.insert(0, 'server')
from app.database.session import SessionLocal
from app.models.user import User

db = SessionLocal()
try:
    admins = db.query(User).filter(User.system_role == 'super_admin').all()
    print(f'Total super_admin accounts found: {len(admins)}')
    for a in admins:
        print(f'  - ID {a.id}: {a.email} (Active: {a.is_active}, Created: {a.created_at})')
finally:
    db.close()
"@
    & $ServerPy -c $code
}

function Invoke-TestAuth {
    Write-Header "Running Authentication & Authorization Test Suite"
    $scriptPath = Join-Path $RootDir "tests\test_auth_api.py"
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "test_auth_api.py not found at $scriptPath"
        return
    }
    & $ServerPy $scriptPath -v
}

function Invoke-TestManagement {
    Write-Header "Running Location, Department & Employee Management Test Suite"
    $scriptPath = Join-Path $RootDir "tests\test_management_apis.py"
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "test_management_apis.py not found at $scriptPath"
        return
    }
    & $ServerPy $scriptPath -v
}

function Invoke-TestCameras {
    Write-Header "Running Camera Management & Configuration Test Suite"
    $scriptPath = Join-Path $RootDir "tests\test_camera_apis.py"
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "test_camera_apis.py not found at $scriptPath"
        return
    }
    & $ServerPy $scriptPath -v
}

function Invoke-TestZones {
    Write-Header "Running Workstation Zone & Location Schedule Test Suite"
    $scriptPath = Join-Path $RootDir "tests\test_zone_and_schedule_apis.py"
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "test_zone_and_schedule_apis.py not found at $scriptPath"
        return
    }
    & $ServerPy $scriptPath -v
}

function Invoke-TestEnrollment {
    Write-Header "Running Face Enrollment & Biometric Template Test Suite"
    $scriptPath = Join-Path $RootDir "tests\test_face_enrollment_apis.py"
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "test_face_enrollment_apis.py not found at $scriptPath"
        return
    }
    & $ServerPy $scriptPath -v
}

function Invoke-TestEvents {
    Write-Header "Running Detection Event & Telemetry Test Suite"
    $scriptPath = Join-Path $RootDir "tests\test_event_apis.py"
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "test_event_apis.py not found at $scriptPath"
        return
    }
    & $ServerPy $scriptPath -v
}

function Invoke-TestAlerts {
    Write-Header "Running Security & Operational Alert Test Suite"
    $scriptPath = Join-Path $RootDir "tests\test_alert_apis.py"
    if (-not (Test-Path $scriptPath)) {
        Write-ErrorMsg "test_alert_apis.py not found at $scriptPath"
        return
    }
    & $ServerPy $scriptPath -v
}

function Invoke-TestAll {
    Write-Header "Running All Automated Test Suites"
    Write-Info "1/7: Authentication & Authorization Tests"
    & $ServerPy (Join-Path $RootDir "tests\test_auth_api.py") -v
    Write-Info "2/7: Location, Department & Employee Management Tests"
    & $ServerPy (Join-Path $RootDir "tests\test_management_apis.py") -v
    Write-Info "3/7: Camera Management & Configuration Tests"
    & $ServerPy (Join-Path $RootDir "tests\test_camera_apis.py") -v
    Write-Info "4/7: Workstation Zone & Location Schedule Tests"
    & $ServerPy (Join-Path $RootDir "tests\test_zone_and_schedule_apis.py") -v
    Write-Info "5/7: Face Enrollment & Biometric Template Tests"
    & $ServerPy (Join-Path $RootDir "tests\test_face_enrollment_apis.py") -v
    Write-Info "6/7: Detection Event & Telemetry Tests"
    & $ServerPy (Join-Path $RootDir "tests\test_event_apis.py") -v
    Write-Info "7/7: Security & Operational Alert Tests"
    & $ServerPy (Join-Path $RootDir "tests\test_alert_apis.py") -v
}

function Invoke-ActivateBackend {
    Write-Header "Backend Virtual Environment (server/.venv)"
    Write-Host "To activate in your current PowerShell session, copy & run:" -ForegroundColor Yellow
    Write-Host "  .\server\.venv\Scripts\Activate.ps1`n" -ForegroundColor White
    Write-Host "Or run any backend python command directly without activating:" -ForegroundColor Yellow
    Write-Host "  .\server\.venv\Scripts\python.exe <script.py>`n" -ForegroundColor White
}

function Invoke-ActivateAI {
    Write-Header "AI Engine Virtual Environment (ai_engine/.venv)"
    Write-Host "To activate in your current PowerShell session, copy & run:" -ForegroundColor Yellow
    Write-Host "  .\ai_engine\.venv\Scripts\Activate.ps1`n" -ForegroundColor White
    Write-Host "Or run any AI python command directly without activating:" -ForegroundColor Yellow
    Write-Host "  .\ai_engine\.venv\Scripts\python.exe <script.py>`n" -ForegroundColor White
}

function Invoke-Status {
    Write-Header "Camera Intelligence System Status"
    $backendStatus = if (Test-Path $ServerPy) { "Ready (server/.venv)" } else { "Missing" }
    $aiStatus = if (Test-Path $AIPy) { "Ready (ai_engine/.venv)" } else { "Missing" }
    $frontendStatus = if (Test-Path (Join-Path $ClientDir "package.json")) { "Initialized" } else { "Empty (client/)" }

    Write-Host "Root Directory:     $RootDir"
    Write-Host "Backend Venv:       $backendStatus"
    Write-Host "AI Engine Venv:     $aiStatus"
    Write-Host "Frontend App:       $frontendStatus"

    Write-Host "`nTesting Database Connection:" -ForegroundColor Yellow
    Invoke-DbCheck

    Write-Host "`nTesting Migration State:" -ForegroundColor Yellow
    Invoke-MigrateStatus
}

function Invoke-AIEval {
    Write-Header "Running Face Recognition Evaluation (AI Engine)"
    $script = Join-Path $RootDir "tests\evaluate_face_recognition.py"
    if (Test-Path $script) {
        & $AIPy $script @ArgsList
    } else {
        Write-ErrorMsg "$script not found."
    }
}

function Invoke-AITemplates {
    Write-Header "Building AuraFace Employee Templates"
    $script = Join-Path $RootDir "tests\build_employee_templates.py"
    if (Test-Path $script) {
        & $AIPy $script @ArgsList
    } else {
        Write-ErrorMsg "$script not found."
    }
}

function Invoke-AITestDet {
    Write-Header "Running Detection Test"
    $script = Join-Path $RootDir "tests\test_detection.py"
    if (Test-Path $script) {
        & $AIPy $script @ArgsList
    } else {
        Write-ErrorMsg "$script not found."
    }
}

function Invoke-AIAlign {
    Write-Header "Running Face Alignment Test"
    $script = Join-Path $RootDir "tests\test_face_alignment.py"
    if (Test-Path $script) {
        & $AIPy $script @ArgsList
    } else {
        Write-ErrorMsg "$script not found."
    }
}

function Invoke-DockerUp {
    Write-Header "Starting Docker Compose Services"
    docker compose up -d
}

function Invoke-DockerDown {
    Write-Header "Stopping Docker Compose Services"
    docker compose down
}

function Invoke-DockerLogs {
    Write-Header "Tailing Docker Compose Logs"
    docker compose logs -f
}

function Invoke-DockerPgStart {
    Write-Header "Starting Standalone PostgreSQL Docker Container"
    docker run --name camera_intelligence_pg `
        -e POSTGRES_USER=postgres `
        -e POSTGRES_PASSWORD=postgres `
        -e POSTGRES_DB=camera_intelligence `
        -p 5432:5432 `
        -d postgres:16-alpine
    Write-Success "PostgreSQL container started on port 5432."
}

function Invoke-DockerPgStop {
    Write-Header "Stopping Standalone PostgreSQL Docker Container"
    docker stop camera_intelligence_pg
    docker rm camera_intelligence_pg
    Write-Success "PostgreSQL container stopped and removed."
}

# -------------------------------------------------------------
# MAIN DISPATCHER
# -------------------------------------------------------------
switch ($Command.ToLower()) {
    "backend"           { Invoke-Backend }
    "backend-prod"      { Invoke-BackendProd }
    "backend-health"    { Invoke-BackendHealth }
    "frontend"          { Invoke-Frontend }
    "frontend-install"  { Invoke-FrontendInstall }
    "frontend-build"    { Invoke-FrontendBuild }
    "db-check"          { Invoke-DbCheck }
    "migrate"           { Invoke-Migrate }
    "migrate-status"    { Invoke-MigrateStatus }
    "migrate-history"   { Invoke-MigrateHistory }
    "migrate-create"    { Invoke-MigrateCreate ($ArgsList -join " ") }
    "seed-admin"        { Invoke-SeedAdmin }
    "seed-status"       { Invoke-SeedStatus }
    "test-auth"         { Invoke-TestAuth }
    "test-management"   { Invoke-TestManagement }
    "test-cameras"      { Invoke-TestCameras }
    "test-zones"        { Invoke-TestZones }
    "test-enrollment"   { Invoke-TestEnrollment }
    "test-events"       { Invoke-TestEvents }
    "test-alerts"       { Invoke-TestAlerts }
    "test-all"          { Invoke-TestAll }
    "activate-backend"  { Invoke-ActivateBackend }
    "activate-ai"       { Invoke-ActivateAI }
    "status"            { Invoke-Status }
    "ai-eval"           { Invoke-AIEval }
    "ai-templates"      { Invoke-AITemplates }
    "ai-test-det"       { Invoke-AITestDet }
    "ai-align"          { Invoke-AIAlign }
    "docker-up"         { Invoke-DockerUp }
    "docker-down"       { Invoke-DockerDown }
    "docker-logs"       { Invoke-DockerLogs }
    "docker-pg-start"   { Invoke-DockerPgStart }
    "docker-pg-stop"    { Invoke-DockerPgStop }
    default             { Invoke-Help }
}
