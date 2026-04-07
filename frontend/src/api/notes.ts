/**
 * Note API functions.
 *
 * Handles SOAP note generation, retrieval, and export.
 */

import { apiClient } from './client'

/**
 * SOAP note content structure.
 */
export interface SOAPContent {
  subjective: {
    chief_complaint: string
    history_of_present_illness: string
    review_of_systems: string
    past_medical_history: string
    medications: string[]
    supplements: string[]
    allergies: string[]
    social_history: string
    family_history: string
  }
  objective: {
    vitals: {
      blood_pressure: string
      heart_rate: string
      temperature: string
      weight: string
    }
    physical_exam: string
    lab_results: string
  }
  assessment: {
    diagnoses: string[]
    clinical_reasoning: string
  }
  plan: {
    treatment_plan: string
    medications_prescribed: string[]
    supplements_recommended: string[]
    lifestyle_recommendations: string
    lab_orders: string[]
    follow_up: string
    patient_education: string
  }
  metadata: {
    generated_at: string
    model_version: string
    confidence_score: number | null
  }
}

/**
 * Note response data.
 */
export interface NoteResponse {
  id: string
  visit_id: string
  content: SOAPContent
  note_type: string
  status: 'draft' | 'reviewed' | 'finalized'
  synced_sections: Record<string, boolean>
  all_synced: boolean
  created_at: string
  updated_at: string
}

/**
 * Sync section response.
 */
export interface SyncSectionResponse {
  synced_sections: Record<string, boolean>
  all_synced: boolean
}

/**
 * Generate note request.
 */
export interface GenerateNoteRequest {
  additional_context?: string
}

/**
 * Generate note response.
 */
export interface GenerateNoteResponse {
  note_id: string
  visit_id: string
  status: string
  message: string
}

/**
 * Note update request.
 */
export interface NoteUpdateRequest {
  content?: SOAPContent
  status?: 'draft' | 'reviewed' | 'finalized'
}

/**
 * Note export request.
 */
export interface NoteExportRequest {
  format: 'markdown' | 'text' | 'json'
}

/**
 * Note export response.
 */
export interface NoteExportResponse {
  visit_id: string
  note_id: string
  format: string
  content: string
}

/**
 * Generate a SOAP note for a visit.
 *
 * @param visitId - Visit ID
 * @param data - Generation request data
 * @returns Generation response
 */
export const generateNote = async (
  visitId: string,
  data?: GenerateNoteRequest
): Promise<GenerateNoteResponse> => {
  const response = await apiClient.post<GenerateNoteResponse>(
    `/visits/${visitId}/notes/generate`,
    data || {}
  )
  return response.data
}

/**
 * Get the note for a visit.
 *
 * @param visitId - Visit ID
 * @returns Note data or null
 */
export const getNote = async (visitId: string): Promise<NoteResponse | null> => {
  const response = await apiClient.get<NoteResponse | null>(
    `/visits/${visitId}/notes`
  )
  return response.data
}

/**
 * Update a note.
 *
 * @param visitId - Visit ID
 * @param noteId - Note ID
 * @param data - Update data
 * @returns Updated note
 */
export const updateNote = async (
  visitId: string,
  noteId: string,
  data: NoteUpdateRequest
): Promise<NoteResponse> => {
  const response = await apiClient.put<NoteResponse>(
    `/visits/${visitId}/notes/${noteId}`,
    data
  )
  return response.data
}

/**
 * Delete a note.
 *
 * @param visitId - Visit ID
 * @param noteId - Note ID
 */
export const deleteNote = async (
  visitId: string,
  noteId: string
): Promise<void> => {
  await apiClient.delete(`/visits/${visitId}/notes/${noteId}`)
}

/**
 * Mark a SOAP section as synced (copied to EHR).
 *
 * @param visitId - Visit ID
 * @param noteId - Note ID
 * @param section - SOAP section name
 * @returns Sync status response
 */
export const syncSection = async (
  visitId: string,
  noteId: string,
  section: string
): Promise<SyncSectionResponse> => {
  const response = await apiClient.post<SyncSectionResponse>(
    `/visits/${visitId}/notes/${noteId}/sync-section`,
    { section }
  )
  return response.data
}

/**
 * Export a note in the specified format.
 *
 * @param visitId - Visit ID
 * @param noteId - Note ID
 * @param format - Export format
 * @returns Export response with content
 */
export const exportNote = async (
  visitId: string,
  noteId: string,
  format: 'markdown' | 'text' | 'json' = 'markdown'
): Promise<NoteExportResponse> => {
  const response = await apiClient.post<NoteExportResponse>(
    `/visits/${visitId}/notes/${noteId}/export`,
    { format }
  )
  return response.data
}
