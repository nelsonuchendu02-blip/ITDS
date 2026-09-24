import type { ReactNode } from 'react'

export type BadgeTone = 'neutral' | 'ok' | 'warn' | 'danger' | 'info'

const TONE_BY_VALUE: Record<string, BadgeTone> = {
  // Device / general lifecycle
  active: 'ok',
  inactive: 'neutral',
  retired: 'neutral',
  // Health
  healthy: 'ok',
  degraded: 'warn',
  unhealthy: 'danger',
  offline: 'danger',
  unknown: 'neutral',
  // Agent
  pending: 'warn',
  revoked: 'danger',
  // Incident / severity / priority
  low: 'ok',
  medium: 'warn',
  high: 'danger',
  urgent: 'danger',
  critical: 'danger',
  open: 'warn',
  in_progress: 'info',
  resolved: 'ok',
  closed: 'neutral',
  acknowledged: 'info',
  // Discovery / diagnostics / remediation status families
  running: 'info',
  completed: 'ok',
  failed: 'danger',
  cancelled: 'neutral',
  pass: 'ok',
  warn: 'warn',
  fail: 'danger',
  discovered: 'ok',
  not_reachable: 'warn',
  matched: 'ok',
  unmatched: 'neutral',
  conflict: 'warn',
  draft: 'neutral',
  pending_approval: 'warn',
  approved: 'ok',
  rejected: 'danger',
  queued: 'info',
  executing: 'info',
  succeeded: 'ok',
  verification_required: 'warn',
  verified: 'ok',
  reviewed: 'info',
  accepted: 'ok',
  implemented: 'ok',
  passed: 'ok',
  inconclusive: 'warn',
}

/**
 * Renders a status value with both color and text so information is never
 * color-only. Falls back to a neutral tone with the raw value for statuses
 * outside the known vocabulary rather than hiding them.
 */
export function StatusBadge({ value, tone }: { value: string; tone?: BadgeTone }) {
  const resolvedTone = tone ?? TONE_BY_VALUE[value] ?? 'neutral'
  return <span className={`badge badge-${resolvedTone}`}>{formatLabel(value)}</span>
}

function formatLabel(value: string): string {
  return value
    .split('_')
    .map((part) => (part.length ? part[0].toUpperCase() + part.slice(1) : part))
    .join(' ')
}

export function InlineTag({ children, tone = 'neutral' }: { children: ReactNode; tone?: BadgeTone }) {
  return <span className={`tag tag-${tone}`}>{children}</span>
}
