/** Device inventory (management view: apps/api/app/schemas/device_management.py). */
export type Device = {
  id: string
  organization_id: string
  hostname: string
  device_type: string
  operating_system: string
  ip_address: string | null
  status: 'active' | 'inactive' | 'retired'
  last_seen_at: string | null
  created_at: string
  updated_at: string
}
