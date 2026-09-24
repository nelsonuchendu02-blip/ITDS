import { useState } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePolledResource } from '../hooks/usePolledResource'
import { listNetworks, listSites, listSsids, listSubnets, listVlans } from '../services/networks'
import { PermissionGate } from '../components/feedback/PermissionGate'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { DataTable, type Column } from '../components/tables/DataTable'
import type { Network, SSID, Site, Subnet, VLAN } from '../types/networks'

type Tab = 'sites' | 'networks' | 'subnets' | 'vlans' | 'ssids'

const TABS: { id: Tab; label: string }[] = [
  { id: 'sites', label: 'Sites' },
  { id: 'networks', label: 'Networks' },
  { id: 'subnets', label: 'Subnets' },
  { id: 'vlans', label: 'VLANs' },
  { id: 'ssids', label: 'SSIDs' },
]

const siteColumns: Column<Site>[] = [
  { key: 'name', header: 'Name', render: (site) => site.name },
  { key: 'address', header: 'Address', render: (site) => site.address ?? '—' },
  { key: 'description', header: 'Description', render: (site) => site.description ?? '—' },
]

const networkColumns: Column<Network>[] = [
  { key: 'name', header: 'Name', render: (network) => network.name },
  { key: 'site_id', header: 'Site', render: (network) => network.site_id ?? '—' },
  { key: 'description', header: 'Description', render: (network) => network.description ?? '—' },
]

const subnetColumns: Column<Subnet>[] = [
  { key: 'cidr', header: 'CIDR', render: (subnet) => subnet.cidr },
  { key: 'gateway', header: 'Gateway', render: (subnet) => subnet.gateway ?? '—' },
  { key: 'network_id', header: 'Network', render: (subnet) => subnet.network_id ?? '—' },
]

const vlanColumns: Column<VLAN>[] = [
  { key: 'vlan_id', header: 'VLAN ID', render: (vlan) => vlan.vlan_id, align: 'right' },
  { key: 'name', header: 'Name', render: (vlan) => vlan.name },
  { key: 'network_id', header: 'Network', render: (vlan) => vlan.network_id ?? '—' },
]

const ssidColumns: Column<SSID>[] = [
  { key: 'ssid', header: 'SSID', render: (ssid) => ssid.ssid },
  { key: 'security', header: 'Security', render: (ssid) => ssid.security ?? '—' },
  { key: 'network_id', header: 'Network', render: (ssid) => ssid.network_id ?? '—' },
]

function NetworksContent() {
  const { apiClient } = useAuth()
  const [tab, setTab] = useState<Tab>('sites')

  const sites = usePolledResource(() => listSites(apiClient), { enabled: tab === 'sites' })
  const networks = usePolledResource(() => listNetworks(apiClient), { enabled: tab === 'networks' })
  const subnets = usePolledResource(() => listSubnets(apiClient), { enabled: tab === 'subnets' })
  const vlans = usePolledResource(() => listVlans(apiClient), { enabled: tab === 'vlans' })
  const ssids = usePolledResource(() => listSsids(apiClient), { enabled: tab === 'ssids' })

  const active = { sites, networks, subnets, vlans, ssids }[tab]

  return (
    <div className="page">
      <SectionHeader title="Networks" description="Site, network, subnet, VLAN, and SSID inventory." />
      <div className="tab-bar" role="tablist">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            aria-selected={tab === entry.id}
            className={`tab-button${tab === entry.id ? ' is-active' : ''}`}
            onClick={() => setTab(entry.id)}
          >
            {entry.label}
          </button>
        ))}
      </div>
      <RefreshBar lastUpdated={active.lastUpdated} refreshing={active.refreshing} onRefresh={active.refresh} />

      {active.loading ? (
        <LoadingState label={`Loading ${tab}…`} />
      ) : active.error ? (
        <ErrorState message={active.error} onRetry={active.refresh} />
      ) : (
        <>
          {tab === 'sites' && (
            <DataTable columns={siteColumns} rows={sites.data ?? []} rowKey={(site) => site.id} emptyMessage="No sites configured." />
          )}
          {tab === 'networks' && (
            <DataTable
              columns={networkColumns}
              rows={networks.data ?? []}
              rowKey={(network) => network.id}
              emptyMessage="No networks configured."
            />
          )}
          {tab === 'subnets' && (
            <DataTable columns={subnetColumns} rows={subnets.data ?? []} rowKey={(subnet) => subnet.id} emptyMessage="No subnets configured." />
          )}
          {tab === 'vlans' && (
            <DataTable columns={vlanColumns} rows={vlans.data ?? []} rowKey={(vlan) => vlan.id} emptyMessage="No VLANs configured." />
          )}
          {tab === 'ssids' && (
            <DataTable columns={ssidColumns} rows={ssids.data ?? []} rowKey={(ssid) => ssid.id} emptyMessage="No SSIDs configured." />
          )}
        </>
      )}
    </div>
  )
}

export function Networks() {
  return (
    <PermissionGate permission="networks:read" resource="network inventory">
      <NetworksContent />
    </PermissionGate>
  )
}
