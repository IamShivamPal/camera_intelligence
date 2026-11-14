# MASTER CONTINUATION PROMPT FOR ANTIGRAVITY ON NEW MACHINE

> **Instructions for the User:**  
> When you open this project in **Antigravity** on your new machine, copy the entire prompt block below and paste it as your first message to the Antigravity agent.

---

```markdown
<USER_REQUEST>
You are now the primary senior coding agent for the Camera Intelligence project.

I have transferred this project from my previous development machine to this new machine.
All foundation work, database architecture, and complete REST APIs have already been designed, implemented, and thoroughly verified.

Before taking any actions or modifying any code, follow these MANDATORY ONBOARDING STEPS:

### 1. Read the Handover Documentation First
Thoroughly read all documentation files located in `docs/handover/`:
- `docs/handover/PROJECT_MASTER_CONTEXT.md` (Project goals, architecture, personas, tech stack)
- `docs/handover/CURRENT_STATUS.md` (Current system health, verified test counts)
- `docs/handover/DEVELOPMENT_HISTORY.md` (Chronological history of Phase 1 and Phase 2)
- `docs/handover/DATABASE_GUIDE.md` (PostgreSQL 15 tables, 40 FKs, partial indexes, constraints)
- `docs/handover/AI_ENGINE_GUIDE.md` (YOLO11s, ByteTrack, RetinaFace, AuraFace pipeline)
- `docs/handover/API_REFERENCE.md` (All 11 registered FastAPI endpoint modules)
- `docs/handover/NEW_MACHINE_SETUP.md` (Windows installation commands and environment setup)
- `docs/handover/GIT_MIGRATION_GUIDE.md` (Git state and large model handling)
- `docs/handover/REMAINING_ROADMAP.md` (Remaining roadmap for Phase 3, 4, and 5)
- `docs/handover/HANDOVER_CHECKLIST.md` (Verification checklists)
- `docs/handover/HANDOVER_MANIFEST.md` (Inventory of files)

### 2. Understand Exactly Where Development Stopped
- **Phase 1 (Backend Foundation):** Complete.
- **Phase 2 (Database & REST APIs):** Completely finished and tested.
  - Task 1: Database Schema Architecture (Complete)
  - Task 2: 13 SQLAlchemy Models + 2 Association Tables (Complete)
  - Task 3: Pre-migration Validation (Complete)
  - Task 4: Clean Initial Migration `573e887c33ec` (Complete)
  - Task 5: Applied to PostgreSQL (Complete)
  - Task 6: Super Admin Bootstrap with Argon2id (Complete)
  - Task 7: JWT Auth & RBAC APIs — 15 Tests (Complete)
  - Task 8: Location, Department, Role & Employee APIs — 24 Tests (Complete)
  - Task 9: Camera Management & Sanitization APIs — 14 Tests (Complete)
  - Task 10: Workstation Zone & Schedule APIs — 21 Tests (Complete)
  - Task 11: Face Enrollment & 512D Biometric APIs — 14 Tests (Complete)
  - Task 12: Event Logging, Telemetry & Alert APIs — 29 Tests (Complete)
- **Cumulative Test Results:** Exactly 117 / 117 automated tests pass via `.\run.ps1 test-all`.
- **Database Status:** Pristine. All 15 application tables are clean with 0 residual test records and exactly 1 active `super_admin` account.
- **Active Alembic Head:** Exactly one head: `573e887c33ec`.

### 3. Verify Baseline Health on This New Machine
Run the following verification checks using the master script:
1. `.\run.ps1 status` — Check virtual environments and database connectivity.
2. `.\run.ps1 migrate-status` — Confirm database is at head `573e887c33ec`.
3. `.\run.ps1 test-all` — Execute all 7 test suites. Confirm that all 117 tests pass.

If any test fails or environment issue is found, report it immediately and fix the environment configuration before proceeding.

### 4. Strict Architecture & Safety Rules
- **DO NOT rewrite or repeat completed work:** Tasks 1 through 12 are complete. Do not re-generate migrations, do not alter existing models, and do not modify passing tests.
- **Strict Environment Isolation:**
  - `server/.venv`: Hosts FastAPI, SQLAlchemy, psycopg 3, and backend tests. Run with `.\server\.venv\Scripts\python.exe`.
  - `ai_engine/.venv`: Hosts PyTorch, CUDA, ONNX Runtime GPU, Ultralytics YOLO, and OpenCV. Run with `.\ai_engine\.venv\Scripts\python.exe`.
  - NEVER install AI dependencies into the server venv or vice-versa.
- **Database Safety:**
  - Never execute destructive schema changes (`DROP TABLE`, unapproved migrations).
  - Clean up any test records in `tearDownClass`.
- **Security & Privacy:**
  - Never expose raw 512D embedding vectors or raw images in public API responses or logs.
  - Never log or hardcode database passwords, JWT secrets, or user passwords.
- **Execution Mode:**
  - Use `.\run.ps1 <command>` for common actions.
  - Run database-connected commands with `BypassSandbox: true` if localhost:5432 socket permission is blocked by the Windows sandbox.

### 5. Next Task to Execute
Once environment parity (117/117 passing tests) is verified, report the baseline status to me and await confirmation to begin:

👉 **Phase 3, Task 1: Production RTSP Camera Stream Ingestion Worker**  
(Refer to `docs/handover/REMAINING_ROADMAP.md` for full specifications).
</USER_REQUEST>
```

