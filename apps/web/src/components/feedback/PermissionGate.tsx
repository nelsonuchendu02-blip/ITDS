import type { ReactNode } from 'react'
import { usePermission } from '../../hooks/usePermission'
import { AccessDenied } from '../feedback/AccessDenied'

export function PermissionGate({
  permission,
  resource,
  children,
}: {
  permission: string
  resource: string
  children: ReactNode
}) {
  const allowed = usePermission(permission)
  if (!allowed) return <AccessDenied resource={resource} />
  return <>{children}</>
}
