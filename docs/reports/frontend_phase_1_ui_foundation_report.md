# Camera Intelligence — Frontend Phase 1: UI Foundation Report

---

### Executive Summary

Phase 1 of the frontend development delivers a dark enterprise security command-center dashboard for the Camera Intelligence platform. The user interface has been built in `client/` using React 19, Vite 8, TypeScript, Tailwind CSS v4, Lucide React, Recharts, React Router 7, Axios, and TanStack Query v5.

All 12 required sidebar navigation routes, responsive collapse behavior, live telemetry status clocks, JWT authentication flow, protected routing, and real-time backend API data queries are implemented. The production bundle builds in ~400ms with zero errors.

---

### 1. Technology Stack & Dependencies Installed

#### Core Framework & Build Tooling
- **React (`^19.3.1`)** & **React DOM (`^19.3.1`)**: Component architecture and state management.
- **Vite (`^8.3.6`)**: Fast HMR dev server and Rolldown/Rollup-based production bundler.
- **TypeScript (`~7.0.2`)**: Type-safe development with path aliasing (`@/*` $\rightarrow$ `./src/*`).

#### Styling & Design Foundation
- **Tailwind CSS (`^4.3.5`)** with **`@tailwindcss/vite`**: Zero-config dark command-center theme.
- **`clsx` (`^2.1.1`)** & **`tailwind-merge` (`^3.7.0`)**: Utility merge helper (`cn()`).
- **`class-variance-authority` (`^0.7.1`)**: Component variant styling.

#### Routing & Data Layer
- **React Router (`^7.18.5`)**: Client-side routing, protected routes, and breadcrumbs.
- **Axios (`^1.21.1`)**: Reusable HTTP client with JWT interceptor and 401 handling.
- **TanStack Query (`^5.107.1`)**: Server state management with automatic background refetching and caching.

#### Visualization & Icons
- **Recharts (`^3.10.1`)**: 24-hour detection timeline and telemetry area charts.
- **Lucide React (`^1.73.0`)**: Enterprise security iconography.

---

### 2. Files Created & Project Structure

```text
client/
├── .env.example
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.app.json
├── vite.config.ts
└── src/
    ├── main.tsx
    ├── App.tsx
    ├── index.css
    ├── api/
    │   └── client.ts                    # Axios instance with Bearer interceptor & 401 redirect
    ├── context/
    │   ├── AuthContext.tsx              # JWT authentication provider & session state
    │   └── useAuth.ts                   # Auth hook
    ├── lib/
    │   └── utils.ts                     # cn() utility helper
    ├── types/
    │   └── api.ts                       # TypeScript schemas for User, Camera, Zone, Event, Alert
    ├── services/
    │   ├── authService.ts               # POST /api/v1/auth/login, GET /me, POST /logout
    │   ├── cameraService.ts             # GET /api/v1/cameras, GET /api/v1/cameras/{id}
    │   ├── zoneService.ts               # GET /api/v1/zones
    │   ├── eventService.ts              # GET /api/v1/events, GET /api/v1/alerts
    │   └── systemService.ts             # GET /health
    ├── components/
    │   ├── auth/
    │   │   └── ProtectedRoute.tsx       # Auth guard with dark loading spinner
    │   └── layout/
    │       ├── DashboardLayout.tsx      # Master layout container
    │       ├── Sidebar.tsx              # Collapsible 12-route navigation bar
    │       └── Header.tsx               # Top bar, breadcrumbs, UTC clock, notifications, user menu
    └── pages/
        ├── Login.tsx                    # Enterprise login form with error alerts
        ├── Overview.tsx                 # Command center KPI grid, Recharts timeline, camera health
        └── PlaceholderPage.tsx          # Reusable module layout for subsequent phases
```

---

### 3. Application Layout & Navigation

The layout implements a dark enterprise CCTV command center (`#090c10` / `#0d1117` / `#12161f`):

1. **Collapsible Sidebar (`Sidebar.tsx`)**:
   - Toggle button collapsing width between `w-64` (full) and `w-20` (icon-only).
   - "SYSTEM ACTIVE" pulsing emerald status indicator.
   - All 12 routes implemented:
     1. **Overview** (`/`)
     2. **Live Monitoring** (`/live`)
     3. **Cameras** (`/cameras`)
     4. **Employees** (`/employees`)
     5. **Face Enrollment** (`/enrollment`)
     6. **Locations** (`/locations`)
     7. **Workstations** (`/workstations`)
     8. **Attendance** (`/attendance`)
     9. **Analytics** (`/analytics`)
     10. **Events & Alerts** (`/events`)
     11. **AI Engine** (`/ai-engine`)
     12. **Settings** (`/settings`)
