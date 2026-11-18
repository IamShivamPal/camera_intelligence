import apiClient from '@/api/client'
import type { HealthCheckResponse } from '@/types/api'

export const systemService = {
  async getHealth(): Promise<HealthCheckResponse> {
    const response = await apiClient.get<HealthCheckResponse>('/health')
    return response.data
  },
}
