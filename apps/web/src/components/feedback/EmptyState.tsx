import type { ReactNode } from 'react'

export function EmptyState({
  title,
  description,
  action,
}: {
  title: string
  description?: string
  action?: ReactNode
}) {
  return (
    <div className="state-panel state-empty" role="status">
      <p className="state-title">{title}</p>
      {description && <p className="state-description">{description}</p>}
      {action}
    </div>
  )
}
