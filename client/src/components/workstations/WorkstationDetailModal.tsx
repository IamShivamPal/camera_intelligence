import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  X,
  Monitor,
  Building2,
  Camera,
  Clock,
  Layers,
  Edit2,
  Power,
  AlertCircle,
  Cpu,
  User,
  Briefcase,
} from 'lucide-react'
import { zoneService } from '@/services/zoneService'
import type { WorkstationZoneDetail } from '@/types/api'
import { PolygonEditorCanvas } from './PolygonEditorCanvas'
import { cn } from '@/lib/utils'

interface WorkstationDetailModalProps {
  zoneId: number | null
  isOpen: boolean
  onClose: () => void
  onEdit: (zone: WorkstationZoneDetail) => void
  onDeactivate: (zone: WorkstationZoneDetail) => void
  canManage: boolean
}

export const WorkstationDetailModal: React.FC<WorkstationDetailModalProps> = ({
  zoneId,
  isOpen,
  onClose,
  onEdit,
  onDeactivate,
  canManage,
}) => {
  const {
    data: zone,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['zone', zoneId],
    queryFn: () => (zoneId ? zoneService.getZoneById(zoneId) : Promise.reject('No ID')),
    enabled: isOpen && zoneId !== null,
  })

  if (!isOpen || zoneId === null) return null

  const minutes = zone ? Math.floor(zone.inactivity_threshold_seconds / 60) : 0
  const remainingSeconds = zone ? zone.inactivity_threshold_seconds % 60 : 0
  const humanDuration = `${minutes}m ${remainingSeconds > 0 ? `${remainingSeconds}s` : ''}`

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-3xl rounded-xl border border-[#222d3f] bg-[#0c1017] shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1b2331] px-6 py-4 bg-[#090d14]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Monitor className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                  {zone?.zone_code || `ZONE #${zoneId}`}
                </h2>
                {zone && (
                  <span
                    className={cn(
                      'rounded px-2 py-0.5 text-[10px] font-mono uppercase font-bold',
                      zone.is_active
                        ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                        : 'border border-rose-500/30 bg-rose-500/10 text-rose-400'
                    )}
                  >
                    {zone.is_active ? 'ACTIVE MONITORING' : 'INACTIVE'}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                {zone?.name || 'Loading workstation specification...'}
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

        {/* Content Body */}
        <div className="p-6 text-xs font-mono">
          {isLoading ? (
            <div className="py-16 text-center text-slate-400">
              <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent mb-3" />
              <p>Querying workstation zone geometry and AI analytics parameters...</p>
            </div>
          ) : isError || !zone ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-rose-400 space-y-3">
              <AlertCircle className="h-8 w-8 text-rose-400" />
              <p>Failed to retrieve workstation zone from backend API.</p>
              <button
                onClick={() => refetch()}
                className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-1 text-[11px] text-rose-300 hover:bg-rose-500/20"
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Parameters Grid */}
              <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-4 space-y-3">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider border-b border-[#1b2331] pb-2 flex items-center gap-1.5">
                  <Cpu className="h-3.5 w-3.5 text-cyan-400" />
                  Topology & AI Analytics Parameters
                </h3>

                <div className="grid grid-cols-1 gap-y-2.5 gap-x-4 sm:grid-cols-2 text-[11px]">
                  <div>
                    <span className="text-slate-400">FACILITY LOCATION:</span>
                    <p className="text-slate-200 font-semibold mt-0.5 flex items-center gap-1">
                      <Building2 className="h-3.5 w-3.5 text-slate-400" />
                      {zone.location_name || `Location #${zone.location_id}`}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400">MONITORING CAMERA SENSOR:</span>
                    <p className="text-slate-200 font-semibold mt-0.5 flex items-center gap-1">
                      <Camera className="h-3.5 w-3.5 text-emerald-400" />
                      {zone.camera_code ? `${zone.camera_code} (${zone.camera_name})` : `Camera #${zone.camera_id}`}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400">INACTIVITY ALERT THRESHOLD:</span>
                    <p className="text-slate-200 font-semibold mt-0.5 flex items-center gap-1">
                      <Clock className="h-3.5 w-3.5 text-emerald-400" />
                      {zone.inactivity_threshold_seconds}s (~{humanDuration})
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400">SPATIAL CONTAINMENT LOGIC:</span>
                    <p className="text-slate-200 font-semibold mt-0.5">
                      Ray-Casting (Bottom-Center Feet Point)
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400">ASSIGNED PERSONNEL:</span>
                    <p className="text-slate-300 font-semibold mt-0.5 flex items-center gap-1">
                      <User className="h-3.5 w-3.5 text-slate-500" />
                      {zone.assigned_employee_name || 'Unassigned (Hot-desk)'}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400">DEPARTMENT:</span>
                    <p className="text-slate-300 font-semibold mt-0.5 flex items-center gap-1">
                      <Briefcase className="h-3.5 w-3.5 text-slate-500" />
                      {zone.department_name || 'Unassigned'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Polygon Boundary Canvas (Read-Only) */}
              <div className="space-y-2 border-t border-[#1b2331] pt-4">
                <div className="flex items-center justify-between">
                  <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-cyan-400" />
                    Spatial Polygon Geometry ({zone.polygon_points.length} Vertices)
                  </label>
                  <span className="text-[10px] text-slate-500">INSPECT BOUNDARY</span>
                </div>

                <PolygonEditorCanvas
                  points={zone.polygon_points as [number, number][]}
                  onChange={() => {}}
                  readOnly={true}
                />
              </div>

              {/* Audit Timestamps */}
              <div className="flex items-center justify-between text-[10px] text-slate-500 border-t border-[#1b2331] pt-3">
                <span>Created: {new Date(zone.created_at).toLocaleString()}</span>
                <span>Updated: {new Date(zone.updated_at).toLocaleString()}</span>
              </div>

              {/* Action Buttons */}
              <div className="flex items-center justify-end gap-3 border-t border-[#1b2331] pt-4">
                <button
                  type="button"
                  onClick={onClose}
                  className="rounded-md border border-[#243044] bg-[#111722] px-4 py-2 text-xs font-medium text-slate-300 hover:bg-[#18202d] hover:text-white transition-colors"
                >
                  Close
                </button>

                {canManage && (
                  <>
                    <button
                      type="button"
                      onClick={() => {
                        onClose()
                        onDeactivate(zone)
                      }}
                      className={cn(
                        'flex items-center gap-1.5 rounded-md px-3.5 py-2 text-xs font-semibold transition-colors',
                        zone.is_active
                          ? 'border border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20'
                          : 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                      )}
                    >
                      <Power className="h-3.5 w-3.5" />
                      <span>{zone.is_active ? 'Deactivate Zone' : 'Activate Zone'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        onClose()
                        onEdit(zone)
                      }}
                      className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500 transition-colors"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                      <span>Edit Workstation</span>
                    </button>
                  </>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
