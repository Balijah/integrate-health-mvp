/**
 * Live transcription hook using WebSocket.
 *
 * Provides real-time audio streaming and transcript receiving functionality.
 */

import { useState, useRef, useCallback, useEffect } from 'react'
import {
  startLiveTranscription,
  getWebSocketUrl,
} from '../api/liveTranscription'

/**
 * Transcript segment from the live transcription.
 */
export interface TranscriptSegment {
  speaker: 'provider' | 'patient'
  text: string
  timestamp: number
  isFinal: boolean
  confidence: number
}

/**
 * Live transcription session status.
 */
export type LiveTranscriptionStatus = 'idle' | 'connecting' | 'active' | 'paused' | 'stopped' | 'error'

/**
 * Return type for useLiveTranscription hook.
 */
export interface UseLiveTranscriptionReturn {
  /** WebSocket connection status */
  isConnected: boolean
  /** Whether recording is active */
  isRecording: boolean
  /** Whether recording is paused */
  isPaused: boolean
  /** Current session status */
  status: LiveTranscriptionStatus
  /** Live transcript segments */
  transcript: TranscriptSegment[]
  /** Recording duration in seconds */
  duration: number
  /** Error message if any */
  error: string | null
  /** Start live recording */
  startRecording: () => Promise<void>
  /** Pause recording */
  pauseRecording: () => void
  /** Resume recording */
  resumeRecording: () => void
  /** Stop recording and get final transcript */
  stopRecording: () => Promise<string>
  /** Reset the hook state */
  reset: () => void
}

/**
 * Options for useLiveTranscription hook.
 */
interface UseLiveTranscriptionOptions {
  /** Sample rate for audio (default: 16000) */
  sampleRate?: number
  /** Callback when transcript is received */
  onTranscript?: (segment: TranscriptSegment) => void
  /** Callback when error occurs */
  onError?: (error: string) => void
}

/**
 * Custom hook for live transcription with WebSocket streaming.
 *
 * @param visitId - Visit UUID for the transcription session
 * @param options - Hook options
 * @returns Live transcription state and controls
 */
