/**
 * Audio Recorder component.
 *
 * Provides UI for recording, previewing, and uploading audio.
 */

import { useAudioRecorder, RecordingState } from '../../hooks/useAudioRecorder'
import { Button } from '../common/Button'

interface AudioRecorderProps {
  /** Callback when recording is complete and ready to upload */
  onRecordingComplete: (blob: Blob) => void
  /** Maximum recording duration in seconds */
  maxDurationSeconds?: number
  /** Whether upload is in progress */
  isUploading?: boolean
  /** Disable the recorder */
  disabled?: boolean
}

/**
 * Format seconds to MM:SS display.
 */
const formatDuration = (seconds: number): string => {
  const mins = Math.floor(seconds / 60)
  const secs = seconds % 60
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
}

/**
 * Format file size for display.
 */
const formatFileSize = (bytes: number): string => {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

/**
 * Get recording state color.
 */
const getStateColor = (state: RecordingState): string => {
  switch (state) {
    case 'recording':
      return 'text-red-500'
    case 'paused':
      return 'text-yellow-500'
    case 'stopped':
      return 'text-green-500'
    default:
      return 'text-gray-500'
  }
}

export const AudioRecorder = ({
  onRecordingComplete,
  maxDurationSeconds = 3600,
  isUploading = false,
  disabled = false,
}: AudioRecorderProps) => {
  const {
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
  } = useAudioRecorder({ maxDurationSeconds })

  const handleUpload = () => {
    if (audioBlob) {
      onRecordingComplete(audioBlob)
    }
  }

  return (
    <div className="space-y-4">
      {/* Error message */}
      {error && (
        <div className="rounded-md bg-red-50 p-3">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      )}

      {/* Recording visualization */}
      <div className="flex items-center justify-center rounded-lg bg-gray-50 p-6">
        <div className="text-center">
          {/* Recording indicator */}
          <div className="mb-4 flex items-center justify-center">
            <div
              className={`h-4 w-4 rounded-full ${
                state === 'recording'
                  ? 'animate-pulse bg-red-500'
                  : state === 'paused'
                  ? 'bg-yellow-500'
                  : state === 'stopped'
                  ? 'bg-green-500'
                  : 'bg-gray-300'
              }`}
            />
            <span className={`ml-2 text-sm font-medium ${getStateColor(state)}`}>
              {state === 'idle' && 'Ready to record'}
              {state === 'recording' && 'Recording...'}
              {state === 'paused' && 'Paused'}
              {state === 'stopped' && 'Recording complete'}
            </span>
          </div>

          {/* Timer */}
          <div className="text-4xl font-mono font-bold text-gray-900">
            {formatDuration(duration)}
          </div>

          {/* Max duration warning */}
          {state === 'recording' && duration >= maxDurationSeconds - 60 && (
            <p className="mt-2 text-sm text-yellow-600">
              {formatDuration(maxDurationSeconds - duration)} remaining
            </p>
          )}
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-center gap-3">
        {state === 'idle' && (
          <Button
            onClick={startRecording}
            disabled={disabled}
            className="gap-2"
          >
            <MicrophoneIcon />
            Start Recording
          </Button>
        )}

        {state === 'recording' && (
          <>
            <Button variant="secondary" onClick={pauseRecording}>
              <PauseIcon />
            </Button>
            <Button variant="danger" onClick={stopRecording}>
              <StopIcon />
              Stop
            </Button>
          </>
        )}

        {state === 'paused' && (
          <>
            <Button variant="secondary" onClick={resumeRecording}>
              <PlayIcon />
              Resume
            </Button>
            <Button variant="danger" onClick={stopRecording}>
              <StopIcon />
              Stop
            </Button>
          </>
        )}

        {state === 'stopped' && (
          <>
            <Button variant="secondary" onClick={resetRecording}>
              <ResetIcon />
              Re-record
            </Button>
            <Button
              onClick={handleUpload}
              isLoading={isUploading}
              disabled={disabled}
            >
              <UploadIcon />
              Upload Recording
            </Button>
          </>
        )}
      </div>

      {/* Audio preview */}
      {audioUrl && state === 'stopped' && (
        <div className="rounded-lg border border-gray-200 p-4">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-medium text-gray-700">Preview</span>
            {audioBlob && (
              <span className="text-sm text-gray-500">
                {formatFileSize(audioBlob.size)}
              </span>
            )}
          </div>
          <audio src={audioUrl} controls className="w-full" />
        </div>
      )}
    </div>
  )
}

// Icon components
const MicrophoneIcon = () => (
  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M7 4a3 3 0 016 0v4a3 3 0 11-6 0V4zm4 10.93A7.001 7.001 0 0017 8a1 1 0 10-2 0A5 5 0 015 8a1 1 0 00-2 0 7.001 7.001 0 006 6.93V17H6a1 1 0 100 2h8a1 1 0 100-2h-3v-2.07z"
      clipRule="evenodd"
    />
  </svg>
)

const StopIcon = () => (
  <svg className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zM8 7a1 1 0 00-1 1v4a1 1 0 001 1h4a1 1 0 001-1V8a1 1 0 00-1-1H8z"
      clipRule="evenodd"
    />
  </svg>
)

const PauseIcon = () => (
  <svg className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z"
      clipRule="evenodd"
    />
  </svg>
)

const PlayIcon = () => (
  <svg className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"
      clipRule="evenodd"
    />
  </svg>
)

const ResetIcon = () => (
  <svg className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M4 2a1 1 0 011 1v2.101a7.002 7.002 0 0111.601 2.566 1 1 0 11-1.885.666A5.002 5.002 0 005.999 7H9a1 1 0 010 2H4a1 1 0 01-1-1V3a1 1 0 011-1zm.008 9.057a1 1 0 011.276.61A5.002 5.002 0 0014.001 13H11a1 1 0 110-2h5a1 1 0 011 1v5a1 1 0 11-2 0v-2.101a7.002 7.002 0 01-11.601-2.566 1 1 0 01.61-1.276z"
      clipRule="evenodd"
    />
  </svg>
)

const UploadIcon = () => (
  <svg className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
    <path
      fillRule="evenodd"
      d="M3 17a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zM6.293 6.707a1 1 0 010-1.414l3-3a1 1 0 011.414 0l3 3a1 1 0 01-1.414 1.414L11 5.414V13a1 1 0 11-2 0V5.414L7.707 6.707a1 1 0 01-1.414 0z"
      clipRule="evenodd"
    />
  </svg>
)
