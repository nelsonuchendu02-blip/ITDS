import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listDiagnosticResults, listDiagnosticRuns } from '../services/diagnostics'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime } from '../utils/format'
import type { DiagnosticResult, DiagnosticRun } from '../types/diagnostics'

const PAGE_SIZE = 25

function DiagnosticsContent() {
  const { apiClient } = useAuth()
  const [page, setPage] = useState(1)
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null)

  const runs = usePolledResource(() => listDiagnosticRuns(apiClient, { page, pageSize: PAGE_SIZE }), { reloadKey: page })
  const results = usePolledResource(
    () => (selectedRunId ? listDiagnosticResults(apiClient, selectedRunId, { pageSize: 25 }) : Promise.resolve(null)),
    { enabled: selectedRunId !== null, reloadKey: selectedRunId },
  )

  const runColumns: Column<DiagnosticRun>[] = [
    { key: 'diagnostic_type', header: 'Type', render: (run) => run.diagnostic_type },
    { key: 'provider', header: 'Provider', render: (run) => run.provider },
    { key: 'status', header: 'Status', render: (run) => <StatusBadge value={run.status} /> },
    { key: 'created_at', header: 'Created', render: (run) => formatDateTime(run.created_at) },
  ]

  const resultColumns: Column<DiagnosticResult>[] = [
    { key: 'title', header: 'Check', render: (result) => result.title },
    { key: 'check_type', header: 'Category', render: (result) => result.check_type },
    { key: 'status', header: 'Result', render: (result) => <StatusBadge value={result.status} /> },
    { key: 'severity', header: 'Severity', render: (result) => <StatusBadge value={result.severity} /> },
    { key: 'checked_at', header: 'Checked', render: (result) => formatDateTime(result.checked_at) },
  ]

  return (
    <div className="page">
      <SectionHeader title="Diagnostics" description="Diagnostic runs and per-check results." />
      <RefreshBar lastUpdated={runs.lastUpdated} refreshing={runs.refreshing} onRefresh={runs.refresh} />
      {runs.loading ? (
        <LoadingState label="Loading diagnostic runs…" />
      ) : runs.error ? (
        <ErrorState message={runs.error} onRetry={runs.refresh} />
      ) : (
        <>
          <DataTable
            columns={runColumns}
            rows={runs.data?.items ?? []}
            rowKey={(run) => run.id}
            onRowClick={(run) => setSelectedRunId(run.id)}
            emptyMessage="No diagnostic runs recorded."
          />
          {runs.data && <Pagination page={runs.data.page} pageSize={runs.data.pageSize} total={runs.data.total} onPageChange={setPage} />}
        </>
      )}

      {selectedRunId && (
        <section className="panel">
          <SectionHeader title="Check results" description={`Run ${selectedRunId}`} />
          {results.loading ? (
            <LoadingState />
          ) : results.error ? (
            <ErrorState message={results.error} onRetry={results.refresh} />
          ) : (
            <DataTable
              columns={resultColumns}
              rows={results.data?.items ?? []}
              rowKey={(result) => result.id}
              emptyMessage="No results for this run."
            />
          )}
        </section>
      )}
    </div>
  )
}

export function Diagnostics() {
  return (
    <PermissionGate permission="diagnostics:read" resource="diagnostics">
      <DiagnosticsContent />
    </PermissionGate>
  )
}
