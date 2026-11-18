import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  X,
  Monitor,
  AlertCircle,
  Check,
  Building2,
  Camera,
  Clock,
  Layers,
} from 'lucide-react'
import { zoneService } from '@/services/zoneService'
import { locationService } from '@/services/locationService'
import { cameraService } from '@/services/cameraService'
import { PolygonEditorCanvas } from './PolygonEditorCanvas'

interface WorkstationRegisterModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export const WorkstationRegisterModal: React.FC<WorkstationRegisterModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [name, setName] = useState('')
  const [zoneCode, setZoneCode] = useState('')
  const [locationId, setLocationId] = useState<number | ''>('')
  const [cameraId, setCameraId] = useState<number | ''>('')
  const [inactivitySeconds, setInactivitySeconds] = useState(900)
  const [isActive, setIsActive] = useState(true)

  // Initial standard desk polygon preset
  const [polygonPoints, setPolygonPoints] = useState<[number, number][]>([
    [0.25, 0.35],
    [0.75, 0.35],
    [0.75, 0.8],
    [0.25, 0.8],
  ])

  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Query accessible locations
  const { data: locations = [], isLoading: locationsLoading } = useQuery({
    queryKey: ['locations'],
    queryFn: () => locationService.getLocations({ is_active: true }),
    enabled: isOpen,
  })

  // Query cameras in the selected location
  const { data: cameraData, isLoading: camerasLoading } = useQuery({
    queryKey: ['cameras', 'location_filter', locationId],
    queryFn: () =>
      locationId
        ? cameraService.getCameras({ location_id: Number(locationId), is_active: true, size: 50 })
        : Promise.resolve({ items: [], total: 0, page: 1, size: 50, pages: 0 }),
    enabled: isOpen && typeof locationId === 'number' && locationId > 0,
  })

  const availableCameras = cameraData?.items || []

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    const cleanName = name.trim()
    const cleanCode = zoneCode.trim()

    if (!cleanName) {
      setFormError('Workstation name is required.')
      return
    }

    if (!cleanCode) {
      setFormError('Zone code is required (e.g. WS-DEV-01).')
      return
    }

    if (!locationId || typeof locationId !== 'number') {
      setFormError('Please select a facility location.')
      return
    }

    if (!cameraId || typeof cameraId !== 'number') {
      setFormError('Please select a camera sensor monitoring this workstation.')
      return
    }

    if (inactivitySeconds <= 0) {
      setFormError('Inactivity threshold must be greater than 0 seconds.')
      return
    }

    if (polygonPoints.length < 3) {
      setFormError('Polygon must contain at least 3 vertices to form a closed spatial boundary.')
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
      await zoneService.createZone({
        name: cleanName,
        zone_code: cleanCode,
        location_id: locationId,
        camera_id: cameraId,
        polygon_points: polygonPoints,
        inactivity_threshold_seconds: inactivitySeconds,
        is_active: isActive,
      })

      // Reset form and notify
      setName('')
      setZoneCode('')
      setLocationId('')
      setCameraId('')
      setInactivitySeconds(900)
      setIsActive(true)
      setPolygonPoints([
        [0.25, 0.35],
        [0.75, 0.35],
        [0.75, 0.8],
        [0.25, 0.8],
      ])
      onSuccess()
      onClose()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setFormError(detail)
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg || JSON.stringify(d)).join(', '))
      } else {
        setFormError('Failed to create workstation zone. Please verify backend connectivity.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  // Format seconds to human readable
  const minutes = Math.floor(inactivitySeconds / 60)
  const remainingSeconds = inactivitySeconds % 60
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
              <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                REGISTER WORKSTATION ZONE
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                Define spatial desk boundary polygon, camera mapping & optical flow thresholds
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

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 text-xs font-mono">
          {formError && (
            <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
              <div className="text-[11px] leading-relaxed">{formError}</div>
            </div>
          )}

          {/* Form Fields Grid */}
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
                placeholder="e.g. Engineering Pod Desk 01"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
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
                placeholder="e.g. WS-ENG-01"
                value={zoneCode}
                onChange={(e) => setZoneCode(e.target.value)}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              />
            </div>

            {/* Facility Location */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
                <Building2 className="h-3.5 w-3.5 text-slate-400" />
                Facility Location <span className="text-rose-400">*</span>
              </label>
              <select
                required
                disabled={locationsLoading}
                value={locationId}
                onChange={(e) => {
                  const newLocId = e.target.value ? Number(e.target.value) : ''
                  setLocationId(newLocId)
                  setCameraId('') // Reset camera on location change
                }}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors disabled:opacity-50"
              >
                <option value="">{locationsLoading ? 'Loading facilities...' : 'Select facility...'}</option>
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} (ID: {loc.id})
                  </option>
                ))}
              </select>
            </div>

            {/* Bound Camera */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
                <Camera className="h-3.5 w-3.5 text-slate-400" />
                Monitoring Camera <span className="text-rose-400">*</span>
              </label>
              <select
                required
                disabled={!locationId || camerasLoading}
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value ? Number(e.target.value) : '')}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                <option value="">
                  {!locationId
                    ? 'Select location first...'
                    : camerasLoading
                    ? 'Loading cameras...'
                    : availableCameras.length === 0
                    ? 'No cameras in this facility'
                    : 'Select camera sensor...'}
                </option>
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
                  <Clock className="h-3.5 w-3.5 text-emerald-400" />
                  Inactivity Alert Threshold (Seconds) <span className="text-rose-400">*</span>
                </label>
                <span className="text-[10px] text-emerald-400 font-bold">~{humanDuration}</span>
              </div>
              <input
                type="number"
                min={1}
                max={86400}
                required
                value={inactivitySeconds}
                onChange={(e) => setInactivitySeconds(Math.max(1, Number(e.target.value)))}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              />
              <p className="mt-1 text-[10px] text-slate-400">
                AI Engine monitors Farneback optical flow within zone. Default: 900s (15 min).
              </p>
            </div>

            {/* Active Status Toggle */}
            <div className="flex flex-col justify-end">
              <div className="flex items-center justify-between rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
                <div>
                  <p className="text-xs font-semibold text-slate-200">Active Monitoring</p>
                  <p className="text-[10px] text-slate-400">
                    Enable optical flow & occupancy tracking in AI Engine
                  </p>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={isActive}
                    onChange={(e) => setIsActive(e.target.checked)}
                    className="sr-only peer"
                  />
                  <div className="w-10 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
                </label>
              </div>
            </div>
          </div>

          {/* Interactive Polygon Boundary Editor */}
          <div className="space-y-2 border-t border-[#1b2331] pt-4">
            <div className="flex items-center justify-between">
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Layers className="h-3.5 w-3.5 text-cyan-400" />
                Workstation Polygon Boundary Coordinates <span className="text-rose-400">*</span>
              </label>
              <span className="text-[10px] text-slate-500">CLICK TO ADD &bull; DRAG TO ADJUST</span>
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
              disabled={isSubmitting || polygonPoints.length < 3 || !locationId || !cameraId}
              className="flex items-center gap-1.5 rounded-md bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {isSubmitting ? (
                <>
                  <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  <span>Registering...</span>
                </>
              ) : (
                <>
                  <Check className="h-3.5 w-3.5" />
                  <span>Register Workstation</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
