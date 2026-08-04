import { TranscriptSegment } from '../api/visits'

interface StoredTranscriptProps {
  segments?: TranscriptSegment[] | null
  transcript?: string | null
}

export const StoredTranscript = ({ segments, transcript }: StoredTranscriptProps) => {
  if (segments?.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-2xl p-4 max-h-80 overflow-y-auto space-y-3">
        {segments.map((segment, index) => {
          const provider = segment.speaker.toLowerCase() === 'provider'
          return (
            <div key={`${segment.speaker}-${index}`} className="flex gap-3">
              <span className={`shrink-0 text-xs font-medium px-2 py-0.5 rounded-full h-fit mt-0.5 ${
                provider ? 'bg-[#4ac6d6]/20 text-[#2a8fa0]' : 'bg-gray-100 text-gray-600'
              }`}>
                {provider ? 'Provider' : 'Patient'}
              </span>
              <p className="text-sm text-gray-700 leading-relaxed">{segment.text}</p>
            </div>
          )
        })}
      </div>
    )
  }

  if (transcript) {
    return (
      <div className="bg-white border border-gray-200 rounded-2xl p-4 max-h-80 overflow-y-auto">
        <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">{transcript}</p>
      </div>
    )
  }

  return <p className="text-sm text-gray-400 italic text-center py-2">Loading transcript...</p>
}
