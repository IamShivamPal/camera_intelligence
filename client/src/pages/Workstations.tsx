import React, { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Monitor,
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
  Camera,
  Clock,
  Lock,
  AlertCircle,
  CheckCircle2,
  X,
  ChevronLeft,
  ChevronRight,
  Activity,
} from 'lucide-react'

import { useAuth } from '@/context/useAuth'
import { zoneService } from '@/services/zoneService'
import { locationService } from '@/services/locationService'
import { cameraService } from '@/services/cameraService'
import type { WorkstationZone, WorkstationZoneDetail } from '@/types/api'
import { cn } from '@/lib/utils'

import { WorkstationRegisterModal } from '@/components/workstations/WorkstationRegisterModal'
import { WorkstationEditModal } from '@/components/workstations/WorkstationEditModal'
import { WorkstationDetailModal } from '@/components/workstations/WorkstationDetailModal'
import { WorkstationDeactivateDialog } from '@/components/workstations/WorkstationDeactivateDialog'

export const Workstations: React.FC = () => {
  const { user } = useAuth()
  const canManageZones =
    user?.system_role === 'super_admin' || user?.system_role === 'location_admin'

  // View state
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')

  // Search & Filter state
  const [search, setSearch] = useState('')
  const [selectedLocation, setSelectedLocation] = useState<string>('all')
  const [selectedCamera, setSelectedCamera] = useState<string>('all')
  const [selectedActive, setSelectedActive] = useState<string>('all')

  // Pagination state
  const [page, setPage] = useState(1)
  const [size, setSize] = useState(10)

  // Notification state
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)

  // Modal states
  const [isRegisterOpen, setIsRegisterOpen] = useState(false)
  const [editZone, setEditZone] = useState<WorkstationZone | WorkstationZoneDetail | null>(null)
  const [detailZoneId, setDetailZoneId] = useState<number | null>(null)
  const [deactivateZone, setDeactivateZone] = useState<WorkstationZone | WorkstationZoneDetail | null>(null)

  // Auxiliary Query: Accessible Locations
  const { data: locations = [] } = useQuery({
    queryKey: ['locations'],
    queryFn: () => locationService.getLocations(),
  })

  const locationMap = useMemo(() => {
    const map = new Map<number, string>()
    locations.forEach((loc) => map.set(loc.id, loc.name))
    return map
  }, [locations])

  // Auxiliary Query: Cameras for filter and name lookup
  const { data: cameraData } = useQuery({
    queryKey: ['cameras', 'fleet_lookup'],
    queryFn: () => cameraService.getCameras({ page: 1, size: 100 }),
  })

  const camerasList = useMemo(() => cameraData?.items || [], [cameraData])
  const cameraMap = useMemo(() => {
    const map = new Map<number, { code: string; name: string }>()
    camerasList.forEach((c) => map.set(c.id, { code: c.camera_code, name: c.name }))
    return map
  }, [camerasList])

  // Build query parameters
  const queryParams = useMemo(() => {
    return {
      page,
      size,
      search: search.trim() ? search.trim() : undefined,
      location_id: selectedLocation !== 'all' ? Number(selectedLocation) : undefined,
      camera_id: selectedCamera !== 'all' ? Number(selectedCamera) : undefined,
      is_active:
        selectedActive === 'all'
          ? undefined
          : selectedActive === 'active'
          ? true
          : false,
    }
  }, [page, size, search, selectedLocation, selectedCamera, selectedActive])

  // Primary Workstation Zones Query
  const {
    data: zoneData,
    isLoading: zonesLoading,
    isError: zonesError,
    refetch: refetchZones,
    isFetching,
  } = useQuery({
    queryKey: ['zones', queryParams],
    queryFn: () => zoneService.getZones(queryParams),
  })

  // Global Zones Query (for top KPI counters)
  const { data: globalZoneData, refetch: refetchGlobal } = useQuery({
    queryKey: ['zones', 'global_stats'],
    queryFn: () => zoneService.getZones({ page: 1, size: 100 }),
  })

  const refreshAll = () => {
    refetchZones()
    refetchGlobal()
  }

  // Telemetry KPIs derived from genuine backend records
  const totalZones = globalZoneData?.total ?? zoneData?.total ?? 0
  const globalItems = globalZoneData?.items ?? []
  const activeZones = globalItems.filter((z) => z.is_active).length
  const inactiveZones = totalZones - activeZones
  const boundCamerasCount = new Set(globalItems.map((z) => z.camera_id)).size

  // Average inactivity threshold
  const avgInactivity =
    globalItems.length > 0
      ? Math.round(
          globalItems.reduce((acc, z) => acc + z.inactivity_threshold_seconds, 0) /
            globalItems.length
        )
      : 900

  const hasActiveFilters =
    search.trim() !== '' ||
    selectedLocation !== 'all' ||
    selectedCamera !== 'all' ||
    selectedActive !== 'all'

  const clearFilters = () => {
    setSearch('')
    setSelectedLocation('all')
    setSelectedCamera('all')
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
            <Monitor className="h-6 w-6 text-emerald-400" />
            Workstation Zones & Spatial Polygons
          </h1>
          <p className="mt-1 text-xs text-slate-400 font-mono">
            DESK BOUNDARY GEOMETRY &bull; FARNEBACK OPTICAL FLOW &bull; PRESENCE ANALYTICS
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={refreshAll}
            disabled={isFetching}
            className="flex items-center gap-1.5 rounded-md border border-[#1e2633] bg-[#12161f] px-3 py-1.5 text-xs font-mono text-slate-300 hover:text-white hover:bg-[#1a202c] transition-colors disabled:opacity-50"
            title="Synchronize workstation zones with backend"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin text-emerald-400')} />
            <span>{isFetching ? 'SYNCING...' : 'SYNC ZONES'}</span>
          </button>

          {canManageZones ? (
            <button
              onClick={() => setIsRegisterOpen(true)}
              className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3.5 py-1.5 text-xs font-mono font-semibold text-white hover:bg-emerald-500 shadow-sm transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>REGISTER WORKSTATION</span>
            </button>
          ) : (
            <div
              className="flex items-center gap-1.5 rounded-md border border-[#1e2633] bg-[#12161f] px-3 py-1.5 text-xs font-mono text-slate-500 cursor-not-allowed"
              title="Location Admin or Super Admin role required to create workstation zones."
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
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-5">
        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Workstations</span>
            <Monitor className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {zonesLoading ? '...' : totalZones}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">TOTAL ZONES</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Active Monitored</span>
            <Activity className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-emerald-400">
              {zonesLoading ? '...' : activeZones}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">TRACKING</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Inactive Zones</span>
            <AlertCircle className="h-4 w-4 text-slate-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-400">
              {zonesLoading ? '...' : inactiveZones}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">SUSPENDED</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Bound Cameras</span>
            <Camera className="h-4 w-4 text-purple-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {zonesLoading ? '...' : boundCamerasCount}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">FEED SENSORS</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm col-span-2 sm:col-span-1">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Inactivity Avg</span>
            <Clock className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {Math.round(avgInactivity / 60)}m
            </span>
            <span className="text-[10px] text-slate-400 font-mono">FLOW THRESHOLD</span>
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
              placeholder="Search workstation code (e.g. WS-01) or desk name..."
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
                title="Table View"
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

        {/* Filter Dropdowns */}
        <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-3 pt-2 border-t border-[#18202d]">
          {/* Location Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              Facility Location
            </label>
            <select
              value={selectedLocation}
              onChange={(e) => {
                setSelectedLocation(e.target.value)
                setSelectedCamera('all')
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

          {/* Camera Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Camera className="h-3 w-3" />
              Monitoring Camera
            </label>
            <select
              value={selectedCamera}
              onChange={(e) => {
                setSelectedCamera(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All Cameras</option>
              {camerasList
                .filter((c) =>
                  selectedLocation === 'all' ? true : c.location_id === Number(selectedLocation)
                )
                .map((cam) => (
                  <option key={cam.id} value={cam.id}>
                    {cam.camera_code} — {cam.name}
                  </option>
                ))}
            </select>
          </div>

          {/* Active Status Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Filter className="h-3 w-3" />
              Monitoring State
            </label>
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
              Filters active. Showing {zoneData?.total ?? 0} matching workstation(s).
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

      {/* Main Content Area */}
      <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-5 shadow-sm">
        {zonesLoading ? (
          <div className="py-20 text-center font-mono text-xs text-slate-400">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent mb-3" />
            <p>Loading workstation zones from FastAPI backend...</p>
          </div>
        ) : zonesError ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <AlertCircle className="h-10 w-10 text-rose-400 mb-2" />
            <h3 className="text-sm font-bold text-rose-300 font-mono">
              Failed to Load Workstation Zones
            </h3>
            <p className="text-xs text-slate-400 font-mono mt-1 max-w-md">
              The backend returned an error or could not be reached at http://127.0.0.1:8000.
            </p>
            <button
              onClick={() => refetchZones()}
              className="mt-4 rounded-md border border-rose-500/40 bg-rose-500/10 px-4 py-1.5 text-xs font-mono text-rose-300 hover:bg-rose-500/20"
            >
              Retry Connection
            </button>
          </div>
        ) : (zoneData?.items?.length ?? 0) === 0 ? (
          hasActiveFilters ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Filter className="h-10 w-10 text-slate-500 mb-2 opacity-60" />
              <h3 className="text-sm font-bold text-slate-200 font-mono">
                No Workstations Match Active Filters
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-1 max-w-md">
                Try loosening your filter parameters or clear all filters to inspect registered zones.
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
                <Monitor className="h-7 w-7 text-slate-400" />
              </div>
              <h3 className="text-sm font-bold text-slate-200 font-mono">
                No Workstation Zones Registered
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-1 max-w-sm">
                Define spatial polygon boundaries on camera views to monitor desk occupancy and inactivity.
              </p>
              {canManageZones ? (
                <button
                  onClick={() => setIsRegisterOpen(true)}
                  className="mt-5 flex items-center gap-1.5 rounded-md bg-emerald-600 px-4 py-2 text-xs font-mono font-semibold text-white hover:bg-emerald-500 transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  <span>Register First Workstation</span>
                </button>
              ) : (
                <p className="mt-4 text-[11px] text-slate-500 font-mono">
                  Administrative authority (location_admin or super_admin) is required to register zones.
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
                  <th className="py-3 px-3">Zone Code</th>
                  <th className="py-3 px-3">Name</th>
                  <th className="py-3 px-3">Facility Location</th>
                  <th className="py-3 px-3">Camera Sensor</th>
                  <th className="py-3 px-3">Vertices</th>
                  <th className="py-3 px-3">Inactivity Limit</th>
                  <th className="py-3 px-3">State</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#18202d] text-slate-300 text-[11px]">
                {zoneData?.items.map((zone) => {
                  const camInfo = cameraMap.get(zone.camera_id)
                  const vertexCount = zone.polygon_points?.length || 0

                  return (
                    <tr key={zone.id} className="hover:bg-[#12161f] transition-colors">
                      {/* Code */}
                      <td className="py-3 px-3 font-bold text-slate-100">
                        <button
                          onClick={() => setDetailZoneId(zone.id)}
                          className="hover:text-emerald-400 hover:underline transition-colors text-left"
                        >
                          {zone.zone_code}
                        </button>
                      </td>

                      {/* Name */}
                      <td className="py-3 px-3 text-slate-300 max-w-[200px] truncate" title={zone.name}>
                        {zone.name}
                      </td>

                      {/* Location */}
                      <td className="py-3 px-3 text-slate-400">
                        <span className="flex items-center gap-1">
                          <Building2 className="h-3 w-3 text-slate-500 shrink-0" />
                          {locationMap.get(zone.location_id) || `Loc #${zone.location_id}`}
                        </span>
                      </td>

                      {/* Camera */}
                      <td className="py-3 px-3 text-slate-300">
                        <span className="flex items-center gap-1">
                          <Camera className="h-3 w-3 text-cyan-400 shrink-0" />
                          {camInfo ? `${camInfo.code}` : `Camera #${zone.camera_id}`}
                        </span>
                      </td>

                      {/* Vertices */}
                      <td className="py-3 px-3 text-slate-400">
                        <span className="rounded bg-[#18202d] border border-[#222d3f] px-2 py-0.5 text-[10px] text-slate-300">
                          {vertexCount} pts
                        </span>
                      </td>

                      {/* Inactivity Threshold */}
                      <td className="py-3 px-3 text-slate-400">
                        <span className="flex items-center gap-1">
                          <Clock className="h-3 w-3 text-emerald-400 shrink-0" />
                          {Math.round(zone.inactivity_threshold_seconds / 60)} min
                        </span>
                      </td>

                      {/* State */}
                      <td className="py-3 px-3">
                        <span
                          className={cn(
                            'rounded px-1.5 py-0.5 text-[10px] uppercase font-semibold',
                            zone.is_active
                              ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                              : 'text-slate-500 bg-slate-800 border border-slate-700'
                          )}
                        >
                          {zone.is_active ? 'ACTIVE' : 'INACTIVE'}
                        </span>
                      </td>

                      {/* Actions */}
                      <td className="py-3 px-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            onClick={() => setDetailZoneId(zone.id)}
                            className="rounded p-1.5 text-slate-400 hover:text-white hover:bg-[#1a2230] transition-colors"
                            title="View Details"
                          >
                            <Eye className="h-3.5 w-3.5" />
                          </button>

                          {canManageZones && (
                            <>
                              <button
                                onClick={() => setEditZone(zone)}
                                className="rounded p-1.5 text-slate-400 hover:text-cyan-400 hover:bg-[#1a2230] transition-colors"
                                title="Edit Workstation"
                              >
                                <Edit2 className="h-3.5 w-3.5" />
                              </button>

                              <button
                                onClick={() => setDeactivateZone(zone)}
                                className={cn(
                                  'rounded p-1.5 transition-colors',
                                  zone.is_active
                                    ? 'text-slate-400 hover:text-rose-400 hover:bg-[#1a2230]'
                                    : 'text-slate-500 hover:text-emerald-400 hover:bg-[#1a2230]'
                                )}
                                title={zone.is_active ? 'Deactivate Zone' : 'Activate Zone'}
                              >
                                <Power className="h-3.5 w-3.5" />
                              </button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        ) : (
          /* CARD GRID VIEW */
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {zoneData?.items.map((zone) => {
              const camInfo = cameraMap.get(zone.camera_id)
              const vertexCount = zone.polygon_points?.length || 0

              return (
                <div
                  key={zone.id}
                  className="rounded-xl border border-[#1e2633] bg-[#0c1017] p-4 flex flex-col justify-between hover:border-[#2d3a4e] transition-colors"
                >
                  <div>
                    <div className="flex items-start justify-between">
                      <div>
                        <button
                          onClick={() => setDetailZoneId(zone.id)}
                          className="text-sm font-bold font-mono text-slate-100 hover:text-emerald-400 text-left transition-colors"
                        >
                          {zone.zone_code}
                        </button>
                        <p className="text-xs text-slate-400 font-mono mt-0.5 truncate max-w-[200px]" title={zone.name}>
                          {zone.name}
                        </p>
                      </div>

                      <span
                        className={cn(
                          'rounded px-1.5 py-0.5 text-[9px] font-mono uppercase font-semibold',
                          zone.is_active
                            ? 'text-emerald-400 bg-emerald-500/10 border border-emerald-500/20'
                            : 'text-slate-500 bg-slate-800 border border-slate-700'
                        )}
                      >
                        {zone.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </span>
                    </div>

                    <div className="mt-3 space-y-1.5 font-mono text-[11px] text-slate-400">
                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">LOCATION:</span>
                        <span className="text-slate-300 truncate max-w-[150px]">
                          {locationMap.get(zone.location_id) || `Loc #${zone.location_id}`}
                        </span>
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">CAMERA:</span>
                        <span className="text-slate-300 truncate max-w-[150px]">
                          {camInfo ? `${camInfo.code}` : `Camera #${zone.camera_id}`}
                        </span>
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">POLYGON:</span>
                        <span className="text-slate-300">{vertexCount} vertices</span>
                      </div>

                      <div className="flex items-center justify-between">
                        <span className="text-slate-500">INACTIVITY:</span>
                        <span className="text-emerald-400 font-semibold">
                          {Math.round(zone.inactivity_threshold_seconds / 60)} min limit
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="mt-4 pt-3 border-t border-[#18202d] flex items-center justify-between">
                    <span className="text-[10px] text-slate-500 font-mono">
                      Farneback Optical Flow
                    </span>

                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setDetailZoneId(zone.id)}
                        className="rounded p-1 text-slate-400 hover:text-white hover:bg-[#1a2230] transition-colors"
                        title="View Details"
                      >
                        <Eye className="h-3.5 w-3.5" />
                      </button>

                      {canManageZones && (
                        <>
                          <button
                            onClick={() => setEditZone(zone)}
                            className="rounded p-1 text-slate-400 hover:text-cyan-400 hover:bg-[#1a2230] transition-colors"
                            title="Edit Workstation"
                          >
                            <Edit2 className="h-3.5 w-3.5" />
                          </button>

                          <button
                            onClick={() => setDeactivateZone(zone)}
                            className={cn(
                              'rounded p-1 transition-colors',
                              zone.is_active
                                ? 'text-slate-400 hover:text-rose-400 hover:bg-[#1a2230]'
                                : 'text-slate-500 hover:text-emerald-400 hover:bg-[#1a2230]'
                            )}
                            title={zone.is_active ? 'Deactivate Zone' : 'Activate Zone'}
                          >
                            <Power className="h-3.5 w-3.5" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        )}

        {/* Pagination Controls */}
        {(zoneData?.total ?? 0) > 0 && (
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
                Total: <strong className="text-slate-300">{zoneData?.total}</strong> items
              </span>
            </div>

            <div className="flex items-center gap-3">
              <span>
                Page <strong className="text-slate-200">{page}</strong> of{' '}
                <strong className="text-slate-200">{zoneData?.pages || 1}</strong>
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
                  onClick={() => setPage((p) => Math.min(p + 1, zoneData?.pages || 1))}
                  disabled={page >= (zoneData?.pages || 1)}
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
      <WorkstationRegisterModal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        onSuccess={() => showSuccessFeedback('Workstation zone registered successfully.')}
      />

      <WorkstationEditModal
        zone={editZone}
        isOpen={editZone !== null}
        onClose={() => setEditZone(null)}
        onSuccess={() => showSuccessFeedback('Workstation configuration updated successfully.')}
      />

      <WorkstationDetailModal
        zoneId={detailZoneId}
        isOpen={detailZoneId !== null}
        onClose={() => setDetailZoneId(null)}
        onEdit={(z) => setEditZone(z)}
        onDeactivate={(z) => setDeactivateZone(z)}
        canManage={canManageZones}
      />

      <WorkstationDeactivateDialog
        zone={deactivateZone}
        isOpen={deactivateZone !== null}
        onClose={() => setDeactivateZone(null)}
        onSuccess={() =>
          showSuccessFeedback(
            deactivateZone?.is_active
              ? 'Workstation deactivated successfully.'
              : 'Workstation reactivated successfully.'
          )
        }
      />
    </div>
  )
}

export default Workstations
