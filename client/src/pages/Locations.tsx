import React, { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Building2,
  Plus,
  Search,
  Filter,
  RefreshCw,
  LayoutGrid,
  List,
  Eye,
  Edit2,
  Power,
  Calendar,
  Globe,
  MapPin,
  Lock,
  AlertCircle,
  CheckCircle2,
  X,
  Camera,
  Activity,
} from 'lucide-react'

import { useAuth } from '@/context/useAuth'
import { locationService } from '@/services/locationService'
import { cameraService } from '@/services/cameraService'
import type { Location, LocationDetail } from '@/types/api'
import { cn } from '@/lib/utils'

import { LocationRegisterModal } from '@/components/locations/LocationRegisterModal'
import { LocationEditModal } from '@/components/locations/LocationEditModal'
import { LocationScheduleModal } from '@/components/locations/LocationScheduleModal'
import { LocationDetailModal } from '@/components/locations/LocationDetailModal'
import { LocationDeactivateDialog } from '@/components/locations/LocationDeactivateDialog'

export const Locations: React.FC = () => {
  const { user } = useAuth()
  const isSuperAdmin = user?.system_role === 'super_admin'
  const canManageLocations = isSuperAdmin || user?.system_role === 'location_admin'

  // View state
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')

  // Search & Filter state
  const [search, setSearch] = useState('')
  const [selectedStatus, setSelectedStatus] = useState<'all' | 'active' | 'inactive'>('all')

  // Notification state
  const [feedback, setFeedback] = useState<{
    type: 'success' | 'error'
    message: string
  } | null>(null)

  // Modal states
  const [isRegisterOpen, setIsRegisterOpen] = useState(false)
  const [editLocation, setEditLocation] = useState<Location | LocationDetail | null>(null)
  const [detailLocationId, setDetailLocationId] = useState<number | null>(null)
  const [scheduleLocation, setScheduleLocation] = useState<Location | LocationDetail | null>(null)
  const [deactivateLocation, setDeactivateLocation] = useState<Location | LocationDetail | null>(null)

  // Primary Locations Query
  const {
    data: locations = [],
    isLoading: locationsLoading,
    isError: locationsError,
    refetch: refetchLocations,
    isFetching,
  } = useQuery({
    queryKey: ['locations'],
    queryFn: () => locationService.getLocations(),
  })

  // Cameras Query (for camera count stats across locations)
  const { data: cameraData, refetch: refetchCameras } = useQuery({
    queryKey: ['cameras', 'fleet_stats'],
    queryFn: () => cameraService.getCameras({ page: 1, size: 100 }),
  })

  const refreshAll = () => {
    refetchLocations()
    refetchCameras()
  }

  // Filtered Locations
  const filteredLocations = useMemo(() => {
    return locations.filter((loc) => {
      // 1. Search filter
      const term = search.trim().toLowerCase()
      if (term) {
        const matchesName = loc.name.toLowerCase().includes(term)
        const matchesAddress = loc.address ? loc.address.toLowerCase().includes(term) : false
        const matchesId = String(loc.id).includes(term)
        if (!matchesName && !matchesAddress && !matchesId) return false
      }

      // 2. Active status filter
      if (selectedStatus === 'active' && !loc.is_active) return false
      if (selectedStatus === 'inactive' && loc.is_active) return false

      return true
    })
  }, [locations, search, selectedStatus])

  // Telemetry KPIs derived from genuine backend records
  const totalLocations = locations.length
  const activeLocations = locations.filter((l) => l.is_active).length
  const inactiveLocations = totalLocations - activeLocations
  const totalCameras = cameraData?.total ?? 0

  const hasActiveFilters = search.trim() !== '' || selectedStatus !== 'all'

  const clearFilters = () => {
    setSearch('')
    setSelectedStatus('all')
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
            <Building2 className="h-6 w-6 text-emerald-400" />
            Facilities & Locations Management
          </h1>
          <p className="mt-1 text-xs text-slate-400 font-mono">
            MULTI-FACILITY TOPOLOGY &bull; OPERATING SCHEDULES &bull; CAMPUS INVENTORY
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={refreshAll}
            disabled={isFetching}
            className="flex items-center gap-1.5 rounded-md border border-[#1e2633] bg-[#12161f] px-3 py-1.5 text-xs font-mono text-slate-300 hover:text-white hover:bg-[#1a202c] transition-colors disabled:opacity-50"
            title="Synchronize facilities with backend"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin text-emerald-400')} />
            <span>{isFetching ? 'SYNCING...' : 'SYNC DATA'}</span>
          </button>

          {isSuperAdmin ? (
            <button
              onClick={() => setIsRegisterOpen(true)}
              className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-3.5 py-1.5 text-xs font-mono font-semibold text-white hover:bg-emerald-500 shadow-sm transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>REGISTER FACILITY</span>
            </button>
          ) : (
            <div
              className="flex items-center gap-1.5 rounded-md border border-[#1e2633] bg-[#12161f] px-3 py-1.5 text-xs font-mono text-slate-500 cursor-not-allowed"
              title="Super Admin authority required to provision new facility locations."
            >
              <Lock className="h-3.5 w-3.5 text-slate-500" />
              <span>REGISTER (SUPER ADMIN)</span>
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
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-2 md:grid-cols-4">
        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Total Facilities</span>
            <Building2 className="h-4 w-4 text-cyan-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {locationsLoading ? '...' : totalLocations}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">CAMPUSES</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Active Facilities</span>
            <Activity className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-emerald-400">
              {locationsLoading ? '...' : activeLocations}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">OPERATIONAL</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">Inactive Facilities</span>
            <AlertCircle className="h-4 w-4 text-slate-500" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-400">
              {locationsLoading ? '...' : inactiveLocations}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">SUSPENDED</span>
          </div>
        </div>

        <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 shadow-sm">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-[11px] font-mono tracking-wider uppercase">CCTV Fleet</span>
            <Camera className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold font-mono text-slate-100">
              {locationsLoading ? '...' : totalCameras}
            </span>
            <span className="text-[10px] text-slate-400 font-mono">TOTAL SENSORS</span>
          </div>
        </div>
      </div>

      {/* Search and Filters Toolbar */}
      <div className="rounded-xl border border-[#1e2633] bg-[#0d1117] p-4 space-y-3 font-mono text-xs">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500" />
            <input
              type="text"
              placeholder="Search facility by name, address, or ID..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
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

          <div className="flex items-center gap-3">
            {/* Status Filter */}
            <div className="flex items-center gap-1.5">
              <span className="text-[10px] text-slate-400 uppercase flex items-center gap-1">
                <Filter className="h-3 w-3" />
                Status:
              </span>
              <select
                value={selectedStatus}
                onChange={(e) => setSelectedStatus(e.target.value as 'all' | 'active' | 'inactive')}
                className="rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 text-xs focus:border-emerald-500 focus:outline-none"
              >
                <option value="all">All Statuses</option>
                <option value="active">Active Only</option>
                <option value="inactive">Inactive Only</option>
              </select>
            </div>

            {/* View Switcher */}
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

        {hasActiveFilters && (
          <div className="flex items-center justify-between pt-1 text-[11px] text-slate-400 border-t border-[#18202d]">
            <span>
              Filters active. Showing {filteredLocations.length} of {locations.length} facility(ies).
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
        {locationsLoading ? (
          <div className="py-20 text-center font-mono text-xs text-slate-400">
            <div className="mx-auto h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent mb-3" />
            <p>Loading facility locations from FastAPI backend...</p>
          </div>
        ) : locationsError ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <AlertCircle className="h-10 w-10 text-rose-400 mb-2" />
            <h3 className="text-sm font-bold text-rose-300 font-mono">
              Failed to Load Locations
            </h3>
            <p className="text-xs text-slate-400 font-mono mt-1 max-w-md">
              The backend returned an error or could not be reached at http://127.0.0.1:8000.
            </p>
            <button
              onClick={() => refetchLocations()}
              className="mt-4 rounded-md border border-rose-500/40 bg-rose-500/10 px-4 py-1.5 text-xs font-mono text-rose-300 hover:bg-rose-500/20"
            >
              Retry Connection
            </button>
          </div>
        ) : filteredLocations.length === 0 ? (
          hasActiveFilters ? (
            <div className="flex flex-col items-center justify-center py-16 text-center">
              <Filter className="h-10 w-10 text-slate-500 mb-2 opacity-60" />
              <h3 className="text-sm font-bold text-slate-200 font-mono">
                No Facilities Match Active Filters
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-1 max-w-md">
                Try loosening your filter parameters or clear search query.
              </p>
              <button
                onClick={clearFilters}
                className="mt-4 rounded-md border border-[#1e2633] bg-[#12161f] px-4 py-1.5 text-xs font-mono text-slate-300 hover:text-white"
              >
                Clear Filters
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-dashed border-[#222d3f] bg-[#111722] text-slate-500 mb-3">
                <Building2 className="h-7 w-7 text-slate-400" />
              </div>
              <h3 className="text-sm font-bold text-slate-200 font-mono">
                No Facilities Registered in System
              </h3>
              <p className="text-xs text-slate-400 font-mono mt-1 max-w-sm">
                Provision enterprise campuses and facility boundaries to associate camera streams.
              </p>
              {isSuperAdmin ? (
                <button
                  onClick={() => setIsRegisterOpen(true)}
                  className="mt-5 flex items-center gap-1.5 rounded-md bg-emerald-600 px-4 py-2 text-xs font-mono font-semibold text-white hover:bg-emerald-500 transition-colors"
                >
                  <Plus className="h-4 w-4" />
                  <span>Register First Facility</span>
                </button>
              ) : (
                <p className="mt-4 text-[11px] text-slate-500 font-mono">
                  Super Admin authority is required to provision facility locations.
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
                  <th className="py-3 px-3">Facility Name</th>
                  <th className="py-3 px-3">Location ID</th>
                  <th className="py-3 px-3">Physical Address</th>
                  <th className="py-3 px-3">Timezone</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Provisioned</th>
                  <th className="py-3 px-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#18202d] text-slate-300 text-[11px]">
                {filteredLocations.map((loc) => (
                  <tr key={loc.id} className="hover:bg-[#12161f] transition-colors">
                    {/* Name */}
                    <td className="py-3 px-3 font-bold text-slate-100">
                      <button
                        onClick={() => setDetailLocationId(loc.id)}
                        className="hover:text-emerald-400 hover:underline transition-colors text-left"
                      >
                        {loc.name}
                      </button>
                    </td>

                    {/* ID */}
                    <td className="py-3 px-3 text-slate-400">
                      <span className="rounded bg-[#18202d] border border-[#222d3f] px-2 py-0.5 text-[10px] font-mono text-slate-300">
                        LOC #{loc.id}
                      </span>
                    </td>

                    {/* Address */}
                    <td className="py-3 px-3 text-slate-300 max-w-[220px] truncate" title={loc.address || ''}>
                      <span className="flex items-center gap-1">
                        <MapPin className="h-3 w-3 text-slate-500 shrink-0" />
                        {loc.address || 'Unspecified'}
                      </span>
                    </td>

                    {/* Timezone */}
                    <td className="py-3 px-3 text-slate-400 font-semibold">
                      <span className="flex items-center gap-1">
                        <Globe className="h-3 w-3 text-emerald-400/80 shrink-0" />
                        {loc.timezone}
                      </span>
                    </td>

                    {/* Status */}
                    <td className="py-3 px-3">
                      <span
                        className={cn(
                          'inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] uppercase font-bold',
                          loc.is_active
                            ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                            : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                        )}
                      >
                        <span
                          className={cn(
                            'h-1.5 w-1.5 rounded-full',
                            loc.is_active ? 'bg-emerald-400' : 'bg-rose-400'
                          )}
                        />
                        {loc.is_active ? 'ACTIVE' : 'INACTIVE'}
                      </span>
                    </td>

                    {/* Provisioned */}
                    <td className="py-3 px-3 text-slate-400 text-[10px]">
                      {new Date(loc.created_at).toLocaleDateString()}
                    </td>

                    {/* Actions */}
                    <td className="py-3 px-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setDetailLocationId(loc.id)}
                          className="rounded p-1.5 text-slate-400 hover:text-white hover:bg-[#1a2230] transition-colors"
                          title="View Details"
                        >
                          <Eye className="h-3.5 w-3.5" />
                        </button>

                        <button
                          onClick={() => setScheduleLocation(loc)}
                          className="rounded p-1.5 text-slate-400 hover:text-purple-400 hover:bg-[#1a2230] transition-colors"
                          title="Manage Operating Schedules"
                        >
                          <Calendar className="h-3.5 w-3.5" />
                        </button>

                        {canManageLocations && (
                          <>
                            <button
                              onClick={() => setEditLocation(loc)}
                              className="rounded p-1.5 text-slate-400 hover:text-cyan-400 hover:bg-[#1a2230] transition-colors"
                              title="Edit Facility"
                            >
                              <Edit2 className="h-3.5 w-3.5" />
                            </button>

                            <button
                              onClick={() => setDeactivateLocation(loc)}
                              className={cn(
                                'rounded p-1.5 transition-colors',
                                loc.is_active
                                  ? 'text-slate-400 hover:text-rose-400 hover:bg-[#1a2230]'
                                  : 'text-slate-500 hover:text-emerald-400 hover:bg-[#1a2230]'
                              )}
                              title={loc.is_active ? 'Deactivate Location' : 'Activate Location'}
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
            {filteredLocations.map((loc) => (
              <div
                key={loc.id}
                className="rounded-xl border border-[#1e2633] bg-[#0c1017] p-4 flex flex-col justify-between hover:border-[#2d3a4e] transition-colors"
              >
                <div>
                  <div className="flex items-start justify-between">
                    <div>
                      <button
                        onClick={() => setDetailLocationId(loc.id)}
                        className="text-sm font-bold font-mono text-slate-100 hover:text-emerald-400 text-left transition-colors"
                      >
                        {loc.name}
                      </button>
                      <p className="text-[10px] text-slate-500 font-mono mt-0.5">
                        FACILITY ID: #{loc.id}
                      </p>
                    </div>

                    <span
                      className={cn(
                        'inline-flex items-center gap-1 rounded px-2 py-0.5 text-[9px] font-mono uppercase font-bold',
                        loc.is_active
                          ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                          : 'bg-rose-500/10 text-rose-400 border border-rose-500/30'
                      )}
                    >
                      <span
                        className={cn(
                          'h-1.5 w-1.5 rounded-full',
                          loc.is_active ? 'bg-emerald-400' : 'bg-rose-400'
                        )}
                      />
                      {loc.is_active ? 'ACTIVE' : 'INACTIVE'}
                    </span>
                  </div>

                  <div className="mt-3 space-y-1.5 font-mono text-[11px] text-slate-400">
                    <div className="flex items-start justify-between gap-2">
                      <span className="text-slate-500 shrink-0">ADDRESS:</span>
                      <span className="text-slate-300 text-right truncate max-w-[180px]">
                        {loc.address || 'Unspecified'}
                      </span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">TIMEZONE:</span>
                      <span className="text-slate-300 font-semibold">{loc.timezone}</span>
                    </div>

                    <div className="flex items-center justify-between">
                      <span className="text-slate-500">PROVISIONED:</span>
                      <span className="text-slate-300 text-[10px]">
                        {new Date(loc.created_at).toLocaleDateString()}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="mt-4 pt-3 border-t border-[#18202d] flex items-center justify-between">
                  <button
                    onClick={() => setScheduleLocation(loc)}
                    className="flex items-center gap-1 text-[11px] text-purple-400 hover:text-purple-300 font-mono transition-colors"
                  >
                    <Calendar className="h-3.5 w-3.5" />
                    <span>Schedules</span>
                  </button>

                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => setDetailLocationId(loc.id)}
                      className="rounded p-1 text-slate-400 hover:text-white hover:bg-[#1a2230] transition-colors"
                      title="View Details"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </button>

                    {canManageLocations && (
                      <>
                        <button
                          onClick={() => setEditLocation(loc)}
                          className="rounded p-1 text-slate-400 hover:text-cyan-400 hover:bg-[#1a2230] transition-colors"
                          title="Edit Facility"
                        >
                          <Edit2 className="h-3.5 w-3.5" />
                        </button>

                        <button
                          onClick={() => setDeactivateLocation(loc)}
                          className={cn(
                            'rounded p-1 transition-colors',
                            loc.is_active
                              ? 'text-slate-400 hover:text-rose-400 hover:bg-[#1a2230]'
                              : 'text-slate-500 hover:text-emerald-400 hover:bg-[#1a2230]'
                          )}
                          title={loc.is_active ? 'Deactivate Location' : 'Activate Location'}
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
      </div>

      {/* Modals & Dialogs */}
      <LocationRegisterModal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        onSuccess={() => showSuccessFeedback('Facility location registered successfully.')}
      />

      <LocationEditModal
        location={editLocation}
        isOpen={editLocation !== null}
        onClose={() => setEditLocation(null)}
        onSuccess={() => showSuccessFeedback('Facility location updated successfully.')}
      />

      <LocationScheduleModal
        location={scheduleLocation}
        isOpen={scheduleLocation !== null}
        onClose={() => setScheduleLocation(null)}
        canManage={canManageLocations}
      />

      <LocationDetailModal
        locationId={detailLocationId}
        isOpen={detailLocationId !== null}
        onClose={() => setDetailLocationId(null)}
        onEdit={(loc) => setEditLocation(loc)}
        onOpenSchedule={(loc) => setScheduleLocation(loc)}
        onDeactivate={(loc) => setDeactivateLocation(loc)}
        canManage={canManageLocations}
        canEditSchedule={canManageLocations}
      />

      <LocationDeactivateDialog
        location={deactivateLocation}
        isOpen={deactivateLocation !== null}
        onClose={() => setDeactivateLocation(null)}
        onSuccess={() =>
          showSuccessFeedback(
            deactivateLocation?.is_active
              ? 'Facility deactivated successfully.'
              : 'Facility reactivated successfully.'
          )
        }
      />
    </div>
  )
}

export default Locations