2. **Top Navigation Bar (`Header.tsx`)**:
   - Dynamic breadcrumb navigation (`System > Overview`, etc.).
   - Live UTC synchronized security clock (`YYYY-MM-DD HH:mm:ss UTC`).
   - Active security notifications popover with 2 preview alerts and deep-link.
   - User profile dropdown displaying name, email, system role (`SUPER_ADMIN`), and one-click session termination (Logout).

---

### 4. Overview Command Center Dashboard (`Overview.tsx`)

1. **Top KPI Metrics Grid**:
   - **Total Cameras**: Online vs. Offline breakdown with green/red status indicators.
   - **Employees Present**: Active presence session count and facility normalcy score.
   - **Workstations**: Active, Idle, and Vacant zone counts.
   - **Unknown Persons**: Detections requiring operator review today.
   - **Security Alerts**: Critical and Warning count with red alert borders.
   - **AI Engine Status**: GPU hardware (CUDA, RTX 3060), ~18ms latency, 5.0 FPS.
2. **24-Hour Telemetry Area Chart**:
   - Responsive AreaChart with dual series (Detections and Occupancy) with dark tooltips.
3. **Camera Fleet Health Summary**:
   - Table showing Camera Code, Name, Role badge (`entry_exit`, `workstation`), Stream protocol (`RTSP`), Online status indicator, and Sampling FPS.
4. **Recent Real-Time Event Activity**:
   - Live event stream displaying detection type, camera reference, timestamp, and confidence score.
5. **AI Engine Architecture Card**:
   - Hardware and pipeline specs (YOLO11s, ByteTrack, RetinaFace, AuraFace 512D, Farneback Optical Flow, SQLite WAL Queue).
6. **Preview Mode Handling**:
   - When the backend database contains 0 registered cameras, a clearly labeled `PREVIEW MODE` notice explains that preview metrics are displayed for visual demonstration while preserving live backend connectivity indicators.

---

### 5. Authentication & API Architecture

1. **JWT Authentication Flow**:
   - `Login.tsx` posts credentials to `POST /api/v1/auth/login`.
   - On success, `access_token` and `user` profile are cached in `localStorage` and `AuthContext`.
   - Protected routes automatically intercept unauthenticated sessions and redirect to `/login`.
2. **API Client (`client.ts`)**:
   - Base URL defaults to `http://127.0.0.1:8000` or `import.meta.env.VITE_API_URL`.
   - Request interceptor injects `Authorization: Bearer <token>`.
   - Response interceptor listens for HTTP 401, clears invalid tokens, and dispatches an `auth:unauthorized` event to redirect to login.
3. **TanStack Query Caching**:
   - Queries configured with 30s `staleTime`, window focus re-fetch prevention, and manual sync buttons.

---

### 6. Build and Verification Results

#### Production Build Command
```powershell
npm run build
# Or via master controller:
.\run.ps1 frontend-build
```

**Build Output:**
```text
> client@0.0.0 build
> tsc -b && vite build

vite v8.3.8 building client environment for production...
transforming...
✓ 2584 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                   0.66 kB │ gzip:   0.42 kB
dist/assets/index-CSEIMVXi.css   27.96 kB │ gzip:   6.01 kB
dist/assets/index-nyC-e1Rk.js   793.26 kB │ gzip: 239.87 kB

✓ built in 403ms
[OK] Frontend production build complete.
```

#### Code Quality & Linter
```powershell
npm run lint
```
**Output:**
```text
> client@0.0.0 lint
> oxlint

Found 0 warnings and 0 errors.
Finished in 16ms on 20 files with 116 rules using 12 threads.
```

---

### 7. Remaining Work (Subsequent Frontend Phases)

The UI foundation is complete. Upcoming phases will implement:
- **Phase 2**: Live video streaming player canvas (WebRTC/HLS) with overlay bounding boxes.
- **Phase 3**: Camera configuration forms, RTSP validation tools, and location management CRUD.
- **Phase 4**: Workstation polygon drawing editor on live camera snapshots.
- **Phase 5**: Employee face enrollment photo upload, webcam capture, and AuraFace 512D preview.
- **Phase 6**: Events and alerts triage table with filters, pagination, and false-positive resolution workflows.

---
> [!NOTE]
> Frontend Phase 1 (UI Foundation) is complete and verified. Work has stopped per instructions.
