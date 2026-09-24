export type NavEntry = {
  path: string
  label: string
  /**
   * Permission(s) required to see this entry. A single permission gates
   * module-specific pages. The Dashboard aggregates several modules, so it
   * uses an array: it is visible to any user who can read at least one of
   * the operational resources it summarizes, rather than being tied to a
   * single module's permission (see docs/ui/dashboard.md).
   */
  permission: string | string[]
}

/**
 * Sidebar/route entries with their gating permission. `usePermission` hides
 * or disables anything the signed-in user lacks; the backend remains the
 * real authorization boundary regardless of what the UI shows.
 */
export const NAV_ENTRIES: NavEntry[] = [
  {
    path: '/',
    label: 'Dashboard',
    permission: ['devices:read', 'monitoring:read', 'agents:read', 'incidents:read', 'discovery:read', 'recommendations:read'],
  },
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
