import apiClient from '@/api/client'
import type {
  Camera,
  CameraDetail,
  CameraCreatePayload,
  CameraUpdatePayload,
  CameraQueryParams,
  PaginatedResponse,
  WorkstationZoneSummary,
} from '@/types/api'

export const cameraService = {
  async getCameras(params?: CameraQueryParams): Promise<PaginatedResponse<Camera>> {
    const response = await apiClient.get<PaginatedResponse<Camera>>('/api/v1/cameras', {
      params,
    })
    return response.data
  },

  async getCameraById(id: number): Promise<CameraDetail> {
    const response = await apiClient.get<CameraDetail>(`/api/v1/cameras/${id}`)
    return response.data
  },

  async createCamera(payload: CameraCreatePayload): Promise<CameraDetail> {
    const response = await apiClient.post<CameraDetail>('/api/v1/cameras', payload)
    return response.data
  },

  async updateCamera(id: number, payload: CameraUpdatePayload): Promise<CameraDetail> {
    const response = await apiClient.patch<CameraDetail>(`/api/v1/cameras/${id}`, payload)
    return response.data
  },

  async deactivateCamera(id: number): Promise<Camera> {
    const response = await apiClient.delete<Camera>(`/api/v1/cameras/${id}`)
    return response.data
  },

  async getCameraZones(id: number): Promise<WorkstationZoneSummary[]> {
    const response = await apiClient.get<WorkstationZoneSummary[]>(`/api/v1/cameras/${id}/zones`)
    return response.data
  },

  async associateWorkstationZone(cameraId: number, zoneId: number): Promise<CameraDetail> {
    const response = await apiClient.post<CameraDetail>(
      `/api/v1/cameras/${cameraId}/zones/${zoneId}`
    )
    return response.data
  },

  async getSnapshot(cameraId: number, quality = 80, maxAge = 5.0): Promise<Blob> {
    const response = await apiClient.get(`/api/v1/cameras/${cameraId}/snapshot`, {
      params: { quality, max_age: maxAge },
      responseType: 'blob',
    })
    return response.data
  },

  getStreamUrl(cameraId: number, fps = 15, quality = 75): string {
    const baseUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000'
    return `${baseUrl}/api/v1/cameras/${cameraId}/stream?fps=${fps}&quality=${quality}`
  },
}
