import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { Agents } from './Agents'

const mockUsePermission = vi.fn<(permission: string) => boolean>()
const mockUsePolledResource = vi.fn()

vi.mock('../hooks/usePermission', () => ({
  usePermission: (permission: string) => mockUsePermission(permission),
}))
vi.mock('../app/providers/AuthProvider', () => ({ useAuth: () => ({ apiClient: {} }) }))
vi.mock('../hooks/usePolledResource', () => ({
  usePolledResource: (...args: unknown[]) => mockUsePolledResource(...args),
}))
vi.mock('../services/agents', () => ({ listAgents: vi.fn() }))

describe('Agents page', () => {
  it('denies access when the user lacks agents:read', () => {
    mockUsePermission.mockReturnValue(false)

    render(<Agents />)

    expect(screen.getByText(/do not have permission/i)).toBeInTheDocument()
  })

  it('renders enrolled agents with status and platform', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource.mockReturnValue({
      data: [
        { id: 'ag1', agent_name: 'edge-agent-01', platform: 'windows', agent_version: '1.2.0', status: 'active', last_ip_address: '10.0.0.9', last_seen_at: '2025-01-01T00:00:00Z' },
      ],
      loading: false,
      refreshing: false,
      error: null,
      lastUpdated: new Date('2025-01-01T00:00:00Z'),
      refresh: vi.fn(),
    })

    render(<Agents />)

    expect(screen.getByText('edge-agent-01')).toBeInTheDocument()
    expect(screen.getByText('windows')).toBeInTheDocument()
  })

  it('shows a loading state before agents arrive', () => {
    mockUsePermission.mockReturnValue(true)
    mockUsePolledResource.mockReturnValue({
      data: null,
      loading: true,
      refreshing: false,
      error: null,
      lastUpdated: null,
      refresh: vi.fn(),
    })

    render(<Agents />)

    expect(screen.getByText('Loading agents…')).toBeInTheDocument()
  })

  it('shows an error state with a retry action when loading fails', () => {
    mockUsePermission.mockReturnValue(true)
    const refresh = vi.fn()
    mockUsePolledResource.mockReturnValue({
      data: null,
      loading: false,
      refreshing: false,
      error: 'Unable to load data.',
      lastUpdated: null,
      refresh,
    })

    render(<Agents />)

    expect(screen.getByText('Unable to load data.')).toBeInTheDocument()
  })
})
