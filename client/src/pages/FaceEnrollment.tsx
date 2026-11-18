import React, { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  UserCheck,
  Search,
  Shield,
  Clock,
  CheckCircle2,
  AlertCircle,
  Users,
  RefreshCw,
  Cpu,
  Lock,
} from 'lucide-react'

import { useAuth } from '@/context/useAuth'
import { employeeService } from '@/services/employeeService'
import { faceEnrollmentService } from '@/services/faceEnrollmentService'
import { locationService } from '@/services/locationService'
import { FaceEnrollmentModal } from '@/components/enrollment/FaceEnrollmentModal'
import { FaceTemplateList } from '@/components/enrollment/FaceTemplateList'
import { cn } from '@/lib/utils'

export const FaceEnrollment: React.FC = () => {
  const { user } = useAuth()
  const canManage = user?.system_role === 'super_admin' || user?.system_role === 'location_admin'

  const [search, setSearch] = useState('')
  const [filterTab, setFilterTab] = useState<'all' | 'pending' | 'enrolled'>('all')
  const [selectedEmployeeId, setSelectedEmployeeId] = useState<number | null>(null)
  const [isEnrollModalOpen, setIsEnrollModalOpen] = useState(false)

  // Query accessible locations for lookup
  const { data: locations = [] } = useQuery({
    queryKey: ['locations'],
    queryFn: () => locationService.getLocations(),
  })

  const locationMap = useMemo(() => {
    const map = new Map<number, string>()
    locations.forEach((l) => map.set(l.id, l.name))
    return map
  }, [locations])

  // Query employees list
  const {
    data: employeesData,
    isLoading: employeesLoading,
    refetch: refetchEmployees,
    isFetching: employeesFetching,
  } = useQuery({
    queryKey: ['employees', 'for_enrollment_workspace'],
    queryFn: () => employeeService.getEmployees({ page: 1, size: 100 }),
  })

  const allEmployees = useMemo(() => employeesData?.items || [], [employeesData])

  // Filter employees for the left selector column
  const filteredEmployees = useMemo(() => {
    return allEmployees.filter((emp) => {
      const matchSearch =
        !search.trim() ||
        emp.full_name.toLowerCase().includes(search.toLowerCase()) ||
        emp.employee_code.toLowerCase().includes(search.toLowerCase())

      if (!matchSearch) return false

      if (filterTab === 'pending') {
        return emp.enrollment_status === 'pending' || emp.enrollment_status === 'needs_re_enroll'
      }
      if (filterTab === 'enrolled') {
        return emp.enrollment_status === 'enrolled'
      }
      return true
    })
  }, [allEmployees, search, filterTab])

  // Automatically select first employee if none selected
  const activeSelectedId = selectedEmployeeId ?? (filteredEmployees[0]?.id || null)

  const selectedEmployee = useMemo(() => {
    return allEmployees.find((e) => e.id === activeSelectedId) || null
  }, [allEmployees, activeSelectedId])

  // Query templates for selected employee
  const {
    data: templates = [],
    isLoading: templatesLoading,
    refetch: refetchTemplates,
  } = useQuery({
    queryKey: ['face_templates', activeSelectedId],
    queryFn: () => faceEnrollmentService.listEmployeeEnrollments(activeSelectedId!),
    enabled: !!activeSelectedId,
  })

  const handleEnrollSuccess = () => {
    refetchTemplates()
    refetchEmployees()
  }

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'enrolled':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-emerald-400">
            <CheckCircle2 className="h-3 w-3" />
            ENROLLED
          </span>
        )
      case 'pending':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-amber-400">
            <Clock className="h-3 w-3" />
            PENDING
          </span>
        )
      case 'needs_re_enroll':
        return (
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-rose-400">
            <AlertCircle className="h-3 w-3" />
            RE-ENROLL
          </span>
        )
      default:
        return <span className="text-[10px] text-slate-500 uppercase">{status}</span>
    }
  }

  return (
    <div className="space-y-6 font-mono text-slate-200">
      {/* Top Banner & Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-[#1b2331] pb-5">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
              <UserCheck className="h-5 w-5" />
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-wider text-slate-100 uppercase">
                Face Biometric Enrollment
              </h1>
              <p className="text-xs text-slate-400">
                AuraFace v1 512D Template Registration, Facial Alignment & Multi-Angle Biometric Registry
              </p>
            </div>
          </div>
        </div>

        <button
          onClick={() => {
            refetchEmployees()
            refetchTemplates()
          }}
          disabled={employeesFetching}
          className="flex items-center gap-1.5 self-start sm:self-auto rounded-lg border border-[#243044] bg-[#0c1017] px-3 py-2 text-xs font-semibold text-slate-300 hover:bg-[#161d2a] hover:text-white transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn('h-3.5 w-3.5', employeesFetching && 'animate-spin text-emerald-400')} />
          <span>Sync Registry</span>
        </button>
      </div>

      {/* AI Engine Architecture & Sync Telemetry Banner */}
      <div className="rounded-xl border border-emerald-500/30 bg-emerald-950/10 p-4 text-xs">
        <div className="flex items-start gap-3">
          <Cpu className="h-5 w-5 text-emerald-400 shrink-0 mt-0.5" />
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold text-slate-100 uppercase tracking-wider">
                AuraFace v1 ONNX Pipeline Status
              </span>
              <span className="rounded border border-emerald-500/40 bg-emerald-500/20 px-2 py-0.2 text-[10px] font-semibold text-emerald-400">
                MODEL: GLINTR100 (512D)
              </span>
              <span className="rounded border border-blue-500/40 bg-blue-500/20 px-2 py-0.2 text-[10px] font-semibold text-blue-300">
                ALIGNMENT: RETINAFACE R34
              </span>
            </div>
            <p className="text-[11px] text-slate-400 leading-relaxed">
              Enrolled face templates are strictly persisted in the PostgreSQL biometric repository (`employee_face_embeddings`).
              The running AI Engine edge service matches live CCTV streams against cached employee templates.
              <span className="text-amber-300 font-semibold block mt-1">
                Notice: Edge dynamic synchronization requires the Edge Ingestion Service to pull updated templates on startup or via periodic config sync.
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* Main Two-Column Workspace */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 items-start">
        {/* Left Column: Personnel Selector (4 cols) */}
        <div className="lg:col-span-4 rounded-xl border border-[#1b2331] bg-[#0c1017] overflow-hidden flex flex-col h-[650px]">
          {/* Column Header */}
          <div className="p-4 border-b border-[#1b2331] bg-[#090d14] space-y-3">
            <div className="flex items-center justify-between">
              <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                <Users className="h-4 w-4 text-emerald-400" />
                Select Personnel ({filteredEmployees.length})
              </h3>
            </div>

            {/* Search Input */}
            <div className="relative">
              <Search className="absolute left-2.5 top-2.5 h-3.5 w-3.5 text-slate-500" />
              <input
                type="text"
                placeholder="Search name or code..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-md border border-[#222d3f] bg-[#111722] pl-8 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:border-emerald-500 focus:outline-none"
              />
            </div>

            {/* Filter Tabs */}
            <div className="flex items-center gap-1 pt-1 text-[11px]">
              <button
                type="button"
                onClick={() => setFilterTab('all')}
                className={cn(
                  'flex-1 rounded py-1 transition-colors',
                  filterTab === 'all'
                    ? 'bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30'
                    : 'text-slate-400 hover:bg-[#151c27]'
                )}
              >
                All
              </button>
              <button
                type="button"
                onClick={() => setFilterTab('pending')}
                className={cn(
                  'flex-1 rounded py-1 transition-colors',
                  filterTab === 'pending'
                    ? 'bg-amber-500/20 text-amber-400 font-semibold border border-amber-500/30'
                    : 'text-slate-400 hover:bg-[#151c27]'
                )}
              >
                Pending
              </button>
              <button
                type="button"
                onClick={() => setFilterTab('enrolled')}
                className={cn(
                  'flex-1 rounded py-1 transition-colors',
                  filterTab === 'enrolled'
                    ? 'bg-emerald-500/20 text-emerald-400 font-semibold border border-emerald-500/30'
                    : 'text-slate-400 hover:bg-[#151c27]'
                )}
              >
                Enrolled
              </button>
            </div>
          </div>

          {/* Employees List */}
          <div className="flex-1 overflow-y-auto divide-y divide-[#161e2b] p-2 space-y-1">
            {employeesLoading ? (
              <div className="p-8 text-center text-xs text-slate-500">
                Loading personnel list...
              </div>
            ) : filteredEmployees.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-500">
                No matching personnel found.
              </div>
            ) : (
              filteredEmployees.map((emp) => {
                const isSelected = emp.id === activeSelectedId
                return (
                  <button
                    key={emp.id}
                    type="button"
                    onClick={() => setSelectedEmployeeId(emp.id)}
                    className={cn(
                      'w-full text-left p-3 rounded-lg transition-colors flex items-center justify-between',
                      isSelected
                        ? 'bg-emerald-500/15 border border-emerald-500/40 text-slate-100'
                        : 'hover:bg-[#111722] text-slate-300'
                    )}
                  >
                    <div>
                      <div className="font-semibold text-xs truncate max-w-[170px]">
                        {emp.full_name}
                      </div>
                      <div className="text-[10px] text-slate-400">
                        {emp.employee_code}
                      </div>
                    </div>
                    <div>{getStatusBadge(emp.enrollment_status)}</div>
                  </button>
                )
              })
            )}
          </div>
        </div>

        {/* Right Column: Biometric Template Inspector & Enrollment (8 cols) */}
        <div className="lg:col-span-8 space-y-6">
          {selectedEmployee ? (
            <>
              {/* Selected Employee Summary Card */}
              <div className="rounded-xl border border-[#1b2331] bg-[#0c1017] p-5">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#1b2331] pb-4">
                  <div className="flex items-center gap-3">
                    <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-emerald-500/30 bg-emerald-500/10 text-emerald-400">
                      <Users className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h2 className="text-base font-bold text-slate-100">
                          {selectedEmployee.full_name}
                        </h2>
                        {getStatusBadge(selectedEmployee.enrollment_status)}
                      </div>
                      <p className="text-xs text-slate-400">
                        {selectedEmployee.employee_code} • #{selectedEmployee.id}
                      </p>
                    </div>
                  </div>

                  {canManage ? (
                    <button
                      type="button"
                      onClick={() => setIsEnrollModalOpen(true)}
                      className="flex items-center gap-2 rounded-lg bg-emerald-600 px-4 py-2 text-xs font-semibold text-white hover:bg-emerald-500 transition-colors shadow-lg shadow-emerald-950/40"
                    >
                      <UserCheck className="h-4 w-4" />
                      <span>Enroll Face Template</span>
                    </button>
                  ) : (
                    <div className="flex items-center gap-1 rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-1.5 text-xs text-slate-500">
                      <Lock className="h-3.5 w-3.5 text-slate-500" />
                      <span>Read-Only Privileges</span>
                    </div>
                  )}
                </div>

                <div className="grid grid-cols-2 gap-4 pt-4 text-xs sm:grid-cols-3">
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block">Facility</span>
                    <span className="text-slate-200 font-semibold truncate block">
                      {selectedEmployee.location_id
                        ? locationMap.get(selectedEmployee.location_id) || `Location #${selectedEmployee.location_id}`
                        : 'Unassigned'}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block">Email</span>
                    <span className="text-slate-200 font-semibold truncate block">
                      {selectedEmployee.email || 'None'}
                    </span>
                  </div>
                  <div>
                    <span className="text-[10px] text-slate-500 uppercase block">Active State</span>
                    <span
                      className={`font-semibold ${
                        selectedEmployee.is_active ? 'text-emerald-400' : 'text-slate-500'
                      }`}
                    >
                      {selectedEmployee.is_active ? 'ACTIVE' : 'DEACTIVATED'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Registered Templates Section */}
              <div className="rounded-xl border border-[#1b2331] bg-[#0c1017] p-5 space-y-4">
                <div className="flex items-center justify-between border-b border-[#1b2331] pb-3">
                  <div>
                    <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                      <Shield className="h-4 w-4 text-emerald-400" />
                      Enrolled Biometric Templates ({templates.length})
                    </h3>
                    <p className="text-[11px] text-slate-500 mt-0.5">
                      AuraFace 512D embeddings associated with this identity
                    </p>
                  </div>
                </div>

                <FaceTemplateList
                  employeeId={selectedEmployee.id}
                  templates={templates}
                  isLoading={templatesLoading}
                  canManage={canManage}
                  onRefresh={() => {
                    refetchTemplates()
                    refetchEmployees()
                  }}
                />
              </div>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center p-20 rounded-xl border border-[#1b2331] bg-[#0c1017] text-center">
              <Users className="h-10 w-10 text-slate-600 mb-3" />
              <h3 className="text-sm font-semibold text-slate-300 uppercase">
                No Personnel Selected
              </h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm">
                Select an employee from the left panel to inspect or register facial biometric templates.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Enrollment Modal */}
      {selectedEmployee && (
        <FaceEnrollmentModal
          isOpen={isEnrollModalOpen}
          employee={selectedEmployee}
          onClose={() => setIsEnrollModalOpen(false)}
          onSuccess={handleEnrollSuccess}
        />
      )}
    </div>
  )
}
