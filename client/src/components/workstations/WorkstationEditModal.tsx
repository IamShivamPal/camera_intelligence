import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  X,
  Edit2,
  AlertCircle,
  Check,
  Camera,
  Clock,
  Layers,
} from 'lucide-react'
import { zoneService } from '@/services/zoneService'
import { cameraService } from '@/services/cameraService'
import type { WorkstationZone, WorkstationZoneDetail } from '@/types/api'
import { PolygonEditorCanvas } from './PolygonEditorCanvas'

interface WorkstationEditModalProps {
  zone: WorkstationZone | WorkstationZoneDetail | null
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

interface WorkstationEditFormProps {
  zone: WorkstationZone | WorkstationZoneDetail
  onClose: () => void
  onSuccess: () => void
}

const WorkstationEditForm: React.FC<WorkstationEditFormProps> = ({
  zone,
  onClose,
  onSuccess,
}) => {
  const [name, setName] = useState(zone.name)
  const [zoneCode, setZoneCode] = useState(zone.zone_code)
  const [cameraId, setCameraId] = useState<number>(zone.camera_id)
  const [inactivitySeconds, setInactivitySeconds] = useState(zone.inactivity_threshold_seconds)
  const [isActive, setIsActive] = useState(zone.is_active)
  const [polygonPoints, setPolygonPoints] = useState<[number, number][]>(
    zone.polygon_points as [number, number][]
  )

  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Query cameras in the zone's location
  const { data: cameraData, isLoading: camerasLoading } = useQuery({
    queryKey: ['cameras', 'location_edit', zone.location_id],
    queryFn: () =>
      cameraService.getCameras({ location_id: zone.location_id, is_active: true, size: 50 }),
  })

  const availableCameras = cameraData?.items || []

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    const cleanName = name.trim()
    const cleanCode = zoneCode.trim()

    if (!cleanName) {
      setFormError('Workstation name cannot be empty.')
      return
    }

    if (!cleanCode) {
      setFormError('Zone code cannot be empty.')
      return
    }

    if (inactivitySeconds <= 0) {
      setFormError('Inactivity threshold must be greater than 0 seconds.')
      return
    }

    if (polygonPoints.length < 3) {
      setFormError('Polygon must contain at least 3 vertices.')
      return
    }

    const uniqueCount = new Set(
      polygonPoints.map(([x, y]) => `${x.toFixed(4)},${y.toFixed(4)}`)
    ).size
    if (uniqueCount < 3) {
      setFormError('Polygon must contain at least 3 distinct non-collinear vertices.')
      return
    }

    setIsSubmitting(true)

    try {
      await zoneService.updateZone(zone.id, {
        name: cleanName,
        zone_code: cleanCode,
        camera_id: cameraId,
        polygon_points: polygonPoints,
        inactivity_threshold_seconds: inactivitySeconds,
        is_active: isActive,
      })

      onSuccess()
      onClose()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setFormError(detail)
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg || JSON.stringify(d)).join(', '))
      } else {
        setFormError('Failed to update workstation zone.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  const minutes = Math.floor(inactivitySeconds / 60)
  const remainingSeconds = inactivitySeconds % 60
  const humanDuration = `${minutes}m ${remainingSeconds > 0 ? `${remainingSeconds}s` : ''}`

  return (
    <form onSubmit={handleSubmit} className="p-6 space-y-5 text-xs font-mono">
      {formError && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
          <div className="text-[11px] leading-relaxed">{formError}</div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Zone Name */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
            Workstation Name <span className="text-rose-400">*</span>
          </label>
          <input
            type="text"
            required
            maxLength={150}
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors"
          />
        </div>

        {/* Zone Code */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
            Zone Code (Unique) <span className="text-rose-400">*</span>
          </label>
          <input
            type="text"
            required
            maxLength={100}
            value={zoneCode}
            onChange={(e) => setZoneCode(e.target.value)}
            className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors"
          />
        </div>

        {/* Camera Sensor Selection */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Camera className="h-3.5 w-3.5 text-slate-400" />
            Monitoring Camera <span className="text-rose-400">*</span>
          </label>
          <select
            required
            disabled={camerasLoading}
            value={cameraId}
            onChange={(e) => setCameraId(Number(e.target.value))}
            className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors"
          >
            {availableCameras.map((cam) => (
              <option key={cam.id} value={cam.id}>
                {cam.camera_code} — {cam.name}
              </option>
            ))}
          </select>
        </div>

        {/* Inactivity Threshold */}
        <div>
          <div className="flex items-center justify-between mb-1">
            <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1">
              <Clock className="h-3.5 w-3.5 text-cyan-400" />
              Inactivity Alert Threshold (Seconds) <span className="text-rose-400">*</span>
            </label>
            <span className="text-[10px] text-cyan-400 font-bold">~{humanDuration}</span>
          </div>
          <input
            type="number"
            min={1}
            max={86400}
            required
            value={inactivitySeconds}
            onChange={(e) => setInactivitySeconds(Math.max(1, Number(e.target.value)))}
            className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-cyan-500 focus:outline-none focus:ring-1 focus:ring-cyan-500 transition-colors"
          />
        </div>

        {/* Active Monitoring Toggle */}
        <div className="sm:col-span-2">
          <div className="flex items-center justify-between rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
            <div>
              <p className="text-xs font-semibold text-slate-200">Active Monitoring Status</p>
              <p className="text-[10px] text-slate-400">
                AI Engine evaluates optical flow inactivity and presence sessions when active
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-10 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-cyan-600"></div>
            </label>
          </div>
        </div>
      </div>

      {/* Interactive Polygon Boundary Editor */}
      <div className="space-y-2 border-t border-[#1b2331] pt-4">
        <div className="flex items-center justify-between">
          <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
            <Layers className="h-3.5 w-3.5 text-cyan-400" />
            Adjust Polygon Boundary Coordinates <span className="text-rose-400">*</span>
          </label>
          <span className="text-[10px] text-slate-500">DRAG VERTICES TO REFINE BOUNDARY</span>
        </div>

        <PolygonEditorCanvas
          points={polygonPoints}
          onChange={(pts) => setPolygonPoints(pts)}
        />
      </div>

      {/* Footer Actions */}
      <div className="flex items-center justify-end gap-3 border-t border-[#1b2331] pt-4">
        <button
          type="button"
          onClick={onClose}
          disabled={isSubmitting}
          className="rounded-md border border-[#243044] bg-[#111722] px-4 py-2 text-xs font-medium text-slate-300 hover:bg-[#18202d] hover:text-white transition-colors"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting || polygonPoints.length < 3}
          className="flex items-center gap-1.5 rounded-md bg-cyan-600 px-4 py-2 text-xs font-semibold text-white hover:bg-cyan-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {isSubmitting ? (
            <>
              <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
              <span>Saving Changes...</span>
            </>
          ) : (
            <>
              <Check className="h-3.5 w-3.5" />
              <span>Update Workstation</span>
            </>
          )}
        </button>
      </div>
    </form>
  )
}

export const WorkstationEditModal: React.FC<WorkstationEditModalProps> = ({
  zone,
  isOpen,
  onClose,
  onSuccess,
}) => {
  if (!isOpen || !zone) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-3xl rounded-xl border border-[#222d3f] bg-[#0c1017] shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1b2331] px-6 py-4 bg-[#090d14]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-400">
              <Edit2 className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                CONFIGURE WORKSTATION: {zone.zone_code}
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                Update polygon vertices, inactivity duration and camera sensor binding
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

        {/* Remounted Form */}
        <WorkstationEditForm
          key={zone.id}
          zone={zone}
          onClose={onClose}
          onSuccess={onSuccess}
        />
      </div>
    </div>
  )
}
