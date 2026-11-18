import React, { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  X,
  AlertCircle,
  Building2,
  Briefcase,
  Shield,
  Mail,
  Hash,
} from 'lucide-react'

import { employeeService } from '@/services/employeeService'
import { locationService } from '@/services/locationService'
import { departmentService } from '@/services/departmentService'
import { roleService } from '@/services/roleService'
import type { Employee, EnrollmentStatus } from '@/types/api'

interface EmployeeEditModalProps {
  isOpen: boolean
  employee: Employee | null
  onClose: () => void
  onSuccess: () => void
}

interface EmployeeEditFormProps {
  employee: Employee
  onClose: () => void
  onSuccess: () => void
}

const EmployeeEditForm: React.FC<EmployeeEditFormProps> = ({
  employee,
  onClose,
  onSuccess,
}) => {
  const [fullName, setFullName] = useState(employee.full_name)
  const [email, setEmail] = useState(employee.email || '')
  const [locationId, setLocationId] = useState<number | ''>(employee.location_id ?? '')
  const [departmentId, setDepartmentId] = useState<number | ''>(employee.department_id ?? '')
  const [selectedRoleIds, setSelectedRoleIds] = useState<number[]>(
    employee.roles ? employee.roles.map((r) => r.id) : []
  )
  const [enrollmentStatus, setEnrollmentStatus] = useState<EnrollmentStatus>(
    employee.enrollment_status
  )
  const [isActive, setIsActive] = useState(employee.is_active)

  const [formError, setFormError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  // Fetch active locations
  const { data: locations = [], isLoading: locationsLoading } = useQuery({
    queryKey: ['locations', 'active_for_employee_edit'],
    queryFn: () => locationService.getLocations({ is_active: true }),
  })

  // Fetch departments (filtered by selected location)
  const { data: departments = [], isLoading: departmentsLoading } = useQuery({
    queryKey: ['departments', 'by_location_edit', locationId],
    queryFn: () =>
      departmentService.getDepartments({
        location_id: locationId ? Number(locationId) : undefined,
        is_active: true,
      }),
  })

  // Fetch system roles
  const { data: roles = [], isLoading: rolesLoading } = useQuery({
    queryKey: ['roles'],
    queryFn: () => roleService.getRoles(),
  })

  const handleRoleToggle = (roleId: number) => {
    setSelectedRoleIds((prev) =>
      prev.includes(roleId) ? prev.filter((id) => id !== roleId) : [...prev, roleId]
    )
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setFormError(null)

    const cleanName = fullName.trim()
    const cleanEmail = email.trim() ? email.trim().toLowerCase() : null

    if (!cleanName) {
      setFormError('Employee full name cannot be blank.')
      return
    }

    setIsSubmitting(true)

    try {
      await employeeService.updateEmployee(employee.id, {
        full_name: cleanName,
        email: cleanEmail,
        location_id: locationId ? Number(locationId) : null,
        department_id: departmentId ? Number(departmentId) : null,
        role_ids: selectedRoleIds,
        enrollment_status: enrollmentStatus,
        is_active: isActive,
      })

      onSuccess()
      onClose()
    } catch (err: any) {
      const detail = err.response?.data?.detail
      if (typeof detail === 'string') {
        setFormError(detail)
      } else if (Array.isArray(detail) && detail[0]?.msg) {
        setFormError(`${detail[0].loc.join(' -> ')}: ${detail[0].msg}`)
      } else {
        setFormError('Failed to update employee profile.')
      }
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="p-6 space-y-4 text-xs font-mono">
      {formError && (
        <div className="flex items-start gap-2.5 rounded-lg border border-rose-500/30 bg-rose-500/10 p-3 text-rose-300">
          <AlertCircle className="h-4 w-4 shrink-0 mt-0.5 text-rose-400" />
          <div className="text-[11px] leading-relaxed">{formError}</div>
        </div>
      )}

      {/* Static Code & ID Info Banner */}
      <div className="flex items-center justify-between rounded-lg border border-[#1e2738] bg-[#090d14] p-3 text-slate-400">
        <div className="flex items-center gap-2">
          <Hash className="h-4 w-4 text-slate-500" />
          <span>EMPLOYEE CODE:</span>
          <span className="text-slate-200 font-semibold">{employee.employee_code}</span>
        </div>
        <div className="text-[11px] text-slate-500">ID: #{employee.id}</div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Full Name */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1">
            Full Name <span className="text-rose-400">*</span>
          </label>
          <input
            type="text"
            required
            maxLength={150}
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
          />
        </div>

        {/* Corporate Email */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Mail className="h-3.5 w-3.5 text-slate-400" />
            Corporate Email
          </label>
          <input
            type="email"
            maxLength={150}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
          />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Facility Location */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Building2 className="h-3.5 w-3.5 text-slate-400" />
            Facility Location
          </label>
          <select
            disabled={locationsLoading}
            value={locationId}
            onChange={(e) => {
              const newLocId = e.target.value ? Number(e.target.value) : ''
              setLocationId(newLocId)
              setDepartmentId('') // Clear department if location changes
            }}
            className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors disabled:opacity-50"
          >
            <option value="">{locationsLoading ? 'Loading facilities...' : 'Select facility (Optional)...'}</option>
            {locations.map((loc) => (
              <option key={loc.id} value={loc.id}>
                {loc.name} (ID: {loc.id})
              </option>
            ))}
          </select>
        </div>

        {/* Department */}
        <div>
          <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
            <Briefcase className="h-3.5 w-3.5 text-slate-400" />
            Department
          </label>
          <select
            disabled={departmentsLoading}
            value={departmentId}
            onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : '')}
            className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors disabled:opacity-50"
          >
            <option value="">{departmentsLoading ? 'Loading departments...' : 'Select department (Optional)...'}</option>
            {departments.map((dept) => (
              <option key={dept.id} value={dept.id}>
                {dept.name} {dept.code ? `(${dept.code})` : ''}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Biometric Status Override */}
      <div>
        <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-1 flex items-center gap-1">
          <Shield className="h-3.5 w-3.5 text-slate-400" />
          Biometric Enrollment Status
        </label>
        <select
          value={enrollmentStatus}
          onChange={(e) => setEnrollmentStatus(e.target.value as EnrollmentStatus)}
          className="w-full rounded-md border border-[#243044] bg-[#111722] px-3 py-2 text-slate-100 focus:border-emerald-500 focus:outline-none focus:ring-1 focus:ring-emerald-500 transition-colors"
        >
          <option value="pending">pending (Awaiting Face Enrollment)</option>
          <option value="enrolled">enrolled (Active Biometric Profile)</option>
          <option value="needs_re_enroll">needs_re_enroll (Templates Inactivated / Quality Retest Required)</option>
          <option value="revoked">revoked (Biometric Access Barred)</option>
        </select>
      </div>

      {/* Job Roles Multi-Select */}
      <div>
        <label className="block text-[11px] font-semibold text-slate-300 uppercase tracking-wider mb-2">
          Assigned Job Roles
        </label>
        {rolesLoading ? (
          <div className="text-slate-500 text-[11px]">Loading roles...</div>
        ) : roles.length === 0 ? (
          <div className="text-slate-500 text-[11px]">No roles configured in system.</div>
        ) : (
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 p-3 rounded-lg border border-[#1b2331] bg-[#090d14]">
            {roles.map((r) => {
              const isChecked = selectedRoleIds.includes(r.id)
              return (
                <label
                  key={r.id}
                  className="flex items-center gap-2 cursor-pointer text-slate-300 hover:text-white transition-colors"
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => handleRoleToggle(r.id)}
                    className="rounded border-[#243044] bg-[#111722] text-emerald-500 focus:ring-emerald-500/20"
                  />
                  <span className="text-[11px] truncate">{r.name}</span>
                </label>
              )
            })}
          </div>
        )}
      </div>

      {/* Active Status Toggle */}
      <div className="flex items-center gap-3 pt-2">
        <label className="relative inline-flex cursor-pointer items-center">
          <input
            type="checkbox"
            checked={isActive}
            onChange={(e) => setIsActive(e.target.checked)}
            className="peer sr-only"
          />
          <div className="peer h-5 w-9 rounded-full bg-slate-800 after:absolute after:top-[2px] after:left-[2px] after:h-4 after:w-4 rounded-full bg-slate-600 after:rounded-full after:bg-white after:transition-all after:content-[''] peer-checked:bg-emerald-600 peer-checked:after:translate-x-full"></div>
        </label>
        <div>
          <span className="text-xs font-semibold text-slate-200">Active Personnel Status</span>
          <p className="text-[10px] text-slate-500">
            Inactive employees cannot be recognized on security streams or trigger workstation sessions.
          </p>
        </div>
      </div>

      {/* Footer Controls */}
      <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#1b2331]">
        <button
          type="button"
          onClick={onClose}
          disabled={isSubmitting}
          className="rounded-lg border border-[#243044] bg-transparent px-4 py-2 text-slate-300 hover:bg-[#151c27] transition-colors disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="submit"
          disabled={isSubmitting}
          className="flex items-center gap-2 rounded-lg bg-emerald-600 px-5 py-2 font-semibold text-white hover:bg-emerald-500 transition-colors disabled:opacity-50"
        >
          {isSubmitting ? (
            <>
              <div className="h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
              <span>Saving...</span>
            </>
          ) : (
            <span>Save Profile Changes</span>
          )}
        </button>
      </div>
    </form>
  )
}

export const EmployeeEditModal: React.FC<EmployeeEditModalProps> = ({
  isOpen,
  employee,
  onClose,
  onSuccess,
}) => {
  if (!isOpen || !employee) return null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 overflow-y-auto">
      <div className="relative w-full max-w-2xl rounded-xl border border-[#222d3f] bg-[#0c1017] shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-[#1b2331] px-6 py-4 bg-[#090d14]">
          <div className="flex items-center gap-2.5">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Users className="h-4 w-4" />
            </div>
            <div>
              <h2 className="text-base font-bold text-slate-100 font-mono tracking-wide">
                EDIT PERSONNEL PROFILE
              </h2>
              <p className="text-xs text-slate-400 font-mono">
                Update personnel records, facility assignments, and biometric status
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

        <EmployeeEditForm
          key={employee.id}
          employee={employee}
          onClose={onClose}
          onSuccess={onSuccess}
        />
      </div>
    </div>
  )
}
