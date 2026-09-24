import type { ApiClient } from './api'
import type { Page } from '../types/common'
import type { Escalation, Incident } from '../types/incident'

type IncidentPageResponse = {
  items: Incident[]
  total: number
  page: number
  page_size: number
}

export async function listIncidents(
  client: ApiClient,
  params: { page?: number; pageSize?: number } = {},
): Promise<Page<Incident>> {
  const response = await client.get<IncidentPageResponse>('/incidents', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 25,
  })
  return {
    items: response.items,
    page: response.page,
    pageSize: response.page_size,
    total: response.total,
  }
}

export async function listIncidentEscalations(client: ApiClient, incidentId: string): Promise<Escalation[]> {
  return client.get<Escalation[]>(`/incidents/${incidentId}/escalations`)
}
