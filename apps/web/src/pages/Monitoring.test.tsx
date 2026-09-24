import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Monitoring } from './Monitoring'

const mockUsePermission = vi.fn<(permission: string) => boolean>()
const mockUsePolledResource = vi.fn()

vi.mock('../hooks/usePermission', () => ({
  usePermission: (permission: string) => mockUsePermission(permission),
}))
vi.mock('../app/providers/AuthProvider', () => ({ useAuth: () => ({ apiClient: {} }) }))
vi.mock('../hooks/usePolledResource', () => ({
  usePolledResource: (...args: unknown[]) => mockUsePolledResource(...args),
}))
vi.mock('../services/monitoring', () => ({
  fetchMonitoringSummary: vi.fn(),
  listMonitoringTargets: vi.fn(),
  listTargetTelemetry: vi.fn(),
}))

const baseResource = {
  loading: false,
  refreshing: false,
  error: null,
  lastUpdated: new Date('2025-01-01T00:00:00Z'),
  refresh: vi.fn(),
}

describe('Monitoring page', () => {
  it('denies access when the user lacks monitoring:read', () => {
    mockUsePermission.mockReturnValue(false)

    render(<Monitoring />)

    expect(screen.getByText(/do not have permission/i)).toBeInTheDocument()
  })

  it('renders the health distribution and monitoring targets table', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource
      .mockReturnValueOnce({
        ...baseResource,
        data: { total_targets: 4, enabled_targets: 4, healthy: 3, degraded: 1, unhealthy: 0, offline: 0, unknown: 0 },
      }) // summary
      .mockReturnValueOnce({
        ...baseResource,
        data: {
          items: [
            { id: 't1', device_id: 'dev-1', health_status: 'healthy', enabled: true, check_interval_seconds: 60, last_seen_at: '2025-01-01T00:00:00Z' },
          ],
          page: 1,
          pageSize: 25,
          total: 1,
        },
      }) // targets
      .mockReturnValueOnce({ ...baseResource, data: null, loading: false }) // telemetry (disabled)

    render(<Monitoring />)

    expect(screen.getByText('dev-1')).toBeInTheDocument()
  })

  it('shows a loading state for monitoring targets while they load', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource
      .mockReturnValueOnce({ ...baseResource, data: null })
      .mockReturnValueOnce({ ...baseResource, data: null, loading: true })
      .mockReturnValueOnce({ ...baseResource, data: null })

    render(<Monitoring />)

    expect(screen.getByText('Loading targets…')).toBeInTheDocument()
  })
})
