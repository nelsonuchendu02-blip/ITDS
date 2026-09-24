/** apps/api/app/schemas/recommendation.py::RecommendationRead */
export type Recommendation = {
  id: string
  organization_id: string
  device_id: string | null
  incident_id: string | null
  diagnostic_result_id: string | null
  root_cause_finding_id: string | null
  root_cause_analysis_id: string | null
  title: string
  description: string | null
  rationale: string | null
  rule_id: string
  category: string
  severity: string
  summary: string
  expected_effect: string
  confidence: string
  remediation_type: string
  requires_human_approval: boolean
  reviewed_at: string | null
  rejection_reason: string | null
  implemented_at: string | null
  implementation_notes: string | null
  priority: 'low' | 'medium' | 'high'
  status: 'pending' | 'reviewed' | 'accepted' | 'rejected' | 'implemented'
  created_at: string
  updated_at: string
}
