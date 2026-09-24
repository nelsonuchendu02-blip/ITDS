import type { ApiClient } from './api'
import type { RemediationPlan } from '../types/remediation'

type RemediationPlanListResponse = {
  items: RemediationPlan[]
  total: number
}

export async function listRemediationPlans(
  client: ApiClient,
  params: { limit?: number; offset?: number } = {},
): Promise<{ items: RemediationPlan[]; total: number }> {
  const response = await client.get<RemediationPlanListResponse>('/remediation/plans', {
    limit: params.limit ?? 50,
    offset: params.offset ?? 0,
  })
  return response
}
