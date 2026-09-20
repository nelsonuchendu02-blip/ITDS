export type HealthStatus = {
  status: string
  service: string
  version: string
  environment: string
}

export async function fetchHealthStatus(baseUrl: string): Promise<HealthStatus> {
  const response = await fetch(`${baseUrl}/api/health`)
  if (!response.ok) {
    throw new Error(`Health check failed with status ${response.status}`)
  }

  return (await response.json()) as HealthStatus
}
