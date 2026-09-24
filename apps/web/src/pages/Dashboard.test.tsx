import { fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { Dashboard } from './Dashboard'

const mockUsePermission = vi.fn<(permission: string) => boolean>()
const mockUsePolledResource = vi.fn()
const refreshSpies = Array.from({ length: 5 }, () => vi.fn(async () => {}))

vi.mock('../hooks/usePermission', () => ({
  usePermission: (permission: string) => mockUsePermission(permission),
}))

vi.mock('../app/providers/AuthProvider', () => ({
  useAuth: () => ({ apiClient: {} }),
}))

vi.mock('../hooks/usePolledResource', () => ({
  usePolledResource: (...args: unknown[]) => mockUsePolledResource(...args),
}))

vi.mock('../services/dashboard', () => ({ fetchDashboardOverview: vi.fn() }))
vi.mock('../services/agents', () => ({ listAgents: vi.fn() }))
vi.mock('../services/incidents', () => ({ listIncidents: vi.fn() }))
vi.mock('../services/discovery', () => ({ listDiscoveryJobs: vi.fn() }))
vi.mock('../services/recommendations', () => ({ listRecommendations: vi.fn() }))

const baseState = {
  loading: false,
  refreshing: false,
  error: null,
  lastUpdated: new Date('2025-01-01T00:00:00Z'),
}

// Mocks the 5 usePolledResource calls Dashboard makes, in call order:
// overview, agents, incidents, discoveryJobs, recommendations.
function mockResources(
  overrides: Partial<Record<'overview' | 'agents' | 'incidents' | 'discovery' | 'recommendations', Record<string, unknown>>> = {},
) {
  mockUsePolledResource.mockReset()
  mockUsePolledResource
    .mockReturnValueOnce({
      ...baseState,
      data: {
        devices: { total: 18 },
        monitoring: { total_targets: 12, enabled_targets: 10, healthy: 7, degraded: 2, unhealthy: 1, offline: 1, unknown: 1 },
        agents: { total: 5, active: 4 },
        incidents: { total: 3, open: 1, in_progress: 0, resolved: 2, closed: 0 },
        discovery: { total: 2, running: 1 },
        recommendations: { total: 4, pending: 3 },
      },
      refresh: refreshSpies[0],
      ...overrides.overview,
    }) // overview
    .mockReturnValueOnce({
      ...baseState,
      data: [{ id: 'a1', status: 'active', agent_name: 'A', last_seen_at: '2025-01-01T00:00:00Z' }],
      refresh: refreshSpies[1],
      ...overrides.agents,
    }) // agents
    .mockReturnValueOnce({
      ...baseState,
      data: { items: [{ id: 'i1', title: 'CPU spike', status: 'open', updated_at: '2025-01-01T00:00:00Z' }] },
      refresh: refreshSpies[2],
      ...overrides.incidents,
    }) // incidents
    .mockReturnValueOnce({
      ...baseState,
      data: { items: [] },
      refresh: refreshSpies[3],
      ...overrides.discovery,
    }) // discovery
    .mockReturnValueOnce({
      ...baseState,
      data: { items: [] },
      refresh: refreshSpies[4],
      ...overrides.recommendations,
    }) // recommendations
}

describe('Dashboard', () => {
  afterEach(() => {
    mockUsePermission.mockReset()
  })

  it('renders KPIs sourced from the overview endpoint and refreshes all resources', () => {
    mockUsePermission.mockReturnValue(true)
    mockResources()

    render(<Dashboard />)

    expect(screen.getByText('Total devices')).toBeInTheDocument()
    expect(screen.getByText('18')).toBeInTheDocument()
    const monitoringCard = screen.getByText('Monitored targets').closest('.kpi-card')
    expect(monitoringCard).toBeTruthy()
    expect(within(monitoringCard as HTMLElement).getByText('12')).toBeInTheDocument()
    const incidentsCard = screen.getByText('Open incidents').closest('.kpi-card')
    expect(incidentsCard).toBeTruthy()
    expect(within(incidentsCard as HTMLElement).getByText('1')).toBeInTheDocument()
    const discoveryCard = screen.getByText('Discovery jobs running').closest('.kpi-card')
    expect(discoveryCard).toBeTruthy()
    expect(within(discoveryCard as HTMLElement).getByText('1')).toBeInTheDocument()
    const recommendationsCard = screen.getByText('Pending recommendations').closest('.kpi-card')
    expect(recommendationsCard).toBeTruthy()
    expect(within(recommendationsCard as HTMLElement).getByText('3')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))
    for (const spy of refreshSpies) {
      expect(spy).toHaveBeenCalled()
    }
  })

  it('does not manually refresh dashboard resources that the user cannot read', () => {
    mockUsePermission.mockImplementation((permission) => permission === 'devices:read')
    mockResources()

    render(<Dashboard />)
    fireEvent.click(screen.getByRole('button', { name: 'Refresh' }))

    expect(refreshSpies[0]).toHaveBeenCalled()
    for (const spy of refreshSpies.slice(1)) {
      expect(spy).not.toHaveBeenCalled()
    }
  })

  it('keeps loading state true while discovery or overview are still loading, so activity is not shown as empty prematurely', () => {
    mockUsePermission.mockReturnValue(true)
    mockResources({
      discovery: { loading: true, data: null },
      overview: { loading: true, data: null },
    })

    render(<Dashboard />)

    expect(screen.getByText('Loading dashboard data…')).toBeInTheDocument()
  })

  it('shows a permission-based empty state when the user has none of the contributing read permissions', () => {
    mockUsePermission.mockReturnValue(false)
    mockResources()

    render(<Dashboard />)

    expect(screen.getByText('No dashboard data available')).toBeInTheDocument()
    expect(screen.queryByText('Total devices')).not.toBeInTheDocument()
  })
})
