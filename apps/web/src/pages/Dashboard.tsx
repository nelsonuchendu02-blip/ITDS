import { useMemo } from 'react'
import { useAuth } from '../app/providers/AuthProvider'
import { usePermission } from '../hooks/usePermission'
import { usePolledResource } from '../hooks/usePolledResource'
import { fetchDashboardOverview } from '../services/dashboard'
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
  const canReadDashboard =
    canReadDevices || canReadMonitoring || canReadAgents || canReadIncidents || canReadDiscovery || canReadRecommendations

  // Aggregate, organization-wide KPIs come from one endpoint: the paginated
  // module APIs below only return a page at a time, so they cannot answer
  // "how many are open/active/pending across the whole organization"
  // accurately. See docs/api/dashboard.md.
  const overview = usePolledResource(() => fetchDashboardOverview(apiClient), { enabled: canReadDashboard })

  // Detailed, permission-gated feeds still use their own module endpoints;
  // they drive the recent-activity list and per-module tables, not the KPIs.
  const agents = usePolledResource(() => listAgents(apiClient), { enabled: canReadAgents })
  const incidents = usePolledResource(() => listIncidents(apiClient, { pageSize: 10 }), { enabled: canReadIncidents })
  const discoveryJobs = usePolledResource(() => listDiscoveryJobs(apiClient, { pageSize: 5 }), {
    enabled: canReadDiscovery,
  })
  const recommendations = usePolledResource(() => listRecommendations(apiClient, { pageSize: 5, status: 'pending' }), {
    enabled: canReadRecommendations,
  })

  // Every resource that contributes visible dashboard content must be
  // included here, not just the KPI-driving ones - otherwise the page can
  // render "no recent activity" while discovery/recommendations are still
  // loading in the background.
  const anyLoading =
    (canReadDashboard && overview.loading) ||
    (canReadAgents && agents.loading) ||
    (canReadIncidents && incidents.loading) ||
    (canReadDiscovery && discoveryJobs.loading) ||
    (canReadRecommendations && recommendations.loading)

  const anyRefreshing =
    (canReadDashboard && overview.refreshing) ||
    (canReadAgents && agents.refreshing) ||
    (canReadIncidents && incidents.refreshing) ||
    (canReadDiscovery && discoveryJobs.refreshing) ||
    (canReadRecommendations && recommendations.refreshing)

  const lastUpdated = useMemo(() => {
    const dates = [overview, agents, incidents, discoveryJobs, recommendations]
      .map((resource) => resource.lastUpdated)
      .filter((value): value is Date => value !== null)
    if (dates.length === 0) return null
    return new Date(Math.max(...dates.map((date) => date.getTime())))
  }, [overview.lastUpdated, agents.lastUpdated, incidents.lastUpdated,
      discoveryJobs.lastUpdated, recommendations.lastUpdated])

  function refreshAll() {
    if (canReadDashboard) void overview.refresh()
    if (canReadAgents) void agents.refresh()
    if (canReadIncidents) void incidents.refresh()
    if (canReadDiscovery) void discoveryJobs.refresh()
    if (canReadRecommendations) void recommendations.refresh()
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
            value={overview.error ? '—' : (overview.data?.devices?.total ?? '—')}
            loading={overview.loading}
            hint={overview.error ?? undefined}
          />
        )}
        {canReadMonitoring && (
          <KpiCard
            label="Monitored targets"
            value={overview.error ? '—' : (overview.data?.monitoring?.total_targets ?? '—')}
            loading={overview.loading}
            hint={overview.error ?? `${overview.data?.monitoring?.enabled_targets ?? 0} enabled`}
          />
        )}
        {canReadAgents && (
          <KpiCard
            label="Active agents"
            value={overview.error ? '—' : (overview.data?.agents?.active ?? '—')}
            loading={overview.loading}
            tone="ok"
            hint={overview.error ?? `${overview.data?.agents?.total ?? 0} enrolled`}
          />
        )}
        {canReadIncidents && (
          <KpiCard
            label="Open incidents"
            value={
              overview.error
                ? '—'
                : overview.data?.incidents
                  ? overview.data.incidents.open + overview.data.incidents.in_progress
                  : '—'
            }
            loading={overview.loading}
            tone={(overview.data?.incidents?.open ?? 0) > 0 ? 'danger' : 'ok'}
            hint={overview.error ?? undefined}
          />
        )}
        {canReadDiscovery && (
          <KpiCard
            label="Discovery jobs running"
            value={overview.error ? '—' : (overview.data?.discovery?.running ?? '—')}
            loading={overview.loading}
            hint={overview.error ?? `${overview.data?.discovery?.total ?? 0} total`}
          />
        )}
        {canReadRecommendations && (
          <KpiCard
            label="Pending recommendations"
            value={overview.error ? '—' : (overview.data?.recommendations?.pending ?? '—')}
            loading={overview.loading}
            tone={(overview.data?.recommendations?.pending ?? 0) > 0 ? 'warn' : 'ok'}
            hint={overview.error ?? `${overview.data?.recommendations?.total ?? 0} total`}
          />
        )}
      </div>

      <div className="dashboard-grid">
        {canReadMonitoring && (
          <section className="panel">
            <SectionHeader title="Health distribution" />
            {overview.error ? (
              <ErrorState message={overview.error} onRetry={() => void overview.refresh()} />
            ) : overview.loading ? (
              <LoadingState />
            ) : overview.data?.monitoring ? (
              <HealthDistributionChart
                healthy={overview.data.monitoring.healthy}
                degraded={overview.data.monitoring.degraded}
                unhealthy={overview.data.monitoring.unhealthy}
                offline={overview.data.monitoring.offline}
                unknown={overview.data.monitoring.unknown}
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

      {!canReadDashboard && (
        <EmptyState
          title="No dashboard data available"
          description="Your account does not have permission to view any operations summaries."
        />
      )}

      <p className="dashboard-footnote">Data last refreshed {lastUpdated ? formatRelativeTime(lastUpdated.toISOString()) : 'never'}.</p>
    </div>
  )
}
