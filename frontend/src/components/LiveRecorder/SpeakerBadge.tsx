/**
 * Speaker Badge component.
 *
 * Displays a badge indicating who is speaking (provider or patient).
 */

interface SpeakerBadgeProps {
  speaker: 'provider' | 'patient'
}

export const SpeakerBadge = ({ speaker }: SpeakerBadgeProps) => {
  const isProvider = speaker === 'provider'

  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
        isProvider
          ? 'bg-blue-100 text-blue-800'
          : 'bg-green-100 text-green-800'
      }`}
    >
      {isProvider ? 'Provider' : 'Patient'}
    </span>
  )
}
