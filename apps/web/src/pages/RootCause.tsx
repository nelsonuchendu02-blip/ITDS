import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listRootCauseAnalyses, listRootCauseFindings } from '../services/rootCause'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime } from '../utils/format'
import type { RootCauseAnalysis, RootCauseFinding } from '../types/rootCause'

const PAGE_SIZE = 25

function RootCauseContent() {
  const { apiClient } = useAuth()
  const [page, setPage] = useState(1)
  const [selectedAnalysisId, setSelectedAnalysisId] = useState<string | null>(null)

  const analyses = usePolledResource(() => listRootCauseAnalyses(apiClient, { page, pageSize: PAGE_SIZE }), {
    reloadKey: page,
  })
  const findings = usePolledResource(
    () => (selectedAnalysisId ? listRootCauseFindings(apiClient, selectedAnalysisId, { pageSize: 25 }) : Promise.resolve(null)),
    { enabled: selectedAnalysisId !== null, reloadKey: selectedAnalysisId },
  )

  const analysisColumns: Column<RootCauseAnalysis>[] = [
    { key: 'provider', header: 'Provider', render: (analysis) => analysis.provider },
    { key: 'status', header: 'Status', render: (analysis) => <StatusBadge value={analysis.status} /> },
    { key: 'created_at', header: 'Created', render: (analysis) => formatDateTime(analysis.created_at) },
  ]

  const findingColumns: Column<RootCauseFinding>[] = [
    { key: 'title', header: 'Finding', render: (finding) => finding.title },
    { key: 'category', header: 'Category', render: (finding) => finding.category },
    { key: 'severity', header: 'Severity', render: (finding) => <StatusBadge value={finding.severity} /> },
    { key: 'confidence', header: 'Confidence', render: (finding) => <StatusBadge value={finding.confidence} /> },
    { key: 'status', header: 'Status', render: (finding) => <StatusBadge value={finding.status} /> },
  ]

  return (
    <div className="page">
      <SectionHeader title="Root cause analysis" description="Automated root-cause analyses and supporting findings." />
      <RefreshBar lastUpdated={analyses.lastUpdated} refreshing={analyses.refreshing} onRefresh={analyses.refresh} />
      {analyses.loading ? (
        <LoadingState label="Loading analyses…" />
      ) : analyses.error ? (
        <ErrorState message={analyses.error} onRetry={analyses.refresh} />
      ) : (
        <>
          <DataTable
            columns={analysisColumns}
            rows={analyses.data?.items ?? []}
            rowKey={(analysis) => analysis.id}
            onRowClick={(analysis) => setSelectedAnalysisId(analysis.id)}
            emptyMessage="No root-cause analyses recorded."
          />
          {analyses.data && (
            <Pagination page={analyses.data.page} pageSize={analyses.data.pageSize} total={analyses.data.total} onPageChange={setPage} />
          )}
        </>
      )}

      {selectedAnalysisId && (
        <section className="panel">
          <SectionHeader title="Findings" description={`Analysis ${selectedAnalysisId}`} />
          {findings.loading ? (
            <LoadingState />
          ) : findings.error ? (
            <ErrorState message={findings.error} onRetry={findings.refresh} />
          ) : (
            <DataTable
              columns={findingColumns}
              rows={findings.data?.items ?? []}
              rowKey={(finding) => finding.id}
              emptyMessage="No findings for this analysis."
            />
          )}
        </section>
      )}
    </div>
  )
}

export function RootCause() {
  return (
    <PermissionGate permission="root_cause:read" resource="root-cause analyses">
      <RootCauseContent />
    </PermissionGate>
  )
}
