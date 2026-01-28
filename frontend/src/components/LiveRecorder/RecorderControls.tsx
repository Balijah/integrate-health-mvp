/**
 * Recorder Controls component.
 *
 * Provides play/pause/stop controls for live recording.
 */

import { Button } from '../common/Button'

interface RecorderControlsProps {
  isRecording: boolean
  isPaused: boolean
  onStart: () => void
  onPause: () => void
  onResume: () => void
  onStop: () => void
  disabled?: boolean
}

export const RecorderControls = ({
  isRecording,
  isPaused,
  onStart,
  onPause,
  onResume,
  onStop,
  disabled = false,
}: RecorderControlsProps) => {
  // Not recording - show start button
  if (!isRecording && !isPaused) {
    return (
      <div className="flex items-center justify-center gap-3">
        <Button
          onClick={onStart}
          disabled={disabled}
          className="gap-2 bg-red-600 hover:bg-red-700"
        >
          <MicrophoneIcon />
          Start Live Recording
        </Button>
      </div>
    )
  }

  // Recording - show pause and stop
  if (isRecording && !isPaused) {
    return (
      <div className="flex items-center justify-center gap-3">
        <Button variant="secondary" onClick={onPause} disabled={disabled}>
          <PauseIcon />
          Pause
        </Button>
        <Button variant="danger" onClick={onStop} disabled={disabled}>
          <StopIcon />
          Stop
        </Button>
      </div>
    )
  }

  // Paused - show resume and stop
  return (
    <div className="flex items-center justify-center gap-3">
      <Button variant="secondary" onClick={onResume} disabled={disabled}>
        <PlayIcon />
        Resume
      </Button>
      <Button variant="danger" onClick={onStop} disabled={disabled}>
        <StopIcon />
        Stop
      </Button>
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
  <svg className="h-5 w-5 mr-1" viewBox="0 0 20 20" fill="currentColor">
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
