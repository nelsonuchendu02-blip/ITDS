import type { ApiClient } from './api'
import type { Page } from '../types/common'
import type { Recommendation } from '../types/recommendation'

type RecommendationPageResponse = {
  items: Recommendation[]
  meta: { page: number; page_size: number; total: number }
}

export async function listRecommendations(
  client: ApiClient,
  params: { page?: number; pageSize?: number; status?: string } = {},
): Promise<Page<Recommendation>> {
  const response = await client.get<RecommendationPageResponse>('/recommendations', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 25,
    status: params.status,
  })
  return {
    items: response.items,
    page: response.meta.page,
    pageSize: response.meta.page_size,
    total: response.meta.total,
  }
}
