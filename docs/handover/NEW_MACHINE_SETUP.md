# Camera Intelligence — New Machine Installation & Setup Guide

**Document ID:** `docs/handover/NEW_MACHINE_SETUP.md`  
**Target Operating System:** Windows 10 / Windows 11 (64-bit)  
**Required Python Version:** Python 3.12.10 (exact match recommended)  
**Database:** PostgreSQL 16 or newer (tested on PostgreSQL 18.6)  

---

## 1. System Prerequisites & Software Installation

Before cloning or setting up the code, install the following tools on the new Windows machine:

### 1.1 Git for Windows
- Download from: [https://git-scm.com/download/win](https://git-scm.com/download/win)
- During installation, choose **"Git from the command line and also from 3rd-party software"**.

### 1.2 Python 3.12.10 (64-bit)
- Download Python 3.12.10 installer from: [https://www.python.org/downloads/release/python-31210/](https://www.python.org/downloads/release/python-31210/)
- **CRITICAL:** Check the box **"Add python.exe to PATH"** on the first installation screen.

### 1.3 PostgreSQL 16+
- Download installer from: [https://www.postgresql.org/download/windows/](https://www.postgresql.org/download/windows/)
- During installation, specify a password for the default `postgres` superuser (remember this password).
- Ensure port `5432` is selected.
- Add PostgreSQL `bin` directory (e.g. `C:\Program Files\PostgreSQL\18\bin`) to system `PATH`.

### 1.4 NVIDIA GPU Drivers & CUDA (If Machine Has NVIDIA GPU)
- If your new machine has an NVIDIA GPU (e.g. RTX 3080/4080/4090):
  - Install latest NVIDIA Game Ready / Studio driver.
  - Install CUDA Toolkit 12.4 or 12.6 from NVIDIA Developer portal.

---

## 2. Directory Structure & Code Placement

> [!WARNING]
> **NEVER copy `.venv` folders between different machines.** Virtual environments contain absolute hardcoded paths to the original machine and will break immediately. Recreate both virtual environments fresh on the new machine.

Clone or copy the project into your target directory:
```powershell
# Open PowerShell in your projects directory (e.g., C:\Projects)
cd C:\Projects
git clone https://github.com/IamShivamPal/camera_intelligence.git
cd camera_intelligence
```

---

## 3. Environment 1: Backend Virtual Environment (`server/.venv`)

The backend environment hosts FastAPI, SQLAlchemy, psycopg 3, and Alembic.

### Step 3.1 Create Backend Virtual Environment
```powershell
# Executed from project root: C:\Projects\camera_intelligence
python -m venv server/.venv
```
- **What it does:** Creates a dedicated, isolated Python 3.12 runtime inside `server/.venv`.
- **Why it is needed:** Keeps backend ASGI dependencies completely isolated from heavy deep learning and CUDA libraries.

### Step 3.2 Upgrade Pip & Install Backend Requirements
```powershell
# Executed from project root
.\server\.venv\Scripts\python.exe -m pip install --upgrade pip
.\server\.venv\Scripts\python.exe -m pip install -r server/requirements.txt
```
- **What it does:** Installs FastAPI, Uvicorn, SQLAlchemy 2.x, psycopg 3 binary, Alembic, pwdlib with Argon2id, and python-jose.
- **Why it is needed:** Provides all libraries needed to serve APIs and communicate with PostgreSQL.

---

## 4. Environment 2: AI Engine Virtual Environment (`ai_engine/.venv`)

The AI Engine environment hosts PyTorch, ONNX Runtime GPU, Ultralytics YOLO, and OpenCV.

### Step 4.1 Create AI Engine Virtual Environment
```powershell
# Executed from project root: C:\Projects\camera_intelligence
python -m venv ai_engine/.venv
```
- **What it does:** Creates an isolated Python runtime inside `ai_engine/.venv`.

### Step 4.2 Upgrade Pip
```powershell
.\ai_engine\.venv\Scripts\python.exe -m pip install --upgrade pip
```

### Step 4.3 Install PyTorch with CUDA Acceleration
- **For machines with NVIDIA GPU:**
  ```powershell
  .\ai_engine\.venv\Scripts\pip.exe install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
  ```
- **For machines without NVIDIA GPU (CPU fallback):**
  ```powershell
  .\ai_engine\.venv\Scripts\pip.exe install torch torchvision torchaudio
  ```

### Step 4.4 Install Computer Vision & Inference Libraries
```powershell
.\ai_engine\.venv\Scripts\pip.exe install onnxruntime-gpu ultralytics opencv-python lap psutil matplotlib polars
```
*(If on a machine without NVIDIA GPU, replace `onnxruntime-gpu` with `onnxruntime`).*

### Step 4.5 Verify AI Engine CUDA & Model Execution
```powershell
.\ai_engine\.venv\Scripts\python.exe -c "import torch, onnxruntime as ort; print('PyTorch CUDA:', torch.cuda.is_available()); print('ORT Providers:', ort.get_available_providers())"
```
- **Expected Output:**
  ```text
  PyTorch CUDA: True
  ORT Providers: ['TensorrtExecutionProvider', 'CUDAExecutionProvider', 'CPUExecutionProvider']
  ```

---

## 5. PostgreSQL Database Setup

### Step 5.1 Create Database
Open PowerShell and create the database using PostgreSQL CLI:
```powershell
# Create database
createdb -U postgres -h localhost -p 5432 camera_intelligence
```
*(Enter your PostgreSQL password when prompted).*

---

## 6. Configure Environment Variables (`server/.env`)

Create `server/.env` based on the configuration template below:

```ini
# Application Metadata
APP_NAME=Camera Intelligence
APP_ENV=development
APP_VERSION=1.0.0
API_V1_PREFIX=/api/v1

# PostgreSQL Database Connection URL (Replace YOUR_PASSWORD with actual password)
DATABASE_URL=postgresql+psycopg://postgres:YOUR_PASSWORD@localhost:5432/camera_intelligence

# Allowed CORS Origins (Frontend Vite dev server)
CORS_ORIGINS=["http://localhost:5173", "http://127.0.0.1:5173"]

# JWT Security Settings (Must be at least 32 characters in production)
JWT_SECRET_KEY=dev-insecure-jwt-secret-key-camera-intelligence-change-in-prod-2026
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
```

---

## 7. Run Database Migrations & Bootstrap Admin

### Step 7.1 Apply Alembic Migrations
Run from project root:
```powershell
.\run.ps1 migrate
```
- **What it does:** Executes `alembic -c server/alembic.ini upgrade head` using `server/.venv`.
- **Why it is needed:** Applies the initial schema (`573e887c33ec`), creating all 15 application tables and 40 foreign keys.

### Step 7.2 Bootstrap Initial Super Admin Account
```powershell
.\run.ps1 seed-admin
```
- Prompts for super admin email (e.g. `admin@cameraintelligence.com`) and secure password.
- Hashes password with Argon2id and records user in database.

### Step 7.3 Verify Bootstrap Status
```powershell
.\run.ps1 seed-status
```
- Confirms 1 active `super_admin` account exists in PostgreSQL.

---

## 8. Run Automated Test Verification

Execute all 7 automated test suites:
```powershell
.\run.ps1 test-all
```
- **Expected Result:**
  ```text
  1/7: Authentication & Authorization Tests       -> 15 Passed
  2/7: Location, Department & Employee Tests      -> 24 Passed
  3/7: Camera Management Tests                    -> 14 Passed
  4/7: Workstation Zone & Schedule Tests          -> 21 Passed
  5/7: Face Enrollment & Biometric Tests          -> 14 Passed
  6/7: Detection Event & Telemetry Tests          -> 16 Passed
  7/7: Security & Operational Alert Tests         -> 13 Passed
  =============================================================
  Total: 117 / 117 TESTS PASSED (100% Pass Rate)
  ```

---

## 9. Start Development Server & Open Documentation

### Step 9.1 Start FastAPI Backend
```powershell
.\run.ps1 backend
```
- Starts Uvicorn development server with hot-reload at `http://127.0.0.1:8000`.

### Step 9.2 Inspect OpenAPI Swagger UI
Open your browser to:
```text
http://127.0.0.1:8000/docs
```
You can now test all endpoints interactively using Swagger UI.

