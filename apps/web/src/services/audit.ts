import type { ApiClient } from './api'
import type { Page } from '../types/common'
import type { AuditEvent } from '../types/audit'

type AuditEventPageResponse = {
  items: AuditEvent[]
  meta: { page: number; page_size: number; total: number }
}

export async function listAuditEvents(
  client: ApiClient,
  params: { page?: number; pageSize?: number; eventType?: string } = {},
): Promise<Page<AuditEvent>> {
  const response = await client.get<AuditEventPageResponse>('/audit-events', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 25,
    event_type: params.eventType,
  })
  return {
    items: response.items,
    page: response.meta.page,
    pageSize: response.meta.page_size,
    total: response.meta.total,
  }
}
