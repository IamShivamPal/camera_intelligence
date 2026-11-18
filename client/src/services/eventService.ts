import apiClient from '@/api/client'
import type { Alert, DetectionEvent, PaginatedResponse } from '@/types/api'

export const eventService = {
  async getEvents(params?: {
    location_id?: number
    camera_id?: number
    employee_id?: number
    event_type?: string
    page?: number
    size?: number
  }): Promise<PaginatedResponse<DetectionEvent>> {
    const response = await apiClient.get<PaginatedResponse<DetectionEvent>>('/api/v1/events', {
      params,
    })
    return response.data
  },

  async getAlerts(params?: {
    location_id?: number
    severity?: string
    status?: string
    page?: number
    size?: number
  }): Promise<PaginatedResponse<Alert>> {
    const response = await apiClient.get<PaginatedResponse<Alert>>('/api/v1/alerts', {
      params,
    })
    return response.data
  },
}
