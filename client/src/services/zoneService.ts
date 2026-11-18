import apiClient from '@/api/client'
import type {
  PaginatedResponse,
  WorkstationZone,
  WorkstationZoneDetail,
  WorkstationZoneCreatePayload,
  WorkstationZoneUpdatePayload,
  WorkstationZoneQueryParams,
} from '@/types/api'

export const zoneService = {
  async getZones(params?: WorkstationZoneQueryParams): Promise<PaginatedResponse<WorkstationZone>> {
    const response = await apiClient.get<PaginatedResponse<WorkstationZone>>('/api/v1/zones', {
      params,
    })
    return response.data
  },

  async getZoneById(id: number): Promise<WorkstationZoneDetail> {
    const response = await apiClient.get<WorkstationZoneDetail>(`/api/v1/zones/${id}`)
    return response.data
  },

  async createZone(payload: WorkstationZoneCreatePayload): Promise<WorkstationZoneDetail> {
    const response = await apiClient.post<WorkstationZoneDetail>('/api/v1/zones', payload)
    return response.data
  },

  async updateZone(id: number, payload: WorkstationZoneUpdatePayload): Promise<WorkstationZoneDetail> {
    const response = await apiClient.patch<WorkstationZoneDetail>(`/api/v1/zones/${id}`, payload)
    return response.data
  },

  async deactivateZone(id: number): Promise<WorkstationZone> {
    const response = await apiClient.delete<WorkstationZone>(`/api/v1/zones/${id}`)
    return response.data
  },

  async assignEmployee(zoneId: number, employeeId: number): Promise<WorkstationZoneDetail> {
    const response = await apiClient.post<WorkstationZoneDetail>(
      `/api/v1/zones/${zoneId}/assign-employee`,
      { employee_id: employeeId }
    )
    return response.data
  },

  async removeEmployee(zoneId: number): Promise<WorkstationZoneDetail> {
    const response = await apiClient.delete<WorkstationZoneDetail>(
      `/api/v1/zones/${zoneId}/assign-employee`
    )
    return response.data
  },
}
