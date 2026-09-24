export type HealthStatus = 'healthy' | 'degraded' | 'unhealthy' | 'offline' | 'unknown'

/** apps/api/app/schemas/monitoring.py::MonitoringTargetRead */
export type MonitoringTarget = {
  id: string
  organization_id: string
  device_id: string
  enabled: boolean
  check_interval_seconds: number
  offline_after_seconds: number
  last_seen_at: string | null
  last_status_at: string | null
  last_error_code: string | null
  health_status: HealthStatus
  created_at: string
  updated_at: string
}

/** apps/api/app/schemas/monitoring.py::TelemetryRead */
export type Telemetry = {
  id: string
  organization_id: string
  target_id: string
  device_id: string
  observed_at: string
  received_at: string
  health_status: HealthStatus
  latency_ms: number | null
  packet_loss_percent: number | null
  cpu_percent: number | null
  memory_percent: number | null
  disk_percent: number | null
  uptime_seconds: number | null
  source: string
  details: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

/** apps/api/app/schemas/monitoring.py::MonitoringSummary */
export type MonitoringSummary = {
  total_targets: number
  enabled_targets: number
  disabled_targets: number
  healthy: number
  degraded: number
  unhealthy: number
  offline: number
  unknown: number
}
