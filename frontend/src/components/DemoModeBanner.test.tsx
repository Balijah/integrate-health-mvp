import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { DemoModeBanner } from './DemoModeBanner'

describe('DemoModeBanner', () => {
  it('identifies synthetic data and disabled integrations', () => {
    const html = renderToStaticMarkup(<DemoModeBanner enabled />)
    expect(html).toContain('Synthetic demo data')
    expect(html).toContain('external services disabled')
  })

  it('renders nothing outside demo mode', () => {
    expect(renderToStaticMarkup(<DemoModeBanner enabled={false} />)).toBe('')
  })
})
