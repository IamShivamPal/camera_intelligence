import React, { useState } from 'react'
import {
  X,
  Building2,
  AlertCircle,
  Check,
  Globe,
  MapPin,
} from 'lucide-react'
import { locationService } from '@/services/locationService'

interface LocationRegisterModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

const COMMON_TIMEZONES = [
  'UTC',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'Europe/London',
  'Europe/Berlin',
  'Europe/Paris',
  'Asia/Dubai',
  'Asia/Kolkata',
  'Asia/Singapore',
  'Asia/Tokyo',
  'Australia/Sydney',
]

export const LocationRegisterModal: React.FC<LocationRegisterModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
}) => {
  const [name, setName] = useState('')
  const [address, setAddress] = useState('')
  const [timezone, setTimezone] = useState('UTC')
  const [isActive, setIsActive] = useState(true)

  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  if (!isOpen) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    const cleanName = name.trim()
    const cleanAddress = address.trim()
    const cleanTimezone = timezone.trim()

    if (!cleanName) {
      setFormError('Facility location name is required.')
      return
    }

    setIsSubmitting(true)

    try {
      await locationService.createLocation({
        name: cleanName,
        address: cleanAddress ? cleanAddress : null,
        timezone: cleanTimezone ? cleanTimezone : 'UTC',
        is_active: isActive,
      })

      // Reset state and notify
      setName('')
      setAddress('')
      setTimezone('UTC')
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
        setFormError('Failed to create location. Please verify backend connectivity.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-xl rounded-xl border border-[#222d3f] bg-[#0c1017] shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1b2331] px-6 py-4 bg-[#090d14]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Building2 className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                REGISTER FACILITY LOCATION
              </h2>
              <p className="text-xs text-slate-400">
                Provision a new enterprise site or campus boundary
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

          {/* Location Name */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
              Location / Branch Name <span className="text-rose-400">*</span>
            </label>
            <input
              type="text"
              required
              maxLength={150}
              placeholder="e.g. Headquarters Campus Alpha, North Warehouse"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
            />
          </div>

          {/* Physical Address */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
              <MapPin className="h-3.5 w-3.5 text-slate-400" />
              Physical Address (Optional)
            </label>
            <input
              type="text"
              maxLength={300}
              placeholder="e.g. 100 Security Boulevard, Suite 400, New York, NY 10001"
              value={address}
              onChange={(e) => setAddress(e.target.value)}
              className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
            />
          </div>

          {/* Timezone */}
          <div>
            <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
              <Globe className="h-3.5 w-3.5 text-emerald-400" />
              Operational Timezone (IANA) <span className="text-rose-400">*</span>
            </label>
            <div className="flex gap-2">
              <select
                value={COMMON_TIMEZONES.includes(timezone) ? timezone : 'custom'}
                onChange={(e) => {
                  if (e.target.value !== 'custom') {
                    setTimezone(e.target.value)
                  }
                }}
                className="w-1/2 rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              >
                {COMMON_TIMEZONES.map((tz) => (
                  <option key={tz} value={tz}>
                    {tz}
                  </option>
                ))}
                <option value="custom">Other / Custom</option>
              </select>

              <input
                type="text"
                required
                maxLength={64}
                placeholder="IANA Timezone (e.g. Europe/Rome)"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                className="w-1/2 rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
              />
            </div>
            <p className="mt-1 text-[10px] text-slate-400">
              Used for facility operating schedules, shift transitions, and after-hours intruder alerts.
            </p>
          </div>

          {/* Active Status Toggle */}
          <div className="flex items-center justify-between rounded-lg border border-[#1e2633] bg-[#0f141d] p-3">
            <div>
              <p className="text-xs font-semibold text-slate-200">Active Operational Status</p>
              <p className="text-[11px] text-slate-400">
                Active locations allow camera stream processing, employee check-ins, and alerting
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
              disabled={isSubmitting}
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
                  <span>Register Location</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
