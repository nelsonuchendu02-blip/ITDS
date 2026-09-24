/**
 * Shared page/pagination envelope shapes returned by ITDS list endpoints.
 * Different Phase 1 endpoints use slightly different meta wrappers
 * (`meta: {...}` vs top-level `total`/`page`/`page_size`), so both are
 * normalized by the `services/api.ts` helpers into this common shape.
 */
export type Page<T> = {
  items: T[]
  page: number
  pageSize: number
  total: number
}

export type CurrentUser = {
  id: string
  organization_id: string
  email: string
  display_name: string
  status: string
  roles: string[]
  permissions: string[]
  created_at: string
  updated_at: string
}

export function hasPermission(user: CurrentUser | null, permission: string): boolean {
  if (!user) return false
  if (user.permissions.includes('*')) return true
  return user.permissions.includes(permission)
}
