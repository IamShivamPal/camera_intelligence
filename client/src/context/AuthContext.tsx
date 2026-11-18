/* eslint-disable react-refresh/only-export-components */
import React, { createContext, useEffect, useState } from 'react'
import { authService } from '@/services/authService'
import type { LoginRequest, User } from '@/types/api'

export interface AuthContextType {
  user: User | null
  token: string | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (credentials: LoginRequest) => Promise<void>
  logout: () => Promise<void>
}

export const AuthContext = createContext<AuthContextType | undefined>(undefined)

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(() => {
    const cached = localStorage.getItem('user_profile')
    return cached ? JSON.parse(cached) : null
  })
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('access_token'))
  const [isLoading, setIsLoading] = useState<boolean>(true)

  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('access_token')
      if (storedToken) {
        try {
          const profile = await authService.getMe()
          setUser(profile)
          localStorage.setItem('user_profile', JSON.stringify(profile))
        } catch {
          // Token expired or invalid
          localStorage.removeItem('access_token')
          localStorage.removeItem('user_profile')
          setUser(null)
          setToken(null)
        }
      }
      setIsLoading(false)
    }

    initAuth()

    const handleUnauthorized = () => {
      setUser(null)
      setToken(null)
    }

    window.addEventListener('auth:unauthorized', handleUnauthorized)
    return () => window.removeEventListener('auth:unauthorized', handleUnauthorized)
  }, [])

  const login = async (credentials: LoginRequest) => {
    const data = await authService.login(credentials)
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('user_profile', JSON.stringify(data.user))
    setToken(data.access_token)
    setUser(data.user)
  }

  const logout = async () => {
    try {
      await authService.logout()
    } finally {
      setToken(null)
      setUser(null)
    }
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isAuthenticated: !!token && !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export { useAuth } from './useAuth'
