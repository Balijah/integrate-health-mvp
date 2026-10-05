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
  is_live_transcription: boolean
  transcription_session_id: string | null
  all_synced: boolean
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
 * Transcription status response.
 */
export interface TranscriptionStatusResponse {
  visit_id: string
  status: 'pending' | 'transcribing' | 'completed' | 'failed'
  transcript: string | null
  error_message: string | null
}

/**
 * Transcription trigger response.
 */
export interface TranscribeResponse {
  visit_id: string
  status: string
  message: string
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

/**
 * Get transcription status for a visit.
 *
 * @param visitId - Visit ID
 * @returns Transcription status
 */
export const getTranscriptionStatus = async (
  visitId: string
): Promise<TranscriptionStatusResponse> => {
  const response = await apiClient.get<TranscriptionStatusResponse>(
    `/visits/${visitId}/transcription/status`
  )
  return response.data
}

/**
 * Retry failed transcription for a visit.
 *
 * @param visitId - Visit ID
 * @returns Transcription retry response
 */
export const retryTranscription = async (
  visitId: string
): Promise<TranscribeResponse> => {
  const response = await apiClient.post<TranscribeResponse>(
    `/visits/${visitId}/transcription/retry`
  )
  return response.data
}
