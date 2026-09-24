/** apps/api/app/schemas/inventory.py — shared inventory resource shapes. */
export type Site = {
  id: string
  organization_id: string
  name: string
  description: string | null
  address: string | null
  created_at: string
  updated_at: string
}

export type Network = {
  id: string
  organization_id: string
  site_id: string | null
  name: string
  description: string | null
  created_at: string
  updated_at: string
}

export type Subnet = {
  id: string
  organization_id: string
  network_id: string | null
  cidr: string
  gateway: string | null
  created_at: string
  updated_at: string
}

export type VLAN = {
  id: string
  organization_id: string
  network_id: string | null
  vlan_id: number
  name: string
  created_at: string
  updated_at: string
}

export type SSID = {
  id: string
  organization_id: string
  network_id: string | null
  ssid: string
  security: string | null
  created_at: string
  updated_at: string
}
