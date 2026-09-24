import { useState } from 'react'
import type { FormEvent } from 'react'
import { Navigate, useLocation, type Location } from 'react-router-dom'
import { useAuth } from '../app/providers/AuthProvider'

type LocationState = { from?: Location } | null

export function Login() {
  const { status, error, login } = useAuth()
  const location = useLocation()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  if (status === 'authenticated') {
    const state = location.state as LocationState
    const redirectTo = state?.from ? `${state.from.pathname}${state.from.search}${state.from.hash}` : '/'
    return <Navigate to={redirectTo} replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    try {
      await login(username, password)
    } catch {
      // Error is already surfaced via auth context state.
    }
  }

  const authenticating = status === 'authenticating'

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={handleSubmit} aria-busy={authenticating}>
        <h1>ITDS Operations</h1>
        <p className="login-subtitle">Sign in to access the operations dashboard.</p>

        <label htmlFor="login-username">Email</label>
        <input
          id="login-username"
          name="username"
          type="email"
          autoComplete="username"
          required
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />

        <label htmlFor="login-password">Password</label>
        <input
          id="login-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        {error && (
          <p className="login-error" role="alert">
            {error}
          </p>
        )}

        <button type="submit" className="btn btn-primary" disabled={authenticating}>
          {authenticating ? 'Signing in…' : 'Sign in'}
        </button>
      </form>
    </div>
  )
}
