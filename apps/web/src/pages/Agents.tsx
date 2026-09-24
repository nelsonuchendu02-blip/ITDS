import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listAgents } from '../services/agents'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime, formatRelativeTime } from '../utils/format'
import type { Agent } from '../types/agent'

function AgentsContent() {
  const { apiClient } = useAuth()
  const { data, loading, refreshing, error, lastUpdated, refresh } = usePolledResource(() => listAgents(apiClient))

  const columns: Column<Agent>[] = [
    { key: 'agent_name', header: 'Agent', render: (agent) => agent.agent_name },
    { key: 'platform', header: 'Platform', render: (agent) => agent.platform },
    { key: 'agent_version', header: 'Version', render: (agent) => agent.agent_version ?? '—' },
    { key: 'status', header: 'Status', render: (agent) => <StatusBadge value={agent.status} /> },
    { key: 'last_ip_address', header: 'Last IP', render: (agent) => agent.last_ip_address ?? '—' },
    {
      key: 'last_seen_at',
      header: 'Last seen',
      render: (agent) => <span title={formatDateTime(agent.last_seen_at)}>{formatRelativeTime(agent.last_seen_at)}</span>,
    },
  ]

  return (
    <div className="page">
      <SectionHeader title="Agents" description="Enrolled endpoint agents reporting telemetry." />
      <RefreshBar lastUpdated={lastUpdated} refreshing={refreshing} onRefresh={refresh} />
      {loading ? (
        <LoadingState label="Loading agents…" />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : (
        <DataTable columns={columns} rows={data ?? []} rowKey={(agent) => agent.id} emptyMessage="No agents enrolled yet." />
      )}
    </div>
  )
}

export function Agents() {
  return (
    <PermissionGate permission="agents:read" resource="agents">
      <AgentsContent />
    </PermissionGate>
  )
}
