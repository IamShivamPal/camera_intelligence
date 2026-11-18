import React, { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  Users,
  Plus,
  Search,
  Filter,
  RefreshCw,
  LayoutGrid,
  List,
  Eye,
  Edit2,
  Power,
  Building2,
  Briefcase,
  Shield,
  UserCheck,
  AlertCircle,
  CheckCircle2,
  Clock,
  X,
  ChevronLeft,
  ChevronRight,
  Lock,
} from 'lucide-react'

import { useAuth } from '@/context/useAuth'
import { employeeService } from '@/services/employeeService'
import { locationService } from '@/services/locationService'
import { departmentService } from '@/services/departmentService'
import type { Employee, EnrollmentStatus } from '@/types/api'
import { cn } from '@/lib/utils'

import { EmployeeRegisterModal } from '@/components/employees/EmployeeRegisterModal'
import { EmployeeEditModal } from '@/components/employees/EmployeeEditModal'
import { EmployeeDetailModal } from '@/components/employees/EmployeeDetailModal'
import { EmployeeDeactivateDialog } from '@/components/employees/EmployeeDeactivateDialog'
import { FaceEnrollmentModal } from '@/components/enrollment/FaceEnrollmentModal'

export const Employees: React.FC = () => {
  const { user } = useAuth()
  const canManage = user?.system_role === 'super_admin' || user?.system_role === 'location_admin'

  // Filter & Search states
  const [search, setSearch] = useState('')
  const [selectedLocation, setSelectedLocation] = useState<string>('all')
  const [selectedDepartment, setSelectedDepartment] = useState<string>('all')
  const [selectedEnrollment, setSelectedEnrollment] = useState<string>('all')
  const [selectedActive, setSelectedActive] = useState<string>('all')
  const [viewMode, setViewMode] = useState<'table' | 'grid'>('table')
  const [page, setPage] = useState(1)
  const size = 15

  // Modals state
  const [isRegisterOpen, setIsRegisterOpen] = useState(false)
  const [editingEmployee, setEditingEmployee] = useState<Employee | null>(null)
  const [detailEmployee, setDetailEmployee] = useState<Employee | null>(null)
  const [deactivatingEmployee, setDeactivatingEmployee] = useState<Employee | null>(null)
  const [enrollingEmployee, setEnrollingEmployee] = useState<Employee | null>(null)

  // Query accessible locations
  const { data: locations = [] } = useQuery({
    queryKey: ['locations'],
    queryFn: () => locationService.getLocations(),
  })

  // Map locations for display lookup
  const locationMap = useMemo(() => {
    const map = new Map<number, string>()
    locations.forEach((loc) => map.set(loc.id, loc.name))
    return map
  }, [locations])

  // Query departments (filtered if location selected)
  const { data: departments = [] } = useQuery({
    queryKey: ['departments', 'filter_list', selectedLocation],
    queryFn: () =>
      departmentService.getDepartments({
        location_id: selectedLocation !== 'all' ? Number(selectedLocation) : undefined,
      }),
  })

  const departmentMap = useMemo(() => {
    const map = new Map<number, string>()
    departments.forEach((dept) => map.set(dept.id, dept.name))
    return map
  }, [departments])

  // Build query parameters
  const queryParams = useMemo(() => {
    return {
      page,
      size,
      search: search.trim() ? search.trim() : undefined,
      location_id: selectedLocation !== 'all' ? Number(selectedLocation) : undefined,
      department_id: selectedDepartment !== 'all' ? Number(selectedDepartment) : undefined,
      enrollment_status: selectedEnrollment !== 'all' ? selectedEnrollment : undefined,
      is_active:
        selectedActive === 'all'
          ? undefined
          : selectedActive === 'active'
          ? true
          : false,
    }
  }, [page, size, search, selectedLocation, selectedDepartment, selectedEnrollment, selectedActive])

  // Main Employees Query
  const {
    data: employeeData,
    isLoading,
    isError,
    error,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['employees', queryParams],
    queryFn: () => employeeService.getEmployees(queryParams),
  })

  // Telemetry KPI Query (unfiltered fleet metrics)
  const { data: allEmployeesData } = useQuery({
    queryKey: ['employees', 'kpi_telemetry'],
    queryFn: () => employeeService.getEmployees({ page: 1, size: 100 }),
    refetchInterval: 30000,
  })

  // Calculate real metrics
  const totalEmployees = allEmployeesData?.total ?? employeeData?.total ?? 0
  const activeEmployees = useMemo(() => {
    if (!allEmployeesData?.items) return 0
    return allEmployeesData.items.filter((e) => e.is_active).length
  }, [allEmployeesData])

  const enrolledCount = useMemo(() => {
    if (!allEmployeesData?.items) return 0
    return allEmployeesData.items.filter((e) => e.enrollment_status === 'enrolled').length
  }, [allEmployeesData])

  const pendingEnrollCount = useMemo(() => {
    if (!allEmployeesData?.items) return 0
    return allEmployeesData.items.filter(
      (e) => e.enrollment_status === 'pending' || e.enrollment_status === 'needs_re_enroll'
    ).length
  }, [allEmployeesData])

  const employeesList = employeeData?.items || []
  const totalPages = employeeData?.pages || 1

  const handleResetFilters = () => {
    setSearch('')
    setSelectedLocation('all')
    setSelectedDepartment('all')
    setSelectedEnrollment('all')
    setSelectedActive('all')
    setPage(1)
  }

  const getEnrollmentBadge = (status: EnrollmentStatus | string) => {
    switch (status) {
      case 'enrolled':
        return (
          <span className="inline-flex items-center gap-1 rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[10px] font-semibold text-emerald-400">
            <CheckCircle2 className="h-3 w-3" />
            ENROLLED
          </span>
        )
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1 rounded border border-amber-500/30 bg-amber-500/10 px-2 py-0.5 text-[10px] font-semibold text-amber-400">
            <Clock className="h-3 w-3" />
            PENDING
          </span>
        )
      case 'needs_re_enroll':
        return (
          <span className="inline-flex items-center gap-1 rounded border border-rose-500/30 bg-rose-500/10 px-2 py-0.5 text-[10px] font-semibold text-rose-400">
            <AlertCircle className="h-3 w-3" />
            RE-ENROLL
          </span>
        )
      default:
        return (
          <span className="inline-flex items-center gap-1 rounded border border-slate-700 bg-slate-800 px-2 py-0.5 text-[10px] font-semibold text-slate-400">
            {status.toUpperCase()}
          </span>
        )
    }
  }

  return (
    <div className="space-y-6 font-mono text-slate-200">
      {/* Top Banner & Title */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-[#1b2331] pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-wider text-slate-100 uppercase">
                Employee Personnel Directory
              </h1>
              <p className="text-xs text-slate-400">
                Manage enterprise personnel profiles, facility assignments, roles & biometric face templates
              </p>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex items-center gap-2.5">
          <button
            onClick={() => refetch()}
            disabled={isFetching}
            className="flex items-center gap-1.5 rounded-lg border border-[#243044] bg-[#0c1017] px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-[#161d2a] hover:text-white transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', isFetching && 'animate-spin text-emerald-400')} />
            <span>Refresh</span>
          </button>

          {canManage ? (
            <button
              onClick={() => setIsRegisterOpen(true)}
              className="flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500 shadow-lg shadow-emerald-950/40 transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>Register Employee</span>
            </button>
          ) : (
            <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-500">
              <Lock className="h-3.5 w-3.5 text-slate-500" />
              <span>Read-Only Access</span>
            </div>
          )}
        </div>
      </div>

      {/* Real KPI Cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        {/* Total Employees */}
        <div className="rounded-xl border border-[#1b2331] bg-[#0c1017] p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="uppercase">Total Personnel</span>
            <Users className="h-4 w-4 text-slate-500" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{totalEmployees}</div>
          <p className="text-[10px] text-slate-500 mt-1">Authorized database records</p>
        </div>

        {/* Active Personnel */}
        <div className="rounded-xl border border-[#1b2331] bg-[#0c1017] p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="uppercase">Active Personnel</span>
            <CheckCircle2 className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">{activeEmployees}</div>
          <p className="text-[10px] text-slate-500 mt-1">Eligible for presence tracking</p>
        </div>

        {/* Biometrics Enrolled */}
        <div className="rounded-xl border border-[#1b2331] bg-[#0c1017] p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="uppercase">Face Enrolled</span>
            <UserCheck className="h-4 w-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">{enrolledCount}</div>
          <p className="text-[10px] text-slate-500 mt-1">AuraFace v1 512D active templates</p>
        </div>

        {/* Pending Enrollment */}
        <div className="rounded-xl border border-[#1b2331] bg-[#0c1017] p-4">
          <div className="flex items-center justify-between text-slate-400 text-xs mb-2">
            <span className="uppercase">Pending / Retest</span>
            <Clock className="h-4 w-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold text-amber-400">{pendingEnrollCount}</div>
          <p className="text-[10px] text-slate-500 mt-1">Awaiting biometric registration</p>
        </div>
      </div>

      {/* Search & Filters Toolbar */}
      <div className="rounded-xl border border-[#1b2331] bg-[#0c1017] p-4 space-y-3">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
          {/* Search Box */}
          <div className="relative flex-1">
            <Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search by full name, employee code, or email..."
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
              className="w-full rounded-lg border border-[#222d3f] bg-[#111722] pl-9 pr-8 py-2 text-xs text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-2.5 text-slate-500 hover:text-slate-300"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>

          {/* View Mode Toggle */}
          <div className="flex items-center gap-1 self-end lg:self-center">
            <button
              onClick={() => setViewMode('table')}
              className={cn(
                'rounded-lg p-2 transition-colors',
                viewMode === 'table'
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:bg-[#161d2a] hover:text-slate-200'
              )}
              title="Table View"
            >
              <List className="h-4 w-4" />
            </button>
            <button
              onClick={() => setViewMode('grid')}
              className={cn(
                'rounded-lg p-2 transition-colors',
                viewMode === 'grid'
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : 'text-slate-400 hover:bg-[#161d2a] hover:text-slate-200'
              )}
              title="Card Grid View"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
          </div>
        </div>

        {/* Filter Dropdowns Grid */}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 pt-2 border-t border-[#18202e] text-xs">
          {/* Location Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Building2 className="h-3 w-3" />
              Facility
            </label>
            <select
              value={selectedLocation}
              onChange={(e) => {
                setSelectedLocation(e.target.value)
                setSelectedDepartment('all') // Reset department on location change
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All Facilities</option>
              {locations.map((loc) => (
                <option key={loc.id} value={loc.id}>
                  {loc.name}
                </option>
              ))}
            </select>
          </div>

          {/* Department Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Briefcase className="h-3 w-3" />
              Department
            </label>
            <select
              value={selectedDepartment}
              onChange={(e) => {
                setSelectedDepartment(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All Departments</option>
              {departments.map((dept) => (
                <option key={dept.id} value={dept.id}>
                  {dept.name}
                </option>
              ))}
            </select>
          </div>

          {/* Biometric Status Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Shield className="h-3 w-3" />
              Enrollment Status
            </label>
            <select
              value={selectedEnrollment}
              onChange={(e) => {
                setSelectedEnrollment(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All Statuses</option>
              <option value="enrolled">Enrolled</option>
              <option value="pending">Pending</option>
              <option value="needs_re_enroll">Needs Re-Enroll</option>
              <option value="revoked">Revoked</option>
            </select>
          </div>

          {/* Active Status Filter */}
          <div>
            <label className="block text-[10px] text-slate-400 uppercase mb-1 flex items-center gap-1">
              <Filter className="h-3 w-3" />
              Personnel State
            </label>
            <select
              value={selectedActive}
              onChange={(e) => {
                setSelectedActive(e.target.value)
                setPage(1)
              }}
              className="w-full rounded border border-[#222d3f] bg-[#111722] px-2.5 py-1.5 text-slate-200 focus:border-emerald-500 focus:outline-none"
            >
              <option value="all">All States</option>
              <option value="active">Active Only</option>
              <option value="inactive">Deactivated Only</option>
            </select>
          </div>
        </div>

        {/* Active Filters Summary */}
        {(search || selectedLocation !== 'all' || selectedDepartment !== 'all' || selectedEnrollment !== 'all' || selectedActive !== 'all') && (
          <div className="flex items-center justify-between pt-2 border-t border-[#18202e] text-[11px] text-slate-400">
            <span>Filtered results active</span>
            <button
              onClick={handleResetFilters}
              className="text-emerald-400 hover:text-emerald-300 underline"
            >
              Clear all filters
            </button>
          </div>
        )}
      </div>

      {/* Main Content Area */}
      {isLoading ? (
        <div className="flex flex-col items-center justify-center p-16 rounded-xl border border-[#1b2331] bg-[#0c1017]">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-emerald-500 border-t-transparent mb-3" />
          <p className="text-xs text-slate-400">Loading authorized personnel directory...</p>
        </div>
      ) : isError ? (
        <div className="flex flex-col items-center justify-center p-12 rounded-xl border border-rose-500/30 bg-rose-500/10 text-rose-300 text-center">
          <AlertCircle className="h-8 w-8 text-rose-400 mb-2" />
          <h3 className="text-sm font-semibold uppercase">Failed to load employees</h3>
          <p className="text-xs text-rose-400/80 mt-1 max-w-md">
            {(error as any)?.response?.data?.detail || 'Database connectivity error or insufficient authorization.'}
          </p>
          <button
            onClick={() => refetch()}
            className="mt-4 rounded-lg bg-rose-600 px-4 py-1.5 text-xs font-semibold text-white hover:bg-rose-500 transition-colors"
          >
            Retry Query
          </button>
        </div>
      ) : employeesList.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-16 rounded-xl border border-[#1b2331] bg-[#0c1017] text-center">
          <Users className="h-10 w-10 text-slate-600 mb-3" />
          <h3 className="text-sm font-semibold text-slate-300 uppercase">No Personnel Records Found</h3>
          <p className="text-xs text-slate-500 mt-1 max-w-md">
            {search || selectedLocation !== 'all' || selectedDepartment !== 'all' || selectedEnrollment !== 'all' || selectedActive !== 'all'
              ? 'No employees match the specified search query or active filter combination.'
              : 'No employees have been registered in the system yet.'}
          </p>
          {canManage && (
            <button
              onClick={() => setIsRegisterOpen(true)}
              className="mt-4 flex items-center gap-1.5 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500 transition-colors"
            >
              <Plus className="h-4 w-4" />
              <span>Register First Employee</span>
            </button>
          )}
        </div>
      ) : viewMode === 'table' ? (
        /* TABLE VIEW */
        <div className="rounded-xl border border-[#1b2331] bg-[#0c1017] overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="border-b border-[#1b2331] bg-[#090d14] text-[11px] uppercase tracking-wider text-slate-400">
                <tr>
                  <th className="px-4 py-3">Employee</th>
                  <th className="px-4 py-3">Code</th>
                  <th className="px-4 py-3">Facility / Location</th>
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3">Biometrics</th>
                  <th className="px-4 py-3">Status</th>
                  <th className="px-4 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#18202e]">
                {employeesList.map((emp) => {
                  const locName = emp.location_id ? locationMap.get(emp.location_id) || `Location #${emp.location_id}` : 'Unassigned'
                  const deptName = emp.department_id ? departmentMap.get(emp.department_id) || `Dept #${emp.department_id}` : 'Unassigned'

                  return (
                    <tr
                      key={emp.id}
                      className="hover:bg-[#101622] transition-colors group"
                    >
                      {/* Name & Email */}
                      <td className="px-4 py-3 font-semibold text-slate-200">
                        <div className="flex items-center gap-2.5">
                          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md border border-[#222d3f] bg-[#111722] text-slate-300">
                            <Users className="h-3.5 w-3.5" />
                          </div>
                          <div>
                            <div className="text-slate-100">{emp.full_name}</div>
                            {emp.email && (
                              <div className="text-[10px] text-slate-500 font-normal truncate max-w-[180px]">
                                {emp.email}
                              </div>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Code */}
                      <td className="px-4 py-3 text-slate-300 font-bold">
                        {emp.employee_code}
                      </td>

                      {/* Location */}
                      <td className="px-4 py-3 text-slate-400">
                        <span className="flex items-center gap-1.5">
                          <Building2 className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                          <span className="truncate max-w-[140px]">{locName}</span>
                        </span>
                      </td>

                      {/* Department */}
                      <td className="px-4 py-3 text-slate-400">
                        <span className="flex items-center gap-1.5">
                          <Briefcase className="h-3.5 w-3.5 text-slate-500 shrink-0" />
                          <span className="truncate max-w-[130px]">{deptName}</span>
                        </span>
                      </td>

                      {/* Biometric Status */}
                      <td className="px-4 py-3">
                        {getEnrollmentBadge(emp.enrollment_status)}
                      </td>

                      {/* Active State */}
                      <td className="px-4 py-3">
                        <span
                          className={cn(
                            'inline-flex items-center gap-1 text-[11px] font-semibold',
                            emp.is_active ? 'text-emerald-400' : 'text-slate-500'
                          )}
                        >
                          <span
                            className={cn(
                              'h-1.5 w-1.5 rounded-full',
                              emp.is_active ? 'bg-emerald-400' : 'bg-slate-600'
                            )}
                          />
                          {emp.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>

                      {/* Action Controls */}
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          {/* Inspect Profile */}
                          <button
                            onClick={() => setDetailEmployee(emp)}
                            className="rounded p-1 text-slate-400 hover:bg-[#1b2331] hover:text-emerald-400 transition-colors"
                            title="View Profile & Biometrics"
                          >
                            <Eye className="h-4 w-4" />
                          </button>

                          {/* Quick Enroll */}
                          {canManage && (
                            <button
                              onClick={() => setEnrollingEmployee(emp)}
                              className="rounded p-1 text-slate-400 hover:bg-[#1b2331] hover:text-emerald-400 transition-colors"
                              title="Enroll Face Biometrics"
                            >
                              <UserCheck className="h-4 w-4" />
                            </button>
                          )}

                          {/* Edit */}
                          {canManage && (
                            <button
                              onClick={() => setEditingEmployee(emp)}
                              className="rounded p-1 text-slate-400 hover:bg-[#1b2331] hover:text-blue-400 transition-colors"
                              title="Edit Employee"
                            >
                              <Edit2 className="h-4 w-4" />
                            </button>
                          )}

                          {/* Deactivate / Reactivate */}
                          {canManage && (
                            <button
                              onClick={() => setDeactivatingEmployee(emp)}
                              className={cn(
                                'rounded p-1 transition-colors',
                                emp.is_active
                                  ? 'text-slate-400 hover:bg-rose-500/10 hover:text-rose-400'
                                  : 'text-slate-500 hover:bg-emerald-500/10 hover:text-emerald-400'
                              )}
                              title={emp.is_active ? 'Deactivate Record' : 'Reactivate Record'}
                            >
                              <Power className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        /* CARD GRID VIEW */
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {employeesList.map((emp) => {
            const locName = emp.location_id ? locationMap.get(emp.location_id) || `Location #${emp.location_id}` : 'Unassigned'
            const deptName = emp.department_id ? departmentMap.get(emp.department_id) || `Dept #${emp.department_id}` : 'Unassigned'

            return (
              <div
                key={emp.id}
                className="flex flex-col justify-between rounded-xl border border-[#1b2331] bg-[#0c1017] p-4.5 hover:border-[#2b384e] transition-colors"
              >
                <div>
                  <div className="flex items-start justify-between gap-2 mb-3">
                    <div className="flex items-center gap-2.5">
                      <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#222d3f] bg-[#111722] text-emerald-400">
                        <Users className="h-4 w-4" />
                      </div>
                      <div>
                        <h4 className="text-sm font-bold text-slate-100">{emp.full_name}</h4>
                        <span className="text-[11px] font-semibold text-slate-400">{emp.employee_code}</span>
                      </div>
                    </div>
                    {getEnrollmentBadge(emp.enrollment_status)}
                  </div>

                  <div className="space-y-1.5 text-[11px] text-slate-400 border-t border-[#161e2b] pt-3">
                    <div className="flex items-center gap-2">
                      <Building2 className="h-3.5 w-3.5 text-slate-500" />
                      <span>{locName}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Briefcase className="h-3.5 w-3.5 text-slate-500" />
                      <span>{deptName}</span>
                    </div>
                    {emp.email && (
                      <div className="text-[10px] text-slate-500 truncate">
                        {emp.email}
                      </div>
                    )}
                  </div>
                </div>

                <div className="flex items-center justify-between pt-4 border-t border-[#161e2b] mt-4">
                  <span
                    className={cn(
                      'text-[10px] font-semibold',
                      emp.is_active ? 'text-emerald-400' : 'text-slate-500'
                    )}
                  >
                    {emp.is_active ? 'ACTIVE' : 'DEACTIVATED'}
                  </span>

                  <div className="flex items-center gap-1.5">
                    <button
                      onClick={() => setDetailEmployee(emp)}
                      className="rounded p-1.5 text-slate-400 hover:bg-[#1b2331] hover:text-emerald-400 transition-colors"
                      title="View Details"
                    >
                      <Eye className="h-3.5 w-3.5" />
                    </button>
                    {canManage && (
                      <button
                        onClick={() => setEnrollingEmployee(emp)}
                        className="rounded p-1.5 text-slate-400 hover:bg-[#1b2331] hover:text-emerald-400 transition-colors"
                        title="Enroll Face"
                      >
                        <UserCheck className="h-3.5 w-3.5" />
                      </button>
                    )}
                    {canManage && (
                      <button
                        onClick={() => setEditingEmployee(emp)}
                        className="rounded p-1.5 text-slate-400 hover:bg-[#1b2331] hover:text-blue-400 transition-colors"
                        title="Edit"
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </button>
                    )}
                    {canManage && (
                      <button
                        onClick={() => setDeactivatingEmployee(emp)}
                        className={cn(
                          'rounded p-1.5 transition-colors',
                          emp.is_active
                            ? 'text-slate-400 hover:bg-rose-500/10 hover:text-rose-400'
                            : 'text-slate-500 hover:bg-emerald-500/10 hover:text-emerald-400'
                        )}
                        title={emp.is_active ? 'Deactivate' : 'Reactivate'}
                      >
                        <Power className="h-3.5 w-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-[#1b2331] pt-4 text-xs">
          <div className="text-slate-400">
            Page <span className="text-slate-100 font-semibold">{page}</span> of{' '}
            <span className="text-slate-100 font-semibold">{totalPages}</span> ({employeeData?.total} total records)
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1 || isFetching}
              className="flex items-center gap-1 rounded border border-[#243044] bg-[#0c1017] px-3 py-1.5 text-slate-300 hover:bg-[#161d2a] disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
              <span>Previous</span>
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages || isFetching}
              className="flex items-center gap-1 rounded border border-[#243044] bg-[#0c1017] px-3 py-1.5 text-slate-300 hover:bg-[#161d2a] disabled:opacity-40 transition-colors"
            >
              <span>Next</span>
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Modals & Drawers */}
      <EmployeeRegisterModal
        isOpen={isRegisterOpen}
        onClose={() => setIsRegisterOpen(false)}
        onSuccess={() => refetch()}
      />

      <EmployeeEditModal
        isOpen={!!editingEmployee}
        employee={editingEmployee}
        onClose={() => setEditingEmployee(null)}
        onSuccess={() => refetch()}
      />

      <EmployeeDetailModal
        isOpen={!!detailEmployee}
        employee={detailEmployee}
        canManage={canManage}
        onClose={() => setDetailEmployee(null)}
        onEdit={(emp) => {
          setDetailEmployee(null)
          setEditingEmployee(emp)
        }}
        onDeactivate={(emp) => {
          setDetailEmployee(null)
          setDeactivatingEmployee(emp)
        }}
        onRefreshParent={() => refetch()}
      />

      <EmployeeDeactivateDialog
        isOpen={!!deactivatingEmployee}
        employee={deactivatingEmployee}
        onClose={() => setDeactivatingEmployee(null)}
        onSuccess={() => refetch()}
      />

      <FaceEnrollmentModal
        isOpen={!!enrollingEmployee}
        employee={enrollingEmployee}
        onClose={() => setEnrollingEmployee(null)}
        onSuccess={() => refetch()}
      />
    </div>
  )
}
