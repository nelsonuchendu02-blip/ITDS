import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { ApiClient, ApiError, resolveApiBaseUrl } from '../../services/api'
import { fetchCurrentUser, login as loginRequest } from '../../services/auth'
import type { CurrentUser } from '../../types/common'

type AuthStatus = 'idle' | 'authenticating' | 'authenticated' | 'error'

type AuthContextValue = {
  status: AuthStatus
  user: CurrentUser | null
  error: string | null
  apiClient: ApiClient
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

const AuthContext = createContext<AuthContextValue | null>(null)

/**
 * Phase 1N does not persist the access token across a page refresh: the
 * backend contract has no refresh-token flow, and storing a bearer token in
 * `localStorage`/`sessionStorage` would be unsafe. The token lives only in
 * memory for the lifetime of the tab; reloading the page requires signing
 * in again. This is documented in `docs/ui/dashboard.md`.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const tokenRef = useRef<string | null>(null)
  const [status, setStatus] = useState<AuthStatus>('idle')
  const [user, setUser] = useState<CurrentUser | null>(null)
  const [error, setError] = useState<string | null>(null)

  const clearSession = useCallback(() => {
    tokenRef.current = null
    setUser(null)
    setStatus('idle')
  }, [])

  const apiClient = useMemo(
    () => new ApiClient(resolveApiBaseUrl(), () => tokenRef.current, clearSession),
    [clearSession],
  )

  const login = useCallback(
    async (username: string, password: string) => {
      setStatus('authenticating')
      setError(null)
      try {
        const token = await loginRequest(apiClient, username, password)
        tokenRef.current = token.access_token
        const currentUser = await fetchCurrentUser(apiClient)
        setUser(currentUser)
        setStatus('authenticated')
      } catch (err) {
        tokenRef.current = null
        setUser(null)
        setStatus('error')
        setError(err instanceof ApiError ? err.message : 'Sign-in failed. Please try again.')
        throw err
      }
    },
    [apiClient],
  )

  const logout = useCallback(() => {
    clearSession()
  }, [clearSession])

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, error, apiClient, login, logout }),
    [status, user, error, apiClient, login, logout],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
