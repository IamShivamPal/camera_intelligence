import React from 'react'
import { NavLink } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  LayoutDashboard,
  Video,
  Camera,
  Users,
  UserCheck,
  Building2,
  Monitor,
  CalendarCheck,
  BarChart3,
  ShieldAlert,
  Cpu,
  Settings,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
} from 'lucide-react'
import { systemService } from '@/services/systemService'
import { cameraService } from '@/services/cameraService'
import { cn } from '@/lib/utils'

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

interface NavItem {
  title: string
  to: string
  icon: React.ElementType
}

const navItems: NavItem[] = [
  { title: 'Overview', to: '/', icon: LayoutDashboard },
  { title: 'Live Monitoring', to: '/live', icon: Video },
  { title: 'Cameras', to: '/cameras', icon: Camera },
  { title: 'Employees', to: '/employees', icon: Users },
  { title: 'Face Enrollment', to: '/enrollment', icon: UserCheck },
  { title: 'Locations', to: '/locations', icon: Building2 },
  { title: 'Workstations', to: '/workstations', icon: Monitor },
  { title: 'Attendance', to: '/attendance', icon: CalendarCheck },
  { title: 'Analytics', to: '/analytics', icon: BarChart3 },
  { title: 'Events & Alerts', to: '/events', icon: ShieldAlert },
  { title: 'AI Engine', to: '/ai-engine', icon: Cpu },
  { title: 'Settings', to: '/settings', icon: Settings },
]

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggle }) => {
  // Query genuine backend health
  const {
    data: healthData,
    isLoading: healthLoading,
    isError: healthError,
  } = useQuery({
    queryKey: ['health'],
    queryFn: () => systemService.getHealth(),
    refetchInterval: 20000,
  })

  // Query actual cameras to know if any live streams exist
  const { data: cameraData } = useQuery({
    queryKey: ['cameras', 'counts'],
    queryFn: () => cameraService.getCameras({ page: 1, size: 10 }),
    refetchInterval: 30000,
  })

  const onlineCamerasCount =
    cameraData?.items?.filter((c) => c.connection_status === 'online').length ?? 0

  const backendOnline = !healthLoading && !healthError && healthData?.status === 'healthy'

  return (
    <aside
      className={cn(
        'relative flex flex-col border-r border-[#1e2633] bg-[#0c1017] transition-all duration-300 z-30 select-none',
        collapsed ? 'w-20' : 'w-64'
      )}
    >
      {/* Brand Header */}
      <div className="flex h-16 items-center justify-between border-b border-[#1e2633] px-4">
        {!collapsed ? (
          <div className="flex items-center gap-3 overflow-hidden">
            <div
              className={cn(
                'flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border transition-colors',
                backendOnline
                  ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                  : 'border-rose-500/30 bg-rose-500/10 text-rose-400'
              )}
            >
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div className="flex flex-col">
              <span className="text-xs font-bold tracking-wider text-slate-100 uppercase">
                Camera Intel
              </span>
              <span
                className={cn(
                  'text-[10px] font-mono flex items-center gap-1.5',
                  backendOnline
                    ? 'text-emerald-400'
                    : healthLoading
                    ? 'text-amber-400'
                    : 'text-rose-400'
                )}
              >
                <span
                  className={cn(
                    'h-1.5 w-1.5 rounded-full',
                    backendOnline
                      ? 'bg-emerald-400 animate-pulse'
                      : healthLoading
                      ? 'bg-amber-400'
                      : 'bg-rose-400'
                  )}
                />
                {backendOnline
                  ? 'BACKEND ONLINE'
                  : healthLoading
                  ? 'CHECKING...'
                  : 'BACKEND OFFLINE'}
              </span>
            </div>
          </div>
        ) : (
          <div
            className={cn(
              'mx-auto flex h-9 w-9 items-center justify-center rounded-lg border',
              backendOnline
                ? 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                : 'border-rose-500/30 bg-rose-500/10 text-rose-400'
            )}
            title={backendOnline ? 'Backend Online' : 'Backend Offline'}
          >
            <ShieldCheck className="h-5 w-5" />
          </div>
        )}

        <button
          onClick={onToggle}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={cn(
            'flex h-7 w-7 items-center justify-center rounded border border-[#232c3d] bg-[#141a24] text-slate-400 hover:text-white hover:bg-[#1c2433] transition-colors',
            collapsed && 'hidden'
          )}
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
      </div>

      {/* Navigation Links */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        {navItems.map((item) => {
          const Icon = item.icon
          const showLivePill = item.to === '/live' && onlineCamerasCount > 0

          return (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/'}
              className={({ isActive }) =>
                cn(
                  'group flex items-center gap-3 rounded-md px-3 py-2.5 text-xs font-medium transition-colors',
                  isActive
                    ? 'bg-emerald-500/10 text-emerald-300 border-l-2 border-emerald-500 pl-2.5 font-semibold'
                    : 'text-slate-400 hover:bg-[#141a24] hover:text-slate-200'
                )
              }
              title={collapsed ? item.title : undefined}
            >
              <Icon className="h-4 w-4 shrink-0 transition-transform group-hover:scale-105" />
              {!collapsed && (
                <div className="flex flex-1 items-center justify-between overflow-hidden">
                  <span className="truncate">{item.title}</span>
                  {showLivePill && (
                    <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 text-[9px] font-bold font-mono text-emerald-400 border border-emerald-500/30">
                      {onlineCamerasCount} LIVE
                    </span>
                  )}
                </div>
              )}
            </NavLink>
          )
        })}
      </nav>

      {/* Collapsed Toggle Button at Bottom for small mode */}
      {collapsed && (
        <div className="border-t border-[#1e2633] p-2">
          <button
            onClick={onToggle}
            className="flex w-full items-center justify-center rounded py-2 text-slate-400 hover:bg-[#141a24] hover:text-white"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* System Telemetry Footer - Strictly Genuine */}
      {!collapsed && (
        <div className="border-t border-[#1e2633] bg-[#090c10]/50 p-3 text-[11px] font-mono">
          <div className="flex items-center justify-between text-slate-400">
            <span>BACKEND API</span>
            <span className={backendOnline ? 'text-emerald-400' : 'text-rose-400'}>
              {backendOnline ? `v${healthData?.version || '1.0.0'}` : 'DISCONNECTED'}
            </span>
          </div>
          <div className="mt-1 flex items-center justify-between text-slate-500 text-[10px]">
            <span>EDGE INGESTION</span>
            <span className="text-slate-400">DAEMON SERVICE</span>
          </div>
        </div>
      )}
    </aside>
  )
}

export default Sidebar
