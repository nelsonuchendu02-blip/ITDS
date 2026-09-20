import { useEffect, useState } from 'react'
import { fetchHealthStatus, type HealthStatus } from './services/health'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function App() {
  const [status, setStatus] = useState<HealthStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadHealth = async () => {
      try {
        const result = await fetchHealthStatus(API_BASE_URL)
        setStatus(result)
        setError(null)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Unknown API error')
      } finally {
        setLoading(false)
      }
    }

    void loadHealth()
  }, [])

  return (
    <main className="app-shell">
      <section className="panel">
        <p className="eyebrow">IT Support Diagnostic System</p>
        <h1>System foundation</h1>
        <p className="subtitle">Phase 0: API and frontend foundation only.</p>

        <div className="status-card">
          <span className="label">Backend API</span>
          {loading && <span className="status is-loading">Checking…</span>}
          {!loading && !error && status && (
            <span className="status is-ok">Operational ({status.environment})</span>
          )}
          {!loading && error && <span className="status is-error">Unavailable</span>}
        </div>

        {error && <p className="error">{error}</p>}

        <dl className="meta">
          <div>
            <dt>API base URL</dt>
            <dd>{API_BASE_URL}</dd>
          </div>
          <div>
            <dt>Health route</dt>
            <dd>/api/health</dd>
          </div>
        </dl>

        {status && (
          <div className="details">
            <p>
              Service: <strong>{status.service}</strong>
            </p>
            <p>
              Version: <strong>{status.version}</strong>
            </p>
          </div>
        )}
      </section>
    </main>
  )
}

export default App
