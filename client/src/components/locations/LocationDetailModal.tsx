import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  X,
  Building2,
  Camera,
  Users,
  Monitor,
  Calendar,
  Clock,
  MapPin,
  Globe,
  Edit2,
  Power,
  AlertCircle,
  Briefcase,
} from 'lucide-react'
import { locationService } from '@/services/locationService'
import { cameraService } from '@/services/cameraService'
import { zoneService } from '@/services/zoneService'
import type { LocationDetail } from '@/types/api'
import { cn } from '@/lib/utils'

interface LocationDetailModalProps {
  locationId: number | null
  isOpen: boolean
  onClose: () => void
  onEdit: (location: LocationDetail) => void
  onOpenSchedule: (location: LocationDetail) => void
  onDeactivate: (location: LocationDetail) => void
  canManage: boolean
  canEditSchedule: boolean
}

export const LocationDetailModal: React.FC<LocationDetailModalProps> = ({
  locationId,
  isOpen,
  onClose,
  onEdit,
  onOpenSchedule,
  onDeactivate,
  canManage,
  canEditSchedule,
}) => {
  const [activeTab, setActiveTab] = useState<'overview' | 'cameras' | 'departments' | 'workstations'>('overview')

  // Query location details
  const {
    data: location,
    isLoading: locationLoading,
    isError: locationError,
    refetch: refetchLocation,
  } = useQuery({
    queryKey: ['location', locationId],
    queryFn: () => (locationId ? locationService.getLocationById(locationId) : Promise.reject('No ID')),
    enabled: isOpen && locationId !== null,
  })

  // Query cameras in location
  const { data: cameraData, isLoading: camerasLoading } = useQuery({
    queryKey: ['cameras', 'location', locationId],
    queryFn: () => (locationId ? cameraService.getCameras({ location_id: locationId, size: 50 }) : Promise.reject('No ID')),
    enabled: isOpen && locationId !== null,
  })

  // Query departments in location
  const { data: departments = [], isLoading: departmentsLoading } = useQuery({
    queryKey: ['departments', 'location', locationId],
    queryFn: () => (locationId ? locationService.getLocationDepartments(locationId) : Promise.reject('No ID')),
    enabled: isOpen && locationId !== null,
  })

  // Query workstation zones in location
  const { data: zoneData, isLoading: zonesLoading } = useQuery({
    queryKey: ['zones', 'location', locationId],
    queryFn: () => (locationId ? zoneService.getZones({ location_id: locationId, size: 50 }) : Promise.reject('No ID')),
    enabled: isOpen && locationId !== null,
  })

  if (!isOpen || locationId === null) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-3xl rounded-xl border border-[#222d3f] bg-[#0c1017] shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1b2331] px-6 py-4 bg-[#090d14]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Building2 className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                  {location?.name || `FACILITY #${locationId}`}
                </h2>
                {location && (
                  <span
                    className={cn(
                      'rounded px-2 py-0.5 text-[10px] font-mono uppercase font-bold',
                      location.is_active
                        ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                        : 'border border-rose-500/30 bg-rose-500/10 text-rose-400'
                    )}
                  >
                    {location.is_active ? 'ACTIVE FACILITY' : 'DEACTIVATED'}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 font-mono flex items-center gap-1.5 mt-0.5">
                <Globe className="h-3 w-3 text-slate-500" />
                <span>Timezone: <strong className="text-slate-300">{location?.timezone || 'UTC'}</strong></span>
                <span>&bull; Facility ID: {locationId}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="rounded-lg p-1.5 text-slate-400 hover:bg-[#1a2230] hover:text-white transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Modal Navigation Tabs */}
        <div className="flex border-b border-[#1b2331] bg-[#0a0e16] px-6 text-xs font-mono">
          <button
            onClick={() => setActiveTab('overview')}
            className={cn(
              'border-b-2 py-2.5 px-3 font-semibold transition-colors',
              activeTab === 'overview'
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            )}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('cameras')}
            className={cn(
              'border-b-2 py-2.5 px-3 font-semibold transition-colors flex items-center gap-1.5',
              activeTab === 'cameras'
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            )}
          >
            <Camera className="h-3.5 w-3.5" />
            <span>Cameras ({location?.camera_count ?? cameraData?.total ?? 0})</span>
          </button>
          <button
            onClick={() => setActiveTab('departments')}
            className={cn(
              'border-b-2 py-2.5 px-3 font-semibold transition-colors flex items-center gap-1.5',
              activeTab === 'departments'
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            )}
          >
            <Briefcase className="h-3.5 w-3.5" />
            <span>Departments ({location?.department_count ?? departments.length})</span>
          </button>
          <button
            onClick={() => setActiveTab('workstations')}
            className={cn(
              'border-b-2 py-2.5 px-3 font-semibold transition-colors flex items-center gap-1.5',
              activeTab === 'workstations'
                ? 'border-emerald-500 text-emerald-400'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            )}
          >
            <Monitor className="h-3.5 w-3.5" />
            <span>Workstation Zones ({zoneData?.total ?? 0})</span>
          </button>
        </div>

        {/* Body Content */}
        <div className="p-6 text-xs font-mono">
          {locationLoading ? (
            <div className="py-16 text-center text-slate-400">
              <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent mb-3" />
              <p>Querying facility location details and entity counts...</p>
            </div>
          ) : locationError || !location ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-rose-400 space-y-3">
              <AlertCircle className="h-8 w-8 text-rose-400" />
              <p>Failed to retrieve location details from backend API.</p>
              <button
                onClick={() => refetchLocation()}
                className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-1 text-[11px] text-rose-300 hover:bg-rose-500/20"
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* TAB 1: OVERVIEW */}
              {activeTab === 'overview' && (
                <div className="space-y-6">
                  {/* Entity Metrics Grid */}
                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                    <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] uppercase tracking-wider">Camera Sensors</span>
                        <Camera className="h-3.5 w-3.5 text-cyan-400" />
                      </div>
                      <p className="mt-1 text-2xl font-bold text-slate-100">
                        {location.camera_count}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-0.5">Assigned CCTV sensors</p>
                    </div>

                    <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] uppercase tracking-wider">Departments</span>
                        <Briefcase className="h-3.5 w-3.5 text-emerald-400" />
                      </div>
                      <p className="mt-1 text-2xl font-bold text-slate-100">
                        {location.department_count}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-0.5">Configured divisions</p>
                    </div>

                    <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
                      <div className="flex items-center justify-between text-slate-400">
                        <span className="text-[10px] uppercase tracking-wider">Personnel</span>
                        <Users className="h-3.5 w-3.5 text-blue-400" />
                      </div>
                      <p className="mt-1 text-2xl font-bold text-slate-100">
                        {location.employee_count}
                      </p>
                      <p className="text-[10px] text-slate-500 mt-0.5">Assigned employees</p>
                    </div>
                  </div>

                  {/* Physical Address & Timezone Metadata */}
                  <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-4 space-y-3">
                    <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider border-b border-[#1b2331] pb-2 flex items-center gap-1.5">
                      <Building2 className="h-3.5 w-3.5 text-emerald-400" />
                      Location Facility Parameters
                    </h3>

                    <div className="grid grid-cols-1 gap-y-2.5 gap-x-4 sm:grid-cols-2 text-[11px]">
                      <div>
                        <span className="text-slate-400">PHYSICAL ADDRESS:</span>
                        <p className="text-slate-200 font-semibold mt-0.5 flex items-start gap-1">
                          <MapPin className="h-3.5 w-3.5 text-slate-500 shrink-0 mt-0.5" />
                          <span>{location.address || 'None provided (Virtual or unassigned)'}</span>
                        </p>
                      </div>

                      <div>
                        <span className="text-slate-400">OPERATIONAL TIMEZONE:</span>
                        <p className="text-slate-200 font-semibold mt-0.5 flex items-center gap-1">
                          <Globe className="h-3.5 w-3.5 text-emerald-400" />
                          {location.timezone}
                        </p>
                      </div>

                      <div>
                        <span className="text-slate-400">CREATED AT:</span>
                        <p className="text-slate-300 font-semibold mt-0.5">
                          {new Date(location.created_at).toLocaleString()}
                        </p>
                      </div>

                      <div>
                        <span className="text-slate-400">LAST UPDATED:</span>
                        <p className="text-slate-300 font-semibold mt-0.5">
                          {new Date(location.updated_at).toLocaleString()}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Schedule Quick Banner */}
                  <div className="flex items-center justify-between rounded-lg border border-[#1e2633] bg-[#0f141d] p-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-purple-500/30 bg-purple-500/10 text-purple-400">
                        <Calendar className="h-4 w-4" />
                      </div>
                      <div>
                        <p className="text-xs font-bold text-slate-200">Facility Operating Schedule</p>
                        <p className="text-[11px] text-slate-400">
                          Configure weekly opening hours, overnight shifts, and after-hours intruder detection thresholds
                        </p>
                      </div>
                    </div>
                    <button
                      type="button"
                      onClick={() => onOpenSchedule(location)}
                      className="rounded-md border border-purple-500/40 bg-purple-500/10 px-3 py-1.5 text-xs text-purple-300 hover:bg-purple-500/20 transition-colors flex items-center gap-1.5"
                    >
                      <Clock className="h-3.5 w-3.5" />
                      <span>Configure Schedule</span>
                    </button>
                  </div>
                </div>
              )}

              {/* TAB 2: CAMERAS */}
              {activeTab === 'cameras' && (
                <div className="space-y-3">
                  {camerasLoading ? (
                    <div className="py-8 text-center text-slate-400">Loading cameras in facility...</div>
                  ) : (cameraData?.items?.length ?? 0) === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10 text-center">
                      <Camera className="h-8 w-8 text-slate-500 mb-2 opacity-50" />
                      <p className="text-xs font-semibold text-slate-300">No Cameras Assigned to this Facility</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Register new cameras in the Cameras module and select this facility location.
                      </p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto rounded border border-[#1e2633]">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-[#1e2633] bg-[#0d1117] text-[10px] uppercase text-slate-400">
                            <th className="py-2.5 px-3">Camera Code</th>
                            <th className="py-2.5 px-3">Name</th>
                            <th className="py-2.5 px-3">Role</th>
                            <th className="py-2.5 px-3">Protocol</th>
                            <th className="py-2.5 px-3">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#18202d] text-slate-300 text-[11px]">
                          {cameraData?.items.map((cam) => (
                            <tr key={cam.id} className="hover:bg-[#12161f]">
                              <td className="py-2.5 px-3 font-bold text-slate-100">{cam.camera_code}</td>
                              <td className="py-2.5 px-3 text-slate-300">{cam.name}</td>
                              <td className="py-2.5 px-3 uppercase text-slate-400">{cam.camera_role}</td>
                              <td className="py-2.5 px-3 uppercase text-slate-400 font-semibold">{cam.stream_type}</td>
                              <td className="py-2.5 px-3">
                                <span
                                  className={cn(
                                    'inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[9px] uppercase font-bold',
                                    cam.connection_status === 'online'
                                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                      : 'bg-slate-500/10 text-slate-400 border border-slate-500/30'
                                  )}
                                >
                                  {cam.connection_status}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 3: DEPARTMENTS */}
              {activeTab === 'departments' && (
                <div className="space-y-3">
                  {departmentsLoading ? (
                    <div className="py-8 text-center text-slate-400">Loading departments...</div>
                  ) : departments.length === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10 text-center">
                      <Briefcase className="h-8 w-8 text-slate-500 mb-2 opacity-50" />
                      <p className="text-xs font-semibold text-slate-300">No Departments Assigned to this Facility</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Departments created in this facility will be listed here.
                      </p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto rounded border border-[#1e2633]">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-[#1e2633] bg-[#0d1117] text-[10px] uppercase text-slate-400">
                            <th className="py-2.5 px-3">Department Name</th>
                            <th className="py-2.5 px-3">Code</th>
                            <th className="py-2.5 px-3">Status</th>
                            <th className="py-2.5 px-3 text-right">Employees</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#18202d] text-slate-300 text-[11px]">
                          {departments.map((dept) => (
                            <tr key={dept.id} className="hover:bg-[#12161f]">
                              <td className="py-2.5 px-3 font-bold text-slate-100">{dept.name}</td>
                              <td className="py-2.5 px-3 text-slate-400 uppercase">{dept.code || 'N/A'}</td>
                              <td className="py-2.5 px-3">
                                <span
                                  className={cn(
                                    'rounded px-1.5 py-0.5 text-[9px] uppercase font-bold',
                                    dept.is_active
                                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                      : 'bg-slate-500/10 text-slate-400 border border-slate-500/30'
                                  )}
                                >
                                  {dept.is_active ? 'ACTIVE' : 'INACTIVE'}
                                </span>
                              </td>
                              <td className="py-2.5 px-3 text-right text-slate-300 font-semibold">
                                {dept.employee_count ?? 0}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* TAB 4: WORKSTATION ZONES */}
              {activeTab === 'workstations' && (
                <div className="space-y-3">
                  {zonesLoading ? (
                    <div className="py-8 text-center text-slate-400">Loading workstation zones...</div>
                  ) : (zoneData?.items?.length ?? 0) === 0 ? (
                    <div className="flex flex-col items-center justify-center py-10 text-center">
                      <Monitor className="h-8 w-8 text-slate-500 mb-2 opacity-50" />
                      <p className="text-xs font-semibold text-slate-300">No Workstation Zones Configured</p>
                      <p className="text-[11px] text-slate-500 mt-0.5">
                        Workstation polygon zones mapped to cameras in this facility will be listed here.
                      </p>
                    </div>
                  ) : (
                    <div className="overflow-x-auto rounded border border-[#1e2633]">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-[#1e2633] bg-[#0d1117] text-[10px] uppercase text-slate-400">
                            <th className="py-2.5 px-3">Zone Code</th>
                            <th className="py-2.5 px-3">Name</th>
                            <th className="py-2.5 px-3">Bound Camera</th>
                            <th className="py-2.5 px-3">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-[#18202d] text-slate-300 text-[11px]">
                          {zoneData?.items.map((zone) => (
                            <tr key={zone.id} className="hover:bg-[#12161f]">
                              <td className="py-2.5 px-3 font-bold text-slate-100">{zone.zone_code}</td>
                              <td className="py-2.5 px-3 text-slate-300">{zone.name}</td>
                              <td className="py-2.5 px-3 text-slate-400 font-mono">Camera #{zone.camera_id}</td>
                              <td className="py-2.5 px-3">
                                <span
                                  className={cn(
                                    'rounded px-1.5 py-0.5 text-[9px] uppercase font-bold',
                                    zone.is_active
                                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/30'
                                      : 'bg-slate-500/10 text-slate-400 border border-slate-500/30'
                                  )}
                                >
                                  {zone.is_active ? 'ACTIVE' : 'INACTIVE'}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </div>
              )}

              {/* Modal Footer Actions */}
              <div className="flex items-center justify-between border-t border-[#1b2331] pt-4">
                <div className="text-[10px] text-slate-500">
                  Created {new Date(location.created_at).toLocaleDateString()}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={onClose}
                    className="rounded-md border border-[#243044] bg-[#111722] px-3.5 py-1.5 text-xs text-slate-300 hover:bg-[#18202d] hover:text-white transition-colors"
                  >
                    Close
                  </button>

                  {canEditSchedule && (
                    <button
                      type="button"
                      onClick={() => onOpenSchedule(location)}
                      className="rounded-md border border-purple-500/40 bg-purple-500/10 px-3 py-1.5 text-xs text-purple-300 hover:bg-purple-500/20 transition-colors flex items-center gap-1.5"
                    >
                      <Calendar className="h-3.5 w-3.5" />
                      <span>Schedules</span>
                    </button>
                  )}

                  {canManage && (
                    <>
                      <button
                        type="button"
                        onClick={() => {
                          onClose()
                          onDeactivate(location)
                        }}
                        className={cn(
                          'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors',
                          location.is_active
                            ? 'border border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20'
                            : 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                        )}
                      >
                        <Power className="h-3.5 w-3.5" />
                        <span>{location.is_active ? 'Deactivate' : 'Activate'}</span>
                      </button>

                      <button
                        type="button"
                        onClick={() => {
                          onClose()
                          onEdit(location)
                        }}
                        className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-cyan-500 transition-colors"
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                        <span>Edit Facility</span>
                      </button>
                    </>
                  )}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
