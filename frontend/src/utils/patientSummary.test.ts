import { describe, expect, it } from 'vitest'

import { patientSummaryToText } from './patientSummary'

describe('patientSummaryToText', () => {
  it('formats all supported patient-summary sections', () => {
    expect(patientSummaryToText({
      visit_summary: 'We reviewed your fatigue and sleep today.',
      plan_sections: [
        { heading: 'Medications', items: ['Take levothyroxine with water.', 'Wait before coffee.'] },
      ],
      watch_for: ['Chest pain'],
      follow_up: ['Return in six weeks'],
    })).toBe([
      'We reviewed your fatigue and sleep today.',
      '',
      'Medications:',
      '- Take levothyroxine with water.',
      '- Wait before coffee.',
      '',
      'Watch For:',
      '- Chest pain',
      '',
      'Follow-Up:',
      '- Return in six weeks',
    ].join('\n'))
  })

  it('omits empty optional sections and malformed array values', () => {
    expect(patientSummaryToText({
      visit_summary: '  Keep up the new routine.  ',
      plan_sections: [
        { heading: 'Lifestyle', items: ['', 'Walk after lunch'] },
        { heading: '', items: [] },
      ],
      watch_for: [],
    })).toBe('Keep up the new routine.\n\nLifestyle:\n- Walk after lunch')
  })

  it('returns an empty string when no summary exists', () => {
    expect(patientSummaryToText(undefined)).toBe('')
  })
})
