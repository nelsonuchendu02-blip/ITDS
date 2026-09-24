import type { ApiClient } from './api'
import type { Page } from '../types/common'
import type { Device } from '../types/device'

export type DeviceListParams = {
  page?: number
  pageSize?: number
  search?: string
  status?: string
  deviceType?: string
}

type DevicePageResponse = {
  items: Device[]
  meta: { page: number; page_size: number; total: number }
}

export async function listDevices(client: ApiClient, params: DeviceListParams = {}): Promise<Page<Device>> {
  const response = await client.get<DevicePageResponse>('/devices', {
    page: params.page ?? 1,
    page_size: params.pageSize ?? 25,
    search: params.search,
    status: params.status,
    device_type: params.deviceType,
  })
  return {
    items: response.items,
    page: response.meta.page,
    pageSize: response.meta.page_size,
    total: response.meta.total,
  }
}
