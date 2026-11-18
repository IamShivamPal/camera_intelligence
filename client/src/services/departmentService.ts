import apiClient from '@/api/client'
import type { Department } from '@/types/api'

export const departmentService = {
  async getDepartments(params?: {
    location_id?: number
    is_active?: boolean
  }): Promise<Department[]> {
    const response = await apiClient.get<Department[]>('/api/v1/departments', {
      params,
    })
    return response.data
  },

  async getDepartmentById(id: number): Promise<Department> {
    const response = await apiClient.get<Department>(`/api/v1/departments/${id}`)
    return response.data
  },

  async createDepartment(data: {
    name: string
    location_id: number
    code?: string
    is_active?: boolean
  }): Promise<Department> {
    const response = await apiClient.post<Department>('/api/v1/departments', data)
    return response.data
  },

  async updateDepartment(
    id: number,
    data: {
      name?: string
      code?: string
      is_active?: boolean
    }
  ): Promise<Department> {
    const response = await apiClient.patch<Department>(`/api/v1/departments/${id}`, data)
    return response.data
  },
}
