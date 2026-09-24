import { useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listDevices } from '../services/devices'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import { Pagination } from '../components/tables/Pagination'
import { StatusBadge } from '../components/status/StatusBadge'
import { formatDateTime, formatRelativeTime } from '../utils/format'
import type { Device } from '../types/device'

const PAGE_SIZE = 25

function DevicesContent() {
  const { apiClient } = useAuth()
  const [searchParams, setSearchParams] = useSearchParams()
  const [page, setPage] = useState(1)
  const search = searchParams.get('search') ?? ''

  const { data, loading, refreshing, error, lastUpdated, refresh } = usePolledResource(
    () => listDevices(apiClient, { page, pageSize: PAGE_SIZE, search: search || undefined }),
    { reloadKey: `${page}:${search}` },
  )

  const columns: Column<Device>[] = [
    { key: 'hostname', header: 'Hostname', render: (device) => device.hostname },
    { key: 'device_type', header: 'Type', render: (device) => device.device_type },
    { key: 'operating_system', header: 'Operating system', render: (device) => device.operating_system },
    { key: 'ip_address', header: 'IP address', render: (device) => device.ip_address ?? '—' },
    { key: 'status', header: 'Status', render: (device) => <StatusBadge value={device.status} /> },
    {
      key: 'last_seen_at',
      header: 'Last seen',
      render: (device) => (
        <span title={formatDateTime(device.last_seen_at)}>{formatRelativeTime(device.last_seen_at)}</span>
      ),
    },
  ]

  return (
    <div className="page">
      <SectionHeader title="Devices" description="Managed device inventory across the organization." />
      <form
        className="filter-bar"
        role="search"
        onSubmit={(event) => {
          event.preventDefault()
          setPage(1)
        }}
      >
        <label htmlFor="device-search" className="sr-only">
          Search devices
        </label>
        <input
          id="device-search"
          type="search"
          placeholder="Search by hostname…"
          value={search}
          onChange={(event) => {
            const value = event.target.value
            setSearchParams(value ? { search: value } : {})
          }}
        />
      </form>
      <RefreshBar lastUpdated={lastUpdated} refreshing={refreshing} onRefresh={refresh} />

      {loading ? (
        <LoadingState label="Loading devices…" />
      ) : error ? (
        <ErrorState message={error} onRetry={refresh} />
      ) : (
        <>
          <DataTable columns={columns} rows={data?.items ?? []} rowKey={(device) => device.id} emptyMessage="No devices match the current filters." />
          {data && <Pagination page={data.page} pageSize={data.pageSize} total={data.total} onPageChange={setPage} />}
        </>
      )}
    </div>
  )
}

export function Devices() {
  return (
    <PermissionGate permission="devices:read" resource="devices">
      <DevicesContent />
    </PermissionGate>
  )
}
