import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listIncidentEscalations, listIncidents } from '../services/incidents'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime, formatRelativeTime } from '../utils/format'
import type { Incident } from '../types/incident'

const PAGE_SIZE = 25

function IncidentsContent() {
  const { apiClient } = useAuth()
  const [page, setPage] = useState(1)
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null)

  const incidents = usePolledResource(() => listIncidents(apiClient, { page, pageSize: PAGE_SIZE }), {
    reloadKey: page,
  })
  const escalations = usePolledResource(
    () => (selectedIncidentId ? listIncidentEscalations(apiClient, selectedIncidentId) : Promise.resolve(null)),
    { enabled: selectedIncidentId !== null, reloadKey: selectedIncidentId },
  )

  const columns: Column<Incident>[] = [
    { key: 'title', header: 'Title', render: (incident) => incident.title },
    { key: 'severity', header: 'Severity', render: (incident) => <StatusBadge value={incident.severity} /> },
    { key: 'priority', header: 'Priority', render: (incident) => <StatusBadge value={incident.priority} /> },
    { key: 'status', header: 'Status', render: (incident) => <StatusBadge value={incident.status} /> },
    {
      key: 'opened_at',
      header: 'Opened',
      render: (incident) => <span title={formatDateTime(incident.opened_at)}>{formatRelativeTime(incident.opened_at)}</span>,
    },
  ]

  return (
    <div className="page">
      <SectionHeader title="Incidents" description="Active and historical incident records." />
      <RefreshBar lastUpdated={incidents.lastUpdated} refreshing={incidents.refreshing} onRefresh={incidents.refresh} />
      {incidents.loading ? (
        <LoadingState label="Loading incidents…" />
      ) : incidents.error ? (
        <ErrorState message={incidents.error} onRetry={incidents.refresh} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={incidents.data?.items ?? []}
            rowKey={(incident) => incident.id}
            onRowClick={(incident) => setSelectedIncidentId(incident.id)}
            emptyMessage="No incidents recorded."
          />
          {incidents.data && (
            <Pagination
              page={incidents.data.page}
              pageSize={incidents.data.pageSize}
              total={incidents.data.total}
              onPageChange={setPage}
            />
          )}
        </>
      )}

      {selectedIncidentId && (
        <section className="panel">
          <SectionHeader title="Escalations" description={`Incident ${selectedIncidentId}`} />
          {escalations.loading ? (
            <LoadingState />
          ) : escalations.error ? (
            <ErrorState message={escalations.error} onRetry={escalations.refresh} />
          ) : escalations.data && escalations.data.length > 0 ? (
            <ul className="escalation-list">
              {escalations.data.map((escalation) => (
                <li key={escalation.id} className="escalation-item">
                  <StatusBadge value={escalation.status} />
                  <span>Level {escalation.escalation_level}</span>
                  <span>{escalation.reason}</span>
                  <span className="telemetry-time">{formatDateTime(escalation.escalated_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="state-description">No escalations for this incident.</p>
          )}
        </section>
      )}
    </div>
  )
}

export function Incidents() {
  return (
    <PermissionGate permission="incidents:read" resource="incidents">
      <IncidentsContent />
    </PermissionGate>
  )
}
