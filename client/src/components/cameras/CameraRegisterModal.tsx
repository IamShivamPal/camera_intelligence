import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  X,
  Camera,
  ShieldAlert,
  AlertCircle,
  Check,
  Building2,
  Lock,
} from 'lucide-react'
import { cameraService } from '@/services/cameraService'
import { locationService } from '@/services/locationService'
import type { CameraRole, StreamType, ConnectionStatus } from '@/types/api'

interface CameraRegisterModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export const CameraRegisterModal: React.FC<CameraRegisterModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [name, setName] = useState('')
  const [cameraCode, setCameraCode] = useState('')
  const [locationId, setLocationId] = useState<number | ''>('')
  const [cameraRole, setCameraRole] = useState<CameraRole>('general')
  const [streamType, setStreamType] = useState<StreamType>('rtsp')
  const [streamSecretRef, setStreamSecretRef] = useState('')
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>('unknown')
  const [isActive, setIsActive] = useState(true)

  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch available locations
  const { data: locations = [], isLoading: locationsLoading } = useQuery({
    queryKey: ['locations'],
    queryFn: () => locationService.getLocations({ is_active: true }),
    enabled: isOpen,
  })

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    // Validation
    const cleanName = name.trim()
    const cleanCode = cameraCode.trim()
    const cleanSecretRef = streamSecretRef.trim()

    if (!cleanName) {
      setFormError('Camera name is required.')
      return
    }

    if (!cleanCode) {
      setFormError('Camera code is required (e.g. CAM-LOBBY-01).')
      return
    }

    if (!locationId || typeof locationId !== 'number') {
      setFormError('Please select a facility location.')
      return
    }

    // Security check: Reject plaintext inline credentials
    if (
      cleanSecretRef &&
      (/:\/\/[^/]+:[^/]+@/.test(cleanSecretRef) ||
        (cleanSecretRef.includes('@') && cleanSecretRef.split('@')[0].includes(':')))
    ) {
      setFormError(
        'Plaintext credentials or inline authentication (user:pass@) are strictly prohibited. Provide a secret key reference or vault pointer instead.'
      )
      return
    }

    setIsSubmitting(true)

    try {
      await cameraService.createCamera({
        name: cleanName,
        camera_code: cleanCode,
        location_id: locationId,
        camera_role: cameraRole,
        stream_type: streamType,
        stream_secret_ref: cleanSecretRef ? cleanSecretRef : null,
        connection_status: connectionStatus,
        is_active: isActive,
      })

      // Reset and close
      setName('')
      setCameraCode('')
      setLocationId('')
      setStreamSecretRef('')
      setCameraRole('general')
      setStreamType('rtsp')
      setConnectionStatus('unknown')
      setIsActive(true)
      onSuccess()
      onClose()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setFormError(detail)
      } else if (Array.isArray(detail)) {
        setFormError(detail.map((d: any) => d.msg || JSON.stringify(d)).join(', '))
      } else {
        setFormError('Failed to register camera. Please verify backend connectivity.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

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
              <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                REGISTER CAMERA SENSOR
              </h2>
              <p className="text-xs text-slate-400">
                Configure new CCTV stream endpoint and location binding
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

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 text-xs font-mono">
          {formError && (
            <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
              <div className="text-[11px] leading-relaxed">{formError}</div>
            </div>
          )}

          {/* Locations Missing Warning */}
          {!locationsLoading && locations.length === 0 && (
            <div className="flex items-start gap-2.5 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-amber-300">
              <Building2 className="h-4 w-4 shrink-0 mt-0.5 text-amber-400" />
              <div className="text-[11px]">
                <p className="font-bold">No Registered Facility Locations</p>
                <p className="text-amber-400/80 mt-0.5">
                  Cameras must be bound to a location. Please ensure at least one active location exists before creating cameras.
                </p>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            {/* Camera Name */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Camera Name <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                required
                maxLength={150}
                placeholder="e.g. Main Lobby Entrance West"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              />
            </div>

            {/* Camera Code */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Camera Code (Unique) <span className="text-rose-400">*</span>
              </label>
              <input
                type="text"
                required
                maxLength={100}
                placeholder="e.g. CAM-LOBBY-01"
                value={cameraCode}
                onChange={(e) => setCameraCode(e.target.value)}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              />
            </div>

            {/* Facility Location */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Facility Location <span className="text-rose-400">*</span>
              </label>
              <select
                required
                value={locationId}
                onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : '')}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              >
                <option value="">Select location...</option>
                {locations.map((loc) => (
                  <option key={loc.id} value={loc.id}>
                    {loc.name} (ID: {loc.id})
                  </option>
                ))}
              </select>
            </div>

            {/* Camera Role */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Functional Role <span className="text-rose-400">*</span>
              </label>
              <select
                value={cameraRole}
                onChange={(e) => setCameraRole(e.target.value as CameraRole)}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              >
                <option value="general">General Surveillance</option>
                <option value="entry_exit">Entry / Exit Gate (Attendance)</option>
                <option value="workstation">Workstation Occupancy</option>
                <option value="perimeter">Perimeter Boundary</option>
              </select>
            </div>

            {/* Stream Protocol */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Stream Protocol <span className="text-rose-400">*</span>
              </label>
              <select
                value={streamType}
                onChange={(e) => setStreamType(e.target.value as StreamType)}
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              >
                <option value="rtsp">RTSP (Real-Time Streaming Protocol)</option>
                <option value="webcam">USB / Local Webcam</option>
                <option value="file">Local Video File Source</option>
                <option value="onvif">ONVIF IP Camera Profile</option>
              </select>
            </div>

            {/* Initial Telemetry Status */}
            <div>
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Initial Status
              </label>
              <select
                value={connectionStatus}
                onChange={(e) =>
                  setConnectionStatus(e.target.value as ConnectionStatus)
                }
                className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              >
                <option value="unknown">Unknown (Pending Heartbeat)</option>
                <option value="online">Online</option>
                <option value="offline">Offline</option>
                <option value="degraded">Degraded</option>
              </select>
            </div>
          </div>

          {/* Stream Secret Reference Pointer */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider flex items-center gap-1.5">
                <Lock className="h-3 w-3 text-emerald-400" />
                Stream Secret Reference (Optional)
              </label>
              <span className="text-[10px] text-slate-500">POINTER / VAULT KEY</span>
            </div>
            <input
              type="text"
              maxLength={255}
              placeholder="e.g. SECRET_CAM_LOBBY_RTSP or vault://cameras/lobby"
              value={streamSecretRef}
              onChange={(e) => setStreamSecretRef(e.target.value)}
              className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
            />
            <p className="mt-1.5 text-[10px] text-slate-400 flex items-start gap-1">
              <ShieldAlert className="h-3 w-3 text-amber-400 shrink-0 mt-0.5" />
              <span>
                <strong>Security Policy:</strong> Never store plaintext RTSP passwords (e.g. <code className="text-rose-400">rtsp://user:pass@host</code>).
                Store a reference key or environment variable pointer consumed by the AI Engine dispatcher.
              </span>
            </p>
          </div>

          {/* Active Status Toggle */}
          <div className="flex items-center justify-between rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
            <div>
              <p className="text-xs font-semibold text-slate-200">Active Sensor Status</p>
              <p className="text-[11px] text-slate-400">
                Enable for active frame ingestion and biometric inference in AI Engine
              </p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input
                type="checkbox"
                checked={isActive}
                onChange={(e) => setIsActive(e.target.checked)}
                className="sr-only peer"
              />
              <div className="w-11 h-6 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
            </label>
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
              disabled={isSubmitting || locations.length === 0}
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
                  <span>Register Camera</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
