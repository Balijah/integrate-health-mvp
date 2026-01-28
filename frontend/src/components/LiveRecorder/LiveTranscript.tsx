/**
 * Live Transcript component.
 *
 * Displays the real-time transcript with speaker labels and auto-scrolling.
 */

import { useEffect, useRef } from 'react'
import { SpeakerBadge } from './SpeakerBadge'
import { TranscriptSegment } from '../../hooks/useLiveTranscription'

interface LiveTranscriptProps {
  segments: TranscriptSegment[]
}

export const LiveTranscript = ({ segments }: LiveTranscriptProps) => {
  const containerRef = useRef<HTMLDivElement>(null)

  // Auto-scroll to bottom on new segments
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [segments])

  return (
    <div
      ref={containerRef}
      className="bg-white border border-gray-200 rounded-lg p-4 h-96 overflow-y-auto"
    >
      <div className="space-y-3">
        {segments.map((segment, index) => (
          <div
            key={`${segment.timestamp}-${index}`}
            className={`flex items-start space-x-3 ${
              !segment.isFinal ? 'opacity-60' : ''
            }`}
          >
            <SpeakerBadge speaker={segment.speaker} />

            <div className="flex-1 min-w-0">
              <p className="text-gray-800 text-sm leading-relaxed">
                {segment.text}
              </p>

              <div className="flex items-center gap-2 mt-1">
                {!segment.isFinal && (
                  <span className="text-xs text-gray-400 italic">
                    typing...
                  </span>
                )}
                {segment.confidence > 0 && segment.isFinal && (
                  <span className="text-xs text-gray-400">
                    {Math.round(segment.confidence * 100)}% confident
                  </span>
                )}
              </div>
            </div>
          </div>
        ))}

        {segments.length === 0 && (
          <div className="text-center py-12">
            <MicrophoneIcon className="mx-auto h-12 w-12 text-gray-300" />
            <p className="mt-4 text-gray-400">
              Transcript will appear here as you speak...
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// Microphone icon for empty state
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
