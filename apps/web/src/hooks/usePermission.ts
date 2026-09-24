import { useAuth } from '../app/providers/AuthProvider'
import { hasPermission } from '../types/common'

export function usePermission(permission: string): boolean {
  const { user } = useAuth()
  return hasPermission(user, permission)
}

export function useAnyPermission(permissions: string[]): boolean {
  const { user } = useAuth()
  return permissions.some((permission) => hasPermission(user, permission))
}
