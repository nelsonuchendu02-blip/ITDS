/** apps/api/app/schemas/root_cause.py::RootCauseAnalysisRead */
export type RootCauseAnalysis = {
  id: string
  organization_id: string
  diagnostic_run_id: string
  device_id: string
  initiated_by_user_id: string | null
  provider: string
  status: 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'
  completed_at: string | null
  cancelled_at: string | null
  error_code: string | null
  created_at: string
  updated_at: string
}

/** apps/api/app/schemas/root_cause.py::RootCauseFindingRead */
export type RootCauseFinding = {
  id: string
  analysis_id: string
  rule_id: string
  severity: 'low' | 'medium' | 'high' | 'critical'
  title: string
  summary: string
  organization_id: string
  device_id: string
  diagnostic_result_id: string
  category: string
  status: 'identified' | 'likely' | 'insufficient_evidence'
  confidence: 'high' | 'medium' | 'low'
  explanation: string
  evidence: Record<string, unknown>
  created_at: string
  updated_at: string
}
