import React, { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Camera,
  Plus,
  Search,
  Filter,
  RefreshCw,
  LayoutGrid,
  List,
  Eye,
  Edit2,
  Power,
  Building2,
  Clock,
  Radio,
  Lock,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  CheckCircle2,
  X,
} from 'lucide-react'

import { useAuth } from '@/context/useAuth'
import { cameraService } from '@/services/cameraService'
import { locationService } from '@/services/locationService'
import type { Camera as CameraType, CameraDetail } from '@/types/api'
import { cn } from '@/lib/utils'

import { CameraRegisterModal } from '@/components/cameras/CameraRegisterModal'
import { CameraEditModal } from '@/components/cameras/CameraEditModal'
import { CameraDetailModal } from '@/components/cameras/CameraDetailModal'
import { CameraDeactivateDialog } from '@/components/cameras/CameraDeactivateDialog'

export const Cameras: React.FC = () => {
  const { user } = useAuth()
  const canManageCameras =
    user?.system_role === 'super_admin' || user?.system_role === 'location_admin'

  // View state
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')

  // Filter & Search states
  const [search, setSearch] = useState('')
  const [selectedLocation, setSelectedLocation] = useState<string>('all')
  const [selectedRole, setSelectedRole] = useState<string>('all')
  const [selectedStreamType, setSelectedStreamType] = useState<string>('all')
  const [selectedStatus, setSelectedStatus] = useState<string>('all')
  const [selectedActive, setSelectedActive] = useState<string>('all')

  // Pagination states
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)

  // Notification / Feedback banner state
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)

  // Modal states
  const [isRegisterOpen, setIsRegisterOpen] = useState(false)
  const [editCamera, setEditCamera] = useState<CameraType | CameraDetail | null>(null)
  const [detailCameraId, setDetailCameraId] = useState<number | null>(null)
  const [deactivateCamera, setDeactivateCamera] = useState<CameraType | CameraDetail | null>(null)

  // Locations Query (for filter dropdown and location names mapping)
  const { data: locations = [] } = useQuery({
    queryKey: ['locations'],
    queryFn: () => locationService.getLocations(),
  })

  // Location map for fast lookup
  const locationMap = useMemo(() => {
    const map = new Map<number, string>()
    locations.forEach((loc) => map.set(loc.id, loc.name))
    return map
  }, [locations])

  // Build query params
  const queryParams = useMemo(() => {
    return {
      page,
      size,
      search: search.trim() ? search.trim() : undefined,
      location_id: selectedLocation !== 'all' ? Number(selectedLocation) : undefined,
      camera_role: selectedRole !== 'all' ? selectedRole : undefined,
      stream_type: selectedStreamType !== 'all' ? selectedStreamType : undefined,
      connection_status: selectedStatus !== 'all' ? selectedStatus : undefined,
      is_active:
        selectedActive === 'all'
          ? undefined
          : selectedActive === 'active'
          ? true
          : false,
    }
  }, [page, size, search, selectedLocation, selectedRole, selectedStreamType, selectedStatus, selectedActive])

  // Primary Camera List Query
  const {
    data: cameraData,
    isLoading: camerasLoading,
    isError: camerasError,
    refetch: refetchCameras,
    isFetching,
  } = useQuery({
    queryKey: ['cameras', queryParams],
    queryFn: () => cameraService.getCameras(queryParams),
  })

  // Global Telemetry Query (Unfiltered for top KPI cards)
  const {
    data: globalCameraData,
    refetch: refetchGlobal,
  } = useQuery({
    queryKey: ['cameras', 'global_stats'],
    queryFn: () => cameraService.getCameras({ page: 1, size: 100 }),
  })

  const refreshAll = () => {
    refetchCameras()
    refetchGlobal()
  }

  // Calculate authentic telemetry counts from global query
  const totalCount = globalCameraData?.total ?? cameraData?.total ?? 0
  const globalItems = globalCameraData?.items ?? []
  const onlineCount = globalItems.filter((c) => c.connection_status === 'online').length
  const offlineCount = globalItems.filter((c) => c.connection_status === 'offline').length
  const degradedUnknownCount = globalItems.filter(
    (c) => c.connection_status === 'unknown' || c.connection_status === 'degraded'
  ).length
  const activeCount = globalItems.filter((c) => c.is_active).length

  // Check if any filter is active
  const hasActiveFilters =
    search.trim() !== '' ||
    selectedLocation !== 'all' ||
    selectedRole !== 'all' ||
    selectedStreamType !== 'all' ||
    selectedStatus !== 'all' ||
    selectedActive !== 'all'

  const clearFilters = () => {
    setSearch('')
    setSelectedLocation('all')
    setSelectedRole('all')
    setSelectedStreamType('all')
    setSelectedStatus('all')
    setSelectedActive('all')
    setPage(1)
  }

  const showSuccessFeedback = (msg: string) => {
    setFeedback({ type: 'success', message: msg })
    setTimeout(() => setFeedback(null), 5000)
    refreshAll()
  }

  return (
    <div className="space-y-6">
      {/* Page Header Bar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-[#1e2633] pb-4">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-100 flex items-center gap-2.5">
            <Camera className="h-6 w-6 text-emerald-400" />
            Camera Fleet & Sensor Matrix
          </h1>
          <p className="mt-1 text-xs text-slate-400 font-mono">
            RTSP STREAM REGISTRATION &bull; SENSOR TOPOLOGY &bull; TELEMETRY CONFIGURATION
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={refreshAll}
            disabled={isFetching}
            className="flex items-center gap-1.5 rounded-md border border-[#1e2633] bg-[#12161f] px-3 py-1.5 text-xs font-mono text-slate-300 hover:text-white hover:bg-[#1a202c] transition-colors disabled:opacity-50"
            title="Synchronize telemetry with backend"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin text-emerald-400')} />
            <span>{isFetching ? 'SYNCING...' : 'SYNC FLEET'}</span>
          </button>

          {canManageCameras ? (
            <button
              onClick={() => setIsRegisterOpen(true)}
              className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3.5 py-1.5 text-xs font-mono font-semibold text-white hover:bg-emerald-500 shadow-sm transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>REGISTER CAMERA</span>
            </button>
          ) : (
            <div
              className="flex items-center gap-1.5 rounded-md border border-[#1e2633] bg-[#12161f] px-3 py-1.5 text-xs font-mono text-slate-500 cursor-not-allowed"
              title="Location Admin or Super Admin role required to register cameras."
            >
              <Lock className="h-3.5 w-3.5 text-slate-500" />
              <span>REGISTER (LOCKED)</span>
            </div>
          )}
        </div>
      </div>

      {/* Feedback Banner */}
      {feedback && (
        <div
          className={cn(
            'flex items-center justify-between rounded-lg p-3 text-xs font-mono transition-all',
            feedback.type === 'success'
              ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300'
              : 'border border-rose-500/30 bg-rose-500/10 text-rose-300'
          )}
        >
          <div className="flex items-center gap-2">
            {feedback.type === 'success' ? (
              <CheckCircle2 className="h-4 w-4 text-emerald-400" />
            ) : (
              <AlertCircle className="h-4 w-4 text-rose-400" />
            )}
            <span>{feedback.message}</span>
          </div>
          <button
            onClick={() => setFeedback(null)}
            className="text-slate-400 hover:text-white"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Genuine Telemetry KPI Cards */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5">
        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Registered</span>
            <Camera className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {camerasLoading ? '...' : totalCount}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">TOTAL SENSORS</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Online</span>
            <Radio className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-emerald-400">
              {camerasLoading ? '...' : onlineCount}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">STREAMING</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Offline</span>
            <AlertCircle className="h-4 w-4 text-rose-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-rose-400">
              {camerasLoading ? '...' : offlineCount}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">DISCONNECTED</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Unknown / Degraded</span>
            <Clock className="h-4 w-4 text-slate-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-300">
              {camerasLoading ? '...' : degradedUnknownCount}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">NO HEARTBEAT</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm col-span-2 sm:col-span-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Active In AI</span>
            <Power className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {camerasLoading ? '...' : activeCount}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">INGESTION ENABLED</span>
          </div>
        </div>
      </div>

      {/* Search and Filters Toolbar */}
      <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 space-y-3 font-mono text-xs">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search camera code (e.g. CAM-01) or display name..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-md border border-[#222d3f] bg-[#111722] pl-9 pr-4 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-3 top-2.5 text-slate-500 hover:text-slate-300"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* View Toggle */}
          <div className="flex items-center gap-2 self-end lg:self-auto">
            <span className="text-[11px] text-slate-400">VIEW:</span>
            <div className="flex rounded-md border border-[#222d3f] bg-[#111722] p-0.5">
              <button
                onClick={() => setViewMode('table')}
                className={cn(
                  'flex items-center gap-1 rounded px-2.5 py-1 text-xs transition-colors',
                  viewMode === 'table'
                    ? 'bg-emerald-600 text-white font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                )}
                title="Table List View"
              >
                <List className="h-3.5 w-3.5" />
                <span>Table</span>
              </button>
              <button
                onClick={() => setViewMode('grid')}
                className={cn(
                  'flex items-center gap-1 rounded px-2.5 py-1 text-xs transition-colors',
                  viewMode === 'grid'
                    ? 'bg-emerald-600 text-white font-semibold'
                    : 'text-slate-400 hover:text-slate-200'
                )}
                title="Card Grid View"
              >
                <LayoutGrid className="h-3.5 w-3.5" />
                <span>Cards</span>
              </button>
            </div>
          </div>
        </div>

        {/* Filter Dropdowns Grid */}
        <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5 pt-2 border-t border-[#18202d]">
          {/* Location Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              Location
            </label>
            <select
              value={selectedLocation}
              onChange={(e) => {
                setSelectedLocation(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All Locations</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </div>

          {/* Role Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Filter className="h-3 w-3" />
              Camera Role
            </label>
            <select
              value={selectedRole}
              onChange={(e) => {
                setSelectedRole(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All Roles</option>
              <option value="general">General</option>
              <option value="entry_exit">Entry / Exit</option>
              <option value="workstation">Workstation</option>
              <option value="perimeter">Perimeter</option>
            </select>
          </div>

          {/* Stream Type Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Radio className="h-3 w-3" />
              Protocol
            </label>
            <select
              value={selectedStreamType}
              onChange={(e) => {
                setSelectedStreamType(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All Protocols</option>
              <option value="rtsp">RTSP Stream</option>
              <option value="webcam">Webcam</option>
              <option value="file">Video File</option>
              <option value="onvif">ONVIF</option>
            </select>
          </div>

          {/* Connection Status Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1">Status</label>
            <select
              value={selectedStatus}
              onChange={(e) => {
                setSelectedStatus(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="online">Online</option>
              <option value="offline">Offline</option>
              <option value="degraded">Degraded</option>
              <option value="unknown">Unknown</option>
            </select>
          </div>

          {/* Active Status Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1">State</label>
            <select
              value={selectedActive}
              onChange={(e) => {
                setSelectedActive(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All States</option>
              <option value="active">Active Only</option>
              <option value="inactive">Inactive Only</option>
            </select>
          </div>
        </div>

        {hasActiveFilters && (
          <div className="flex items-center justify-between pt-1 text-[11px] text-slate-400">
            <span>
              Filters active. Showing {cameraData?.total ?? 0} matching camera(s).
            </span>
            <button
              onClick={clearFilters}
              className="text-emerald-400 hover:text-emerald-300 underline underline-offset-2"
            >
              Reset Filters
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area: Table / Grid / Loading / Empty / Error */}
      <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-5 shadow-sm">
        {camerasLoading ? (
          <div className="py-20 text-center font-mono text-xs text-slate-400">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent mb-3" />
            <p>Loading camera inventory from FastAPI backend...</p>
          </div>
        ) : camerasError ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <AlertCircle className="h-10 w-10 text-rose-400 mb-2" />
            <h3 className="text-sm font-bold text-rose-300 font-mono">
              Failed to Load Cameras
            </h3>
            <p className="text-xs text-slate-400 font-mono mt-1 max-w-md">
              The backend returned an error or could not be reached at http://127.0.0.1:8000.
            </p>
            <button
              onClick={() => refetchCameras()}
              className="mt-4 rounded-md border border-rose-500/40 bg-rose-500/10 px-4 py-1.5 text-xs font-mono text-rose-300 hover:bg-rose-500/20"
            >
              Retry Connection
            </button>
          </div>
        ) : (cameraData?.items?.length ?? 0) === 0 ? (
          /* Empty States */
          hasActiveFilters ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Filter className="h-10 w-10 text-slate-500 mb-2 opacity-60" />
              <h3 className="text-sm font-bold text-slate-200 font-mono">
                No Cameras Match Active Filters
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-1 max-w-md">
                Try loosening your filter parameters or clear all filters to inspect the fleet.
              </p>
              <button
                onClick={clearFilters}
                className="mt-4 rounded-md border border-[#1e2633] bg-[#12161f] px-4 py-1.5 text-xs font-mono text-slate-300 hover:text-white"
              >
                Clear All Filters
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-dashed border-[#222d3f] bg-[#111722] text-slate-500 mb-3">
                <Camera className="h-7 w-7 text-slate-400" />
              </div>
              <h3 className="text-sm font-bold text-slate-200 font-mono">
                No Cameras Registered in System
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-1 max-w-sm">
                No CCTV sensors or RTSP endpoints have been provisioned yet.
              </p>
              {canManageCameras ? (
                <button
                  onClick={() => setIsRegisterOpen(true)}
                  className="mt-5 flex items-center gap-1.5 rounded-md bg-emerald-600 px-4 py-2 text-xs font-mono font-semibold text-white hover:bg-emerald-500 transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  <span>Register First Camera</span>
                </button>
              ) : (
                <p className="mt-4 text-[11px] text-slate-500 font-mono">
                  Administrative authority (location_admin or super_admin) is required to register cameras.
                </p>
              )}
            </div>
          )
        ) : viewMode === 'table' ? (
          /* TABLE VIEW */
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono">
              <thead>
                <tr className="border-b border-[#1e2633] text-[10px] uppercase text-slate-400">
                  <th className="py-3 px-3">Camera Code</th>
                  <th className="py-3 px-3">Name</th>
                  <th className="py-3 px-3">Facility Location</th>
                  <th className="py-3 px-3">Role</th>
                  <th className="py-3 px-3">Protocol</th>
                  <th className="py-3 px-3">Connection</th>
                  <th className="py-3 px-3">Active</th>
                  <th className="py-3 px-3">Last Heartbeat</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#18202d] text-slate-300 text-[11px]">
                {cameraData?.items.map((cam) => (
                  <tr key={cam.id} className="hover:bg-[#12161f] transition-colors">
                    {/* Code */}
                    <td className="py-3 px-3 font-bold text-slate-100">
                      <button
                        onClick={() => setDetailCameraId(cam.id)}
                        className="hover:text-emerald-400 hover:underline transition-colors text-left"
                      >
                        {cam.camera_code}
                      </button>
                    </td>

                    {/* Name */}
                    <td className="py-3 px-3 text-slate-300 max-w-[200px] truncate" title={cam.name}>
                      {cam.name}
                    </td>

                    {/* Location */}
                    <td className="py-3 px-3 text-slate-400">
                      <span className="flex items-center gap-1">
                        <Building2 className="h-3 w-3 text-slate-500 shrink-0" />
                        {locationMap.get(cam.location_id) || `Loc #${cam.location_id}`}
                      </span>
                    </td>

                    {/* Role */}
                    <td className="py-3 px-3">
                      <span className="rounded bg-[#18202d] border border-[#222d3f] px-2 py-0.5 text-[10px] uppercase text-slate-300">
                        {cam.camera_role.replace(/_/g, ' ')}
                      </span>
                    </td>

                    {/* Stream Type */}
                    <td className="py-3 px-3 uppercase text-slate-400 font-semibold">
                      {cam.stream_type}
                    </td>

                    {/* Connection Status */}
                    <td className="py-3 px-3">
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
                              ? 'bg-emerald-400 animate-pulse'
                              : cam.connection_status === 'offline'
                              ? 'bg-rose-400'
                              : 'bg-slate-400'
                          )}
                        />
                        {cam.connection_status}
                      </span>
                    </td>

                    {/* Active */}
                    <td className="py-3 px-3">
                      <span
                        className={cn(
                          'rounded px-1.5 py-0.5 text-[10px] uppercase font-semibold',
                          cam.is_active
                            ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                            : 'text-slate-500 bg-slate-800 border border-slate-700'
                        )}
                      >
                        {cam.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </span>
                    </td>

                    {/* Last Heartbeat */}
                    <td className="py-3 px-3 text-slate-400 text-[10px]">
                      {cam.last_heartbeat_at
                        ? new Date(cam.last_heartbeat_at).toLocaleTimeString()
                        : 'NEVER'}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setDetailCameraId(cam.id)}
                          className="rounded p-1.5 text-slate-400 hover:text-white hover:bg-[#1a2230] transition-colors"
                          title="View Details"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>

                        {canManageCameras && (
                          <>
                            <button
                              onClick={() => setEditCamera(cam)}
                              className="rounded p-1.5 text-slate-400 hover:text-cyan-400 hover:bg-[#1a2230] transition-colors"
                              title="Edit Configuration"
                            >
                              <Edit2 className="h-3.5 w-3.5" />
                            </button>

                            <button
                              onClick={() => setDeactivateCamera(cam)}
                              className={cn(
                                'rounded p-1.5 transition-colors',
                                cam.is_active
                                  ? 'text-slate-400 hover:text-rose-400 hover:bg-[#1a2230]'
                                  : 'text-slate-500 hover:text-emerald-400 hover:bg-[#1a2230]'
                              )}
                              title={cam.is_active ? 'Deactivate Camera' : 'Activate Camera'}
                            >
                              <Power className="h-3.5 w-3.5" />
                            </button>
                          </>
                        )}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          /* CARD GRID VIEW */
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {cameraData?.items.map((cam) => (
              <div
                key={cam.id}
                className="rounded-xl border border-[#1e2633] bg-[#0c1017] p-4 flex flex-col justify-between hover:border-[#2d3a4e] transition-colors"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <button
                        onClick={() => setDetailCameraId(cam.id)}
                        className="text-sm font-bold font-mono text-slate-100 hover:text-emerald-400 text-left transition-colors"
                      >
                        {cam.camera_code}
                      </button>
                      <p className="text-xs text-slate-400 font-mono mt-0.5 truncate max-w-[200px]" title={cam.name}>
                        {cam.name}
                      </p>
                    </div>

                    <span
                      className={cn(
                        'inline-flex items-center gap-1 rounded px-2 py-0.5 text-[9px] font-mono uppercase font-bold',
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
                            ? 'bg-emerald-400 animate-pulse'
                            : cam.connection_status === 'offline'
                            ? 'bg-rose-400'
                            : 'bg-slate-400'
                        )}
                      />
                      {cam.connection_status}
                    </span>
                  </div>

                  <div className="mt-3 space-y-1.5 font-mono text-[11px] text-slate-400">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">LOCATION:</span>
                      <span className="text-slate-300 truncate max-w-[150px]">
                        {locationMap.get(cam.location_id) || `Loc #${cam.location_id}`}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">ROLE:</span>
                      <span className="text-slate-300 uppercase">
                        {cam.camera_role.replace(/_/g, ' ')}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">PROTOCOL:</span>
                      <span className="text-slate-300 uppercase font-semibold">
                        {cam.stream_type}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">LAST HEARTBEAT:</span>
                      <span className="text-slate-300 text-[10px]">
                        {cam.last_heartbeat_at
                          ? new Date(cam.last_heartbeat_at).toLocaleTimeString()
                          : 'NEVER'}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#18202d] flex items-center justify-between">
                  <span
                    className={cn(
                      'rounded px-1.5 py-0.5 text-[9px] font-mono uppercase font-semibold',
                      cam.is_active
                        ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                        : 'text-slate-500 bg-slate-800 border border-slate-700'
                    )}
                  >
                    {cam.is_active ? 'ACTIVE' : 'INACTIVE'}
                  </span>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setDetailCameraId(cam.id)}
                      className="rounded p-1 text-slate-400 hover:text-white hover:bg-[#1a2230] transition-colors"
                      title="View Details"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </button>

                    {canManageCameras && (
                      <>
                        <button
                          onClick={() => setEditCamera(cam)}
                          className="rounded p-1 text-slate-400 hover:text-cyan-400 hover:bg-[#1a2230] transition-colors"
                          title="Edit Configuration"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </button>

                        <button
                          onClick={() => setDeactivateCamera(cam)}
                          className={cn(
                            'rounded p-1 transition-colors',
                            cam.is_active
                              ? 'text-slate-400 hover:text-rose-400 hover:bg-[#1a2230]'
                              : 'text-slate-500 hover:text-emerald-400 hover:bg-[#1a2230]'
                          )}
                          title={cam.is_active ? 'Deactivate Camera' : 'Activate Camera'}
                        >
                          <Power className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Pagination Bar */}
        {(cameraData?.total ?? 0) > 0 && (
          <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-t border-[#18202d] pt-3 font-mono text-xs text-slate-400">
            <div className="flex items-center gap-2">
              <span>Rows per page:</span>
              <select
                value={size}
                onChange={(e) => {
                  setSize(Number(e.target.value))
                  setPage(1)
                }}
                className="rounded border border-[#222d3f] bg-[#111722] px-2 py-1 text-slate-200 text-xs focus:border-emerald-500 focus:outline-none"
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
              </select>
              <span className="text-slate-500">
                Total: <strong className="text-slate-300">{cameraData?.total}</strong> items
              </span>
            </div>

            <div className="flex items-center gap-3">
              <span>
                Page <strong className="text-slate-200">{page}</strong> of{' '}
                <strong className="text-slate-200">{cameraData?.pages || 1}</strong>
              </span>

              <div className="flex items-center gap-1">
                <button
                  onClick={() => setPage((p) => Math.max(p - 1, 1))}
                  disabled={page <= 1}
                  className="rounded border border-[#222d3f] bg-[#111722] p-1.5 text-slate-300 hover:bg-[#18202d] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title="Previous Page"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <button
                  onClick={() => setPage((p) => Math.min(p + 1, cameraData?.pages || 1))}
                  disabled={page >= (cameraData?.pages || 1)}
                  className="rounded border border-[#222d3f] bg-[#111722] p-1.5 text-slate-300 hover:bg-[#18202d] disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                  title="Next Page"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Modals & Dialogs */}
      <CameraRegisterModal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        onSuccess={() => showSuccessFeedback('Camera sensor registered successfully.')}
      />

      <CameraEditModal
        camera={editCamera}
        isOpen={editCamera !== null}
        onClose={() => setEditCamera(null)}
        onSuccess={() => showSuccessFeedback('Camera configuration updated successfully.')}
      />

      <CameraDetailModal
        cameraId={detailCameraId}
        isOpen={detailCameraId !== null}
        onClose={() => setDetailCameraId(null)}
        onEdit={(cam) => setEditCamera(cam)}
        onDeactivate={(cam) => setDeactivateCamera(cam)}
        canManage={canManageCameras}
      />

      <CameraDeactivateDialog
        camera={deactivateCamera}
        isOpen={deactivateCamera !== null}
        onClose={() => setDeactivateCamera(null)}
        onSuccess={() =>
          showSuccessFeedback(
            deactivateCamera?.is_active
              ? 'Camera deactivated successfully.'
              : 'Camera reactivated successfully.'
          )
        }
      />
    </div>
  )
}

export default Cameras
