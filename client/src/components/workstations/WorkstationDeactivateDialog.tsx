import React, { useState } from 'react'
import { AlertTriangle, Power, X, Check } from 'lucide-react'
import { zoneService } from '@/services/zoneService'
import type { WorkstationZone, WorkstationZoneDetail } from '@/types/api'

interface WorkstationDeactivateDialogProps {
  zone: WorkstationZone | WorkstationZoneDetail | null
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

export const WorkstationDeactivateDialog: React.FC<WorkstationDeactivateDialogProps> = ({
  zone,
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen || !zone) return null

  const isDeactivating = zone.is_active

  const handleConfirm = async () => {
    setIsSubmitting(true)
    setError(null)

    try {
      if (isDeactivating) {
        // Soft delete endpoint sets is_active = False
        await zoneService.deactivateZone(zone.id)
      } else {
        // Reactivate via PATCH
        await zoneService.updateZone(zone.id, { is_active: true })
      }
      onSuccess()
      onClose()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      setError(typeof detail === 'string' ? detail : 'Action failed. Please try again.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md rounded-xl border border-[#222d3f] bg-[#0c1017] shadow-2xl p-6 font-mono text-xs">
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:bg-[#1a2230] hover:text-white transition-colors"
        >
          <X className="h-4 w-4" />
        </button>

        <div className="flex items-start gap-3.5">
          <div
            className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${
              isDeactivating
                ? 'border-rose-500/30 bg-rose-500/10 text-rose-400'
                : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
            }`}
          >
            {isDeactivating ? (
              <AlertTriangle className="h-5 w-5" />
            ) : (
              <Power className="h-5 w-5" />
            )}
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100">
              {isDeactivating ? 'Deactivate Workstation Zone?' : 'Reactivate Workstation Zone?'}
            </h3>
            <p className="mt-1 text-slate-400 text-[11px] leading-relaxed">
              Target zone: <span className="text-slate-200 font-bold">{zone.zone_code}</span> ({zone.name})
            </p>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-[#1e2633] bg-[#090d14] p-3 text-[11px] text-slate-400 leading-relaxed">
          {isDeactivating ? (
            <p>
              Soft-deactivating this workstation will set <code className="text-rose-400">is_active = false</code>.
              The AI Engine edge dispatcher will suspend Farneback optical flow inactivity analysis and presence tracking for this desk polygon until reactivated.
            </p>
          ) : (
            <p>
              Reactivating this workstation will set <code className="text-emerald-400">is_active = true</code>.
              The AI Engine edge dispatcher will resume optical flow monitoring and desk occupancy tracking during its next config sync.
            </p>
          )}
        </div>

        {error && (
          <div className="mt-3 rounded-md border border-rose-500/30 bg-rose-500/10 p-2 text-[11px] text-rose-300">
            {error}
          </div>
        )}

        <div className="mt-6 flex items-center justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-md border border-[#243044] bg-[#111722] px-3.5 py-1.5 text-xs text-slate-300 hover:bg-[#18202d] hover:text-white transition-colors"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isSubmitting}
            className={`flex items-center gap-1.5 rounded-md px-3.5 py-1.5 text-xs font-semibold text-white transition-colors ${
              isDeactivating
                ? 'bg-rose-600 hover:bg-rose-500'
                : 'bg-emerald-600 hover:bg-emerald-500'
            }`}
          >
            {isSubmitting ? (
              <>
                <span className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>Processing...</span>
              </>
            ) : (
              <>
                <Check className="h-3.5 w-3.5" />
                <span>{isDeactivating ? 'Confirm Deactivation' : 'Confirm Activation'}</span>
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
