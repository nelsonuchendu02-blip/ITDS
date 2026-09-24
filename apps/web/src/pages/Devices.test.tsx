import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'
import { Devices } from './Devices'

const mockUsePermission = vi.fn<(permission: string) => boolean>()
const mockUsePolledResource = vi.fn()

vi.mock('../hooks/usePermission', () => ({
  usePermission: (permission: string) => mockUsePermission(permission),
}))
vi.mock('../app/providers/AuthProvider', () => ({ useAuth: () => ({ apiClient: {} }) }))
vi.mock('../hooks/usePolledResource', () => ({
  usePolledResource: (...args: unknown[]) => mockUsePolledResource(...args),
}))
vi.mock('../services/devices', () => ({ listDevices: vi.fn() }))

describe('Devices page', () => {
  it('denies access when the user lacks devices:read', () => {
    mockUsePermission.mockReturnValue(false)

    render(
      <MemoryRouter>
        <Devices />
      </MemoryRouter>,
    )

    expect(screen.getByText(/do not have permission/i)).toBeInTheDocument()
  })

  it('renders the device inventory table when permitted', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource.mockReturnValue({
      data: {
        items: [
          { id: 'd1', hostname: 'ws-01', device_type: 'workstation', operating_system: 'Windows 11', ip_address: '10.0.0.5', status: 'active', last_seen_at: '2025-01-01T00:00:00Z' },
        ],
        page: 1,
        pageSize: 25,
        total: 1,
      },
      loading: false,
      refreshing: false,
      error: null,
      lastUpdated: new Date('2025-01-01T00:00:00Z'),
      refresh: vi.fn(),
    })

    render(
      <MemoryRouter>
        <Devices />
      </MemoryRouter>,
    )

    expect(screen.getByText('ws-01')).toBeInTheDocument()
    expect(screen.getByText('workstation')).toBeInTheDocument()
  })

  it('shows an empty state when no devices match', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource.mockReturnValue({
      data: { items: [], page: 1, pageSize: 25, total: 0 },
      loading: false,
      refreshing: false,
      error: null,
      lastUpdated: null,
      refresh: vi.fn(),
    })

    render(
      <MemoryRouter>
        <Devices />
      </MemoryRouter>,
    )

    expect(screen.getByText('No devices match the current filters.')).toBeInTheDocument()
  })
})
