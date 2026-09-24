/** apps/api/app/schemas/management.py::AuditEventRead */
export type AuditEvent = {
  id: string
  organization_id: string | null
  actor_user_id: string | null
  event_type: string
  resource_type: string
  resource_id: string | null
  action: string
  result: string
  event_metadata: Record<string, unknown> | null
  created_at: string
}
