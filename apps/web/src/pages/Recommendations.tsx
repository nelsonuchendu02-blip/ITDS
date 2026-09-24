import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listRecommendations } from '../services/recommendations'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import type { Recommendation } from '../types/recommendation'

const PAGE_SIZE = 25

function RecommendationsContent() {
  const { apiClient } = useAuth()
  const [page, setPage] = useState(1)

  const recommendations = usePolledResource(() => listRecommendations(apiClient, { page, pageSize: PAGE_SIZE }), {
    reloadKey: page,
  })

  const columns: Column<Recommendation>[] = [
    { key: 'title', header: 'Title', render: (recommendation) => recommendation.title },
    { key: 'category', header: 'Category', render: (recommendation) => recommendation.category },
    { key: 'priority', header: 'Priority', render: (recommendation) => <StatusBadge value={recommendation.priority} /> },
    { key: 'status', header: 'Status', render: (recommendation) => <StatusBadge value={recommendation.status} /> },
    { key: 'confidence', header: 'Confidence', render: (recommendation) => recommendation.confidence },
    {
      key: 'requires_human_approval',
      header: 'Approval',
      render: (recommendation) => (recommendation.requires_human_approval ? 'Required' : 'Not required'),
    },
  ]

  return (
    <div className="page">
      <SectionHeader title="Recommendations" description="Automated remediation recommendations awaiting review." />
      <RefreshBar
        lastUpdated={recommendations.lastUpdated}
        refreshing={recommendations.refreshing}
        onRefresh={recommendations.refresh}
      />
      {recommendations.loading ? (
        <LoadingState label="Loading recommendations…" />
      ) : recommendations.error ? (
        <ErrorState message={recommendations.error} onRetry={recommendations.refresh} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={recommendations.data?.items ?? []}
            rowKey={(recommendation) => recommendation.id}
            emptyMessage="No recommendations available."
          />
          {recommendations.data && (
            <Pagination
              page={recommendations.data.page}
              pageSize={recommendations.data.pageSize}
              total={recommendations.data.total}
              onPageChange={setPage}
            />
          )}
        </>
      )}
    </div>
  )
}

export function Recommendations() {
  return (
    <PermissionGate permission="recommendations:read" resource="recommendations">
      <RecommendationsContent />
    </PermissionGate>
  )
}
