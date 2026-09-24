import type { ApiClient } from './api'
import type { DashboardOverview } from '../types/dashboard'

/**
 * Organization-scoped, permission-aware aggregate KPIs for the operations
 * dashboard. Backed by GET /api/v1/dashboard/overview - see
 * apps/api/app/services/dashboard.py for the authorization boundary.
 */
export async function fetchDashboardOverview(client: ApiClient): Promise<DashboardOverview> {
  return client.get<DashboardOverview>('/dashboard/overview')
}
