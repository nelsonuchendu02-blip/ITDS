import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listDiscoveryJobs, listDiscoveryResults } from '../services/discovery'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime } from '../utils/format'
import type { DiscoveryJob, DiscoveryResult } from '../types/discovery'

const PAGE_SIZE = 25

function DiscoveryContent() {
  const { apiClient } = useAuth()
  const [page, setPage] = useState(1)
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null)

  const jobs = usePolledResource(() => listDiscoveryJobs(apiClient, { page, pageSize: PAGE_SIZE }), { reloadKey: page })
  const results = usePolledResource(
    () => (selectedJobId ? listDiscoveryResults(apiClient, selectedJobId, { pageSize: 25 }) : Promise.resolve(null)),
    { enabled: selectedJobId !== null, reloadKey: selectedJobId },
  )

  const jobColumns: Column<DiscoveryJob>[] = [
    { key: 'provider', header: 'Provider', render: (job) => job.provider },
    { key: 'target_type', header: 'Target type', render: (job) => job.target_type },
    { key: 'target_count', header: 'Targets', render: (job) => job.target_count, align: 'right' },
    { key: 'status', header: 'Status', render: (job) => <StatusBadge value={job.status} /> },
    { key: 'created_at', header: 'Created', render: (job) => formatDateTime(job.created_at) },
  ]

  const resultColumns: Column<DiscoveryResult>[] = [
    { key: 'target_ip', header: 'IP address', render: (result) => result.target_ip },
    { key: 'discovered_hostname', header: 'Hostname', render: (result) => result.discovered_hostname ?? '—' },
    { key: 'status', header: 'Status', render: (result) => <StatusBadge value={result.status} /> },
    { key: 'reconciliation_status', header: 'Reconciliation', render: (result) => <StatusBadge value={result.reconciliation_status} /> },
  ]

  return (
    <div className="page">
      <SectionHeader title="Discovery" description="Network discovery jobs and reconciliation results." />
      <RefreshBar lastUpdated={jobs.lastUpdated} refreshing={jobs.refreshing} onRefresh={jobs.refresh} />
      {jobs.loading ? (
        <LoadingState label="Loading discovery jobs…" />
      ) : jobs.error ? (
        <ErrorState message={jobs.error} onRetry={jobs.refresh} />
      ) : (
        <>
          <DataTable
            columns={jobColumns}
            rows={jobs.data?.items ?? []}
            rowKey={(job) => job.id}
            onRowClick={(job) => setSelectedJobId(job.id)}
            emptyMessage="No discovery jobs have run yet."
          />
          {jobs.data && <Pagination page={jobs.data.page} pageSize={jobs.data.pageSize} total={jobs.data.total} onPageChange={setPage} />}
        </>
      )}

      {selectedJobId && (
        <section className="panel">
          <SectionHeader title="Discovery results" description={`Job ${selectedJobId}`} />
          {results.loading ? (
            <LoadingState />
          ) : results.error ? (
            <ErrorState message={results.error} onRetry={results.refresh} />
          ) : (
            <DataTable
              columns={resultColumns}
              rows={results.data?.items ?? []}
              rowKey={(result) => result.id}
              emptyMessage="No results for this job."
            />
          )}
        </section>
      )}
    </div>
  )
}

export function Discovery() {
  return (
    <PermissionGate permission="discovery:read" resource="discovery jobs">
      <DiscoveryContent />
    </PermissionGate>
  )
}
