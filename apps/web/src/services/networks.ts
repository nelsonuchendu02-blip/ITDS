import type { ApiClient } from './api'
import type { Network, SSID, Site, Subnet, VLAN } from '../types/networks'

export async function listSites(client: ApiClient): Promise<Site[]> {
  return client.get<Site[]>('/sites')
}

export async function listNetworks(client: ApiClient): Promise<Network[]> {
  return client.get<Network[]>('/networks')
}

export async function listSubnets(client: ApiClient): Promise<Subnet[]> {
  return client.get<Subnet[]>('/subnets')
}

export async function listVlans(client: ApiClient): Promise<VLAN[]> {
  return client.get<VLAN[]>('/vlans')
}

export async function listSsids(client: ApiClient): Promise<SSID[]> {
  return client.get<SSID[]>('/ssids')
}
