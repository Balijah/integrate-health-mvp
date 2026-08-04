import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { StoredTranscript } from './StoredTranscript'

describe('StoredTranscript', () => {
  it('renders labelled provider and patient segments', () => {
    const html = renderToStaticMarkup(
      <StoredTranscript segments={[
        { speaker: 'provider', text: 'How are you feeling?' },
        { speaker: 'patient', text: 'I am tired.' },
      ]} />,
    )
    expect(html).toContain('Provider')
    expect(html).toContain('Patient')
    expect(html).toContain('How are you feeling?')
    expect(html).toContain('I am tired.')
  })

  it('falls back to the plain transcript', () => {
    const html = renderToStaticMarkup(<StoredTranscript transcript="Provider: Hello" />)
    expect(html).toContain('Provider: Hello')
  })
})
