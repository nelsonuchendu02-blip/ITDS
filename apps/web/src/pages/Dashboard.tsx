import { useMemo } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePermission } from '../hooks/usePermission'
import { usePolledResource } from '../hooks/usePolledResource'
import { fetchMonitoringSummary } from '../services/monitoring'
import { listDevices } from '../services/devices'
import { listAgents } from '../services/agents'
import { listIncidents } from '../services/incidents'
import { listDiscoveryJobs } from '../services/discovery'
import { listRecommendations } from '../services/recommendations'
import { KpiCard } from '../components/dashboard/KpiCard'
import { HealthDistributionChart } from '../components/dashboard/HealthDistributionChart'
import { RecentActivity, type ActivityItem } from '../components/dashboard/RecentActivity'
import { SectionHeader } from '../components/dashboard/SectionHeader'
import { RefreshBar } from '../components/dashboard/RefreshBar'
import { LoadingState } from '../components/feedback/LoadingState'
import { ErrorState } from '../components/feedback/ErrorState'
import { EmptyState } from '../components/feedback/EmptyState'
import { formatRelativeTime } from '../utils/format'

export function Dashboard() {
  const { apiClient } = useAuth()
  const canReadDevices = usePermission('devices:read')
  const canReadMonitoring = usePermission('monitoring:read')
  const canReadAgents = usePermission('agents:read')
  const canReadIncidents = usePermission('incidents:read')
  const canReadDiscovery = usePermission('discovery:read')
  const canReadRecommendations = usePermission('recommendations:read')

  const devices = usePolledResource(() => listDevices(apiClient, { pageSize: 1 }), { enabled: canReadDevices })
  const monitoring = usePolledResource(() => fetchMonitoringSummary(apiClient), { enabled: canReadMonitoring })
  const agents = usePolledResource(() => listAgents(apiClient), { enabled: canReadAgents })
  const incidents = usePolledResource(() => listIncidents(apiClient, { pageSize: 10 }), { enabled: canReadIncidents })
  const discoveryJobs = usePolledResource(() => listDiscoveryJobs(apiClient, { pageSize: 5 }), {
    enabled: canReadDiscovery,
  })
  const recommendations = usePolledResource(() => listRecommendations(apiClient, { pageSize: 5, status: 'pending' }), {
    enabled: canReadRecommendations,
  })

  const anyLoading =
    (canReadDevices && devices.loading) ||
    (canReadMonitoring && monitoring.loading) ||
    (canReadAgents && agents.loading) ||
    (canReadIncidents && incidents.loading)

  const anyRefreshing =
    devices.refreshing || monitoring.refreshing || agents.refreshing || incidents.refreshing ||
    discoveryJobs.refreshing || recommendations.refreshing

  const lastUpdated = useMemo(() => {
    const dates = [devices, monitoring, agents, incidents, discoveryJobs, recommendations]
      .map((resource) => resource.lastUpdated)
      .filter((value): value is Date => value !== null)
    if (dates.length === 0) return null
    return new Date(Math.max(...dates.map((date) => date.getTime())))
  }, [devices.lastUpdated, monitoring.lastUpdated, agents.lastUpdated, incidents.lastUpdated,
      discoveryJobs.lastUpdated, recommendations.lastUpdated])

  function refreshAll() {
    void devices.refresh()
    void monitoring.refresh()
    void agents.refresh()
    void incidents.refresh()
    void discoveryJobs.refresh()
    void recommendations.refresh()
  }

  const activity: ActivityItem[] = useMemo(() => {
    const items: ActivityItem[] = []
    for (const incident of incidents.data?.items ?? []) {
      items.push({
        id: `incident-${incident.id}`,
        source: 'Incident',
        label: `${incident.title} (${incident.status})`,
        timestamp: incident.updated_at,
        tone: incident.status === 'open' ? 'danger' : incident.status === 'in_progress' ? 'warn' : 'ok',
      })
    }
    for (const job of discoveryJobs.data?.items ?? []) {
      items.push({
        id: `discovery-${job.id}`,
        source: 'Discovery',
        label: `${job.provider} scan ${job.status}`,
        timestamp: job.updated_at,
        tone: job.status === 'failed' ? 'danger' : job.status === 'completed' ? 'ok' : 'info',
      })
    }
    for (const recommendation of recommendations.data?.items ?? []) {
      items.push({
        id: `recommendation-${recommendation.id}`,
        source: 'Recommendation',
        label: recommendation.title,
        timestamp: recommendation.updated_at,
        tone: recommendation.priority === 'high' ? 'danger' : recommendation.priority === 'medium' ? 'warn' : 'info',
      })
    }
    for (const agent of agents.data ?? []) {
      if (!agent.last_seen_at) continue
      items.push({
        id: `agent-${agent.id}`,
        source: 'Agent',
        label: `${agent.agent_name} (${agent.status})`,
        timestamp: agent.last_seen_at,
        tone: agent.status === 'active' ? 'ok' : agent.status === 'offline' ? 'neutral' : 'warn',
      })
    }
    return items.slice(0, 25)
  }, [incidents.data, discoveryJobs.data, recommendations.data, agents.data])

  return (
    <div className="page dashboard-page">
      <SectionHeader
        title="Operations overview"
        description="Live status across devices, monitoring, agents, and incidents."
      />
      <RefreshBar lastUpdated={lastUpdated} refreshing={anyRefreshing} onRefresh={refreshAll} />

      {anyLoading && <LoadingState label="Loading dashboard data…" />}

      <div className="kpi-grid">
        {canReadDevices && (
          <KpiCard
            label="Total devices"
            value={devices.error ? '—' : (devices.data?.total ?? '—')}
            loading={devices.loading}
            hint={devices.error ?? undefined}
          />
        )}
        {canReadMonitoring && (
          <KpiCard
            label="Monitored targets"
            value={monitoring.error ? '—' : (monitoring.data?.total_targets ?? '—')}
            loading={monitoring.loading}
            hint={monitoring.error ?? `${monitoring.data?.enabled_targets ?? 0} enabled`}
          />
        )}
        {canReadAgents && (
          <KpiCard
            label="Active agents"
            value={agents.error ? '—' : (agents.data?.filter((a) => a.status === 'active').length ?? '—')}
            loading={agents.loading}
            tone="ok"
            hint={agents.error ?? `${agents.data?.length ?? 0} enrolled`}
          />
        )}
        {canReadIncidents && (
          <KpiCard
            label="Open incidents"
            value={
              incidents.error
                ? '—'
                : (incidents.data?.items.filter((i) => i.status === 'open' || i.status === 'in_progress').length ?? '—')
            }
            loading={incidents.loading}
            tone={
              (incidents.data?.items.filter((i) => i.status === 'open').length ?? 0) > 0 ? 'danger' : 'ok'
            }
            hint={incidents.error ?? undefined}
          />
        )}
      </div>

      <div className="dashboard-grid">
        {canReadMonitoring && (
          <section className="panel">
            <SectionHeader title="Health distribution" />
            {monitoring.error ? (
              <ErrorState message={monitoring.error} onRetry={() => void monitoring.refresh()} />
            ) : monitoring.loading ? (
              <LoadingState />
            ) : monitoring.data ? (
              <HealthDistributionChart
                healthy={monitoring.data.healthy}
                degraded={monitoring.data.degraded}
                unhealthy={monitoring.data.unhealthy}
                offline={monitoring.data.offline}
                unknown={monitoring.data.unknown}
              />
            ) : null}
          </section>
        )}

        <section className="panel">
          <SectionHeader title="Recent activity" />
          {activity.length === 0 ? (
            <EmptyState title="No recent activity" description="Activity will appear once data loads." />
          ) : (
            <RecentActivity items={activity} />
          )}
        </section>
      </div>

      {!canReadDevices && !canReadMonitoring && !canReadAgents && !canReadIncidents && (
        <EmptyState
          title="No dashboard data available"
          description="Your account does not have permission to view any operations summaries."
        />
      )}

      <p className="dashboard-footnote">Data last refreshed {lastUpdated ? formatRelativeTime(lastUpdated.toISOString()) : 'never'}.</p>
    </div>
  )
}
