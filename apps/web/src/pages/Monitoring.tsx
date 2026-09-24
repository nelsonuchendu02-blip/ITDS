import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { fetchMonitoringSummary, listMonitoringTargets, listTargetTelemetry } from '../services/monitoring'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { HealthDistributionChart } from '../components/dashboard/HealthDistributionChart'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime, formatDuration, formatPercent, formatRelativeTime } from '../utils/format'
import type { MonitoringTarget } from '../types/monitoring'

const PAGE_SIZE = 25

function MonitoringContent() {
  const { apiClient } = useAuth()
  const [page, setPage] = useState(1)
  const [selectedTargetId, setSelectedTargetId] = useState<string | null>(null)

  const summary = usePolledResource(() => fetchMonitoringSummary(apiClient))
  const targets = usePolledResource(() => listMonitoringTargets(apiClient, { page, pageSize: PAGE_SIZE }), {
    reloadKey: page,
  })
  const telemetry = usePolledResource(
    () => (selectedTargetId ? listTargetTelemetry(apiClient, selectedTargetId, { pageSize: 10 }) : Promise.resolve(null)),
    { enabled: selectedTargetId !== null, reloadKey: selectedTargetId },
  )

  const columns: Column<MonitoringTarget>[] = [
    { key: 'device_id', header: 'Device ID', render: (target) => <code className="mono">{target.device_id}</code> },
    { key: 'health_status', header: 'Health', render: (target) => <StatusBadge value={target.health_status} /> },
    { key: 'enabled', header: 'Enabled', render: (target) => (target.enabled ? 'Yes' : 'No') },
    { key: 'check_interval_seconds', header: 'Check interval', render: (target) => formatDuration(target.check_interval_seconds) },
    {
      key: 'last_seen_at',
      header: 'Last seen',
      render: (target) => <span title={formatDateTime(target.last_seen_at)}>{formatRelativeTime(target.last_seen_at)}</span>,
    },
  ]

  return (
    <div className="page">
      <SectionHeader title="Monitoring" description="Target health and telemetry across all monitored devices." />
      <RefreshBar
        lastUpdated={summary.lastUpdated}
        refreshing={summary.refreshing || targets.refreshing}
        onRefresh={() => {
          void summary.refresh()
          void targets.refresh()
        }}
      />

      <section className="panel">
        <SectionHeader title="Health distribution" />
        {summary.loading ? (
          <LoadingState />
        ) : summary.error ? (
          <ErrorState message={summary.error} onRetry={summary.refresh} />
        ) : summary.data ? (
          <HealthDistributionChart
            healthy={summary.data.healthy}
            degraded={summary.data.degraded}
            unhealthy={summary.data.unhealthy}
            offline={summary.data.offline}
            unknown={summary.data.unknown}
          />
        ) : null}
      </section>

      <section className="panel">
        <SectionHeader title="Monitoring targets" description="Select a row to view recent telemetry." />
        {targets.loading ? (
          <LoadingState label="Loading targets…" />
        ) : targets.error ? (
          <ErrorState message={targets.error} onRetry={targets.refresh} />
        ) : (
          <>
            <DataTable
              columns={columns}
              rows={targets.data?.items ?? []}
              rowKey={(target) => target.id}
              onRowClick={(target) => setSelectedTargetId(target.id)}
              emptyMessage="No monitoring targets configured."
            />
            {targets.data && (
              <Pagination page={targets.data.page} pageSize={targets.data.pageSize} total={targets.data.total} onPageChange={setPage} />
            )}
          </>
        )}
      </section>

      {selectedTargetId && (
        <section className="panel">
          <SectionHeader title="Recent telemetry" description={`Target ${selectedTargetId}`} />
          {telemetry.loading ? (
            <LoadingState />
          ) : telemetry.error ? (
            <ErrorState message={telemetry.error} onRetry={telemetry.refresh} />
          ) : telemetry.data && telemetry.data.items.length > 0 ? (
            <ul className="telemetry-list">
              {telemetry.data.items.map((entry) => (
                <li key={entry.id} className="telemetry-item">
                  <StatusBadge value={entry.health_status} />
                  <span>CPU {formatPercent(entry.cpu_percent)}</span>
                  <span>Mem {formatPercent(entry.memory_percent)}</span>
                  <span>Disk {formatPercent(entry.disk_percent)}</span>
                  <span>Uptime {formatDuration(entry.uptime_seconds)}</span>
                  <span className="telemetry-time">{formatDateTime(entry.observed_at)}</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="state-description">No telemetry recorded for this target yet.</p>
          )}
        </section>
      )}
    </div>
  )
}

export function Monitoring() {
  return (
    <PermissionGate permission="monitoring:read" resource="monitoring data">
      <MonitoringContent />
    </PermissionGate>
  )
}
