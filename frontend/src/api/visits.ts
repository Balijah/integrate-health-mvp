/**
 * Visit API functions.
 *
 * Handles CRUD operations for patient visits.
 */

import { apiClient } from './client'

/**
 * Visit creation request data.
 */
export interface CreateVisitRequest {
  patient_ref: string
  visit_date: string
  chief_complaint?: string
}

/**
 * Visit update request data.
 */
export interface UpdateVisitRequest {
  patient_ref?: string
  visit_date?: string
  chief_complaint?: string
}

/**
 * Visit response data.
 */
export interface VisitResponse {
  id: string
  user_id: string
  patient_ref: string
  visit_date: string
  chief_complaint: string | null
  audio_file_path: string | null
  audio_duration_seconds: number | null
  transcript: string | null
  transcription_status: string
  created_at: string
  updated_at: string
}

/**
 * Paginated visit list response.
 */
export interface VisitListResponse {
  items: VisitResponse[]
  total: number
  limit: number
  offset: number
}

/**
 * Create a new visit.
 *
 * @param data - Visit creation data
 * @returns Created visit
 */
export const createVisit = async (
  data: CreateVisitRequest
): Promise<VisitResponse> => {
  const response = await apiClient.post<VisitResponse>('/visits', data)
  return response.data
}

/**
 * Get paginated list of visits.
 *
 * @param limit - Number of visits to return
 * @param offset - Number of visits to skip
 * @returns Paginated visit list
 */
export const getVisits = async (
  limit = 20,
  offset = 0
): Promise<VisitListResponse> => {
  const response = await apiClient.get<VisitListResponse>('/visits', {
    params: { limit, offset },
  })
  return response.data
}

/**
 * Get a single visit by ID.
 *
 * @param id - Visit ID
 * @returns Visit data
 */
export const getVisit = async (id: string): Promise<VisitResponse> => {
  const response = await apiClient.get<VisitResponse>(`/visits/${id}`)
  return response.data
}

/**
 * Update a visit.
 *
 * @param id - Visit ID
 * @param data - Update data
 * @returns Updated visit
 */
export const updateVisit = async (
  id: string,
  data: UpdateVisitRequest
): Promise<VisitResponse> => {
  const response = await apiClient.patch<VisitResponse>(`/visits/${id}`, data)
  return response.data
}

/**
 * Delete a visit.
 *
 * @param id - Visit ID
 */
export const deleteVisit = async (id: string): Promise<void> => {
  await apiClient.delete(`/visits/${id}`)
}
