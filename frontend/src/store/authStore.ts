/**
 * Authentication store using Zustand.
 *
 * Manages user authentication state, token storage, and auth actions.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

import {
  getCurrentUser,
  login as loginApi,
  register as registerApi,
  LoginRequest,
  RegisterRequest,
  UserResponse,
} from '../api/auth'
import { getErrorMessage } from '../api/client'
import axios from 'axios'

/**
 * Authentication state interface.
 */
interface AuthState {
  /** Current authenticated user */
  user: UserResponse | null
  /** JWT access token */
  token: string | null
  /** Loading state for auth operations */
  isLoading: boolean
  /** Error message from last operation */
  error: string | null
  /** Whether user is authenticated */
  isAuthenticated: boolean
}

/**
 * Authentication actions interface.
 */
interface AuthActions {
  /** Login with email and password */
  login: (data: LoginRequest) => Promise<boolean>
  /** Register a new user */
  register: (data: RegisterRequest) => Promise<boolean>
  /** Logout and clear state */
  logout: () => void
  /** Load current user from token */
  loadUser: () => Promise<void>
  /** Clear any error messages */
  clearError: () => void
}

/**
 * Combined auth store type.
 */
type AuthStore = AuthState & AuthActions

/**
 * Initial state values.
 */
const initialState: AuthState = {
  user: null,
  token: null,
  isLoading: false,
  error: null,
  isAuthenticated: false,
}

/**
 * Auth store with persistence.
 */
export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      ...initialState,

      login: async (data: LoginRequest): Promise<boolean> => {
        set({ isLoading: true, error: null })
        try {
          const response = await loginApi(data)
          const token = response.access_token

          // Store token in localStorage for API client
          localStorage.setItem('token', token)

          // Load user data
          const user = await getCurrentUser()

          set({
            token,
            user,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })

          return true
        } catch (error) {
          const isUnauthorized = axios.isAxiosError(error) && error.response?.status === 401
          const message = isUnauthorized ? 'Invalid email or password.' : getErrorMessage(error)
          set({
            isLoading: false,
            error: message,
            isAuthenticated: false,
          })
          return false
        }
      },

      register: async (data: RegisterRequest): Promise<boolean> => {
        set({ isLoading: true, error: null })
        try {
          await registerApi(data)
          set({ isLoading: false, error: null })
          return true
        } catch (error) {
          const message = getErrorMessage(error)
          set({ isLoading: false, error: message })
          return false
        }
      },

      logout: () => {
        localStorage.removeItem('token')
        set({
          ...initialState,
        })
      },

      loadUser: async () => {
        const token = get().token || localStorage.getItem('token')
        if (!token) {
          set({ isAuthenticated: false })
          return
        }

        set({ isLoading: true })
        try {
          // Ensure token is in localStorage for API client
          localStorage.setItem('token', token)

          const user = await getCurrentUser()
          set({
            user,
            token,
            isAuthenticated: true,
            isLoading: false,
            error: null,
          })
        } catch {
          // Token is invalid, clear state
          localStorage.removeItem('token')
          set({
            ...initialState,
          })
        }
      },

      clearError: () => {
        set({ error: null })
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
      }),
    }
  )
)
