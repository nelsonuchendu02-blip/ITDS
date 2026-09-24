import type { ApiClient } from './api'
import type { Page } from '../types/common'
import type { RootCauseAnalysis, RootCauseFinding } from '../types/rootCause'

type AnalysisPageResponse = {
  items: RootCauseAnalysis[]
  meta: { page: number; page_size: number; total: number }
}

type FindingPageResponse = {
  items: RootCauseFinding[]
  meta: { page: number; page_size: number; total: number }
}

export async function listRootCauseAnalyses(
  client: ApiClient,
  params: { page?: number; pageSize?: number } = {},
): Promise<Page<RootCauseAnalysis>> {
  const response = await client.get<AnalysisPageResponse>('/root-cause/analyses', {
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

export async function listRootCauseFindings(
  client: ApiClient,
  analysisId: string,
  params: { page?: number; pageSize?: number } = {},
): Promise<Page<RootCauseFinding>> {
  const response = await client.get<FindingPageResponse>(`/root-cause/analyses/${analysisId}/findings`, {
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
