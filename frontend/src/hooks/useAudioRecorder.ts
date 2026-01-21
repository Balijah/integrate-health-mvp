/**
 * Audio recorder hook using MediaRecorder API.
 *
 * Provides audio recording functionality with state management.
 */

import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * Recording state types.
 */
export type RecordingState = 'idle' | 'recording' | 'paused' | 'stopped'

/**
 * Audio recorder hook return type.
 */
export interface UseAudioRecorderReturn {
  /** Current recording state */
  state: RecordingState
  /** Recorded audio blob */
  audioBlob: Blob | null
  /** Audio URL for preview playback */
  audioUrl: string | null
  /** Recording duration in seconds */
  duration: number
  /** Error message if any */
  error: string | null
  /** Start recording */
  startRecording: () => Promise<void>
  /** Stop recording */
  stopRecording: () => void
  /** Pause recording */
  pauseRecording: () => void
  /** Resume recording */
  resumeRecording: () => void
  /** Reset recorder to idle state */
  resetRecording: () => void
}

/**
 * Audio recorder hook options.
 */
interface UseAudioRecorderOptions {
  /** Maximum recording duration in seconds (default: 3600 = 1 hour) */
  maxDurationSeconds?: number
  /** Preferred MIME type (default: auto-detect) */
  mimeType?: string
}

/**
 * Get supported MIME type for audio recording.
 */
const getSupportedMimeType = (): string => {
  const types = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/wav',
  ]

  for (const type of types) {
    if (MediaRecorder.isTypeSupported(type)) {
      return type
    }
  }

  return 'audio/webm'
}

/**
 * Custom hook for audio recording.
 *
 * @param options - Recording options
 * @returns Audio recorder state and controls
 */
export const useAudioRecorder = (
  options: UseAudioRecorderOptions = {}
): UseAudioRecorderReturn => {
  const { maxDurationSeconds = 3600 } = options

  const [state, setState] = useState<RecordingState>('idle')
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [audioUrl, setAudioUrl] = useState<string | null>(null)
  const [duration, setDuration] = useState(0)
  const [error, setError] = useState<string | null>(null)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const chunksRef = useRef<Blob[]>([])
  const streamRef = useRef<MediaStream | null>(null)
  const timerRef = useRef<number | null>(null)
  const startTimeRef = useRef<number>(0)
  const pausedDurationRef = useRef<number>(0)

  // Cleanup function
  const cleanup = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }
    if (audioUrl) {
      URL.revokeObjectURL(audioUrl)
    }
  }, [audioUrl])

  // Cleanup on unmount
  useEffect(() => {
    return cleanup
  }, [cleanup])

  // Start timer for duration tracking
  const startTimer = useCallback(() => {
    startTimeRef.current = Date.now() - pausedDurationRef.current * 1000
    timerRef.current = window.setInterval(() => {
      const elapsed = Math.floor((Date.now() - startTimeRef.current) / 1000)
      setDuration(elapsed)

      // Check max duration
      if (elapsed >= maxDurationSeconds) {
        mediaRecorderRef.current?.stop()
      }
    }, 1000)
  }, [maxDurationSeconds])

  // Stop timer
  const stopTimer = useCallback(() => {
    if (timerRef.current) {
      clearInterval(timerRef.current)
      timerRef.current = null
    }
  }, [])

  // Start recording
  const startRecording = useCallback(async () => {
    try {
      setError(null)
      chunksRef.current = []

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      streamRef.current = stream

      // Create MediaRecorder
      const mimeType = options.mimeType || getSupportedMimeType()
      const mediaRecorder = new MediaRecorder(stream, { mimeType })
      mediaRecorderRef.current = mediaRecorder

      // Handle data available
      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data)
        }
      }

      // Handle stop
      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: mimeType })
        setAudioBlob(blob)
        setAudioUrl(URL.createObjectURL(blob))
        setState('stopped')
        stopTimer()

        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop())
      }

      // Handle error
      mediaRecorder.onerror = () => {
        setError('Recording failed')
        setState('idle')
        stopTimer()
      }

      // Start recording
      mediaRecorder.start(1000) // Collect data every second
      setState('recording')
      pausedDurationRef.current = 0
      startTimer()
    } catch (err) {
      if (err instanceof DOMException) {
        if (err.name === 'NotAllowedError') {
          setError('Microphone access denied. Please allow microphone access.')
        } else if (err.name === 'NotFoundError') {
          setError('No microphone found. Please connect a microphone.')
        } else {
          setError(`Recording error: ${err.message}`)
        }
      } else {
        setError('Failed to start recording')
      }
      setState('idle')
    }
  }, [options.mimeType, startTimer, stopTimer])

  // Stop recording
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && state === 'recording') {
      mediaRecorderRef.current.stop()
    } else if (state === 'paused') {
      // If paused, we need to resume briefly then stop
      mediaRecorderRef.current?.resume()
      setTimeout(() => {
        mediaRecorderRef.current?.stop()
      }, 100)
    }
  }, [state])

  // Pause recording
  const pauseRecording = useCallback(() => {
    if (mediaRecorderRef.current && state === 'recording') {
      mediaRecorderRef.current.pause()
      setState('paused')
      pausedDurationRef.current = duration
      stopTimer()
    }
  }, [state, duration, stopTimer])

  // Resume recording
  const resumeRecording = useCallback(() => {
    if (mediaRecorderRef.current && state === 'paused') {
      mediaRecorderRef.current.resume()
      setState('recording')
      startTimer()
    }
  }, [state, startTimer])

  // Reset recorder
  const resetRecording = useCallback(() => {
    cleanup()
    setAudioBlob(null)
    setAudioUrl(null)
    setDuration(0)
    setError(null)
    setState('idle')
    chunksRef.current = []
    pausedDurationRef.current = 0
  }, [cleanup])

  return {
    state,
    audioBlob,
    audioUrl,
    duration,
    error,
    startRecording,
    stopRecording,
    pauseRecording,
    resumeRecording,
    resetRecording,
  }
}
