import React, { useState, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ShieldAlert,
  UserCheck,
  UserX,
  Monitor,
  Clock,
  Moon,
  AlertTriangle,
  LogIn,
  LogOut,
  RefreshCw,
  Filter,
  Eye,
  Radio,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { eventService } from '@/services/eventService'
import type { DetectionEvent, Camera } from '@/types/api'

interface LiveEventPanelProps {
  cameras: Camera[]
  selectedCameraId: number | null
  onSelectCamera: (cameraId: number) => void
  isOpen: boolean
  onToggle: () => void
}

const EVENT_TYPE_CONFIG: Record<
  string,
  { label: string; icon: React.ElementType; color: string; badgeClass: string }
> = {
  employee_recognized: {
    label: 'Employee Recognized',
    icon: UserCheck,
    color: '#10b981',
    badgeClass: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30',
  },
  unknown_person: {
    label: 'Unknown Person',
    icon: UserX,
    color: '#38bdf8',
    badgeClass: 'bg-sky-500/10 text-sky-400 border-sky-500/30',
  },
  workstation_active: {
    label: 'Workstation Active',
    icon: Monitor,
    color: '#06b6d4',
    badgeClass: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30',
  },
  workstation_idle: {
    label: 'Workstation Idle',
    icon: Clock,
    color: '#f59e0b',
    badgeClass: 'bg-amber-500/10 text-amber-400 border-amber-500/30',
  },
  after_hours_employee: {
    label: 'After-Hours Employee',
    icon: Moon,
    color: '#a855f7',
    badgeClass: 'bg-purple-500/10 text-purple-400 border-purple-500/30',
  },
  after_hours_intrusion: {
    label: 'After-Hours Intrusion',
    icon: AlertTriangle,
    color: '#f43f5e',
    badgeClass: 'bg-rose-500/10 text-rose-400 border-rose-500/30',
  },
  guest_entry: {
    label: 'Guest Entry',
    icon: LogIn,
    color: '#6366f1',
    badgeClass: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30',
  },
  guest_exit: {
    label: 'Guest Exit',
    icon: LogOut,
    color: '#64748b',
    badgeClass: 'bg-slate-500/10 text-slate-400 border-slate-500/30',
  },
}

export const LiveEventPanel: React.FC<LiveEventPanelProps> = ({
  cameras,
  selectedCameraId,
  onSelectCamera,
  isOpen,
  onToggle,
}) => {
  const [filterType, setFilterType] = useState<string>('all')
  const [filterCamera, setFilterCamera] = useState<string>('all')
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true)

  // Map camera ID to camera info
  const cameraMap = new Map<number, Camera>()
  cameras.forEach((c) => cameraMap.set(c.id, c))

  // Query genuine events from FastAPI
  const { data, isLoading, isFetching, refetch } = useQuery({
    queryKey: ['events', 'live-panel', filterCamera, filterType],
    queryFn: () =>
      eventService.getEvents({
        camera_id: filterCamera !== 'all' ? Number(filterCamera) : undefined,
        event_type: filterType !== 'all' ? filterType : undefined,
        size: 50,
      }),
    refetchInterval: autoRefresh ? 4000 : false,
    staleTime: 3000,
  })

  const events: DetectionEvent[] = data?.items || []

  // Reactive clock state for pure relative time formatting
  const [now, setNow] = useState<number>(() => Date.now())
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 5000)
    return () => clearInterval(timer)
  }, [])

  // Relative time helper using reactive clock
  const formatTimeAgo = (ts?: string) => {
    if (!ts) return 'Just now'
    const diff = Math.floor((now - new Date(ts).getTime()) / 1000)
    if (diff < 5) return 'Just now'
    if (diff < 60) return `${diff}s ago`
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`
    return `${Math.floor(diff / 3600)}h ago`
  }

  return (
    <aside
      className={cn(
        'relative flex flex-col border-l border-[#1e2633] bg-[#0c1017] transition-all duration-300 z-20 overflow-hidden',
        isOpen ? 'w-80 md:w-96' : 'w-0 border-l-0'
      )}
    >
      {/* Panel Header */}
      <div className="flex h-14 items-center justify-between border-b border-[#1e2633] px-4 bg-[#0e1420] shrink-0">
        <div className="flex items-center gap-2">
          <Radio className="h-4 w-4 text-rose-500 animate-pulse" />
          <h2 className="text-xs font-bold uppercase tracking-wider text-slate-100">
            Live Telemetry Feed
          </h2>
          <span className="rounded-full bg-slate-800 px-2 py-0.5 text-[10px] font-mono text-cyan-400">
            {events.length}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          {/* Auto Refresh Toggle */}
          <button
            onClick={() => setAutoRefresh(!autoRefresh)}
            className={cn(
              'px-2 py-1 rounded text-[10px] font-semibold border transition-colors',
              autoRefresh
                ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30'
                : 'bg-slate-800 text-slate-400 border-slate-700'
            )}
            title={autoRefresh ? 'Auto-refresh active (4s)' : 'Auto-refresh paused'}
          >
            {autoRefresh ? 'Live' : 'Paused'}
          </button>

          {/* Manual Refresh */}
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="p-1.5 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
            title="Refresh events now"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin')} />
          </button>

          {/* Close Panel */}
          <button
            onClick={onToggle}
            className="p-1.5 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors ml-1"
            title="Collapse event panel"
          >
            &times;
          </button>
        </div>
      </div>

      {/* Filter Controls Bar */}
      <div className="p-3 border-b border-[#1e2633] bg-[#090d14] flex flex-col gap-2 shrink-0">
        {/* Camera Filter */}
        <div className="flex items-center gap-2">
          <Filter className="h-3 w-3 text-slate-400 shrink-0" />
          <select
            value={filterCamera}
            onChange={(e) => setFilterCamera(e.target.value)}
            className="w-full bg-[#131924] border border-[#232d3f] rounded px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
          >
            <option value="all">All Cameras ({cameras.length})</option>
            {cameras.map((c) => (
              <option key={c.id} value={c.id.toString()}>
                {c.camera_code} — {c.name}
              </option>
            ))}
          </select>
        </div>

        {/* Event Type Filter */}
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          className="w-full bg-[#131924] border border-[#232d3f] rounded px-2 py-1 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
        >
          <option value="all">All Event Types</option>
          {Object.entries(EVENT_TYPE_CONFIG).map(([typeKey, cfg]) => (
            <option key={typeKey} value={typeKey}>
              {cfg.label}
            </option>
          ))}
        </select>
      </div>

      {/* Events Scroll Area */}
      <div className="flex-1 overflow-y-auto divide-y divide-[#1e2633]/60 p-2 space-y-1">
        {isLoading && events.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-slate-500 gap-2">
            <RefreshCw className="h-5 w-5 animate-spin text-cyan-500" />
            <span className="text-xs">Loading event telemetry...</span>
          </div>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center justify-center p-8 text-center text-slate-500 gap-2">
            <ShieldAlert className="h-7 w-7 text-slate-600" />
            <p className="text-xs font-semibold text-slate-400">No Events Logged</p>
            <p className="text-[11px] text-slate-500">
              No detection events match the current camera or filter settings.
            </p>
          </div>
        ) : (
          events.map((event) => {
            const config = EVENT_TYPE_CONFIG[event.event_type] || {
              label: event.event_type.replace('_', ' '),
              icon: ShieldAlert,
              color: '#94a3b8',
              badgeClass: 'bg-slate-800 text-slate-300 border-slate-700',
            }
            const Icon = config.icon
            const cam = cameraMap.get(event.camera_id)
            const isSelectedCam = selectedCameraId === event.camera_id

            return (
              <div
                key={event.id}
                onClick={() => onSelectCamera(event.camera_id)}
                className={cn(
                  'group flex flex-col p-2.5 rounded-lg border transition-all duration-150 cursor-pointer text-left',
                  isSelectedCam
                    ? 'border-cyan-500/50 bg-cyan-950/20'
                    : 'border-transparent bg-[#0f141f] hover:bg-[#141b2b] hover:border-slate-700'
                )}
              >
                {/* Event Type & Timestamp Header */}
                <div className="flex items-center justify-between gap-1 mb-1.5">
                  <span
                    className={cn(
                      'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-semibold border',
                      config.badgeClass
                    )}
                  >
                    <Icon className="h-3 w-3" />
                    {config.label}
                  </span>
                  <span className="text-[10px] text-slate-500 font-mono">
                    {formatTimeAgo(event.occurred_at || event.created_at)}
                  </span>
                </div>

                {/* Event Details */}
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-1.5 text-slate-300 truncate">
                    <span className="font-mono text-[11px] font-bold text-cyan-400">
                      {cam ? cam.camera_code : `CAM #${event.camera_id}`}
                    </span>
                    {cam && <span className="text-slate-500 truncate max-w-[100px] text-[11px]">{cam.name}</span>}
                  </div>

                  {/* Confidence if available */}
                  {(event.confidence !== null && event.confidence !== undefined) && (
                    <span className="text-[10px] font-mono text-slate-400">
                      {Math.round(event.confidence * 100)}% conf
                    </span>
                  )}
                </div>

                {/* Supplementary Telemetry (Tracker ID, Employee ID, Bounding Box info) */}
                <div className="flex items-center gap-2 mt-1.5 pt-1.5 border-t border-slate-800/60 text-[10px] text-slate-400">
                  {event.employee_id && (
                    <span className="text-emerald-400 font-medium">
                      Employee ID: {event.employee_id}
                    </span>
                  )}
                  {event.tracker_id && (
                    <span className="font-mono text-slate-400">
                      #{event.tracker_id}
                    </span>
                  )}
                  {event.workstation_zone_id && (
                    <span className="text-cyan-400">
                      Zone #{event.workstation_zone_id}
                    </span>
                  )}
                  {event.metadata_json?.bbox && (
                    <span className="text-slate-500 ml-auto flex items-center gap-0.5">
                      <Eye className="h-2.5 w-2.5" /> bbox
                    </span>
                  )}
                </div>
              </div>
            )
          })
        )}
      </div>
    </aside>
  )
}
