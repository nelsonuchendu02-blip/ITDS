export type NavEntry = {
  path: string
  label: string
  permission: string
}

/**
 * Sidebar/route entries with their gating permission. `usePermission` hides
 * or disables anything the signed-in user lacks; the backend remains the
 * real authorization boundary regardless of what the UI shows.
 */
export const NAV_ENTRIES: NavEntry[] = [
  { path: '/', label: 'Dashboard', permission: 'devices:read' },
  { path: '/devices', label: 'Devices', permission: 'devices:read' },
  { path: '/monitoring', label: 'Monitoring', permission: 'monitoring:read' },
  { path: '/agents', label: 'Agents', permission: 'agents:read' },
  { path: '/incidents', label: 'Incidents', permission: 'incidents:read' },
  { path: '/discovery', label: 'Discovery', permission: 'discovery:read' },
  { path: '/diagnostics', label: 'Diagnostics', permission: 'diagnostics:read' },
  { path: '/root-cause', label: 'Root Cause', permission: 'root_cause:read' },
  { path: '/recommendations', label: 'Recommendations', permission: 'recommendations:read' },
  { path: '/remediation', label: 'Remediation', permission: 'remediation:read' },
  { path: '/networks', label: 'Networks', permission: 'networks:read' },
  { path: '/audit', label: 'Audit', permission: 'audit:read' },
]
