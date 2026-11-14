# Camera Intelligence — Machine Migration Checklist

**Document ID:** `docs/handover/HANDOVER_CHECKLIST.md`  
**Purpose:** Step-by-step verification checklist to guarantee a smooth, zero-downtime transfer to the new machine.

---

## 1. Old Machine Pre-Migration Checklist

- [ ] **Verify Test Suite Status:** Run `.\run.ps1 test-all` and ensure 117 / 117 tests pass.
- [ ] **Verify Database Cleanliness:** Run row count check to ensure zero residual test rows and only 1 super_admin user.
- [ ] **Verify Alembic Revision:** Run `.\run.ps1 migrate-status` to ensure database is at head `573e887c33ec`.
- [ ] **Create PostgreSQL Backup:** Export database using `pg_dump -U postgres -h localhost -p 5432 -d camera_intelligence -F c -b -v -f camera_intelligence_backup.dump`.
- [ ] **Archive Codebase:** Compress `camera_intelligence` project directory, strictly **excluding** `server/.venv/`, `ai_engine/.venv/`, and `runs/detect/`.
- [ ] **Verify Large AI Model Weights Are Present:**
  - [ ] `ai_engine/models/detection/yolo11s.pt` (19.3 MB)
  - [ ] `ai_engine/models/face/auraface_v1_glintr100.onnx` (260.7 MB)
  - [ ] `ai_engine/models/face/retinaface_r34.pth` (88.7 MB)
  - [ ] `ai_engine/third_party/retinaface-pytorch/weights/mobilenetv1_025.pretrained` (1.95 MB)
- [ ] **Securely Record Configuration:** Note down database credentials and JWT secret from `server/.env`.

---

## 2. Transfer & Media Checklist

- [ ] **Option A (Physical / Network Transfer):** Copy `camera_intelligence.zip` (with code, docs, models) and `camera_intelligence_backup.dump` to portable SSD / network drive.
- [ ] **Option B (Git Transfer):** Ensure Git LFS is installed and tracking large model files before pushing to remote repository.
- [ ] **Confirm File Hashes:** Verify that the 260.7 MB `auraface_v1_glintr100.onnx` file transferred without corruption.

---

## 3. New Machine Setup Checklist

- [ ] **Install Prerequisites:**
  - [ ] Git for Windows installed and accessible via `git --version`.
  - [ ] Python 3.12.10 (64-bit) installed with "Add python.exe to PATH" enabled. Verify with `python --version`.
  - [ ] PostgreSQL 16+ installed and running as a service on port 5432.
  - [ ] NVIDIA GPU Driver & CUDA Toolkit installed (if NVIDIA GPU available). Verify with `nvidia-smi`.
- [ ] **Place Project Files:** Extract project into clean directory (e.g. `C:\Projects\camera_intelligence`).
- [ ] **Set Up Backend Virtual Environment (`server/.venv`):**
  - [ ] `python -m venv server/.venv`
  - [ ] `.\server\.venv\Scripts\python.exe -m pip install --upgrade pip`
  - [ ] `.\server\.venv\Scripts\python.exe -m pip install -r server/requirements.txt`
- [ ] **Set Up AI Engine Virtual Environment (`ai_engine/.venv`):**
  - [ ] `python -m venv ai_engine/.venv`
  - [ ] `.\ai_engine\.venv\Scripts\python.exe -m pip install --upgrade pip`
  - [ ] `.\ai_engine\.venv\Scripts\pip.exe install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124` (or CPU equivalent)
  - [ ] `.\ai_engine\.venv\Scripts\pip.exe install onnxruntime-gpu ultralytics opencv-python lap psutil matplotlib polars`
- [ ] **Configure PostgreSQL Database:**
  - [ ] Create database: `createdb -U postgres -h localhost -p 5432 camera_intelligence`
  - [ ] Restore database backup: `pg_restore -U postgres -h localhost -p 5432 -d camera_intelligence -v --no-owner --no-acl camera_intelligence_backup.dump`
- [ ] **Configure Environment File:**
  - [ ] Create `server/.env` with correct `DATABASE_URL` (matching PostgreSQL password).
- [ ] **Verify Migrations:** Run `.\run.ps1 migrate-status` and confirm revision `573e887c33ec`.

---

## 4. Final Validation & Onboarding Checklist

- [ ] **Execute All Tests:** Run `.\run.ps1 test-all` on the new machine.
  - [ ] Authentication & RBAC Tests: 15 / 15 Passed
  - [ ] Management APIs Tests: 24 / 24 Passed
  - [ ] Camera APIs Tests: 14 / 14 Passed
  - [ ] Workstation Zone & Schedule Tests: 21 / 21 Passed
  - [ ] Face Enrollment & Biometric Tests: 14 / 14 Passed
  - [ ] Detection Event Telemetry Tests: 16 / 16 Passed
  - [ ] Security & Operational Alert Tests: 13 / 13 Passed
  - [ ] **Total: 117 / 117 Tests Passed (100% Green)**
- [ ] **Start Backend:** Run `.\run.ps1 backend` and access `http://127.0.0.1:8000/docs`.
- [ ] **Launch Antigravity:** Open the project in Antigravity on the new machine, paste `docs/handover/ANTIGRAVITY_NEW_MACHINE_PROMPT.md`, and proceed to **Phase 3: AI Engine Integration**.

