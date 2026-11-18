import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  X,
  Mail,
  Building2,
  Briefcase,
  Shield,
  UserCheck,
  Edit2,
  Power,
  Activity,
} from 'lucide-react'

import { employeeService } from '@/services/employeeService'
import { faceEnrollmentService } from '@/services/faceEnrollmentService'
import { eventService } from '@/services/eventService'
import { FaceTemplateList } from '@/components/enrollment/FaceTemplateList'
import { FaceEnrollmentModal } from '@/components/enrollment/FaceEnrollmentModal'
import type { Employee } from '@/types/api'

interface EmployeeDetailModalProps {
  isOpen: boolean
  employee: Employee | null
  canManage: boolean
  onClose: () => void
  onEdit: (employee: Employee) => void
  onDeactivate: (employee: Employee) => void
  onRefreshParent: () => void
}

export const EmployeeDetailModal: React.FC<EmployeeDetailModalProps> = ({
  isOpen,
  employee,
  canManage,
  onClose,
  onEdit,
  onDeactivate,
  onRefreshParent,
}) => {
  const [isEnrollModalOpen, setIsEnrollModalOpen] = useState(false)

  // Fetch full employee details including relational names
  const {
    data: detail,
    refetch: refetchDetail,
  } = useQuery({
    queryKey: ['employee', 'detail', employee?.id],
    queryFn: () => employeeService.getEmployeeById(employee!.id),
    enabled: isOpen && !!employee,
  })

  // Fetch face templates
  const {
    data: templates = [],
    isLoading: templatesLoading,
    refetch: refetchTemplates,
  } = useQuery({
    queryKey: ['face_templates', employee?.id],
    queryFn: () => faceEnrollmentService.listEmployeeEnrollments(employee!.id),
    enabled: isOpen && !!employee,
  })

  // Fetch recent detection events
  const { data: eventsData, isLoading: eventsLoading } = useQuery({
    queryKey: ['detection_events', 'by_employee', employee?.id],
    queryFn: () => eventService.getEvents({ employee_id: employee!.id, size: 5 }),
    enabled: isOpen && !!employee,
  })

  if (!isOpen || !employee) return null

  const empData = detail || employee

  const handleEnrollSuccess = () => {
    refetchDetail()
    refetchTemplates()
    onRefreshParent()
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'enrolled':
        return 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400'
      case 'pending':
        return 'border-amber-500/30 bg-amber-500/10 text-amber-400'
      case 'needs_re_enroll':
        return 'border-rose-500/30 bg-rose-500/10 text-rose-400'
      default:
        return 'border-slate-700 bg-slate-800 text-slate-400'
    }
  }

  return (
    <>
      <div className="fixed inset-0 z-40 flex items-center justify-end bg-black/70 backdrop-blur-xs">
        <div className="relative h-full w-full max-w-2xl border-l border-[#1f293d] bg-[#0c1017] shadow-2xl overflow-y-auto font-mono text-xs flex flex-col">
          {/* Header */}
          <div className="flex items-center justify-between border-b border-[#1b2331] px-6 py-4 bg-[#090d14] sticky top-0 z-10">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                <Users className="h-5 w-5" />
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-base font-bold text-slate-100 uppercase tracking-wide">
                    {empData.full_name}
                  </h2>
                  <span
                    className={`rounded border px-2 py-0.5 text-[10px] font-semibold uppercase ${getStatusBadge(
                      empData.enrollment_status
                    )}`}
                  >
                    {empData.enrollment_status}
                  </span>
                </div>
                <p className="text-xs text-slate-400">
                  {empData.employee_code} • ID #{empData.id}
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

          {/* Drawer Content */}
          <div className="p-6 space-y-6 flex-1">
            {/* Quick Actions Row */}
            {canManage && (
              <div className="flex flex-wrap items-center gap-2.5 pb-4 border-b border-[#1b2331]">
                <button
                  type="button"
                  onClick={() => setIsEnrollModalOpen(true)}
                  className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-semibold text-white hover:bg-emerald-500 transition-colors"
                >
                  <UserCheck className="h-3.5 w-3.5" />
                  Enroll Biometrics
                </button>
                <button
                  type="button"
                  onClick={() => onEdit(empData)}
                  className="flex items-center gap-1.5 rounded-lg border border-[#243044] bg-[#111722] px-3 py-1.5 text-xs text-slate-200 hover:bg-[#192233] transition-colors"
                >
                  <Edit2 className="h-3.5 w-3.5" />
                  Edit Profile
                </button>
                <button
                  type="button"
                  onClick={() => onDeactivate(empData)}
                  className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition-colors ${
                    empData.is_active
                      ? 'border-rose-500/30 bg-rose-500/10 text-rose-400 hover:bg-rose-500/20'
                      : 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
                  }`}
                >
                  <Power className="h-3.5 w-3.5" />
                  {empData.is_active ? 'Deactivate' : 'Reactivate'}
                </button>
              </div>
            )}

            {/* Profile Overview Card */}
            <div className="rounded-xl border border-[#1b2331] bg-[#090d14] p-4 space-y-3">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Briefcase className="h-3.5 w-3.5 text-emerald-400" />
                Organizational Assignment
              </h3>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 text-[11px]">
                <div className="flex items-center gap-2 text-slate-400">
                  <Building2 className="h-4 w-4 text-slate-500" />
                  <span>Facility:</span>
                  <span className="text-slate-200 font-semibold truncate">
                    {detail?.location_name || (empData.location_id ? `Location #${empData.location_id}` : 'Unassigned')}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-slate-400">
                  <Briefcase className="h-4 w-4 text-slate-500" />
                  <span>Department:</span>
                  <span className="text-slate-200 font-semibold truncate">
                    {detail?.department_name || (empData.department_id ? `Dept #${empData.department_id}` : 'Unassigned')}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-slate-400">
                  <Mail className="h-4 w-4 text-slate-500" />
                  <span>Corporate Email:</span>
                  <span className="text-slate-200 font-semibold truncate">
                    {empData.email || 'None'}
                  </span>
                </div>

                <div className="flex items-center gap-2 text-slate-400">
                  <Shield className="h-4 w-4 text-slate-500" />
                  <span>Status:</span>
                  <span
                    className={`font-semibold ${
                      empData.is_active ? 'text-emerald-400' : 'text-slate-500'
                    }`}
                  >
                    {empData.is_active ? 'ACTIVE' : 'DEACTIVATED'}
                  </span>
                </div>
              </div>

              {/* Roles */}
              <div className="pt-2 border-t border-[#161d2a]">
                <span className="text-[10px] text-slate-500 uppercase block mb-1.5">
                  Assigned Job Roles:
                </span>
                {empData.roles && empData.roles.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {empData.roles.map((r) => (
                      <span
                        key={r.id}
                        className="rounded border border-[#232f44] bg-[#101724] px-2 py-0.5 text-[10px] text-slate-300"
                      >
                        {r.name}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span className="text-slate-500 text-[10px]">No specific roles assigned.</span>
                )}
              </div>
            </div>

            {/* Face Biometric Templates Section */}
            <div className="space-y-3">
              <div className="flex items-center justify-between">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <UserCheck className="h-3.5 w-3.5 text-emerald-400" />
                  AuraFace Biometric Templates ({templates.length})
                </h3>
                {canManage && (
                  <button
                    type="button"
                    onClick={() => setIsEnrollModalOpen(true)}
                    className="text-[11px] text-emerald-400 hover:text-emerald-300"
                  >
                    + Enroll New Template
                  </button>
                )}
              </div>

              <FaceTemplateList
                employeeId={empData.id}
                templates={templates}
                isLoading={templatesLoading}
                canManage={canManage}
                onRefresh={() => {
                  refetchDetail()
                  refetchTemplates()
                  onRefreshParent()
                }}
              />
            </div>

            {/* Recent Detection Events Section */}
            <div className="space-y-3">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Activity className="h-3.5 w-3.5 text-emerald-400" />
                Recent AI Detection Telemetry
              </h3>

              {eventsLoading ? (
                <div className="p-4 text-center text-slate-500 text-[11px]">
                  Loading detection events...
                </div>
              ) : !eventsData || eventsData.items.length === 0 ? (
                <div className="rounded-lg border border-[#1b2331] bg-[#090d14] p-4 text-center text-slate-500 text-[11px]">
                  No detection telemetry events recorded for this employee.
                </div>
              ) : (
                <div className="space-y-2">
                  {eventsData.items.map((ev) => (
                    <div
                      key={ev.id}
                      className="flex items-center justify-between rounded-lg border border-[#1b2331] bg-[#090d14] p-2.5 text-[11px]"
                    >
                      <div className="flex items-center gap-2">
                        <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-300">
                          {ev.event_type}
                        </span>
                        <span className="text-slate-400">
                          Camera #{ev.camera_id}
                        </span>
                      </div>
                      <div className="text-slate-500 text-[10px]">
                        {new Date(ev.occurred_at).toLocaleString()}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Record Timestamps */}
            <div className="flex items-center justify-between pt-4 border-t border-[#1b2331] text-[10px] text-slate-500">
              <div>Created: {new Date(empData.created_at).toLocaleString()}</div>
              <div>Updated: {new Date(empData.updated_at).toLocaleString()}</div>
            </div>
          </div>
        </div>
      </div>

      {/* Face Enrollment Modal */}
      <FaceEnrollmentModal
        isOpen={isEnrollModalOpen}
        employee={empData}
        onClose={() => setIsEnrollModalOpen(false)}
        onSuccess={handleEnrollSuccess}
      />
    </>
  )
}
