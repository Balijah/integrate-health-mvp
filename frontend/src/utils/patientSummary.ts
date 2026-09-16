import type { SOAPContent } from '../api/notes'

function stringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
}

/** Convert the structured AI response into editable, patient-friendly plain text. */
export function patientSummaryToText(summary: SOAPContent['patient_summary']): string {
  if (!summary) return ''

  const lines: string[] = []
  if (summary.visit_summary?.trim()) {
    lines.push(summary.visit_summary.trim(), '')
  }

  if (Array.isArray(summary.plan_sections)) {
    summary.plan_sections.forEach(section => {
      const items = stringArray(section?.items)
      const heading = section?.heading?.trim()
      if (!heading && items.length === 0) return
      if (heading) lines.push(`${heading}:`)
      items.forEach(item => lines.push(`- ${item}`))
      lines.push('')
    })
  }

  const watchFor = stringArray(summary.watch_for)
  if (watchFor.length > 0) {
    lines.push('Watch For:')
    watchFor.forEach(item => lines.push(`- ${item}`))
    lines.push('')
  }

  const followUp = stringArray(summary.follow_up)
  if (followUp.length > 0) {
    lines.push('Follow-Up:')
    followUp.forEach(item => lines.push(`- ${item}`))
    lines.push('')
  }

  return lines.join('\n').trim()
}
