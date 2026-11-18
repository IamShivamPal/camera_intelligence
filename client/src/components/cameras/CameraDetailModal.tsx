import React from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  X,
  Camera,
  Activity,
  ShieldAlert,
  Building2,
  Clock,
  Lock,
  Layers,
  Edit2,
  Power,
  AlertCircle,
  Radio,
} from 'lucide-react'
import { cameraService } from '@/services/cameraService'
import type { CameraDetail } from '@/types/api'
import { cn } from '@/lib/utils'

interface CameraDetailModalProps {
  cameraId: number | null
  isOpen: boolean
  onClose: () => void
  onEdit: (camera: CameraDetail) => void
  onDeactivate: (camera: CameraDetail) => void
  canManage: boolean
}

export const CameraDetailModal: React.FC<CameraDetailModalProps> = ({
  cameraId,
  isOpen,
  onClose,
  onEdit,
  onDeactivate,
  canManage,
}) => {
  const {
    data: camera,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['camera', cameraId],
    queryFn: () => (cameraId ? cameraService.getCameraById(cameraId) : Promise.reject('No ID')),
    enabled: isOpen && cameraId !== null,
  })

  if (!isOpen || cameraId === null) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-xl border border-[#222d3f] bg-[#0c1017] shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1b2331] px-6 py-4 bg-[#090d14]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Camera className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                  {camera?.camera_code || `CAMERA #${cameraId}`}
                </h2>
                {camera && (
                  <span
                    className={cn(
                      'inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-mono uppercase font-bold',
                      camera.connection_status === 'online'
                        ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
                        : camera.connection_status === 'offline'
                        ? 'border border-rose-500/30 bg-rose-500/10 text-rose-400'
                        : 'border border-slate-500/30 bg-slate-500/10 text-slate-400'
                    )}
                  >
                    <span
                      className={cn(
                        'h-1.5 w-1.5 rounded-full',
                        camera.connection_status === 'online'
                          ? 'bg-emerald-400'
                          : camera.connection_status === 'offline'
                          ? 'bg-rose-400'
                          : 'bg-slate-400'
                      )}
                    />
                    {camera.connection_status}
                  </span>
                )}
                {camera && (
                  <span
                    className={cn(
                      'rounded px-1.5 py-0.5 text-[10px] font-mono uppercase',
                      camera.is_active
                        ? 'bg-emerald-950 text-emerald-300 border border-emerald-800'
                        : 'bg-slate-800 text-slate-400 border border-slate-700'
                    )}
                  >
                    {camera.is_active ? 'ACTIVE' : 'INACTIVE'}
                  </span>
                )}
              </div>
              <p className="text-xs text-slate-400 font-mono mt-0.5">
                {camera?.name || 'Loading metadata...'}
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
              <p>Querying camera telemetry and configuration...</p>
            </div>
          ) : isError || !camera ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-rose-400 space-y-3">
              <AlertCircle className="h-8 w-8 text-rose-400" />
              <p>Failed to retrieve camera details from backend API.</p>
              <button
                onClick={() => refetch()}
                className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-1 text-[11px] text-rose-300 hover:bg-rose-500/20"
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="space-y-6">
              {/* Top KPI Cards (Authentic Telemetry Counts) */}
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-[10px] uppercase tracking-wider">Detection Events</span>
                    <Activity className="h-3.5 w-3.5 text-emerald-400" />
                  </div>
                  <p className="mt-1 text-xl font-bold text-slate-100">
                    {camera.detection_event_count}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-0.5">Ingested by AI Engine</p>
                </div>

                <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-[10px] uppercase tracking-wider">Security Alerts</span>
                    <ShieldAlert className="h-3.5 w-3.5 text-rose-400" />
                  </div>
                  <p className="mt-1 text-xl font-bold text-slate-100">
                    {camera.alert_count}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-0.5">Generated alerts</p>
                </div>

                <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
                  <div className="flex items-center justify-between text-slate-400">
                    <span className="text-[10px] uppercase tracking-wider">Workstation Zones</span>
                    <Layers className="h-3.5 w-3.5 text-cyan-400" />
                  </div>
                  <p className="mt-1 text-xl font-bold text-slate-100">
                    {camera.workstation_zones.length}
                  </p>
                  <p className="text-[10px] text-slate-500 mt-0.5">Bound polygon zones</p>
                </div>
              </div>

              {/* Configuration Matrix */}
              <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-4 space-y-3">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider border-b border-[#1b2331] pb-2 flex items-center gap-1.5">
                  <Radio className="h-3.5 w-3.5 text-emerald-400" />
                  Stream Configuration & Telemetry
                </h3>

                <div className="grid grid-cols-1 gap-y-2.5 gap-x-4 sm:grid-cols-2 text-[11px]">
                  <div>
                    <span className="text-slate-400">FACILITY LOCATION:</span>
                    <p className="text-slate-200 font-semibold mt-0.5 flex items-center gap-1">
                      <Building2 className="h-3 w-3 text-slate-400" />
                      {camera.location_name || `Location #${camera.location_id}`}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400">CAMERA ROLE:</span>
                    <p className="text-slate-200 font-semibold mt-0.5 uppercase">
                      {camera.camera_role.replace(/_/g, ' ')}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400">STREAM PROTOCOL:</span>
                    <p className="text-slate-200 font-semibold mt-0.5 uppercase">
                      {camera.stream_type}
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-400">LAST HEARTBEAT:</span>
                    <p className="text-slate-200 font-semibold mt-0.5 flex items-center gap-1">
                      <Clock className="h-3 w-3 text-slate-400" />
                      {camera.last_heartbeat_at
                        ? new Date(camera.last_heartbeat_at).toLocaleString()
                        : 'NEVER RECEIVED'}
                    </p>
                  </div>

                  <div className="sm:col-span-2 border-t border-[#18202d] pt-2">
                    <span className="text-slate-400 flex items-center gap-1">
                      <Lock className="h-3 w-3 text-cyan-400" />
                      STREAM SECRET REFERENCE:
                    </span>
                    <p className="text-slate-300 font-semibold mt-0.5 bg-[#090d14] px-2 py-1 rounded border border-[#1e2633] text-[11px]">
                      {camera.stream_secret_ref || 'None configured (Local or Open source)'}
                    </p>
                  </div>
                </div>
              </div>

              {/* Attached Workstation Zones */}
              <div className="rounded-lg border border-[#1e2633] bg-[#0f141d] p-4">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider border-b border-[#1b2331] pb-2 flex items-center justify-between">
                  <span className="flex items-center gap-1.5">
                    <Layers className="h-3.5 w-3.5 text-cyan-400" />
                    Bound Workstation Zones
                  </span>
                  <span className="text-[10px] text-slate-400">
                    {camera.workstation_zones.length} ASSIGNED
                  </span>
                </h3>

                <div className="mt-3">
                  {camera.workstation_zones.length === 0 ? (
                    <p className="text-[11px] text-slate-500 italic py-2">
                      No workstation zones currently attached to this camera sensor.
                    </p>
                  ) : (
                    <div className="divide-y divide-[#18202d]">
                      {camera.workstation_zones.map((zone) => (
                        <div key={zone.id} className="py-2 flex items-center justify-between text-[11px]">
                          <div>
                            <span className="font-bold text-slate-200">{zone.zone_code}</span>
                            <span className="text-slate-400 ml-2">&bull; {zone.name}</span>
                          </div>
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
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Audit Timestamps */}
              <div className="flex items-center justify-between text-[10px] text-slate-500 border-t border-[#1b2331] pt-3">
                <span>Created: {new Date(camera.created_at).toLocaleString()}</span>
                <span>Updated: {new Date(camera.updated_at).toLocaleString()}</span>
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
                        onDeactivate(camera)
                      }}
                      className={cn(
                        'flex items-center gap-1.5 rounded-md px-3.5 py-2 text-xs font-semibold transition-colors',
                        camera.is_active
                          ? 'border border-rose-500/30 bg-rose-500/10 text-rose-300 hover:bg-rose-500/20'
                          : 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-300 hover:bg-emerald-500/20'
                      )}
                    >
                      <Power className="h-3.5 w-3.5" />
                      <span>{camera.is_active ? 'Deactivate Camera' : 'Activate Camera'}</span>
                    </button>

                    <button
                      type="button"
                      onClick={() => {
                        onClose()
                        onEdit(camera)
                      }}
                      className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500 transition-colors"
                    >
                      <Edit2 className="h-3.5 w-3.5" />
                      <span>Edit Configuration</span>
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
