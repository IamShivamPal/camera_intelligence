# Camera Intelligence — Git & Machine Transfer Guide

**Document ID:** `docs/handover/GIT_MIGRATION_GUIDE.md`  
**Current Git Branch:** `main`  
**Remote Origin:** `https://github.com/IamShivamPal/camera_intelligence.git`  
**Last Remote Commit:** `ac74624 Add directory placeholders for ai_engine, client, docs, and storage`  

---

## 1. Current Working Tree Audit

The current repository contains significant uncommitted work representing all Phase 1 and Phase 2 development.

### 1.1 Modified Tracked Files (8 files)
- `server/app/core/config.py`
- `server/app/database/session.py`
- `server/app/main.py`
- `server/app/models/__init__.py`
- `server/app/models/camera.py`
- `server/app/models/employee.py`
- `server/app/models/location.py`
- `server/app/models/role.py`

### 1.2 Untracked New Files & Directories
- Master runner & commands: `run.ps1`, `COMMANDS.md`
- Database Migrations: `server/alembic.ini`, `server/migrations/`
- Backend APIs: `server/app/api/deps.py`, `server/app/api/v1/`
- Backend Core & Security: `server/app/core/permissions.py`, `server/app/core/security.py`
- Backend Models: `server/app/models/` (alert, department, detection_event, employee_face_embedding, guest_visit, location_schedule, presence_session, user, workstation_zone)
- Backend Schemas: `server/app/schemas/` (11 schema files)
- Backend Services: `server/app/services/` (10 service files)
- Automated Test Suites: `tests/` (7 backend test suites + AI evaluation scripts)
- AI Engine Assets: `ai_engine/models/`, `ai_engine/datasets/`, `ai_engine/third_party/`

---

## 2. Large File & GitHub Quota Warning

> [!WARNING]
> GitHub enforces a strict **100 MB per-file limit** on standard git pushes.
> The file `ai_engine/models/face/auraface_v1_glintr100.onnx` is **260.7 MB**.
> Attempting a standard `git push` without Git LFS will cause GitHub to **reject the push**.

### Large Files in Repository:
1. `ai_engine/models/face/auraface_v1_glintr100.onnx` — **260.7 MB** (Exceeds 100 MB limit!)
2. `ai_engine/models/face/retinaface_r34.pth` — **88.7 MB** (Nearing limit)
3. `ai_engine/models/detection/yolo11s.pt` — **19.3 MB**
4. Test Video Files: `office_test.mp4` (5.5 MB), `1.mp4` (2.7 MB), `2.mp4` (2.7 MB)

---

## 3. Recommended Migration Strategies

You have two reliable options to transfer this project to your new machine:

### Option A (Recommended): Direct Portable Archive (Fastest & Safest)
Because the codebase contains large binary model weights and 117 fully passing tests, transferring an archive via external drive, USB 3.0, or private local network share avoids GitHub 100MB rejection and preserves your exact working tree state.

#### On Old Machine:
1. Create a zip archive of `camera_intelligence`, **excluding** `.venv/` folders:
   ```powershell
   # Open PowerShell in project root
   # Compress while excluding virtual environments
   $sourceDir = "C:\Users\PC\Desktop\Shivam\camera_intelligence"
   $destZip = "D:\camera_intelligence_migration.zip"

   # Or using 7-Zip / Windows Explorer (Exclude server\.venv and ai_engine\.venv)
   ```
2. Export PostgreSQL database dump (see `docs/handover/DATABASE_GUIDE.md`):
   ```powershell
   pg_dump -U postgres -h localhost -p 5432 -d camera_intelligence -F c -b -v -f "D:\camera_intelligence_backup.dump"
   ```
3. Securely note down the `server/.env` configuration parameters.

#### On New Machine:
1. Extract `camera_intelligence_migration.zip` into your new workspace (e.g. `C:\Projects\camera_intelligence`).
2. Follow [docs/handover/NEW_MACHINE_SETUP.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/NEW_MACHINE_SETUP.md) to install Python 3.12, create fresh `.venv` folders, and restore PostgreSQL.
3. Run `.\run.ps1 test-all` to confirm all 117 tests pass.

---

### Option B: Git Push with Git LFS (If Using GitHub)
If you prefer migrating strictly through your GitHub remote:

#### On Old Machine:
1. Install Git LFS:
   ```powershell
   git lfs install
   ```
2. Track large model files with Git LFS:
   ```powershell
   git lfs track "*.onnx"
   git lfs track "*.pth"
   git lfs track "*.pt"
   git lfs track "*.mp4"
   git add .gitattributes
   ```
3. Commit all Phase 1 & Phase 2 work:
   ```powershell
   git add .
   git commit -m "Complete Phase 1 and Phase 2 (Tasks 1-12) with 117 automated tests"
   git push origin main
   ```

#### On New Machine:
1. Clone the repository with Git LFS:
   ```powershell
   git lfs install
   git clone https://github.com/IamShivamPal/camera_intelligence.git
   cd camera_intelligence
   git lfs pull
   ```
2. Follow `NEW_MACHINE_SETUP.md` for environment creation, database restore, and test verification.

---

## 4. Post-Transfer Integrity Verification Checklist

After transferring code to the new machine, run these commands in PowerShell:

```powershell
# 1. Verify Git status is clean and on branch main
git status

# 2. Verify large model weights exist
Test-Path ai_engine/models/face/auraface_v1_glintr100.onnx
Test-Path ai_engine/models/face/retinaface_r34.pth
Test-Path ai_engine/models/detection/yolo11s.pt

# 3. Verify database connectivity and Alembic head
.\run.ps1 db-check
.\run.ps1 migrate-status

# 4. Execute all 7 test suites
.\run.ps1 test-all
```
Once all 4 checks pass with 117/117 tests green, your repository transfer is 100% verified.

