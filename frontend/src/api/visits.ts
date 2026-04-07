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
 * Audio upload response.
 */
export interface AudioUploadResponse {
  visit_id: string
  audio_file_path: string
  audio_duration_seconds: number | null
  file_size_bytes: number
  mime_type: string
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
 * Upload audio for a visit.
 *
 * @param visitId - Visit ID
 * @param audioBlob - Audio file blob
 * @param onProgress - Optional progress callback
 * @returns Audio upload response
 */
export const uploadAudio = async (
  visitId: string,
  audioBlob: Blob,
  onProgress?: (progress: number) => void
): Promise<AudioUploadResponse> => {
  const formData = new FormData()

  // Get file extension from MIME type
  const mimeToExt: Record<string, string> = {
    'audio/webm': 'webm',
    'audio/wav': 'wav',
    'audio/mp3': 'mp3',
    'audio/mpeg': 'mp3',
    'audio/mp4': 'm4a',
    'audio/ogg': 'ogg',
  }
  const ext = mimeToExt[audioBlob.type] || 'webm'
  const filename = `recording.${ext}`

  formData.append('file', audioBlob, filename)

  const response = await apiClient.post<AudioUploadResponse>(
    `/visits/${visitId}/audio`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const progress = Math.round(
            (progressEvent.loaded * 100) / progressEvent.total
          )
          onProgress(progress)
        }
      },
    }
  )

  return response.data
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
 * Trigger transcription for a visit.
 *
 * @param visitId - Visit ID
 * @returns Transcription trigger response
 */
export const triggerTranscription = async (
  visitId: string
): Promise<TranscribeResponse> => {
  const response = await apiClient.post<TranscribeResponse>(
    `/visits/${visitId}/transcribe`
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
