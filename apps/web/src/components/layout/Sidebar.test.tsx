import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Sidebar } from './Sidebar'

const permissionMock = vi.fn<(permission: string) => boolean>()

vi.mock('../../hooks/usePermission', () => ({
  usePermission: (permission: string) => permissionMock(permission),
  useAnyPermission: (permissions: string[]) => permissions.some((permission) => permissionMock(permission)),
}))

describe('Sidebar', () => {
  it('renders only permitted navigation links', () => {
    permissionMock.mockImplementation((permission) =>
      ['devices:read', 'monitoring:read', 'incidents:read'].includes(permission),
    )

    render(
      <MemoryRouter>
        <Sidebar open />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Devices' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Monitoring' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Incidents' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Audit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Remediation' })).not.toBeInTheDocument()
  })

  it('shows Dashboard when the user can read any contributing module, even without devices:read', () => {
    permissionMock.mockImplementation((permission) => permission === 'incidents:read')

    render(
      <MemoryRouter>
        <Sidebar open />
      </MemoryRouter>,
    )

    expect(screen.getByRole('link', { name: 'Dashboard' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Devices' })).not.toBeInTheDocument()
  })

  it('hides Dashboard when the user has none of the contributing read permissions', () => {
    permissionMock.mockImplementation(() => false)

    render(
      <MemoryRouter>
        <Sidebar open />
      </MemoryRouter>,
    )

    expect(screen.queryByRole('link', { name: 'Dashboard' })).not.toBeInTheDocument()
  })
})
