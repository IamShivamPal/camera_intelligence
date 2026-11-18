import React, { useState, useEffect, useRef } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import {
  Bell,
  User as UserIcon,
  LogOut,
  Shield,
  Activity,
  AlertTriangle,
  ChevronRight,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react'
import { useAuth } from '@/context/AuthContext'
import { eventService } from '@/services/eventService'
import { cn } from '@/lib/utils'

export const Header: React.FC = () => {
  const { user, logout } = useAuth()
  const location = useLocation()
  const navigate = useNavigate()

  const [currentTime, setCurrentTime] = useState<string>('')
  const [profileOpen, setProfileOpen] = useState<boolean>(false)
  const [notifOpen, setNotifOpen] = useState<boolean>(false)

  const profileRef = useRef<HTMLDivElement>(null)
  const notifRef = useRef<HTMLDivElement>(null)

  // Query genuine open alerts from backend API
  const {
    data: alertsData,
    isLoading: alertsLoading,
    isError: alertsError,
    refetch: refetchAlerts,
  } = useQuery({
    queryKey: ['alerts', 'open'],
    queryFn: () => eventService.getAlerts({ status: 'open', size: 5 }),
    refetchInterval: 15000, // Poll every 15s for live alerts
  })

  // Live system clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date()
      setCurrentTime(
        now.toISOString().replace('T', ' ').substring(0, 19) + ' UTC'
      )
    }
    updateTime()
    const timer = setInterval(updateTime, 1000)
    return () => clearInterval(timer)
  }, [])

  // Close popovers on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (profileRef.current && !profileRef.current.contains(e.target as Node)) {
        setProfileOpen(false)
      }
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) {
        setNotifOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Build breadcrumb segments
  const pathnames = location.pathname.split('/').filter((x) => x)
  const breadcrumbs = [
    { name: 'System', path: '/' },
    ...pathnames.map((value, index) => {
      const to = `/${pathnames.slice(0, index + 1).join('/')}`
      const formatted = value.charAt(0).toUpperCase() + value.slice(1).replace('-', ' ')
      return { name: formatted, path: to }
    }),
  ]

  const handleLogout = async () => {
    await logout()
    navigate('/login')
  }

  const openAlertCount = alertsData?.total ?? 0
  const openAlertsList = alertsData?.items ?? []

  return (
    <header className="flex h-16 w-full items-center justify-between border-b border-[#1e2633] bg-[#0c1017] px-6 select-none z-20">
      {/* Left: Breadcrumbs */}
      <div className="flex items-center gap-2 text-xs font-mono">
        {breadcrumbs.map((crumb, idx) => (
          <React.Fragment key={crumb.path}>
            {idx > 0 && <ChevronRight className="h-3 w-3 text-slate-500" />}
            <span
              className={cn(
                idx === breadcrumbs.length - 1
                  ? 'text-slate-200 font-semibold'
                  : 'text-slate-400 hover:text-slate-300 transition-colors cursor-pointer'
              )}
              onClick={() => idx < breadcrumbs.length - 1 && navigate(crumb.path)}
            >
              {crumb.name}
            </span>
          </React.Fragment>
        ))}
      </div>

      {/* Right Controls */}
      <div className="flex items-center gap-5">
        {/* System Telemetry Clock */}
        <div className="hidden md:flex items-center gap-2 rounded border border-[#1e2633] bg-[#12161f] px-3 py-1 text-[11px] font-mono text-slate-300">
          <Activity className="h-3.5 w-3.5 text-emerald-400" />
          <span>{currentTime || 'SYNCHRONIZING...'}</span>
        </div>

        {/* Notifications Dropdown */}
        <div className="relative" ref={notifRef}>
          <button
            onClick={() => {
              setNotifOpen(!notifOpen)
              if (!notifOpen) refetchAlerts()
            }}
            className={cn(
              'relative flex h-8 w-8 items-center justify-center rounded-md border transition-colors',
              openAlertCount > 0
                ? 'border-rose-500/40 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20'
                : 'border-[#1e2633] bg-[#12161f] text-slate-300 hover:text-white hover:bg-[#1a202c]'
            )}
            title={openAlertCount > 0 ? `${openAlertCount} active alert(s)` : 'No active alerts'}
          >
            <Bell className="h-4 w-4" />
            {/* Show badge ONLY if genuine open alerts exist */}
            {openAlertCount > 0 && (
              <span className="absolute -top-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-rose-500 text-[9px] font-bold text-white shadow-sm">
                {openAlertCount > 99 ? '99+' : openAlertCount}
              </span>
            )}
          </button>

          {notifOpen && (
            <div className="absolute right-0 mt-2 w-80 rounded-lg border border-[#232c3d] bg-[#12161f] p-3 shadow-2xl text-xs z-50">
              <div className="flex items-center justify-between border-b border-[#1e2633] pb-2 font-semibold text-slate-200">
                <span className="flex items-center gap-1.5 font-mono">
                  <AlertTriangle className={cn('h-4 w-4', openAlertCount > 0 ? 'text-rose-400' : 'text-slate-400')} />
                  Active Security Alerts
                </span>
                <span className="text-[10px] text-slate-400 font-mono">
                  {alertsLoading ? 'LOADING...' : `${openAlertCount} OPEN`}
                </span>
              </div>

              {/* Loading State */}
              {alertsLoading && (
                <div className="flex items-center justify-center py-6 text-slate-400 gap-2 font-mono text-[11px]">
                  <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />
                  <span>Querying backend alerts...</span>
                </div>
              )}

              {/* Error State */}
              {alertsError && !alertsLoading && (
                <div className="my-3 flex items-start gap-2 rounded border border-rose-500/30 bg-rose-500/10 p-2 text-rose-300 text-[11px]">
                  <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
                  <span>Failed to load alerts from backend API.</span>
                </div>
              )}

              {/* Empty State */}
              {!alertsLoading && !alertsError && openAlertCount === 0 && (
                <div className="flex flex-col items-center justify-center py-6 text-center">
                  <CheckCircle2 className="h-8 w-8 text-emerald-400 mb-2 opacity-80" />
                  <p className="text-slate-200 font-medium text-xs font-mono">No Active Alerts</p>
                  <p className="text-slate-500 text-[11px] mt-0.5">
                    All location schedules and security perimeters are normal.
                  </p>
                </div>
              )}

              {/* Genuine Alerts List */}
              {!alertsLoading && !alertsError && openAlertCount > 0 && (
                <div className="divide-y divide-[#1e2633] py-2 max-h-60 overflow-y-auto">
                  {openAlertsList.map((alert) => (
                    <div key={alert.id} className="py-2.5">
                      <div className="flex items-center justify-between font-mono text-[10px]">
                        <span
                          className={cn(
                            'font-bold uppercase px-1.5 py-0.5 rounded',
                            alert.severity === 'critical'
                              ? 'bg-rose-500/20 text-rose-400 border border-rose-500/30'
                              : alert.severity === 'high'
                              ? 'bg-orange-500/20 text-orange-400'
                              : 'bg-amber-500/20 text-amber-400'
                          )}
                        >
                          {alert.severity}
                        </span>
                        <span className="text-slate-500">
                          {new Date(alert.created_at).toLocaleTimeString([], {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </span>
                      </div>
                      <p className="mt-1 text-slate-200 text-xs font-medium leading-tight">
                        {alert.title}
                      </p>
                      {alert.description && (
                        <p className="mt-0.5 text-slate-400 text-[11px] truncate">
                          {alert.description}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <button
                onClick={() => {
                  setNotifOpen(false)
                  navigate('/events')
                }}
                className="mt-2 w-full rounded bg-[#181f2b] py-1.5 text-center text-[11px] font-mono text-emerald-400 hover:bg-[#20293a] transition-colors"
              >
                View Events & Alerts Page &rarr;
              </button>
            </div>
          )}
        </div>

        {/* User Profile Menu */}
        <div className="relative" ref={profileRef}>
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="flex items-center gap-2.5 rounded-md border border-[#1e2633] bg-[#12161f] px-2.5 py-1 text-xs hover:border-[#2b3648] transition-colors"
          >
            <div className="flex h-6 w-6 items-center justify-center rounded-full bg-emerald-500/20 text-emerald-400 font-bold text-[10px]">
              {user?.full_name?.charAt(0) || user?.email?.charAt(0) || 'U'}
            </div>
            <div className="hidden sm:flex flex-col text-left">
              <span className="text-xs font-semibold text-slate-200 leading-tight">
                {user?.full_name || user?.email || 'User'}
              </span>
              <span className="text-[9px] font-mono text-emerald-400 uppercase leading-none">
                {user?.system_role || 'AUTHENTICATED'}
              </span>
            </div>
          </button>

          {profileOpen && (
            <div className="absolute right-0 mt-2 w-56 rounded-lg border border-[#232c3d] bg-[#12161f] p-2 shadow-2xl text-xs z-50">
              <div className="border-b border-[#1e2633] px-3 py-2">
                <p className="text-xs font-semibold text-slate-100">{user?.full_name}</p>
                <p className="text-[11px] text-slate-400 truncate">{user?.email}</p>
                <div className="mt-1.5 flex items-center gap-1.5">
                  <Shield className="h-3 w-3 text-emerald-400" />
                  <span className="text-[10px] font-mono text-emerald-400 uppercase">
                    {user?.system_role}
                  </span>
                </div>
              </div>

              <div className="py-1">
                <button
                  onClick={() => {
                    setProfileOpen(false)
                    navigate('/settings')
                  }}
                  className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-slate-300 hover:bg-[#1a2230] hover:text-white transition-colors"
                >
                  <UserIcon className="h-3.5 w-3.5" />
                  Profile Settings
                </button>
                <button
                  onClick={handleLogout}
                  className="flex w-full items-center gap-2 rounded px-3 py-1.5 text-left text-rose-400 hover:bg-rose-500/10 transition-colors"
                >
                  <LogOut className="h-3.5 w-3.5" />
                  Terminate Session (Logout)
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}

export default Header
