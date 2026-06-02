/**
 * API client configuration.
 *
 * Provides a configured axios instance with auth token injection and
 * automatic access-token refresh on 401 responses.
 */

import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: `${API_BASE_URL}/api/v1`,
  headers: {
    'Content-Type': 'application/json',
  },
})

/**
 * Request interceptor — injects the current access token.
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
  (error: AxiosError) => Promise.reject(error)
)

// Prevent concurrent refresh storms — one in-flight refresh at a time.
let _refreshPromise: Promise<string> | null = null

async function _attemptRefresh(): Promise<string> {
  const refreshToken = localStorage.getItem('refresh_token')
  if (!refreshToken) throw new Error('no refresh token')

  // Use a plain axios call (not apiClient) to avoid interceptor loops.
  const { data } = await axios.post(`${API_BASE_URL}/api/v1/auth/refresh`, {
    refresh_token: refreshToken,
  })

  localStorage.setItem('token', data.access_token)
  localStorage.setItem('refresh_token', data.refresh_token)

  // Keep Zustand's persisted state in sync so loadUser() works after reload.
  try {
    const persisted = localStorage.getItem('auth-storage')
    if (persisted) {
      const parsed = JSON.parse(persisted)
      parsed.state.token = data.access_token
      localStorage.setItem('auth-storage', JSON.stringify(parsed))
    }
  } catch {
    // ignore
  }

  return data.access_token
}

/**
 * Response interceptor — on 401, attempts a silent token refresh and retries
 * the original request once. Redirects to /login if refresh fails.
 */
apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status
    const url = error.config?.url || ''
    const isAuthEndpoint = url.includes('/auth/')

    if (status === 401 && !isAuthEndpoint) {
      try {
        if (!_refreshPromise) {
          _refreshPromise = _attemptRefresh().finally(() => {
            _refreshPromise = null
          })
        }
        const newToken = await _refreshPromise

        // Retry original request with updated token
        const retryConfig = error.config!
        retryConfig.headers = retryConfig.headers ?? {}
        retryConfig.headers.Authorization = `Bearer ${newToken}`
        return apiClient.request(retryConfig)
      } catch {
        localStorage.removeItem('token')
        localStorage.removeItem('refresh_token')
        window.location.href = '/login'
      }
    }

    if (status === 403 && !isAuthEndpoint) {
      localStorage.removeItem('token')
      localStorage.removeItem('refresh_token')
      window.location.href = '/login'
    }

    return Promise.reject(error)
  }
)

export interface ApiError {
  detail: string
}

export const getErrorMessage = (error: unknown): string => {
  if (axios.isAxiosError(error)) {
    const apiError = error.response?.data as ApiError | undefined
    return apiError?.detail || error.message || 'An error occurred'
  }
  return 'An unexpected error occurred'
}
