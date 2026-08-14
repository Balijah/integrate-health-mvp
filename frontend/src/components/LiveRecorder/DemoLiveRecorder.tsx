/**
 * Safe live-recording simulation for the synthetic demo environment.
 *
 * This component only replays checked-in transcript segments in memory. It
 * deliberately has no visit ID, microphone access, WebSocket, or API client.
 */

import { useCallback, useEffect, useMemo, useState } from 'react'

import type { TranscriptSegment as StoredTranscriptSegment } from '../../api/visits'
import type { TranscriptSegment as LiveTranscriptSegment } from '../../hooks/useLiveTranscription'
import { LiveTranscript } from './LiveTranscript'
import { RecorderControls } from './RecorderControls'

interface DemoLiveRecorderProps {
  segments: StoredTranscriptSegment[]
  onComplete: () => void
}

const SEGMENT_INTERVAL_MS = 450

const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export const DemoLiveRecorder = ({ segments, onComplete }: DemoLiveRecorderProps) => {
  const [isRecording, setIsRecording] = useState(false)
  const [isPaused, setIsPaused] = useState(false)
  const [visibleCount, setVisibleCount] = useState(0)
  const [duration, setDuration] = useState(0)

  const liveSegments = useMemo<LiveTranscriptSegment[]>(() => (
    segments.slice(0, visibleCount).map((segment, index) => ({
      speaker: segment.speaker.toLowerCase() === 'provider' ? 'provider' : 'patient',
      text: segment.text,
      timestamp: segment.start ?? index,
      isFinal: true,
      confidence: segment.confidence ?? 1,
    }))
  ), [segments, visibleCount])

  const complete = useCallback(() => {
    setVisibleCount(segments.length)
    setIsRecording(false)
    setIsPaused(false)
    onComplete()
  }, [onComplete, segments.length])

  useEffect(() => {
    if (!isRecording || isPaused) return
    if (visibleCount >= segments.length) {
      const completionTimer = window.setTimeout(complete, SEGMENT_INTERVAL_MS)
      return () => window.clearTimeout(completionTimer)
    }

    const segmentTimer = window.setTimeout(
      () => setVisibleCount(count => Math.min(count + 1, segments.length)),
      SEGMENT_INTERVAL_MS,
    )
    return () => window.clearTimeout(segmentTimer)
  }, [complete, isPaused, isRecording, segments.length, visibleCount])

  useEffect(() => {
    if (!isRecording || isPaused) return
    const durationTimer = window.setInterval(() => setDuration(value => value + 1), 1000)
    return () => window.clearInterval(durationTimer)
  }, [isPaused, isRecording])

  const start = () => {
    setVisibleCount(0)
    setDuration(0)
    setIsPaused(false)
    setIsRecording(true)
  }

  return (
    <div className="space-y-6" data-testid="demo-live-recorder">
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2">
            <div className={`h-2.5 w-2.5 rounded-full ${isRecording ? 'bg-green-500' : 'bg-gray-300'}`} />
            <span className="text-sm text-gray-600">{isRecording ? 'Connected' : 'Disconnected'}</span>
          </div>
          {isRecording && (
            <div className="flex items-center space-x-2">
              <div className={`h-2.5 w-2.5 rounded-full ${isPaused ? 'bg-yellow-500' : 'animate-pulse bg-red-500'}`} />
              <span className="text-sm font-medium text-gray-700">{isPaused ? 'Paused' : 'Recording'}</span>
            </div>
          )}
        </div>
        {isRecording && (
          <span className="font-mono text-2xl font-bold text-gray-900">{formatDuration(duration)}</span>
        )}
      </div>

      {!isRecording ? (
        <div className="flex items-center justify-center rounded-lg bg-gray-50 p-8">
          <div className="text-center">
            <MicrophoneIcon className="mx-auto h-16 w-16 text-gray-300" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">Ready for Live Transcription</h3>
            <p className="mt-2 text-sm text-gray-500">Start recording to transcribe your patient visit in real-time</p>
          </div>
        </div>
      ) : (
        <LiveTranscript segments={liveSegments} />
      )}

      <RecorderControls
        isRecording={isRecording}
        isPaused={isPaused}
        onStart={start}
        onPause={() => setIsPaused(true)}
        onResume={() => setIsPaused(false)}
        onStop={complete}
      />

      <p className="text-center text-xs text-amber-700">
        Synthetic recording simulation — no microphone or external transcription service is used.
      </p>
    </div>
  )
}

const MicrophoneIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z" />
    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8" />
  </svg>
)
