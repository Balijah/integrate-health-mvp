/**
 * Live Recorder component.
 *
 * Main component for live transcription with real-time audio streaming.
 */

import { useLiveTranscription } from '../../hooks/useLiveTranscription'
import { RecorderControls } from './RecorderControls'
import { LiveTranscript } from './LiveTranscript'

interface LiveRecorderProps {
  /** Visit ID for the transcription session */
  visitId: string
  /** Callback when transcription is complete */
  onComplete: (transcript: string) => void
  /** Callback when error occurs */
  onError?: (error: string) => void
}

/**
 * Format seconds to MM:SS display.
 */
const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

export const LiveRecorder = ({
  visitId,
  onComplete,
  onError,
}: LiveRecorderProps) => {
  const {
    isConnected,
    isRecording,
    isPaused,
    status,
    transcript,
    duration,
    error,
    startRecording,
    pauseRecording,
    resumeRecording,
    stopRecording,
  } = useLiveTranscription(visitId, { onError })

  const handleStop = async () => {
    try {
      const fullTranscript = await stopRecording()
      onComplete(fullTranscript)
    } catch (err) {
      onError?.(err instanceof Error ? err.message : 'Failed to stop recording')
    }
  }

  return (
    <div className="space-y-6">
      {/* Connection Status & Duration */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          {/* Connection indicator */}
          <div className="flex items-center space-x-2">
            <div
              className={`w-2.5 h-2.5 rounded-full ${
                isConnected ? 'bg-green-500' :
                status === 'connecting' ? 'bg-yellow-500 animate-pulse' :
                'bg-gray-300'
              }`}
            />
            <span className="text-sm text-gray-600">
              {isConnected ? 'Connected' :
               status === 'connecting' ? 'Connecting...' :
               'Disconnected'}
            </span>
          </div>

          {/* Recording indicator */}
          {isRecording && (
            <div className="flex items-center space-x-2">
              <div
                className={`w-2.5 h-2.5 rounded-full ${
                  isPaused ? 'bg-yellow-500' : 'bg-red-500 animate-pulse'
                }`}
              />
              <span className="text-sm font-medium text-gray-700">
                {isPaused ? 'Paused' : 'Recording'}
              </span>
            </div>
          )}
        </div>

        {/* Duration */}
        {(isRecording || status === 'stopped') && (
          <div className="flex items-center space-x-2">
            <ClockIcon className="h-5 w-5 text-gray-400" />
            <span className="text-2xl font-mono font-bold text-gray-900">
              {formatDuration(duration)}
            </span>
          </div>
        )}
      </div>

      {/* Error Display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <ErrorIcon className="h-5 w-5 text-red-400 flex-shrink-0" />
            <p className="ml-3 text-sm text-red-700">{error}</p>
          </div>
        </div>
      )}

      {/* Recording Visualization */}
      {!isRecording && status !== 'stopped' && (
        <div className="flex items-center justify-center rounded-lg bg-gray-50 p-8">
          <div className="text-center">
            <MicrophoneIcon className="mx-auto h-16 w-16 text-gray-300" />
            <h3 className="mt-4 text-lg font-medium text-gray-900">
              Ready for Live Transcription
            </h3>
            <p className="mt-2 text-sm text-gray-500">
              Start recording to transcribe your patient visit in real-time
            </p>
          </div>
        </div>
      )}

      {/* Live Transcript */}
      {(isRecording || status === 'stopped') && (
        <LiveTranscript segments={transcript} />
      )}

      {/* Controls */}
      <RecorderControls
        isRecording={isRecording}
        isPaused={isPaused}
        onStart={startRecording}
        onPause={pauseRecording}
        onResume={resumeRecording}
        onStop={handleStop}
        disabled={status === 'connecting'}
      />

      {/* Status message */}
      {status === 'stopped' && (
        <div className="text-center">
          <p className="text-sm text-green-600">
            Recording complete. Transcript saved.
          </p>
        </div>
      )}
    </div>
  )
}

// Icon components
const ClockIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z"
      clipRule="evenodd"
    />
  </svg>
)

const ErrorIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
      clipRule="evenodd"
    />
  </svg>
)

const MicrophoneIcon = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 24 24" fill="none" stroke="currentColor">
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.5}
      d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"
    />
    <path
      strokeLinecap="round"
      strokeLinejoin="round"
      strokeWidth={1.5}
      d="M19 10v2a7 7 0 01-14 0v-2M12 19v4M8 23h8"
    />
  </svg>
)
