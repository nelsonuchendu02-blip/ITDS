import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listAuditEvents } from '../services/audit'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime } from '../utils/format'
import type { AuditEvent } from '../types/audit'

const PAGE_SIZE = 25

function AuditContent() {
  const { apiClient } = useAuth()
  const [page, setPage] = useState(1)

  const { data, loading, refreshing, error, lastUpdated, refresh } = usePolledResource(
    () => listAuditEvents(apiClient, { page, pageSize: PAGE_SIZE }),
    { reloadKey: page },
  )

  const columns: Column<AuditEvent>[] = [
    { key: 'event_type', header: 'Event', render: (event) => event.event_type },
    { key: 'resource_type', header: 'Resource', render: (event) => event.resource_type },
    { key: 'action', header: 'Action', render: (event) => event.action },
    { key: 'result', header: 'Result', render: (event) => <StatusBadge value={event.result} /> },
    { key: 'created_at', header: 'Timestamp', render: (event) => formatDateTime(event.created_at) },
  ]

  return (
    <div className="page">
      <SectionHeader title="Audit log" description="Security-relevant lifecycle and authentication events." />
      <RefreshBar lastUpdated={lastUpdated} refreshing={refreshing} onRefresh={refresh} />
      {loading ? (
        <LoadingState label="Loading audit events…" />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : (
        <>
          <DataTable columns={columns} rows={data?.items ?? []} rowKey={(event) => event.id} emptyMessage="No audit events recorded." />
          {data && <Pagination page={data.page} pageSize={data.pageSize} total={data.total} onPageChange={setPage} />}
        </>
      )}
    </div>
  )
}

export function Audit() {
  return (
    <PermissionGate permission="audit:read" resource="the audit log">
      <AuditContent />
    </PermissionGate>
  )
}
