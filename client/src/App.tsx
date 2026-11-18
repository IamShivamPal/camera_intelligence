import React from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import {
  CalendarCheck,
  BarChart3,
  ShieldAlert,
  Cpu,
  Settings,
} from 'lucide-react'

import { AuthProvider } from '@/context/AuthContext'
import ProtectedRoute from '@/components/auth/ProtectedRoute'
import DashboardLayout from '@/components/layout/DashboardLayout'

import Login from '@/pages/Login'
import Overview from '@/pages/Overview'
import Cameras from '@/pages/Cameras'
import Locations from '@/pages/Locations'
import Workstations from '@/pages/Workstations'
import { Employees } from '@/pages/Employees'
import { FaceEnrollment } from '@/pages/FaceEnrollment'
import LiveMonitoring from '@/pages/LiveMonitoring'
import PlaceholderPage from '@/pages/PlaceholderPage'

// Create TanStack Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 30, // 30 seconds
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
})

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <Routes>
            {/* Public Authentication Route */}
            <Route path="/login" element={<Login />} />

            {/* Protected Enterprise Dashboard Routes */}
            <Route element={<ProtectedRoute />}>
              <Route element={<DashboardLayout />}>
                <Route path="/" element={<Overview />} />
                <Route path="/live" element={<LiveMonitoring />} />
                <Route path="/cameras" element={<Cameras />} />
                <Route path="/employees" element={<Employees />} />
                <Route path="/enrollment" element={<FaceEnrollment />} />
                <Route path="/locations" element={<Locations />} />
                <Route path="/workstations" element={<Workstations />} />
                <Route
                  path="/attendance"
                  element={
                    <PlaceholderPage
                      title="Attendance & Presence Sessions"
                      subtitle="Review verified facility entry/exit logs, presence sessions, and automated work shift records."
                      icon={CalendarCheck}
                      badge="OPERATIONS"
                    />
                  }
                />
                <Route
                  path="/analytics"
                  element={
                    <PlaceholderPage
                      title="Business Intelligence & Analytics"
                      subtitle="Analyze occupancy density, foot traffic trends, workstation utilization, and department activity."
                      icon={BarChart3}
                      badge="INTELLIGENCE"
                    />
                  }
                />
                <Route
                  path="/events"
                  element={
                    <PlaceholderPage
                      title="Security Events & Critical Alerts"
                      subtitle="Audit trail of detection events, anomaly triggers, intruder alerts, and triage resolution notes."
                      icon={ShieldAlert}
                      badge="SECURITY"
                    />
                  }
                />
                <Route
                  path="/ai-engine"
                  element={
                    <PlaceholderPage
                      title="AI Engine & Edge Runtime Telemetry"
                      subtitle="Inspect YOLO11s detection rates, GPU CUDA memory allocation, and SQLite WAL queue backlog."
                      icon={Cpu}
                      badge="EDGE RUNTIME"
                    />
                  }
                />
                <Route
                  path="/settings"
                  element={
                    <PlaceholderPage
                      title="System Configuration & RBAC"
                      subtitle="Manage JWT settings, API tokens, user permissions, audit policies, and integration webhooks."
                      icon={Settings}
                      badge="ADMINISTRATION"
                    />
                  }
                />
              </Route>
            </Route>

            {/* Catch-all redirect */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}

export default App
