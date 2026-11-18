import apiClient from '@/api/client'
import type {
  Location,
  LocationDetail,
  LocationCreatePayload,
  LocationUpdatePayload,
  LocationSchedule,
  LocationScheduleListResponse,
  LocationScheduleCreatePayload,
  LocationScheduleUpdatePayload,
  Department,
} from '@/types/api'

export const locationService = {
  async getLocations(params?: { is_active?: boolean }): Promise<Location[]> {
    const response = await apiClient.get<Location[]>('/api/v1/locations', {
      params,
    })
    return response.data
  },

  async getLocationById(id: number): Promise<LocationDetail> {
    const response = await apiClient.get<LocationDetail>(`/api/v1/locations/${id}`)
    return response.data
  },

  async createLocation(payload: LocationCreatePayload): Promise<Location> {
    const response = await apiClient.post<Location>('/api/v1/locations', payload)
    return response.data
  },

  async updateLocation(id: number, payload: LocationUpdatePayload): Promise<Location> {
    const response = await apiClient.patch<Location>(`/api/v1/locations/${id}`, payload)
    return response.data
  },

  async deactivateLocation(id: number): Promise<Location> {
    const response = await apiClient.delete<Location>(`/api/v1/locations/${id}`)
    return response.data
  },

  async getLocationSchedules(locationId: number): Promise<LocationScheduleListResponse> {
    const response = await apiClient.get<LocationScheduleListResponse>(
      `/api/v1/locations/${locationId}/schedules`
    )
    return response.data
  },

  async createLocationSchedule(
    locationId: number,
    payload: LocationScheduleCreatePayload
  ): Promise<LocationSchedule> {
    const response = await apiClient.post<LocationSchedule>(
      `/api/v1/locations/${locationId}/schedules`,
      payload
    )
    return response.data
  },

  async updateDaySchedule(
    locationId: number,
    day: string | number,
    payload: LocationScheduleUpdatePayload
  ): Promise<LocationSchedule> {
    const response = await apiClient.patch<LocationSchedule>(
      `/api/v1/locations/${locationId}/schedules/${day}`,
      payload
    )
    return response.data
  },

  async deleteDaySchedule(
    locationId: number,
    day: string | number
  ): Promise<{ detail?: string }> {
    const response = await apiClient.delete<{ detail?: string }>(
      `/api/v1/locations/${locationId}/schedules/${day}`
    )
    return response.data
  },

  async getLocationDepartments(locationId: number): Promise<Department[]> {
    const response = await apiClient.get<Department[]>('/api/v1/departments', {
      params: { location_id: locationId },
    })
    return response.data
  },
}
