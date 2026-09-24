import { EmptyState } from '../feedback/EmptyState'
import { formatDateTime } from '../../utils/format'
import type { BadgeTone } from '../status/StatusBadge'

export type ActivityItem = {
  id: string
  source: string
  label: string
  timestamp: string
  tone?: BadgeTone
}

export function RecentActivity({ items }: { items: ActivityItem[] }) {
  if (items.length === 0) {
    return <EmptyState title="No recent activity" description="Activity from incidents, agents, discovery, and recommendations will appear here." />
  }

  const sorted = [...items].sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())

  return (
    <ul className="activity-list">
      {sorted.map((item) => (
        <li key={item.id} className="activity-item">
          <span className={`activity-dot activity-${item.tone ?? 'neutral'}`} aria-hidden="true" />
          <div className="activity-body">
            <p className="activity-label">{item.label}</p>
            <p className="activity-meta">
              <span className="activity-source">{item.source}</span> · {formatDateTime(item.timestamp)}
            </p>
          </div>
        </li>
      ))}
    </ul>
  )
}
