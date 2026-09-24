/** apps/api/app/schemas/discovery.py::DiscoveryJobRead */
export type DiscoveryJob = {
  id: string
  organization_id: string
  created_by_user_id: string | null
  provider: string
  target_type: string
  target_definition: string
  target_count: number
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  error_code: string | null
  created_at: string
  updated_at: string
}

/** apps/api/app/schemas/discovery.py::DiscoveryResultRead */
export type DiscoveryResult = {
  id: string
  discovery_job_id: string
  organization_id: string
  target_ip: string
  discovered_hostname: string | null
  discovered_device_type: string | null
  discovered_operating_system: string | null
  provider: string
  status: 'discovered' | 'not_reachable' | 'failed'
  reconciliation_status: 'unmatched' | 'matched' | 'conflict'
  matched_device_id: string | null
  discovered_at: string
  result_metadata: Record<string, unknown> | null
}
