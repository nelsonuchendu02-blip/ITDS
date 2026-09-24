import type { ReactNode } from 'react'

export function SectionHeader({
  title,
  description,
  actions,
}: {
  title: string
  description?: string
  actions?: ReactNode
}) {
  return (
    <div className="section-header">
      <div>
        <h2>{title}</h2>
        {description && <p className="section-description">{description}</p>}
      </div>
      {actions && <div className="section-actions">{actions}</div>}
    </div>
  )
}
