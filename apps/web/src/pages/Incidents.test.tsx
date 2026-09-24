import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Incidents } from './Incidents'

const mockUsePermission = vi.fn<(permission: string) => boolean>()
const mockUsePolledResource = vi.fn()

vi.mock('../hooks/usePermission', () => ({
  usePermission: (permission: string) => mockUsePermission(permission),
}))
vi.mock('../app/providers/AuthProvider', () => ({ useAuth: () => ({ apiClient: {} }) }))
vi.mock('../hooks/usePolledResource', () => ({
  usePolledResource: (...args: unknown[]) => mockUsePolledResource(...args),
}))
vi.mock('../services/incidents', () => ({ listIncidents: vi.fn(), listIncidentEscalations: vi.fn() }))

const baseResource = {
  loading: false,
  refreshing: false,
  error: null,
  lastUpdated: new Date('2025-01-01T00:00:00Z'),
  refresh: vi.fn(),
}

describe('Incidents page', () => {
  it('denies access when the user lacks incidents:read', () => {
    mockUsePermission.mockReturnValue(false)

    render(<Incidents />)

    expect(screen.getByText(/do not have permission/i)).toBeInTheDocument()
  })

  it('renders incident rows with severity and status', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource
      .mockReturnValueOnce({
        ...baseResource,
        data: {
          items: [
            { id: 'i1', title: 'Disk almost full', severity: 'high', priority: 'p1', status: 'open', opened_at: '2025-01-01T00:00:00Z' },
          ],
          page: 1,
          pageSize: 25,
          total: 1,
        },
      })
      .mockReturnValueOnce({ ...baseResource, data: null })

    render(<Incidents />)

    expect(screen.getByText('Disk almost full')).toBeInTheDocument()
  })

  it('shows an empty state when there are no incidents', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource
      .mockReturnValueOnce({ ...baseResource, data: { items: [], page: 1, pageSize: 25, total: 0 } })
      .mockReturnValueOnce({ ...baseResource, data: null })

    render(<Incidents />)

    expect(screen.getByText('No incidents recorded.')).toBeInTheDocument()
  })
})
