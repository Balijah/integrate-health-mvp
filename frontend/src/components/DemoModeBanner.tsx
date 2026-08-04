import { DEMO_MODE } from '../config/demo'

export const DemoModeBanner = ({ enabled = DEMO_MODE }: { enabled?: boolean }) => {
  if (!enabled) return null

  return (
    <div
      role="status"
      className="rounded-full border border-amber-300 bg-amber-50 px-4 py-1.5 text-xs font-medium text-amber-800"
    >
      Synthetic demo data · external services disabled
    </div>
  )
}
