export type AgentStatus = 'pending' | 'active' | 'offline' | 'revoked' | 'retired'

/** apps/api/app/schemas/agent.py::AgentRead */
export type Agent = {
  id: string
  organization_id: string
  device_id: string | null
  agent_name: string
  agent_version: string | null
  platform: string
  status: AgentStatus
  enrolled_at: string | null
  last_seen_at: string | null
  last_ip_address: string | null
  last_error_code: string | null
  created_at: string
  updated_at: string
}
