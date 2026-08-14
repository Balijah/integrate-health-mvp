import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { DemoLiveRecorder } from './DemoLiveRecorder'

describe('DemoLiveRecorder', () => {
  it('starts with the real recording call to action and an explicit simulation notice', () => {
    const html = renderToStaticMarkup(
      <DemoLiveRecorder segments={[{ speaker: 'provider', text: 'How are you feeling?' }]} onComplete={() => undefined} />,
    )

    expect(html).toContain('Start Live Recording')
    expect(html).toContain('Ready for Live Transcription')
    expect(html).toContain('no microphone or external transcription service is used')
  })
})
