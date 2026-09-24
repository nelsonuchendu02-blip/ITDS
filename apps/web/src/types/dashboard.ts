import type { MonitoringSummary } from './monitoring'

/**
 * apps/api/app/schemas/dashboard.py::DashboardOverview
 *
 * Each section is present only when the requesting user holds the
 * corresponding module's read permission. A missing section means the
 * caller cannot view that data - it is never reported as a zero count.
 */
export type DashboardOverview = {
  generated_at: string
  devices: { total: number } | null
  monitoring: MonitoringSummary | null
  agents: { total: number; active: number } | null
  incidents: { open: number; in_progress: number } | null
  discovery: { total: number; running: number; pending: number; completed: number; failed: number } | null
  recommendations: { total: number; pending: number } | null
}
