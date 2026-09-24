import { fireEvent, render, screen, within } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Dashboard } from './Dashboard'

const mockUsePermission = vi.fn<(permission: string) => boolean>()
const mockUsePolledResource = vi.fn()
const refreshSpies = Array.from({ length: 6 }, () => vi.fn(async () => {}))

vi.mock('../hooks/usePermission', () => ({
  usePermission: (permission: string) => mockUsePermission(permission),
}))

vi.mock('../app/providers/AuthProvider', () => ({
  useAuth: () => ({ apiClient: {} }),
}))

vi.mock('../hooks/usePolledResource', () => ({
  usePolledResource: (...args: unknown[]) => mockUsePolledResource(...args),
}))

vi.mock('../services/monitoring', () => ({
  fetchMonitoringSummary: vi.fn(),
}))
vi.mock('../services/devices', () => ({ listDevices: vi.fn() }))
vi.mock('../services/agents', () => ({ listAgents: vi.fn() }))
vi.mock('../services/incidents', () => ({ listIncidents: vi.fn() }))
vi.mock('../services/discovery', () => ({ listDiscoveryJobs: vi.fn() }))
vi.mock('../services/recommendations', () => ({ listRecommendations: vi.fn() }))

describe('Dashboard', () => {
  it('renders KPIs and refreshes all resources', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource.mockReset()

    const baseState = {
      loading: false,
      refreshing: false,
      error: null,
      lastUpdated: new Date('2025-01-01T00:00:00Z'),
    }

    mockUsePolledResource
      .mockReturnValueOnce({
        ...baseState,
        data: { total: 18, items: [] },
        refresh: refreshSpies[0],
      }) // devices
      .mockReturnValueOnce({
        ...baseState,
        data: { total_targets: 12, enabled_targets: 10, healthy: 7, degraded: 2, unhealthy: 1, offline: 1, unknown: 1 },
        refresh: refreshSpies[1],
      }) // monitoring
      .mockReturnValueOnce({
        ...baseState,
        data: [{ id: 'a1', status: 'active', agent_name: 'A', last_seen_at: '2025-01-01T00:00:00Z' }],
        refresh: refreshSpies[2],
      }) // agents
      .mockReturnValueOnce({
        ...baseState,
        data: { items: [{ id: 'i1', title: 'CPU spike', status: 'open', updated_at: '2025-01-01T00:00:00Z' }] },
        refresh: refreshSpies[3],
      }) // incidents
      .mockReturnValueOnce({
        ...baseState,
        data: { items: [] },
        refresh: refreshSpies[4],
      }) // discovery
      .mockReturnValueOnce({
        ...baseState,
        data: { items: [] },
        refresh: refreshSpies[5],
      }) // recommendations

    render(<Dashboard />)

    expect(screen.getByText('Total devices')).toBeInTheDocument()
    expect(screen.getByText('18')).toBeInTheDocument()
    const monitoringCard = screen.getByText('Monitored targets').closest('.kpi-card')
    expect(monitoringCard).toBeTruthy()
    expect(within(monitoringCard as HTMLElement).getByText('12')).toBeInTheDocument()
    const incidentsCard = screen.getByText('Open incidents').closest('.kpi-card')
    expect(incidentsCard).toBeTruthy()
    expect(within(incidentsCard as HTMLElement).getByText('1')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    for (const spy of refreshSpies) {
      expect(spy).toHaveBeenCalled()
    }
  })
})
