import type { ApiClient } from './api'
import type { Page } from '../types/common'
import type { DiscoveryJob, DiscoveryResult } from '../types/discovery'

type DiscoveryJobPageResponse = {
  items: DiscoveryJob[]
  meta: { page: number; page_size: number; total: number }
}

type DiscoveryResultPageResponse = {
  items: DiscoveryResult[]
  meta: { page: number; page_size: number; total: number }
}

export async function listDiscoveryJobs(
  client: ApiClient,
  params: { page?: number; pageSize?: number } = {},
): Promise<Page<DiscoveryJob>> {
  const response = await client.get<DiscoveryJobPageResponse>('/discovery/jobs', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 25,
  })
  return {
    items: response.items,
    page: response.meta.page,
    pageSize: response.meta.page_size,
    total: response.meta.total,
  }
}

export async function listDiscoveryResults(
  client: ApiClient,
  jobId: string,
  params: { page?: number; pageSize?: number } = {},
): Promise<Page<DiscoveryResult>> {
  const response = await client.get<DiscoveryResultPageResponse>(`/discovery/jobs/${jobId}/results`, {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 25,
  })
  return {
    items: response.items,
    page: response.meta.page,
    pageSize: response.meta.page_size,
    total: response.meta.total,
  }
}
