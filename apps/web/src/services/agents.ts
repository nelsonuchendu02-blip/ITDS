import type { ApiClient } from './api'
import type { Agent } from '../types/agent'

export async function listAgents(client: ApiClient): Promise<Agent[]> {
  return client.get<Agent[]>('/agents')
}
