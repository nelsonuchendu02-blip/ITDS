/** apps/api/app/schemas/remediation.py::RemediationActionRead */
export type RemediationAction = {
  id: string
  sequence: number
  action_key: string
  parameters: Record<string, unknown>
  status: 'pending' | 'ready' | 'executing' | 'succeeded' | 'failed' | 'skipped' | 'cancelled'
  result: Record<string, unknown> | null
}

/** apps/api/app/schemas/remediation.py::RemediationVerificationRead */
export type RemediationVerification = {
  id: string
  device_id: string
  check_key: string
  status: 'pending' | 'passed' | 'failed' | 'inconclusive'
  observed: Record<string, unknown> | null
  details: string | null
  verified_at: string | null
}

/** apps/api/app/schemas/remediation.py::RemediationPlanRead */
export type RemediationPlan = {
  id: string
  organization_id: string
  device_id: string
  recommendation_id: string | null
  root_cause_finding_id: string | null
  title: string
  rationale: string
  plan_hash: string
  dry_run: boolean
  status:
    | 'draft'
    | 'pending_approval'
    | 'approved'
    | 'rejected'
    | 'queued'
    | 'executing'
    | 'succeeded'
    | 'failed'
    | 'cancelled'
    | 'verification_required'
    | 'verified'
  verification_status: 'pending' | 'passed' | 'failed' | 'inconclusive'
  approved_at: string | null
  executed_at: string | null
  created_at: string
  updated_at: string
  actions: RemediationAction[]
  verifications: RemediationVerification[]
}
