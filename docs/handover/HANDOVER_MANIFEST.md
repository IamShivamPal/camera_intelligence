# Camera Intelligence — Handover Package Manifest

**Document ID:** `docs/handover/HANDOVER_MANIFEST.md`  
**Package Name:** Camera Intelligence Machine Migration Handover Package  
**Generated Date:** November 2026  
**Status:** Complete & Verified  

---

## 1. Handover Documentation Inventory (`docs/handover/`)

| # | Document File | Description & Purpose |
| :---: | :--- | :--- |
| **1** | [PROJECT_MASTER_CONTEXT.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/PROJECT_MASTER_CONTEXT.md) | Complete executive summary, problem statement, technology stack, target personas, architecture diagrams, and CCTV workflow. |
| **2** | [DEVELOPMENT_HISTORY.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/DEVELOPMENT_HISTORY.md) | Detailed chronological narrative of Phase 1 and Phase 2 (Tasks 1–12), files created, models involved, and test milestone progression. |
| **3** | [CURRENT_STATUS.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/CURRENT_STATUS.md) | Precise system state, test suite execution results (117/117 passing), database cleanliness, Git working tree audit, and next action. |
| **4** | [DATABASE_GUIDE.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/DATABASE_GUIDE.md) | Relational architecture, documentation of all 15 tables and 40 foreign keys, check constraints, partial unique indexes, and `pg_dump`/`pg_restore` guide. |
| **5** | [AI_ENGINE_GUIDE.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/AI_ENGINE_GUIDE.md) | AI pipeline specification (YOLO11s, ByteTrack, RetinaFace, AuraFace), 512D embedding normalization, ROC metrics, CUDA setup, and benchmark data. |
| **6** | [API_REFERENCE.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/API_REFERENCE.md) | Comprehensive specification of all 11 registered FastAPI endpoint modules, request/response schemas, validation rules, and error codes. |
| **7** | [NEW_MACHINE_SETUP.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/NEW_MACHINE_SETUP.md) | Step-by-step Windows installation guide for Python 3.12, PostgreSQL, dual virtual environments, and initial service bootstrap. |
| **8** | [GIT_MIGRATION_GUIDE.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/GIT_MIGRATION_GUIDE.md) | Git status audit, working tree preservation, 100MB GitHub limit warning for `auraface_v1_glintr100.onnx`, and transfer options. |
| **9** | [REMAINING_ROADMAP.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/REMAINING_ROADMAP.md) | Complete pending work roadmap for Phase 3 (AI Engine Integration), Phase 4 (React Web App), and Phase 5 (Production Deployment). |
| **10**| [ANTIGRAVITY_NEW_MACHINE_PROMPT.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/ANTIGRAVITY_NEW_MACHINE_PROMPT.md) | Master self-contained prompt to be pasted directly into Antigravity on the new machine to resume development immediately. |
| **11**| [HANDOVER_CHECKLIST.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/HANDOVER_CHECKLIST.md) | Pre-migration, media transfer, new machine setup, and final 117-test validation checklist. |
| **12**| [HANDOVER_MANIFEST.md](file:///C:/Users/PC/Desktop/Shivam/camera_intelligence/docs/handover/HANDOVER_MANIFEST.md) | This manifest document listing all inventory files, included assets, and excluded directories. |

---

## 2. Essential Files & Directories to Transfer

### 2.1 Core Application Code (Must Transfer)
- `server/`: Complete backend application code (`app/`, `migrations/`, `scripts/`, `requirements.txt`, `alembic.ini`).
- `ai_engine/`: Pipeline code, third-party libraries (`third_party/retinaface-pytorch/`), datasets (`datasets/`).
- `docs/`: All documentation including `docs/handover/`.
- `tests/`: All 7 backend test suites and AI evaluation scripts.
- `run.ps1`: Master operational CLI runner.
- `COMMANDS.md`: Operational cheat-sheet and manual reference.
- `client/`: Frontend placeholder directory (`.gitkeep`).
- `storage/`: Visual snapshot directory placeholder (`.gitkeep`).

### 2.2 Large Model Weight Files (Transfer Separately or via LFS)
- `ai_engine/models/detection/yolo11s.pt` (19.3 MB)
- `ai_engine/models/face/auraface_v1_glintr100.onnx` (260.7 MB — Exceeds GitHub 100 MB limit)
- `ai_engine/models/face/retinaface_r34.pth` (88.7 MB)
- `ai_engine/third_party/retinaface-pytorch/weights/mobilenetv1_025.pretrained` (1.95 MB)

### 2.3 Evaluation Test Media (Optional but Recommended)
- `office_test.mp4` (5.5 MB)
- `1.mp4` (2.7 MB)
- `2.mp4` (2.7 MB)
- `bus.jpg` (137 KB)

---

## 3. Excluded Files & Directories (DO NOT Transfer)

| Path / Pattern | Reason for Exclusion | Action on New Machine |
| :--- | :--- | :--- |
| **`server/.venv/`** | Machine-specific Python binaries & absolute symlinks. | Recreated fresh via `python -m venv server/.venv`. |
| **`ai_engine/.venv/`** | Machine-specific CUDA libraries and virtual env. | Recreated fresh via `python -m venv ai_engine/.venv`. |
| **`server/.env`** | Contains machine-specific passwords and local secrets. | Authored fresh on new machine from template. |
| **`runs/`** | Local evaluation outputs, predictions, and benchmark artifacts. | Auto-generated during AI evaluation runs. |
| **`__pycache__/`, `*.pyc`** | Compiled Python bytecode. | Automatically recompiled by Python interpreter. |
| **`scratch/`** | Temporary debug scripts. | Not required for production operation. |

