/**
 * Authentication API functions.
 *
 * Handles user registration, login, and current user retrieval.
 */

import { apiClient } from './client'

/**
 * User registration request data.
 */
export interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

/**
 * Login request data.
 */
export interface LoginRequest {
  email: string
  password: string
}

/**
 * Token response from login.
 */
export interface TokenResponse {
  access_token: string
  token_type: string
}

/**
 * User data response.
 */
export interface UserResponse {
  id: string
  email: string
  full_name: string
  is_active: boolean
  created_at: string
  updated_at: string
}

/**
 * Register a new user.
 *
 * @param data - Registration data
 * @returns Created user
 */
export const register = async (data: RegisterRequest): Promise<UserResponse> => {
  const response = await apiClient.post<UserResponse>('/auth/register', data)
  return response.data
}

/**
 * Login with email and password.
 *
 * @param data - Login credentials
 * @returns Access token
 */
export const login = async (data: LoginRequest): Promise<TokenResponse> => {
  const response = await apiClient.post<TokenResponse>('/auth/login', data)
  return response.data
}

/**
 * Get the current authenticated user.
 *
 * @returns Current user data
 */
export const getCurrentUser = async (): Promise<UserResponse> => {
  const response = await apiClient.get<UserResponse>('/auth/me')
  return response.data
}