export const useLiveTranscription = (
  visitId: string,
  options: UseLiveTranscriptionOptions = {}
): UseLiveTranscriptionReturn => {
  const { sampleRate = 16000, onTranscript, onError } = options

  const [status, setStatus] = useState<LiveTranscriptionStatus>('idle')
  const [transcript, setTranscript] = useState<TranscriptSegment[]>([])
  const transcriptRef = useRef<TranscriptSegment[]>([]) // always-current ref, avoids closure staleness
  const [duration, setDuration] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  // Refs for WebSocket and audio processing
  const wsRef = useRef<WebSocket | null>(null)
  const audioContextRef = useRef<AudioContext | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const durationIntervalRef = useRef<number | null>(null)
  const sessionIdRef = useRef<string | null>(null)
  const statusRef = useRef<LiveTranscriptionStatus>('idle')
  const isConnectedRef = useRef(false)

  // Keep refs in sync with state
  useEffect(() => { statusRef.current = status }, [status])
  useEffect(() => { isConnectedRef.current = isConnected }, [isConnected])
  useEffect(() => { transcriptRef.current = transcript }, [transcript])

  // Convert Float32Array to Int16Array (PCM)
  const floatTo16BitPCM = (float32Array: Float32Array): ArrayBuffer => {
    const buffer = new ArrayBuffer(float32Array.length * 2)
    const view = new DataView(buffer)
    for (let i = 0; i < float32Array.length; i++) {
      const s = Math.max(-1, Math.min(1, float32Array[i]))
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true)
    }
    return buffer
  }

  // Open a backend session + WebSocket and wire its handlers.
  //   reconnect=false → fresh start (new audio graph)
  //   reconnect=true  → recovery after the socket died (e.g. Deepgram dropped during a long
  //                     pause). Keeps the accumulated transcript/duration and reuses the live
  //                     audio graph; the backend appends to the already-saved transcript so
  //                     nothing recorded before the drop is lost.
  const connect = useCallback(async (reconnect: boolean) => {
    // Reuse the mic stream if we still hold a live one (we keep it open across pauses).
    let stream = streamRef.current
    if (!stream || stream.getTracks().every((t) => t.readyState === 'ended')) {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: sampleRate,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
      streamRef.current = stream
    }

    // Start session via REST API
    const response = await startLiveTranscription(visitId, {
      sample_rate: sampleRate,
      encoding: 'linear16',
    })

    sessionIdRef.current = response.session_id

    // Create WebSocket connection
    const ws = new WebSocket(getWebSocketUrl(response.session_id))
    wsRef.current = ws

    ws.onopen = () => {
      console.log(reconnect ? '[recovery] WebSocket reconnected' : 'WebSocket connected')
      setIsConnected(true)
      isConnectedRef.current = true
      setStatus('active')
      statusRef.current = 'active'
      setError(null) // clear any "connection interrupted" notice now that we're live again

      // On reconnect the audio graph from before the drop is still live and will stream to
      // the new socket automatically once status is 'active'; only build it if it's gone.
      if (!reconnect || !processorRef.current || !audioContextRef.current) {
        startAudioProcessing(stream!)
      }

      if (durationIntervalRef.current) clearInterval(durationIntervalRef.current)
      durationIntervalRef.current = window.setInterval(() => {
        setDuration((prev) => prev + 1)
      }, 1000)
    }

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data)
        handleWebSocketMessage(message)
      } catch (e) {
        console.error('Error parsing WebSocket message:', e)
      }
    }

    ws.onerror = (event) => {
      // [PHASE0-DIAG] Log status at the moment of error.
      console.error(`[PHASE0-DIAG] WebSocket error (status=${statusRef.current}):`, event)
      // Don't hard-fail into 'error' while paused — keep the session recoverable via Resume.
      if (statusRef.current !== 'paused') {
        const errorMsg = 'WebSocket connection error'
        setError(errorMsg)
        setStatus('error')
        onError?.(errorMsg)
      }
    }

    ws.onclose = (event) => {
      // [PHASE0-DIAG] Capture close code/reason + status.
      console.log(
        `[PHASE0-DIAG] WebSocket closed (code=${event.code}, reason="${event.reason}", ` +
        `wasClean=${event.wasClean}, status=${statusRef.current})`
      )
      setIsConnected(false)
      isConnectedRef.current = false
      if (statusRef.current === 'active') {
        setStatus('stopped')
      }
    }
  }, [visitId, sampleRate, onError])

  // Start recording and transcription
  const startRecording = useCallback(async () => {
    try {
      setError(null)
      setTranscript([])
      setDuration(0)
      setStatus('connecting')
      await connect(false)
    } catch (err) {
      const errorMsg = err instanceof Error ? err.message : 'Failed to start recording'
      setError(errorMsg)
      setStatus('error')
      onError?.(errorMsg)
    }
  }, [connect, onError])

  // Start audio processing with Web Audio API
  const startAudioProcessing = (stream: MediaStream) => {
    try {
      // Create audio context
      const audioContext = new AudioContext({ sampleRate })
      audioContextRef.current = audioContext

      // Create source from stream
      const source = audioContext.createMediaStreamSource(stream)

      // Create script processor for capturing audio
      // Note: ScriptProcessorNode is deprecated but still widely supported
      // AudioWorklet is the modern replacement but requires more setup
      const processor = audioContext.createScriptProcessor(4096, 1, 1)
      processorRef.current = processor

      processor.onaudioprocess = (e) => {
        // Only send if connected and active
        if (!isConnectedRef.current || statusRef.current !== 'active') {
          return
        }

        const inputData = e.inputBuffer.getChannelData(0)
        const pcmData = floatTo16BitPCM(inputData)

        // Send as base64
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const base64 = arrayBufferToBase64(pcmData)
          wsRef.current.send(JSON.stringify({
            type: 'audio_chunk',
            data: base64,
            timestamp: Date.now(),
          }))
        }
      }

      // Connect the audio graph
      source.connect(processor)
      processor.connect(audioContext.destination)

      console.log('Audio processing started')
    } catch (err) {
      console.error('Error starting audio processing:', err)
      const errorMsg = 'Failed to start audio processing'
      setError(errorMsg)
      onError?.(errorMsg)
    }
  }

  // Convert ArrayBuffer to base64
  const arrayBufferToBase64 = (buffer: ArrayBuffer): string => {
    const bytes = new Uint8Array(buffer)
    let binary = ''
    for (let i = 0; i < bytes.byteLength; i++) {
      binary += String.fromCharCode(bytes[i])
    }
    return btoa(binary)
  }

  // Handle incoming WebSocket messages
  const handleWebSocketMessage = (message: {
    type: string
    text?: string
    speaker?: string
    is_final?: boolean
    timestamp?: number
    confidence?: number
    session_status?: string
    duration_seconds?: number
    transcript?: string
    message?: string
  }) => {
    switch (message.type) {
      case 'transcript':
        if (message.text) {
          const segment: TranscriptSegment = {
            speaker: (message.speaker as 'provider' | 'patient') || 'provider',
            text: message.text,
            timestamp: message.timestamp || Date.now(),
            isFinal: message.is_final || false,
            confidence: message.confidence || 0,
          }

          setTranscript((prev) => {
            // For interim results, update the last non-final segment
            if (!segment.isFinal && prev.length > 0) {
              const lastIdx = prev.length - 1
              if (!prev[lastIdx].isFinal) {
                const updated = [...prev]
                updated[lastIdx] = segment
                return updated
              }
            }
            return [...prev, segment]
          })

          onTranscript?.(segment)
        }
        break

      case 'status':
        if (message.session_status === 'paused') {
          setStatus('paused')
          statusRef.current = 'paused'
        } else if (message.session_status === 'active') {
          setStatus('active')
          statusRef.current = 'active'
        }
        if (message.duration_seconds !== undefined) {
          setDuration(message.duration_seconds)
        }
        break

      case 'complete':
        setStatus('stopped')
        statusRef.current = 'stopped'
        break

      case 'error':
        const errorMsg = message.message || 'Unknown error'
        // [PHASE0-DIAG] Server-side error forwarded to browser; log status to correlate with pause.
        console.error(`[PHASE0-DIAG] Server error (status=${statusRef.current}):`, errorMsg)
        setError(errorMsg)
        onError?.(errorMsg)
        break

      case 'connection_closed':
        // Backend signals the upstream Deepgram stream dropped. Keep the session in a 'paused',
        // recoverable state (NOT 'error', which would hide the Resume button) and tell the user
        // exactly what to do. Resume will transparently reconnect and continue.
        console.warn(
          `[recovery] connection_closed (status=${statusRef.current}): ${message.message || ''}`
        )
        if (statusRef.current === 'active' || statusRef.current === 'paused') {
          setStatus('paused')
          statusRef.current = 'paused'
          setError(
            'Recording connection was interrupted. Click Resume to reconnect and continue — ' +
            'everything captured so far has been saved.'
          )
          if (durationIntervalRef.current) {
            clearInterval(durationIntervalRef.current)
            durationIntervalRef.current = null
          }
        }
        break

      case 'pong':
        // Heartbeat response
        break
    }
  }

  // Pause recording
  const pauseRecording = useCallback(() => {
    // [PHASE0-DIAG] Log every pause attempt + the socket state, so we can see exactly when the
    // browser stopped sending audio relative to any later disconnect.
    console.log(
      `[PHASE0-DIAG] pauseRecording() called (status=${statusRef.current}, ` +
      `wsReadyState=${wsRef.current?.readyState})`
    )
    if (statusRef.current === 'active' && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'pause' }))
      setStatus('paused')
      statusRef.current = 'paused'

      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current)
        durationIntervalRef.current = null
      }
    } else {
      console.warn('[PHASE0-DIAG] pauseRecording() no-op — not active or socket not open')
    }
  }, [])

  // Resume recording
  const resumeRecording = useCallback(async () => {
    console.log(
      `[PHASE0-DIAG] resumeRecording() called (status=${statusRef.current}, ` +
      `wsReadyState=${wsRef.current?.readyState})`
    )

    // Healthy socket → resume the SAME session (transcript stays in one continuous stream).
    if (statusRef.current === 'paused' && wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'resume' }))
      setStatus('active')
      statusRef.current = 'active'

      if (durationIntervalRef.current) clearInterval(durationIntervalRef.current)
      durationIntervalRef.current = window.setInterval(() => {
        setDuration((prev) => prev + 1)
      }, 1000)
      return
    }

    // Socket is gone (the connection dropped during the pause). Recover by opening a NEW
    // session and continuing — the backend appends to the transcript already saved, so the
    // pre-pause portion is preserved. This replaces the old silent no-op.
    if (statusRef.current === 'paused' || statusRef.current === 'error') {
      console.warn('[recovery] Resume on a dead socket — opening a new session to continue')
      setStatus('connecting')
      statusRef.current = 'connecting'
      try {
        await connect(true)
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Failed to reconnect'
        setError(`${msg}. Please click Stop to save what was captured, then start a new recording.`)
        setStatus('paused') // stay recoverable so the user can retry Resume or Stop
        statusRef.current = 'paused'
        onError?.(msg)
      }
    }
  }, [connect, onError])

  // Stop recording and get final transcript
  const stopRecording = useCallback(async (): Promise<string> => {
    // Stop audio processing
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }

    if (audioContextRef.current) {
      await audioContextRef.current.close()
      audioContextRef.current = null
    }

    // Stop timer
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current)
      durationIntervalRef.current = null
    }

    // Stop audio stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }

    // Send stop command via WebSocket and wait for complete response
    // The WebSocket "stop" handler on backend will return the full transcript
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'stop' }))

      // Wait a moment for the complete message to arrive
      await new Promise(resolve => setTimeout(resolve, 500))
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    setStatus('stopped')
    statusRef.current = 'stopped'
    setIsConnected(false)
    isConnectedRef.current = false
    sessionIdRef.current = null

    // Read from ref — always current, no closure staleness
    const current = transcriptRef.current
    const finalSegments = current.filter((seg) => seg.isFinal)
    const segmentsToJoin = finalSegments.length > 0 ? finalSegments : current
    const localTranscript = segmentsToJoin.map((seg) => seg.text).join(' ')

    return localTranscript
  }, [])

  // Reset hook state
  const reset = useCallback(() => {
    // Stop any active recording
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }

    if (audioContextRef.current) {
      audioContextRef.current.close()
      audioContextRef.current = null
    }

    // Stop timer
    if (durationIntervalRef.current) {
      clearInterval(durationIntervalRef.current)
      durationIntervalRef.current = null
    }

    // Stop stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop())
      streamRef.current = null
    }

    // Close WebSocket
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }

    // Reset state
    setStatus('idle')
    statusRef.current = 'idle'
    setTranscript([])
    setDuration(0)
    setError(null)
    setIsConnected(false)
    isConnectedRef.current = false
    sessionIdRef.current = null
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current)
      }
      if (processorRef.current) {
        processorRef.current.disconnect()
      }
      if (audioContextRef.current) {
        audioContextRef.current.close()
      }
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop())
      }
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  return {
    isConnected,
    isRecording: status === 'active' || status === 'paused',
    isPaused: status === 'paused',
    status,
    transcript,
    duration,
    error,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
    reset,
  }
}
