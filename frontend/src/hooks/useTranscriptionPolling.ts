/**
 * Hook for polling transcription status.
 *
 * Provides automatic polling with configurable intervals and status management.
 */

import { useState, useEffect, useCallback, useRef } from 'react'

import { getTranscriptionStatus, TranscriptionStatusResponse } from '../api/visits'

interface UseTranscriptionPollingOptions {
  /** Visit ID to poll status for */
  visitId: string | null
  /** Polling interval in milliseconds (default: 5000) */
  intervalMs?: number
  /** Whether polling is enabled (default: true when visitId is provided) */
  enabled?: boolean
  /** Callback when transcription completes */
  onComplete?: (transcript: string) => void
  /** Callback when transcription fails */
  onError?: (error: string) => void
}

interface UseTranscriptionPollingReturn {
  /** Current transcription status */
  status: TranscriptionStatusResponse['status'] | null
  /** Transcript text (when completed) */
  transcript: string | null
  /** Error message (when failed) */
  error: string | null
  /** Whether currently polling */
  isPolling: boolean
  /** Manually refresh status */
  refresh: () => Promise<void>
  /** Start polling */
  startPolling: () => void
  /** Stop polling */
  stopPolling: () => void
}

/**
 * Hook for polling transcription status.
 *
 * @param options - Polling configuration options
 * @returns Transcription status and controls
 */
export const useTranscriptionPolling = ({
  visitId,
  intervalMs = 5000,
  enabled = true,
  onComplete,
  onError,
}: UseTranscriptionPollingOptions): UseTranscriptionPollingReturn => {
  const [status, setStatus] = useState<TranscriptionStatusResponse['status'] | null>(null)
  const [transcript, setTranscript] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [isPolling, setIsPolling] = useState(false)

  const intervalRef = useRef<number | null>(null)
  const mountedRef = useRef(true)

  // Fetch status once
  const fetchStatus = useCallback(async () => {
    if (!visitId) return

    try {
      const response = await getTranscriptionStatus(visitId)

      if (!mountedRef.current) return

      setStatus(response.status)

      if (response.status === 'completed' && response.transcript) {
        setTranscript(response.transcript)
        setError(null)
        onComplete?.(response.transcript)
      } else if (response.status === 'failed') {
        setError(response.error_message || 'Transcription failed')
        onError?.(response.error_message || 'Transcription failed')
      }

      return response.status
    } catch (err) {
      if (!mountedRef.current) return
      const errorMessage = err instanceof Error ? err.message : 'Failed to get status'
      setError(errorMessage)
      return null
    }
  }, [visitId, onComplete, onError])

  // Start polling
  const startPolling = useCallback(() => {
    if (intervalRef.current) return
    setIsPolling(true)

    const poll = async () => {
      const currentStatus = await fetchStatus()

      // Stop polling if completed or failed
      if (currentStatus === 'completed' || currentStatus === 'failed') {
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
        setIsPolling(false)
      }
    }

    // Initial fetch
    poll()

    // Start interval
    intervalRef.current = window.setInterval(poll, intervalMs)
  }, [fetchStatus, intervalMs])

  // Stop polling
  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current)
      intervalRef.current = null
    }
    setIsPolling(false)
  }, [])

  // Manual refresh
  const refresh = useCallback(async () => {
    await fetchStatus()
  }, [fetchStatus])

  // Auto-start polling when enabled and status is pending/transcribing
  useEffect(() => {
    if (!enabled || !visitId) {
      stopPolling()
      return
    }

    // Initial fetch to determine if polling is needed
    const init = async () => {
      const currentStatus = await fetchStatus()

      // Only start polling if status is pending or transcribing
      if (currentStatus === 'pending' || currentStatus === 'transcribing') {
        startPolling()
      }
    }

    init()

    return () => {
      stopPolling()
    }
  }, [enabled, visitId, fetchStatus, startPolling, stopPolling])

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true
    return () => {
      mountedRef.current = false
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [])

  return {
    status,
    transcript,
    error,
    isPolling,
    refresh,
    startPolling,
    stopPolling,
  }
}
