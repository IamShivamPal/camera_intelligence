import React, { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import {
  X,
  Calendar,
  Clock,
  AlertCircle,
  CheckCircle2,
  Moon,
  Trash2,
  Lock,
  Globe,
  Save,
} from 'lucide-react'
import { locationService } from '@/services/locationService'
import type { Location, LocationDetail, LocationSchedule } from '@/types/api'
import { cn } from '@/lib/utils'

interface LocationScheduleModalProps {
  location: Location | LocationDetail | null
  isOpen: boolean
  onClose: () => void
  canManage: boolean
}

const DAYS_OF_WEEK = [
  { index: 0, name: 'Monday' },
  { index: 1, name: 'Tuesday' },
  { index: 2, name: 'Wednesday' },
  { index: 3, name: 'Thursday' },
  { index: 4, name: 'Friday' },
  { index: 5, name: 'Saturday' },
  { index: 6, name: 'Sunday' },
]

interface DayRowState {
  isWorkingDay: boolean
  openTime: string
  closeTime: string
  graceMinutes: number
}

export const LocationScheduleModal: React.FC<LocationScheduleModalProps> = ({
  location,
  isOpen,
  onClose,
  canManage,
}) => {
  const queryClient = useQueryClient()
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; message: string } | null>(
    null
  )

  // Local state for each day of the week
  const [dayStates, setDayStates] = useState<Record<number, DayRowState>>({
    0: { isWorkingDay: true, openTime: '08:00', closeTime: '18:00', graceMinutes: 15 },
    1: { isWorkingDay: true, openTime: '08:00', closeTime: '18:00', graceMinutes: 15 },
    2: { isWorkingDay: true, openTime: '08:00', closeTime: '18:00', graceMinutes: 15 },
    3: { isWorkingDay: true, openTime: '08:00', closeTime: '18:00', graceMinutes: 15 },
    4: { isWorkingDay: true, openTime: '08:00', closeTime: '18:00', graceMinutes: 15 },
    5: { isWorkingDay: false, openTime: '', closeTime: '', graceMinutes: 15 },
    6: { isWorkingDay: false, openTime: '', closeTime: '', graceMinutes: 15 },
  })

  // Query schedules for this location
  const {
    data: scheduleData,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ['location_schedules', location?.id],
    queryFn: async () => {
      if (!location) return null
      const res = await locationService.getLocationSchedules(location.id)
      // Populate local state from existing schedules
      const newStates: Record<number, DayRowState> = { ...dayStates }
      res.schedules.forEach((s) => {
        newStates[s.day_of_week] = {
          isWorkingDay: s.is_working_day,
          openTime: s.open_time ? s.open_time.slice(0, 5) : '',
          closeTime: s.close_time ? s.close_time.slice(0, 5) : '',
          graceMinutes: s.after_hours_grace_minutes ?? 15,
        }
      })
      setDayStates(newStates)
      return res
    },
    enabled: isOpen && location !== null,
  })

  // Mutation to save or update a day schedule
  const saveDayMutation = useMutation({
    mutationFn: async ({
      dayIndex,
      existingSchedule,
    }: {
      dayIndex: number
      existingSchedule?: LocationSchedule
    }) => {
      if (!location) return
      const current = dayStates[dayIndex]

      const formattedOpen = current.isWorkingDay && current.openTime ? `${current.openTime}:00` : null
      const formattedClose = current.isWorkingDay && current.closeTime ? `${current.closeTime}:00` : null

      if (current.isWorkingDay && (!formattedOpen || !formattedClose)) {
        throw new Error('Both open time and close time are required for operational working days.')
      }

      if (current.isWorkingDay && formattedOpen === formattedClose) {
        throw new Error('Opening time and closing time cannot be identical.')
      }

      if (existingSchedule) {
        // Update existing via PATCH
        return await locationService.updateDaySchedule(location.id, dayIndex, {
          is_working_day: current.isWorkingDay,
          open_time: formattedOpen,
          close_time: formattedClose,
          after_hours_grace_minutes: current.graceMinutes,
        })
      } else {
        // Create new via POST
        return await locationService.createLocationSchedule(location.id, {
          day_of_week: dayIndex,
          is_working_day: current.isWorkingDay,
          open_time: formattedOpen,
          close_time: formattedClose,
          after_hours_grace_minutes: current.graceMinutes,
        })
      }
    },
    onSuccess: (_, variables) => {
      const dayName = DAYS_OF_WEEK.find((d) => d.index === variables.dayIndex)?.name
      setFeedback({
        type: 'success',
        message: `${dayName} operational schedule saved successfully.`,
      })
      queryClient.invalidateQueries({ queryKey: ['location_schedules', location?.id] })
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail || err.message || 'Failed to save schedule.'
      setFeedback({ type: 'error', message: detail })
    },
  })

  // Mutation to delete a day schedule
  const deleteDayMutation = useMutation({
    mutationFn: async (dayIndex: number) => {
      if (!location) return
      return await locationService.deleteDaySchedule(location.id, dayIndex)
    },
    onSuccess: (_, dayIndex) => {
      const dayName = DAYS_OF_WEEK.find((d) => d.index === dayIndex)?.name
      setFeedback({
        type: 'success',
        message: `${dayName} schedule entry deleted.`,
      })
      queryClient.invalidateQueries({ queryKey: ['location_schedules', location?.id] })
    },
    onError: (err: any) => {
      const detail = err.response?.data?.detail || err.message || 'Failed to delete schedule.'
      setFeedback({ type: 'error', message: detail })
    },
  })

  if (!isOpen || !location) return null

  const existingMap = new Map<number, LocationSchedule>()
  if (scheduleData?.schedules) {
    scheduleData.schedules.forEach((s) => existingMap.set(s.day_of_week, s))
  }

  const handleFieldChange = (dayIndex: number, field: keyof DayRowState, value: any) => {
    setDayStates((prev) => ({
      ...prev,
      [dayIndex]: {
        ...prev[dayIndex],
        [field]: value,
      },
    }))
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-4xl rounded-xl border border-[#222d3f] bg-[#0c1017] shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1b2331] px-6 py-4 bg-[#090d14]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Calendar className="h-4 w-4" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                  OPERATING SCHEDULE: {location.name}
                </h2>
                <span className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-mono text-emerald-400">
                  ID: {location.id}
                </span>
              </div>
              <p className="text-xs text-slate-400 font-mono flex items-center gap-1.5 mt-0.5">
                <Globe className="h-3 w-3 text-slate-500" />
                <span>Operating Timezone: <strong className="text-slate-300">{location.timezone}</strong></span>
                <span>&bull; Evaluated for after-hours intruder alerts</span>
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

        {/* Feedback Alert */}
        {feedback && (
          <div
            className={cn(
              'mx-6 mt-4 flex items-center justify-between rounded-lg p-3 text-xs font-mono',
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
            <button onClick={() => setFeedback(null)} className="text-slate-400 hover:text-white">
              <X className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Body Content */}
        <div className="p-6 text-xs font-mono">
          {isLoading ? (
            <div className="py-16 text-center text-slate-400">
              <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent mb-3" />
              <p>Querying weekly operating schedule from backend...</p>
            </div>
          ) : isError ? (
            <div className="flex flex-col items-center justify-center py-12 text-center text-rose-400 space-y-3">
              <AlertCircle className="h-8 w-8 text-rose-400" />
              <p>Failed to retrieve operating schedule from backend API.</p>
              <button
                onClick={() => refetch()}
                className="rounded border border-rose-500/40 bg-rose-500/10 px-3 py-1 text-[11px] text-rose-300 hover:bg-rose-500/20"
              >
                Retry
              </button>
            </div>
          ) : (
            <div className="space-y-4">
              {!canManage && (
                <div className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 p-3 text-amber-300 text-[11px]">
                  <Lock className="h-4 w-4 shrink-0 text-amber-400" />
                  <span>
                    Read-only mode. Location Admin or Super Admin authority required to save schedule changes.
                  </span>
                </div>
              )}

              {/* 7-Day Weekly Schedule Table */}
              <div className="overflow-x-auto rounded-lg border border-[#1e2633] bg-[#090d14]">
                <table className="w-full text-left text-xs font-mono">
                  <thead>
                    <tr className="border-b border-[#1e2633] bg-[#0d1117] text-[10px] uppercase text-slate-400">
                      <th className="py-2.5 px-4">Day of Week</th>
                      <th className="py-2.5 px-3">Operational</th>
                      <th className="py-2.5 px-3">Opening Time</th>
                      <th className="py-2.5 px-3">Closing Time</th>
                      <th className="py-2.5 px-3">Grace Period</th>
                      <th className="py-2.5 px-3 text-center">Status</th>
                      <th className="py-2.5 px-4 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#18202d] text-slate-300 text-[11px]">
                    {DAYS_OF_WEEK.map((day) => {
                      const state = dayStates[day.index]
                      const existing = existingMap.get(day.index)
                      const isOvernight =
                        state.isWorkingDay &&
                        state.openTime &&
                        state.closeTime &&
                        state.closeTime < state.openTime

                      return (
                        <tr key={day.index} className="hover:bg-[#0f141f] transition-colors">
                          {/* Day Name */}
                          <td className="py-3 px-4 font-bold text-slate-100">
                            {day.name}
                          </td>

                          {/* Working Day Toggle */}
                          <td className="py-3 px-3">
                            <label className="relative inline-flex items-center cursor-pointer">
                              <input
                                type="checkbox"
                                disabled={!canManage}
                                checked={state.isWorkingDay}
                                onChange={(e) =>
                                  handleFieldChange(day.index, 'isWorkingDay', e.target.checked)
                                }
                                className="sr-only peer"
                              />
                              <div className="w-9 h-5 bg-slate-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600 disabled:opacity-50"></div>
                            </label>
                          </td>

                          {/* Open Time */}
                          <td className="py-3 px-3">
                            <input
                              type="time"
                              disabled={!canManage || !state.isWorkingDay}
                              value={state.openTime}
                              onChange={(e) =>
                                handleFieldChange(day.index, 'openTime', e.target.value)
                              }
                              className="rounded border border-[#222d3f] bg-[#111722] px-2 py-1 text-slate-100 disabled:opacity-30 disabled:cursor-not-allowed focus:border-emerald-500 focus:outline-none"
                            />
                          </td>

                          {/* Close Time */}
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-1.5">
                              <input
                                type="time"
                                disabled={!canManage || !state.isWorkingDay}
                                value={state.closeTime}
                                onChange={(e) =>
                                  handleFieldChange(day.index, 'closeTime', e.target.value)
                                }
                                className="rounded border border-[#222d3f] bg-[#111722] px-2 py-1 text-slate-100 disabled:opacity-30 disabled:cursor-not-allowed focus:border-emerald-500 focus:outline-none"
                              />
                              {isOvernight && (
                                <span
                                  className="inline-flex items-center gap-1 rounded bg-purple-500/10 border border-purple-500/30 px-1.5 py-0.5 text-[9px] text-purple-300 font-bold"
                                  title="Closing time occurs next calendar day"
                                >
                                  <Moon className="h-3 w-3" />
                                  OVERNIGHT
                                </span>
                              )}
                            </div>
                          </td>

                          {/* Grace Minutes */}
                          <td className="py-3 px-3">
                            <div className="flex items-center gap-1">
                              <input
                                type="number"
                                min={0}
                                max={120}
                                disabled={!canManage || !state.isWorkingDay}
                                value={state.graceMinutes}
                                onChange={(e) =>
                                  handleFieldChange(
                                    day.index,
                                    'graceMinutes',
                                    Math.max(0, Number(e.target.value))
                                  )
                                }
                                className="w-16 rounded border border-[#222d3f] bg-[#111722] px-2 py-1 text-slate-100 disabled:opacity-30 disabled:cursor-not-allowed focus:border-emerald-500 focus:outline-none"
                              />
                              <span className="text-[10px] text-slate-500">min</span>
                            </div>
                          </td>

                          {/* Status Badge */}
                          <td className="py-3 px-3 text-center">
                            {existing ? (
                              <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 border border-emerald-500/30 px-2 py-0.5 text-[10px] text-emerald-400 font-bold">
                                CONFIGURED
                              </span>
                            ) : (
                              <span className="rounded bg-slate-800 border border-slate-700 px-2 py-0.5 text-[10px] text-slate-400">
                                DEFAULT
                              </span>
                            )}
                          </td>

                          {/* Row Actions */}
                          <td className="py-3 px-4 text-right">
                            {canManage && (
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  type="button"
                                  onClick={() =>
                                    saveDayMutation.mutate({
                                      dayIndex: day.index,
                                      existingSchedule: existing,
                                    })
                                  }
                                  disabled={saveDayMutation.isPending}
                                  className="flex items-center gap-1 rounded border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-[11px] text-emerald-300 hover:bg-emerald-500/20 transition-colors disabled:opacity-50"
                                  title="Save Day Schedule"
                                >
                                  <Save className="h-3 w-3" />
                                  <span>Save</span>
                                </button>

                                {existing && (
                                  <button
                                    type="button"
                                    onClick={() => deleteDayMutation.mutate(day.index)}
                                    disabled={deleteDayMutation.isPending}
                                    className="rounded border border-rose-500/40 bg-rose-500/10 p-1 text-rose-300 hover:bg-rose-500/20 transition-colors disabled:opacity-50"
                                    title="Delete Schedule Entry"
                                  >
                                    <Trash2 className="h-3 w-3" />
                                  </button>
                                )}
                              </div>
                            )}
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              {/* Explanatory Footnote */}
              <div className="rounded-lg border border-[#1e2633] bg-[#0d1117] p-3 text-[11px] text-slate-400 space-y-1">
                <p className="flex items-center gap-1.5 text-slate-300 font-semibold">
                  <Clock className="h-3.5 w-3.5 text-emerald-400" />
                  Intrusion & After-Hours Detection Rules
                </p>
                <p>
                  Detections occurring outside of configured opening/closing hours plus grace period trigger <code className="text-amber-400">after_hours_employee</code> or <code className="text-rose-400">after_hours_intrusion</code> alerts in the AI Engine.
                </p>
              </div>
            </div>
          )}

          {/* Footer Actions */}
          <div className="mt-6 flex items-center justify-end gap-3 border-t border-[#1b2331] pt-4">
            <button
              type="button"
              onClick={onClose}
              className="rounded-md border border-[#243044] bg-[#111722] px-4 py-2 text-xs font-medium text-slate-300 hover:bg-[#18202d] hover:text-white transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
