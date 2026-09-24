import { describe, expect, it } from 'vitest'
import { hasPermission, type CurrentUser } from './common'

const baseUser: CurrentUser = {
  id: 'u1',
  organization_id: 'o1',
  email: 'user@example.com',
  display_name: 'User',
  status: 'active',
  roles: ['viewer'],
  permissions: ['devices:read'],
  created_at: '2025-01-01T00:00:00Z',
  updated_at: '2025-01-01T00:00:00Z',
}

describe('hasPermission', () => {
  it('returns true for explicitly granted permissions', () => {
    expect(hasPermission(baseUser, 'devices:read')).toBe(true)
    expect(hasPermission(baseUser, 'devices:manage')).toBe(false)
  })

  it('grants all permissions when wildcard exists', () => {
    const admin: CurrentUser = { ...baseUser, permissions: ['*'] }
    expect(hasPermission(admin, 'audit:read')).toBe(true)
    expect(hasPermission(admin, 'remediation:manage')).toBe(true)
  })

  it('rejects null user', () => {
    expect(hasPermission(null, 'devices:read')).toBe(false)
  })
})
