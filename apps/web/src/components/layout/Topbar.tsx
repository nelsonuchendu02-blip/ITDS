import { useState, type FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../../app/providers/AuthProvider'
import { usePermission } from '../../hooks/usePermission'
import { usePolledResource } from '../../hooks/usePolledResource'
import { listIncidents } from '../../services/incidents'

export function Topbar({ onToggleSidebar }: { onToggleSidebar: () => void }) {
  const { user, logout, apiClient } = useAuth()
  const navigate = useNavigate()
  const [searchValue, setSearchValue] = useState('')
  const canReadIncidents = usePermission('incidents:read')

  const { data } = usePolledResource(
    () => listIncidents(apiClient, { page: 1, pageSize: 100 }),
    { intervalMs: 60_000, enabled: canReadIncidents },
  )
  const openIncidentCount =
    data?.items.filter((incident) => incident.status === 'open' || incident.status === 'in_progress').length ?? 0

  function handleSearchSubmit(event: FormEvent) {
    event.preventDefault()
    const trimmed = searchValue.trim()
    navigate(trimmed ? `/devices?search=${encodeURIComponent(trimmed)}` : '/devices')
  }

  return (
    <header className="topbar">
      <button type="button" className="icon-btn sidebar-toggle" onClick={onToggleSidebar} aria-label="Toggle navigation">
        ☰
      </button>
      <form className="topbar-search" role="search" onSubmit={handleSearchSubmit}>
        <label htmlFor="global-search" className="sr-only">
          Search devices
        </label>
        <input
          id="global-search"
          type="search"
          placeholder="Search devices…"
          value={searchValue}
          onChange={(event) => setSearchValue(event.target.value)}
        />
      </form>
      <div className="topbar-actions">
        <button
          type="button"
          className="icon-btn"
          onClick={() => navigate('/incidents')}
          aria-label={`Open incidents: ${openIncidentCount}`}
          title="Open incidents"
        >
          🔔
          {openIncidentCount > 0 && <span className="badge-dot">{openIncidentCount}</span>}
        </button>
        <div className="topbar-user">
          <span className="topbar-username">{user?.display_name}</span>
          <button type="button" className="btn btn-secondary" onClick={logout}>
            Sign out
          </button>
        </div>
      </div>
    </header>
  )
}
