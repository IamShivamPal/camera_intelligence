import apiClient from '@/api/client'
import type {
  Employee,
  EmployeeDetail,
  EmployeeCreatePayload,
  EmployeeUpdatePayload,
  EmployeeQueryParams,
  PaginatedResponse,
} from '@/types/api'

export const employeeService = {
  async getEmployees(params?: EmployeeQueryParams): Promise<PaginatedResponse<Employee>> {
    const response = await apiClient.get<PaginatedResponse<Employee>>('/api/v1/employees', {
      params,
    })
    return response.data
  },

  async getEmployeeById(id: number): Promise<EmployeeDetail> {
    const response = await apiClient.get<EmployeeDetail>(`/api/v1/employees/${id}`)
    return response.data
  },

  async createEmployee(data: EmployeeCreatePayload): Promise<EmployeeDetail> {
    const response = await apiClient.post<EmployeeDetail>('/api/v1/employees', data)
    return response.data
  },

  async updateEmployee(id: number, data: EmployeeUpdatePayload): Promise<EmployeeDetail> {
    const response = await apiClient.patch<EmployeeDetail>(`/api/v1/employees/${id}`, data)
    return response.data
  },

  async deactivateEmployee(id: number): Promise<Employee> {
    const response = await apiClient.delete<Employee>(`/api/v1/employees/${id}`)
    return response.data
  },

  async assignRole(employeeId: number, roleId: number): Promise<EmployeeDetail> {
    const response = await apiClient.post<EmployeeDetail>(`/api/v1/employees/${employeeId}/roles`, {
      role_id: roleId,
    })
    return response.data
  },

  async removeRole(employeeId: number, roleId: number): Promise<EmployeeDetail> {
    const response = await apiClient.delete<EmployeeDetail>(
      `/api/v1/employees/${employeeId}/roles/${roleId}`
    )
    return response.data
  },
}
