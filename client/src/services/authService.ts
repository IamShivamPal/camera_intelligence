import apiClient from '@/api/client'
import type { LoginRequest, TokenResponse, User } from '@/types/api'

export const authService = {
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/api/v1/auth/login', credentials)
    return response.data
  },

  async getMe(): Promise<User> {
    const response = await apiClient.get<User>('/api/v1/auth/me')
    return response.data
  },

  async logout(): Promise<void> {
    try {
      await apiClient.post('/api/v1/auth/logout')
    } finally {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user_profile')
    }
  },
}
