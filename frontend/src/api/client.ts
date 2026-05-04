/**
 * API client configuration.
 *
 * Provides a configured axios instance for making API requests.
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Configured axios instance with interceptors for auth.
 */
export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Request interceptor to add auth token.
 * Falls back to Zustand's persisted auth-storage if the direct 'token' key
 * hasn't been synced yet (e.g. on first render before loadUser() runs).
 */
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    let token = localStorage.getItem('token')
    if (!token) {
      try {
        const persisted = localStorage.getItem('auth-storage')
        token = persisted ? JSON.parse(persisted)?.state?.token ?? null : null
      } catch {
        // ignore parse errors
      }
    }
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

/**
 * Response interceptor to handle auth errors.
 * Handles both 401 (invalid/expired token) and 403 (missing credentials,
 * which HTTPBearer used to return before we switched to auto_error=False).
 */
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    const status = error.response?.status
    if (status === 401 || status === 403) {
      const url = error.config?.url || ''
      // Don't redirect for auth endpoints — let the page handle the error
      const isAuthEndpoint = url.includes('/auth/')
      if (!isAuthEndpoint) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

/**
 * API error response type.
 */
export interface ApiError {
  detail: string
}

/**
 * Extract error message from API error response.
 */
export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const apiError = error.response?.data as ApiError | undefined
    return apiError?.detail || error.message || 'An error occurred'
  }
  return 'An unexpected error occurred'
}
