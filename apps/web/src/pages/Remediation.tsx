import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listRemediationPlans } from '../services/remediation'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime } from '../utils/format'
import type { RemediationPlan } from '../types/remediation'

const PAGE_SIZE = 25

function RemediationContent() {
  const { apiClient } = useAuth()
  const [page, setPage] = useState(1)
  const [expandedPlanId, setExpandedPlanId] = useState<string | null>(null)

  const { data, loading, refreshing, error, lastUpdated, refresh } = usePolledResource(
    () => listRemediationPlans(apiClient, { limit: PAGE_SIZE, offset: (page - 1) * PAGE_SIZE }),
    { reloadKey: page },
  )

  const columns: Column<RemediationPlan>[] = [
    { key: 'title', header: 'Plan', render: (plan) => plan.title },
    { key: 'status', header: 'Status', render: (plan) => <StatusBadge value={plan.status} /> },
    { key: 'verification_status', header: 'Verification', render: (plan) => <StatusBadge value={plan.verification_status} /> },
    { key: 'dry_run', header: 'Dry run', render: (plan) => (plan.dry_run ? 'Yes' : 'No') },
    { key: 'created_at', header: 'Created', render: (plan) => formatDateTime(plan.created_at) },
  ]

  const expandedPlan = data?.items.find((plan) => plan.id === expandedPlanId) ?? null

  return (
    <div className="page">
      <SectionHeader title="Remediation" description="Remediation plans, their actions, and verification checks." />
      <RefreshBar lastUpdated={lastUpdated} refreshing={refreshing} onRefresh={refresh} />
      {loading ? (
        <LoadingState label="Loading remediation plans…" />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : (
        <>
          <DataTable
            columns={columns}
            rows={data?.items ?? []}
            rowKey={(plan) => plan.id}
            onRowClick={(plan) => setExpandedPlanId((current) => (current === plan.id ? null : plan.id))}
            emptyMessage="No remediation plans have been created."
          />
          {data && <Pagination page={page} pageSize={PAGE_SIZE} total={data.total} onPageChange={setPage} />}
        </>
      )}

      {expandedPlan && (
        <section className="panel">
          <SectionHeader title={expandedPlan.title} description={expandedPlan.rationale} />
          <h3>Actions</h3>
          {expandedPlan.actions.length === 0 ? (
            <p className="state-description">No actions defined.</p>
          ) : (
            <ul className="remediation-list">
              {expandedPlan.actions.map((action) => (
                <li key={action.id} className="remediation-item">
                  <span>#{action.sequence}</span>
                  <span>{action.action_key}</span>
                  <StatusBadge value={action.status} />
                </li>
              ))}
            </ul>
          )}
          <h3>Verifications</h3>
          {expandedPlan.verifications.length === 0 ? (
            <p className="state-description">No verification checks defined.</p>
          ) : (
            <ul className="remediation-list">
              {expandedPlan.verifications.map((verification) => (
                <li key={verification.id} className="remediation-item">
                  <span>{verification.check_key}</span>
                  <StatusBadge value={verification.status} />
                  <span className="telemetry-time">{formatDateTime(verification.verified_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  )
}

export function Remediation() {
  return (
    <PermissionGate permission="remediation:read" resource="remediation plans">
      <RemediationContent />
    </PermissionGate>
  )
}
