/**
 * Live transcription API functions.
 *
 * Provides REST API calls for managing live transcription sessions.
 */

import { apiClient } from './client'

/**
 * Request to start live transcription.
 */
export interface StartLiveTranscriptionRequest {
  sample_rate?: number
  encoding?: string
}

/**
 * Response from starting live transcription.
 */
export interface StartLiveTranscriptionResponse {
  session_id: string
  websocket_url: string
  status: string
}

/**
 * Response for live transcription status.
 */
export interface LiveTranscriptionStatusResponse {
  session_id: string
  status: string
  duration_seconds: number
}

/**
 * Response from stopping live transcription.
 */
export interface StopLiveTranscriptionResponse {
  session_id: string
  status: string
  total_duration_seconds: number
  transcript: string
  word_count: number
}

/**
 * Start a live transcription session for a visit.
 *
 * @param visitId - Visit UUID
 * @param options - Transcription options
 * @returns Session info with WebSocket URL
 */
export const startLiveTranscription = async (
  visitId: string,
  options: StartLiveTranscriptionRequest = {}
): Promise<StartLiveTranscriptionResponse> => {
  const response = await apiClient.post<StartLiveTranscriptionResponse>(
    `/visits/${visitId}/transcription/start-live`,
    {
      sample_rate: options.sample_rate || 16000,
      encoding: options.encoding || 'linear16',
    }
  )
  return response.data
}

/**
 * Pause live transcription session.
 *
 * @param visitId - Visit UUID
 * @returns Updated session status
 */
export const pauseLiveTranscription = async (
  visitId: string
): Promise<LiveTranscriptionStatusResponse> => {
  const response = await apiClient.post<LiveTranscriptionStatusResponse>(
    `/visits/${visitId}/transcription/pause-live`
  )
  return response.data
}

/**
 * Resume live transcription session.
 *
 * @param visitId - Visit UUID
 * @returns Updated session status
 */
export const resumeLiveTranscription = async (
  visitId: string
): Promise<LiveTranscriptionStatusResponse> => {
  const response = await apiClient.post<LiveTranscriptionStatusResponse>(
    `/visits/${visitId}/transcription/resume-live`
  )
  return response.data
}

/**
 * Stop live transcription session.
 *
 * @param visitId - Visit UUID
 * @returns Full transcript and session metadata
 */
export const stopLiveTranscription = async (
  visitId: string
): Promise<StopLiveTranscriptionResponse> => {
  const response = await apiClient.post<StopLiveTranscriptionResponse>(
    `/visits/${visitId}/transcription/stop-live`
  )
  return response.data
}

/**
 * Get live transcription session status.
 *
 * @param visitId - Visit UUID
 * @returns Current session status
 */
export const getLiveTranscriptionStatus = async (
  visitId: string
): Promise<LiveTranscriptionStatusResponse> => {
  const response = await apiClient.get<LiveTranscriptionStatusResponse>(
    `/visits/${visitId}/transcription/live-status`
  )
  return response.data
}

/**
 * Get WebSocket URL for live transcription.
 * Uses the API base URL to construct the WebSocket URL.
 *
 * @param sessionId - Session UUID
 * @returns WebSocket URL
 */
export const getWebSocketUrl = (sessionId: string): string => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:8000'
  const wsProtocol = apiUrl.startsWith('https') ? 'wss' : 'ws'
  // Strip path (e.g. /api/v1) — WebSocket lives at the root, not under /api/v1
  const host = new URL(apiUrl).host
  return `${wsProtocol}://${host}/ws/transcription/${sessionId}`
}
