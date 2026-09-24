import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthProvider'

const currentUser = {
  id: 'user-1',
  organization_id: 'org-1',
  email: 'operator@example.com',
  display_name: 'Operations Operator',
  status: 'active',
  roles: ['viewer'],
  permissions: ['devices:read'],
  created_at: '2026-09-24T00:00:00Z',
  updated_at: '2026-09-24T00:00:00Z',
}

function AuthProbe() {
  const { status, user, error, login } = useAuth()
  return (
    <div>
      <output aria-label="status">{status}</output>
      {user && <output aria-label="email">{user.email}</output>}
      {error && <div role="alert">{error}</div>}
      <button
        type="button"
        onClick={() => {
          void login('operator@example.com', 'correct-password').catch(() => undefined)
        }}
      >
        Login
      </button>
    </div>
  )
}

describe('AuthProvider', () => {
  afterEach(() => {
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  it('authenticates through token then current-user endpoints and keeps the bearer token out of web storage', async () => {
    const requests: Array<{ url: string; init?: RequestInit }> = []
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input)
      requests.push({ url, init })

      if (url.endsWith('/api/v1/auth/token')) {
        return new Response(JSON.stringify({ access_token: 'memory-only-token', token_type: 'bearer' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (url.endsWith('/api/v1/auth/me')) {
        return new Response(JSON.stringify(currentUser), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      return new Response(null, { status: 404 })
    })
    vi.stubGlobal('fetch', fetchMock)

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => expect(screen.getByLabelText('status')).toHaveTextContent('authenticated'))
    expect(screen.getByLabelText('email')).toHaveTextContent(currentUser.email)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(requests[0].url).toContain('/api/v1/auth/token')
    expect(requests[1].url).toContain('/api/v1/auth/me')
    expect(requests[1].init?.headers).toMatchObject({ Authorization: 'Bearer memory-only-token' })
    expect(window.localStorage.getItem('itds_access_token')).toBeNull()
    expect(window.sessionStorage.getItem('itds_access_token')).toBeNull()
  })

  it('clears the session and surfaces the API error when token exchange fails', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(
        JSON.stringify({ error: { code: 'invalid_credentials', message: 'Invalid credentials' } }),
        {
          status: 401,
          headers: { 'Content-Type': 'application/json' },
        },
      ),
    )
    vi.stubGlobal('fetch', fetchMock)

    render(
      <AuthProvider>
        <AuthProbe />
      </AuthProvider>,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Login' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Invalid credentials'))
    expect(screen.getByLabelText('status')).toHaveTextContent('error')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(window.localStorage.getItem('itds_access_token')).toBeNull()
    expect(window.sessionStorage.getItem('itds_access_token')).toBeNull()
  })
})
