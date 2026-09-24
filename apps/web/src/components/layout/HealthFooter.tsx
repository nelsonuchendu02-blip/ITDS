import { useEffect, useState } from 'react'
import { fetchHealthStatus, type HealthStatus } from '../../services/health'
import { resolveApiBaseUrl } from '../../services/api'

/**
 * Small unauthenticated backend-reachability indicator, preserved from the
 * Phase 0 shell. Deliberately does not go through the authenticated API
 * client since `/api/health` requires no auth.
 */
export function HealthFooter() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [errored, setErrored] = useState(false)

  useEffect(() => {
    let cancelled = false
    const baseUrl = resolveApiBaseUrl()

    async function check() {
      try {
        const result = await fetchHealthStatus(baseUrl)
        if (!cancelled) {
          setHealth(result)
          setErrored(false)
        }
      } catch {
        if (!cancelled) setErrored(true)
      }
    }

    void check()
    const timer = window.setInterval(check, 60_000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [])

  return (
    <footer className="app-footer">
      <span className={`footer-status ${errored ? 'is-error' : 'is-ok'}`}>
        {errored ? 'Backend unreachable' : `Backend: ${health?.status ?? 'checking…'}`}
      </span>
      {health && (
        <span className="footer-meta">
          {health.service} v{health.version} ({health.environment})
        </span>
      )}
    </footer>
  )
}
