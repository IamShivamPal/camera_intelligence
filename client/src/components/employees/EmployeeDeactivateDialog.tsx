import React, { useState } from 'react'
import { AlertTriangle, X } from 'lucide-react'
import { employeeService } from '@/services/employeeService'
import type { Employee } from '@/types/api'

interface EmployeeDeactivateDialogProps {
  isOpen: boolean
  employee: Employee | null
  onClose: () => void
  onSuccess: () => void
}

export const EmployeeDeactivateDialog: React.FC<EmployeeDeactivateDialogProps> = ({
  isOpen,
  employee,
  onClose,
  onSuccess,
}) => {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen || !employee) return null

  const isDeactivating = employee.is_active

  const handleConfirm = async () => {
    setIsSubmitting(true)
    setError(null)

    try {
      if (isDeactivating) {
        await employeeService.deactivateEmployee(employee.id)
      } else {
        // Reactivate via PATCH
        await employeeService.updateEmployee(employee.id, { is_active: true })
      }
      onSuccess()
      onClose()
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to update personnel status.')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-md rounded-xl border border-[#222d3f] bg-[#0c1017] p-6 shadow-2xl font-mono">
        {/* Close Button */}
        <button
          onClick={onClose}
          className="absolute right-4 top-4 rounded-lg p-1.5 text-slate-400 hover:bg-[#1a2230] hover:text-white transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        {/* Warning Icon & Title */}
        <div className="flex items-center gap-3 mb-4">
          <div
            className={`flex h-10 w-10 items-center justify-center rounded-lg border ${
              isDeactivating
                ? 'border-rose-500/30 bg-rose-500/10 text-rose-400'
                : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
            }`}
          >
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
              {isDeactivating ? 'Deactivate Personnel Record' : 'Reactivate Personnel Record'}
            </h3>
            <p className="text-xs text-slate-400">
              {employee.employee_code} — {employee.full_name}
            </p>
          </div>
        </div>

        {error && (
          <div className="mb-4 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-xs text-rose-300">
            {error}
          </div>
        )}

        {/* Description */}
        <p className="text-xs text-slate-300 leading-relaxed mb-4">
          {isDeactivating ? (
            <>
              Deactivating <strong className="text-white">{employee.full_name}</strong> will
              mark their record as inactive. They will no longer be recognized on CCTV camera
              streams or trigger workstation presence sessions. Historical attendance and face
              biometric templates will remain preserved in the audit log.
            </>
          ) : (
            <>
              Reactivating <strong className="text-white">{employee.full_name}</strong> will restore
              active monitoring, presence session logging, and biometric recognition matching.
            </>
          )}
        </p>

        {/* Action Buttons */}
        <div className="flex items-center justify-end gap-3 pt-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="rounded-lg border border-[#243044] bg-transparent px-4 py-2 text-xs text-slate-300 hover:bg-[#151c27] transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={isSubmitting}
            className={`flex items-center gap-2 rounded-lg px-4 py-2 text-xs font-semibold text-white transition-colors disabled:opacity-50 ${
              isDeactivating
                ? 'bg-rose-600 hover:bg-rose-500'
                : 'bg-emerald-600 hover:bg-emerald-500'
            }`}
          >
            {isSubmitting ? (
              <>
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
                <span>Processing...</span>
              </>
            ) : isDeactivating ? (
              <span>Confirm Deactivation</span>
            ) : (
              <span>Confirm Reactivation</span>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}
