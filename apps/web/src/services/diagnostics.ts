import type { ApiClient } from './api'
import type { Page } from '../types/common'
import type { DiagnosticResult, DiagnosticRun } from '../types/diagnostics'

type DiagnosticRunPageResponse = {
  items: DiagnosticRun[]
  meta: { page: number; page_size: number; total: number }
}

type DiagnosticResultPageResponse = {
  items: DiagnosticResult[]
  meta: { page: number; page_size: number; total: number }
}

export async function listDiagnosticRuns(
  client: ApiClient,
  params: { page?: number; pageSize?: number } = {},
): Promise<Page<DiagnosticRun>> {
  const response = await client.get<DiagnosticRunPageResponse>('/diagnostics/runs', {
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

export async function listDiagnosticResults(
  client: ApiClient,
  runId: string,
  params: { page?: number; pageSize?: number } = {},
): Promise<Page<DiagnosticResult>> {
  const response = await client.get<DiagnosticResultPageResponse>(`/diagnostics/runs/${runId}/results`, {
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
