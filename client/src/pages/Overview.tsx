import React, { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Camera,
  Users,
  Monitor,
  ShieldAlert,
  UserX,
  Cpu,
  Activity,
  RefreshCw,
  AlertCircle,
  Clock,
  Layers,
  HelpCircle,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts'
import { cameraService } from '@/services/cameraService'
import { zoneService } from '@/services/zoneService'
import { eventService } from '@/services/eventService'
import { employeeService } from '@/services/employeeService'
import { systemService } from '@/services/systemService'
import { cn } from '@/lib/utils'

export const Overview: React.FC = () => {
  // 1. Query Cameras
  const {
    data: cameraData,
    isLoading: camerasLoading,
    isError: camerasError,
    refetch: refetchCameras,
  } = useQuery({
    queryKey: ['cameras'],
    queryFn: () => cameraService.getCameras({ page: 1, size: 50 }),
  })

  // 2. Query Workstation Zones
  const {
    data: zoneData,
    isLoading: zonesLoading,
    refetch: refetchZones,
  } = useQuery({
    queryKey: ['zones'],
    queryFn: () => zoneService.getZones({ page: 1, size: 100 }),
  })

  // 3. Query Recent Events
  const {
    data: eventData,
    isLoading: eventsLoading,
    isError: eventsError,
    refetch: refetchEvents,
  } = useQuery({
    queryKey: ['events'],
    queryFn: () => eventService.getEvents({ page: 1, size: 10 }),
  })

  // 4. Query Unknown Person Events (Real count)
  const {
    data: unknownEventsData,
    isLoading: unknownLoading,
  } = useQuery({
    queryKey: ['events', 'unknown'],
    queryFn: () => eventService.getEvents({ event_type: 'unknown_person', size: 1 }),
  })

  // 5. Query Open Alerts (Real count)
  const {
    data: alertData,
    isLoading: alertsLoading,
    refetch: refetchAlerts,
  } = useQuery({
    queryKey: ['alerts', 'open'],
    queryFn: () => eventService.getAlerts({ status: 'open', size: 10 }),
  })

  // 6. Query Employees (Real count)
  const {
    data: employeeData,
    isLoading: employeesLoading,
  } = useQuery({
    queryKey: ['employees'],
    queryFn: () => employeeService.getEmployees({ is_active: true, size: 1 }),
  })

  // 7. Query Backend Health
  const {
    data: healthData,
    isLoading: healthLoading,
    isError: healthError,
    refetch: refetchHealth,
  } = useQuery({
    queryKey: ['health'],
    queryFn: () => systemService.getHealth(),
  })

  const refreshAll = () => {
    refetchCameras()
    refetchZones()
    refetchEvents()
    refetchAlerts()
    refetchHealth()
  }

  // Camera Metrics
  const totalCameras = cameraData?.total ?? 0
  const onlineCameras =
    cameraData?.items?.filter((c) => c.connection_status === 'online').length ?? 0
  const offlineCameras =
    cameraData?.items?.filter((c) => c.connection_status === 'offline').length ?? 0
  const unknownCameras =
    cameraData?.items?.filter(
      (c) => c.connection_status === 'unknown' || c.connection_status === 'degraded'
    ).length ?? 0

  // Workstation Metrics
  const totalZones = zoneData?.total ?? 0
  const activeZones = zoneData?.items?.filter((z) => z.is_active).length ?? 0

  // Event & Alert Metrics
  const unknownPersonsCount = unknownEventsData?.total ?? 0
  const openAlertsCount = alertData?.total ?? 0
  const criticalAlertsCount =
    alertData?.items?.filter((a) => a.severity === 'critical').length ?? 0

  // Employee Metrics
  const totalActiveEmployees = employeeData?.total ?? 0

  // Genuine Event Distribution by Hour for Timeline
  const timelineData = useMemo(() => {
    const items = eventData?.items || []
    if (items.length === 0) return []

    const hourBuckets: Record<string, number> = {}
    items.forEach((item) => {
      const ts = item.occurred_at || item.created_at
      if (!ts) return
      const date = new Date(ts)
      if (isNaN(date.getTime())) return
      const hourStr = `${date.getHours().toString().padStart(2, '0')}:00`
      hourBuckets[hourStr] = (hourBuckets[hourStr] || 0) + 1
    })

    return Object.entries(hourBuckets).map(([time, count]) => ({
      time,
      detections: count,
    }))
  }, [eventData])

  const backendOnline = !healthLoading && !healthError && healthData?.status === 'healthy'

  return (
    <div className="space-y-6">
      {/* Header Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-[#1e2633] pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            Security Command Center
            <span
              className={cn(
                'rounded border px-2 py-0.5 text-[10px] font-mono',
                backendOnline
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                  : 'border-rose-500/30 bg-rose-500/10 text-rose-400'
              )}
            >
              {backendOnline ? 'BACKEND ONLINE' : 'BACKEND DISCONNECTED'}
            </span>
          </h1>
          <p className="mt-1 text-xs text-slate-400 font-mono">
            REAL-TIME DETECTION TELEMETRY &bull; WORKSTATION OCCUPANCY &bull; SURVEILLANCE
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded border border-[#1e2633] bg-[#0d1117] px-3 py-1.5 text-xs text-slate-300">
            <span
              className={cn(
                'h-2 w-2 rounded-full',
                backendOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-400'
              )}
            />
            <span className="font-mono text-[11px]">
              API: {backendOnline ? `HEALTHY (v${healthData?.version || '1.0.0'})` : 'UNREACHABLE'}
            </span>
          </div>

          <button
            onClick={refreshAll}
            className="flex items-center gap-1.5 rounded-md border border-[#1e2633] bg-[#12161f] px-3 py-1.5 text-xs font-mono text-slate-300 hover:text-white hover:bg-[#1a202c] transition-colors"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            <span>SYNC DATA</span>
          </button>
        </div>
      </div>

      {/* Backend Offline Warning Banner */}
      {!backendOnline && !healthLoading && (
        <div className="flex items-start gap-3 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300 font-mono">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
          <div>
            <p className="font-bold">FastAPI Backend Unreachable (http://127.0.0.1:8000)</p>
            <p className="text-[11px] text-rose-400/80 mt-0.5">
              Please ensure the backend server is running via <code className="bg-rose-950/40 px-1 py-0.5 rounded">.\run.ps1 backend</code>. Real-time metrics will reconnect automatically.
            </p>
          </div>
        </div>
      )}

      {/* KPI Cards Grid — 100% Genuine Backend Metrics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        {/* 1. Total Cameras */}
        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Cameras</span>
            <Camera className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {camerasLoading ? '...' : totalCameras}
            </span>
            <span className="text-xs text-slate-400 font-mono">TOTAL</span>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#1a202c] pt-2 text-[10px] font-mono">
            <span className="flex items-center gap-1 text-emerald-400">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
              {camerasLoading ? '-' : onlineCameras} ONLINE
            </span>
            <span className="flex items-center gap-1 text-slate-400">
              <span className="h-1.5 w-1.5 rounded-full bg-rose-400" />
              {camerasLoading ? '-' : offlineCameras + unknownCameras} OFFLINE
            </span>
          </div>
        </div>

        {/* 2. Registered Employees */}
        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Employees</span>
            <Users className="h-4 w-4 text-blue-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {employeesLoading ? '...' : totalActiveEmployees}
            </span>
            <span className="text-xs text-slate-400 font-mono">ACTIVE</span>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#1a202c] pt-2 text-[10px] font-mono text-slate-400">
            <span>ENROLLED IN SYSTEM</span>
            <span className="text-slate-500 font-mono" title="Presence API endpoint not exposed in v1">
              PRESENCE API: N/A
            </span>
          </div>
        </div>

        {/* 3. Workstation Zones */}
        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Workstations</span>
            <Monitor className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {zonesLoading ? '...' : totalZones}
            </span>
            <span className="text-xs text-slate-400 font-mono">ZONES</span>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#1a202c] pt-2 text-[10px] font-mono text-slate-400">
            <span className="text-emerald-400">{activeZones} ACTIVE</span>
            <span>{totalZones - activeZones} INACTIVE</span>
          </div>
        </div>

        {/* 4. Unknown Persons */}
        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Unknown</span>
            <UserX className="h-4 w-4 text-amber-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {unknownLoading ? '...' : unknownPersonsCount}
            </span>
            <span className="text-xs text-slate-400 font-mono">EVENTS</span>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#1a202c] pt-2 text-[10px] font-mono text-slate-400">
            <span>UNIDENTIFIED PERSONS</span>
            <span className={unknownPersonsCount > 0 ? 'text-amber-400' : 'text-slate-500'}>
              {unknownPersonsCount > 0 ? 'REVIEW' : 'CLEAR'}
            </span>
          </div>
        </div>

        {/* 5. Active Security Alerts */}
        <div
          className={cn(
            'rounded-xl border p-4 shadow-sm transition-colors',
            openAlertsCount > 0
              ? 'border-rose-500/40 bg-rose-500/5'
              : 'border-[#1e2633] bg-[#0d1117]'
          )}
        >
          <div className="flex items-center justify-between text-slate-400">
            <span
              className={cn(
                'text-[11px] font-mono tracking-wider uppercase',
                openAlertsCount > 0 ? 'text-rose-400 font-bold' : 'text-slate-400'
              )}
            >
              Security Alerts
            </span>
            <ShieldAlert
              className={cn('h-4 w-4', openAlertsCount > 0 ? 'text-rose-400' : 'text-slate-400')}
            />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span
              className={cn(
                'text-2xl font-bold font-mono',
                openAlertsCount > 0 ? 'text-rose-400' : 'text-slate-100'
              )}
            >
              {alertsLoading ? '...' : openAlertsCount}
            </span>
            <span className="text-xs text-slate-400 font-mono">OPEN</span>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#1a202c] pt-2 text-[10px] font-mono">
            <span className={criticalAlertsCount > 0 ? 'text-rose-400' : 'text-slate-400'}>
              {criticalAlertsCount} CRITICAL
            </span>
            <span className="text-slate-400">
              {openAlertsCount - criticalAlertsCount} STANDARD
            </span>
          </div>
        </div>

        {/* 6. AI Engine State */}
        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">AI Engine</span>
            <Cpu className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-xl font-bold font-mono text-slate-200">STANDALONE</span>
          </div>
          <div className="mt-3 flex items-center justify-between border-t border-[#1a202c] pt-2 text-[10px] font-mono text-slate-400">
            <span>DAEMON RUNTIME</span>
            <span className="text-emerald-400" title="Edge service runs as independent service">
              PYTHON 3.10
            </span>
          </div>
        </div>
      </div>

      {/* Main Analysis Section */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Left Column (2 Cols): Event Distribution Timeline + Camera Matrix */}
        <div className="space-y-6 lg:col-span-2">
          {/* Activity Timeline Chart */}
          <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-[#1e2633] pb-3">
              <div>
                <h2 className="text-sm font-semibold text-slate-100 font-mono uppercase tracking-wider">
                  Detection Event Timeline
                </h2>
                <p className="text-[11px] text-slate-400">
                  Hourly distribution of genuine detection events ingested by the backend.
                </p>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                {eventData?.total ?? 0} TOTAL INGESTED
              </span>
            </div>

            <div className="mt-4 h-64 w-full">
              {eventsLoading ? (
                <div className="flex h-full items-center justify-center font-mono text-xs text-slate-400">
                  Loading timeline telemetry...
                </div>
              ) : timelineData.length > 0 ? (
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={timelineData}>
                    <defs>
                      <linearGradient id="colorDetections" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1c2331" />
                    <XAxis dataKey="time" stroke="#64748b" fontSize={11} fontFamily="monospace" />
                    <YAxis stroke="#64748b" fontSize={11} fontFamily="monospace" allowDecimals={false} />
                    <Tooltip
                      contentStyle={{
                        backgroundColor: '#12161f',
                        borderColor: '#232c3d',
                        borderRadius: '8px',
                        fontSize: '11px',
                        fontFamily: 'monospace',
                      }}
                    />
                    <Area
                      type="monotone"
                      dataKey="detections"
                      name="Detections"
                      stroke="#10b981"
                      strokeWidth={2}
                      fillOpacity={1}
                      fill="url(#colorDetections)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="flex h-full flex-col items-center justify-center rounded-lg border border-dashed border-[#1c2331] p-6 text-center">
                  <Activity className="h-8 w-8 text-slate-500 mb-2 opacity-50" />
                  <p className="text-xs font-mono font-semibold text-slate-300">
                    No Detection Events Recorded
                  </p>
                  <p className="text-[11px] text-slate-500 max-w-sm mt-1">
                    Timeline graph will plot hourly frequencies as the AI Engine Edge Service ingests camera detections.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Genuine Camera Fleet Table */}
          <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-[#1e2633] pb-3">
              <div>
                <h2 className="text-sm font-semibold text-slate-100 font-mono uppercase tracking-wider">
                  Camera Fleet Status
                </h2>
                <p className="text-[11px] text-slate-400">
                  Registered cameras, configured stream protocols, and current backend connection state.
                </p>
              </div>
              <span className="text-[11px] font-mono text-slate-400">
                {camerasLoading ? 'LOADING...' : `${totalCameras} REGISTERED`}
              </span>
            </div>

            <div className="mt-3 overflow-x-auto">
              {camerasLoading ? (
                <div className="py-8 text-center font-mono text-xs text-slate-400">
                  Querying camera inventory...
                </div>
              ) : camerasError ? (
                <div className="py-6 text-center text-xs text-rose-400 font-mono">
                  Failed to load camera records from API.
                </div>
              ) : (cameraData?.items?.length ?? 0) === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <Camera className="h-8 w-8 text-slate-500 mb-2 opacity-50" />
                  <p className="text-xs font-mono font-semibold text-slate-300">
                    No Cameras Registered in System
                  </p>
                  <p className="text-[11px] text-slate-500 max-w-sm mt-1">
                    Add cameras using the Cameras module or register RTSP streams via POST /api/v1/cameras.
                  </p>
                </div>
              ) : (
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-[#1e2633] text-[10px] font-mono uppercase text-slate-400">
                      <th className="py-2.5">Camera Code</th>
                      <th className="py-2.5">Name</th>
                      <th className="py-2.5">Role</th>
                      <th className="py-2.5">Stream Type</th>
                      <th className="py-2.5">Connection Status</th>
                      <th className="py-2.5 text-right">Last Heartbeat</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#18202d] text-slate-300 font-mono text-[11px]">
                    {cameraData?.items?.map((cam) => (
                      <tr key={cam.id} className="hover:bg-[#12161f] transition-colors">
                        <td className="py-2.5 font-bold text-slate-100">{cam.camera_code}</td>
                        <td className="py-2.5 text-slate-300">{cam.name}</td>
                        <td className="py-2.5">
                          <span className="rounded bg-[#18202d] px-2 py-0.5 text-[10px] uppercase text-slate-400">
                            {cam.camera_role}
                          </span>
                        </td>
                        <td className="py-2.5 text-slate-400 uppercase">{cam.stream_type}</td>
                        <td className="py-2.5">
                          <span
                            className={cn(
                              'inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] uppercase font-bold',
                              cam.connection_status === 'online'
                                ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                : cam.connection_status === 'offline'
                                ? 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                                : 'bg-slate-500/10 text-slate-400 border border-slate-500/30'
                            )}
                          >
                            <span
                              className={cn(
                                'h-1.5 w-1.5 rounded-full',
                                cam.connection_status === 'online'
                                  ? 'bg-emerald-400'
                                  : cam.connection_status === 'offline'
                                  ? 'bg-rose-400'
                                  : 'bg-slate-400'
                              )}
                            />
                            {cam.connection_status}
                          </span>
                        </td>
                        <td className="py-2.5 text-right text-slate-400">
                          {cam.last_heartbeat_at
                            ? new Date(cam.last_heartbeat_at).toLocaleTimeString()
                            : 'NEVER'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          </div>
        </div>

        {/* Right Column (1 Col): Real-time Stream + Architecture Spec */}
        <div className="space-y-6">
          {/* Genuine Detection Events Feed */}
          <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-5 shadow-sm">
            <div className="flex items-center justify-between border-b border-[#1e2633] pb-3">
              <h2 className="text-sm font-semibold text-slate-100 font-mono uppercase tracking-wider">
                Recent Detection Events
              </h2>
              <span className="text-[10px] font-mono text-slate-400">
                {eventData?.items?.length ?? 0} RECENT
              </span>
            </div>

            <div className="mt-3 divide-y divide-[#18202d]">
              {eventsLoading ? (
                <div className="py-8 text-center font-mono text-xs text-slate-400">
                  Loading event stream...
                </div>
              ) : eventsError ? (
                <div className="py-6 text-center text-xs text-rose-400 font-mono">
                  Failed to load events from backend API.
                </div>
              ) : (eventData?.items?.length ?? 0) === 0 ? (
                <div className="flex flex-col items-center justify-center py-10 text-center">
                  <Clock className="h-8 w-8 text-slate-500 mb-2 opacity-50" />
                  <p className="text-xs font-mono font-semibold text-slate-300">
                    No Detection Events Recorded
                  </p>
                  <p className="text-[11px] text-slate-500 max-w-xs mt-1">
                    AI recognitions, workstation transitions, and unknown person detections will appear here upon ingestion.
                  </p>
                </div>
              ) : (
                eventData?.items?.map((ev) => (
                  <div key={ev.id} className="py-3 flex items-start gap-3 text-xs">
                    <div
                      className={cn(
                        'mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded border',
                        ev.event_type === 'unknown_person'
                          ? 'border-amber-500/30 bg-amber-500/10 text-amber-400'
                          : ev.event_type === 'after_hours_intrusion'
                          ? 'border-rose-500/30 bg-rose-500/10 text-rose-400'
                          : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                      )}
                    >
                      <Activity className="h-3 w-3" />
                    </div>
                    <div className="flex-1 overflow-hidden">
                      <p className="text-slate-200 text-xs font-mono font-semibold truncate">
                        {ev.event_type.replace(/_/g, ' ').toUpperCase()}
                      </p>
                      <p className="text-[11px] text-slate-400 font-mono mt-0.5">
                        Cam #{ev.camera_id} &bull; {ev.employee_id ? `Emp #${ev.employee_id}` : 'Unidentified'}
                        {ev.tracker_id ? ` (Trk ${ev.tracker_id})` : ''}
                      </p>
                      <div className="mt-1 flex items-center justify-between text-[10px] font-mono text-slate-500">
                        <span>{new Date(ev.occurred_at).toLocaleTimeString()}</span>
                        <span>
                          {ev.confidence !== null && ev.confidence !== undefined
                            ? `CONF: ${(ev.confidence * 100).toFixed(0)}%`
                            : ''}
                        </span>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* AI Engine Architecture & Pipeline Specification */}
          <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-5 shadow-sm text-xs font-mono">
            <div className="flex items-center justify-between border-b border-[#1e2633] pb-3">
              <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider flex items-center gap-2">
                <Layers className="h-4 w-4 text-emerald-400" />
                AI Pipeline Architecture
              </h2>
            </div>
            <div className="mt-4 space-y-3">
              <div className="flex items-center justify-between border-b border-[#18202d] pb-2">
                <span className="text-slate-400">PERSON DETECTOR</span>
                <span className="text-slate-200 font-semibold">YOLO11s (COCO Cls 0)</span>
              </div>
              <div className="flex items-center justify-between border-b border-[#18202d] pb-2">
                <span className="text-slate-400">STREAM TRACKER</span>
                <span className="text-slate-200 font-semibold">ByteTrack (ephemeral)</span>
              </div>
              <div className="flex items-center justify-between border-b border-[#18202d] pb-2">
                <span className="text-slate-400">FACE LANDMARKING</span>
                <span className="text-slate-200 font-semibold">RetinaFace ResNet34</span>
              </div>
              <div className="flex items-center justify-between border-b border-[#18202d] pb-2">
                <span className="text-slate-400">BIOMETRIC EMBEDDINGS</span>
                <span className="text-slate-200 font-semibold">AuraFace v1 512D</span>
              </div>
              <div className="flex items-center justify-between border-b border-[#18202d] pb-2">
                <span className="text-slate-400">WORKSTATION INACTIVITY</span>
                <span className="text-slate-200 font-semibold">Farneback Optical Flow</span>
              </div>
              <div className="flex items-center justify-between border-b border-[#18202d] pb-2">
                <span className="text-slate-400">PERSISTENT QUEUE</span>
                <span className="text-slate-200 font-semibold">SQLite WAL (Bounded)</span>
              </div>
              <div className="flex items-center justify-between pt-1 text-[11px]">
                <span className="text-slate-500">LIVE GPU METRICS</span>
                <span className="text-amber-400/90 flex items-center gap-1">
                  <HelpCircle className="h-3 w-3" />
                  DAEMON BRIDGE PENDING
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}

export default Overview
