import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Sidebar } from './Sidebar'

const permissionMock = vi.fn<(permission: string) => boolean>()

vi.mock('../../hooks/usePermission', () => ({
  usePermission: (permission: string) => permissionMock(permission),
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
})
