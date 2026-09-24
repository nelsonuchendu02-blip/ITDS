import type { ApiClient } from './api'
import type { Page } from '../types/common'
import type { MonitoringSummary, MonitoringTarget, Telemetry } from '../types/monitoring'

type TargetPageResponse = {
  items: MonitoringTarget[]
  meta: { page: number; page_size: number; total: number }
}

type TelemetryPageResponse = {
  items: Telemetry[]
  meta: { page: number; page_size: number; total: number }
}

export async function fetchMonitoringSummary(client: ApiClient): Promise<MonitoringSummary> {
  return client.get<MonitoringSummary>('/monitoring/summary')
}

export async function listMonitoringTargets(
  client: ApiClient,
  params: { page?: number; pageSize?: number; enabled?: boolean; healthStatus?: string } = {},
): Promise<Page<MonitoringTarget>> {
  const response = await client.get<TargetPageResponse>('/monitoring/targets', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 25,
    enabled: params.enabled,
    health_status: params.healthStatus,
  })
  return {
    items: response.items,
    page: response.meta.page,
    pageSize: response.meta.page_size,
    total: response.meta.total,
  }
}

export async function listTargetTelemetry(
  client: ApiClient,
  targetId: string,
  params: { page?: number; pageSize?: number } = {},
): Promise<Page<Telemetry>> {
  const response = await client.get<TelemetryPageResponse>(`/monitoring/targets/${targetId}/telemetry`, {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 10,
  })
  return {
    items: response.items,
    page: response.meta.page,
    pageSize: response.meta.page_size,
    total: response.meta.total,
  }
}
