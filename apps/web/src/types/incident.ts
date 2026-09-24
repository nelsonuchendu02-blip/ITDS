export type IncidentSeverity = 'low' | 'medium' | 'high' | 'critical'
export type IncidentPriority = 'low' | 'medium' | 'high' | 'urgent'
export type IncidentStatus = 'open' | 'in_progress' | 'resolved' | 'closed'
export type EscalationStatus = 'open' | 'acknowledged' | 'resolved'

/** apps/api/app/schemas/incident.py::IncidentRead */
export type Incident = {
  id: string
  organization_id: string
  device_id: string | null
  assigned_user_id: string | null
  title: string
  description: string | null
  severity: IncidentSeverity
  priority: IncidentPriority
  status: IncidentStatus
  opened_at: string
  resolved_at: string | null
  created_by_user_id: string | null
  resolved_by_user_id: string | null
  resolution_summary: string | null
  closed_at: string | null
  closed_by_user_id: string | null
  last_escalated_at: string | null
  created_at: string
  updated_at: string
}

/** apps/api/app/schemas/incident.py::EscalationRead */
export type Escalation = {
  id: string
  organization_id: string
  incident_id: string
  escalation_level: number
  reason: string
  status: EscalationStatus
  assigned_to: string | null
  escalated_at: string
  resolved_at: string | null
  created_at: string
  updated_at: string
}
