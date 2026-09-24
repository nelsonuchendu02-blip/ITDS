/** apps/api/app/schemas/diagnostics.py::DiagnosticRunRead */
export type DiagnosticRun = {
  id: string
  organization_id: string
  device_id: string
  incident_id: string | null
  diagnostic_type: string
  provider: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  started_at: string | null
  completed_at: string | null
  cancelled_at: string | null
  error_code: string | null
  created_at: string
  updated_at: string
}

/** apps/api/app/schemas/diagnostics.py::DiagnosticResultRead */
export type DiagnosticResult = {
  id: string
  diagnostic_run_id: string
  organization_id: string
  device_id: string
  check_identifier: string
  check_type: 'connectivity' | 'configuration' | 'security' | 'performance'
  status: 'pass' | 'warn' | 'fail'
  severity: 'info' | 'low' | 'medium' | 'high' | 'critical'
  observed_value: Record<string, unknown> | null
  expected_value: Record<string, unknown> | null
  message: string | null
  evidence: string | null
  title: string
  summary: string | null
  recommendation: string | null
  checked_at: string
  created_at: string
  updated_at: string
}
