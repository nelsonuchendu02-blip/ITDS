import type { ReactNode } from 'react'
import type { BadgeTone } from '../status/StatusBadge'

export function KpiCard({
  label,
  value,
  tone = 'neutral',
  hint,
  loading,
}: {
  label: string
  value: ReactNode
  tone?: BadgeTone
  hint?: string
  loading?: boolean
}) {
  return (
    <article className={`kpi-card kpi-${tone}`} aria-busy={loading}>
      <p className="kpi-label">{label}</p>
      <p className="kpi-value">{loading ? <span className="skeleton skeleton-kpi" /> : value}</p>
      {hint && <p className="kpi-hint">{hint}</p>}
    </article>
  )
}
