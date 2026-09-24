import { EmptyState } from '../feedback/EmptyState'

type Segment = {
  label: string
  value: number
  color: string
}

const RADIUS = 60
const STROKE = 22
const CIRCUMFERENCE = 2 * Math.PI * RADIUS

/**
 * Dependency-free SVG donut chart for the monitoring health distribution.
 * Percentages are only rendered when the total is meaningful (>0).
 */
export function HealthDistributionChart({
  healthy,
  degraded,
  unhealthy,
  offline,
  unknown,
}: {
  healthy: number
  degraded: number
  unhealthy: number
  offline: number
  unknown: number
}) {
  const segments: Segment[] = [
    { label: 'Healthy', value: healthy, color: 'var(--color-ok)' },
    { label: 'Degraded', value: degraded, color: 'var(--color-warn)' },
    { label: 'Unhealthy', value: unhealthy, color: 'var(--color-danger)' },
    { label: 'Offline', value: offline, color: 'var(--color-danger-strong)' },
    { label: 'Unknown', value: unknown, color: 'var(--color-neutral)' },
  ]
  const total = segments.reduce((sum, segment) => sum + segment.value, 0)

  if (total === 0) {
    return <EmptyState title="No monitoring targets yet" description="Health distribution will appear once targets report telemetry." />
  }

  let offsetAccumulator = 0

  return (
    <div className="health-chart">
      <svg viewBox="0 0 160 160" role="img" aria-label="Monitoring health distribution" className="health-chart-svg">
        <circle cx="80" cy="80" r={RADIUS} fill="none" stroke="var(--color-surface-alt)" strokeWidth={STROKE} />
        {segments
          .filter((segment) => segment.value > 0)
          .map((segment) => {
            const fraction = segment.value / total
            const dash = fraction * CIRCUMFERENCE
            const circle = (
              <circle
                key={segment.label}
                cx="80"
                cy="80"
                r={RADIUS}
                fill="none"
                stroke={segment.color}
                strokeWidth={STROKE}
                strokeDasharray={`${dash} ${CIRCUMFERENCE - dash}`}
                strokeDashoffset={-offsetAccumulator}
                transform="rotate(-90 80 80)"
              />
            )
            offsetAccumulator += dash
            return circle
          })}
        <text x="80" y="76" textAnchor="middle" className="health-chart-total">
          {total}
        </text>
        <text x="80" y="94" textAnchor="middle" className="health-chart-caption">
          targets
        </text>
      </svg>
      <ul className="health-chart-legend">
        {segments.map((segment) => (
          <li key={segment.label}>
            <span className="legend-swatch" style={{ background: segment.color }} aria-hidden="true" />
            <span className="legend-label">{segment.label}</span>
            <span className="legend-value">
              {segment.value} ({total > 0 ? Math.round((segment.value / total) * 100) : 0}%)
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
