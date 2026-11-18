import apiClient from '@/api/client'
import type { Role } from '@/types/api'

export const roleService = {
  async getRoles(): Promise<Role[]> {
    const response = await apiClient.get<Role[]>('/api/v1/roles')
    return response.data
  },

  async getRoleById(id: number): Promise<Role> {
    const response = await apiClient.get<Role>(`/api/v1/roles/${id}`)
    return response.data
  },
}
