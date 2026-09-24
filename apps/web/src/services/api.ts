/**
 * Centralized, authenticated API client for the ITDS dashboard.
 *
 * All versioned backend endpoints live under the `/api/v1` prefix; the
 * unauthenticated health probe stays at `/api/health` and is fetched
 * directly by `services/health.ts` instead of through this client.
 */

export class ApiError extends Error {
  readonly status: number
  readonly code: string

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

const API_PREFIX = '/api/v1'
const DEFAULT_TIMEOUT_MS = 15_000
/** Guards against sending unexpectedly large request bodies from the UI. */
const MAX_REQUEST_BYTES = 256_000

type Query = Record<string, string | number | boolean | undefined | null>

type RequestOptions = {
  body?: unknown
  formBody?: URLSearchParams
  query?: Query
  signal?: AbortSignal
  timeoutMs?: number
}

export type TokenProvider = () => string | null

function buildQueryString(query?: Query): string {
  if (!query) return ''
  const params = new URLSearchParams()
  for (const [key, value] of Object.entries(query)) {
    if (value === undefined || value === null || value === '') continue
    params.set(key, String(value))
  }
  const serialized = params.toString()
  return serialized ? `?${serialized}` : ''
}

function safeMessageForStatus(status: number, backendMessage?: string): string {
  if (backendMessage) return backendMessage
  switch (status) {
    case 401:
      return 'Your session has expired. Please sign in again.'
    case 403:
      return 'You do not have permission to perform this action.'
    case 404:
      return 'The requested resource was not found.'
    case 429:
      return 'Too many requests. Please wait a moment and try again.'
    default:
      if (status >= 500) return 'The server encountered an error. Please try again later.'
      return 'The request could not be completed.'
  }
}

function extractErrorPayload(payload: unknown): { code: string; message: string } | null {
  if (
    payload &&
    typeof payload === 'object' &&
    'error' in payload &&
    payload.error &&
    typeof payload.error === 'object'
  ) {
    const error = payload.error as { code?: unknown; message?: unknown }
    return {
      code: typeof error.code === 'string' ? error.code : 'error',
      message: typeof error.message === 'string' ? error.message : '',
    }
  }
  return null
}

/**
 * Thin fetch wrapper: JSON handling, bearer auth, timeouts, structured
 * errors, and a single 401 hook so the auth provider can clear a stale
 * session. Never logs tokens, request bodies, or raw response payloads.
 */
export class ApiClient {
  private readonly baseUrl: string
  private readonly getToken: TokenProvider
  private readonly onUnauthorized?: () => void

  constructor(baseUrl: string, getToken: TokenProvider, onUnauthorized?: () => void) {
    this.baseUrl = baseUrl.replace(/\/+$/, '')
    this.getToken = getToken
    this.onUnauthorized = onUnauthorized
  }

  private resolve(path: string): string {
    const normalized = path.startsWith('/') ? path : `/${path}`
    return `${this.baseUrl}${API_PREFIX}${normalized}`
  }

  async request<T>(method: string, path: string, options: RequestOptions = {}): Promise<T> {
    const controller = new AbortController()
    const timeoutMs = options.timeoutMs ?? DEFAULT_TIMEOUT_MS
    const timer = setTimeout(() => controller.abort(), timeoutMs)

    const headers: Record<string, string> = { Accept: 'application/json' }
    const token = this.getToken()
    if (token) headers.Authorization = `Bearer ${token}`

    let body: BodyInit | undefined
    if (options.formBody) {
      headers['Content-Type'] = 'application/x-www-form-urlencoded'
      body = options.formBody
    } else if (options.body !== undefined) {
      const serialized = JSON.stringify(options.body)
      if (serialized.length > MAX_REQUEST_BYTES) {
        clearTimeout(timer)
        throw new ApiError(0, 'payload_too_large', 'Request payload exceeds the allowed size.')
      }
      headers['Content-Type'] = 'application/json'
      body = serialized
    }

    let response: Response
    try {
      response = await fetch(`${this.resolve(path)}${buildQueryString(options.query)}`, {
        method,
        headers,
        body,
        signal: options.signal ?? controller.signal,
        credentials: 'omit',
      })
    } catch (error) {
      clearTimeout(timer)
      if (error instanceof DOMException && error.name === 'AbortError') {
        throw new ApiError(0, 'timeout', 'The request timed out. Please try again.')
      }
      throw new ApiError(0, 'network_error', 'Unable to reach the API. Check your connection.')
    }
    clearTimeout(timer)

    if (response.status === 204) {
      return undefined as T
    }

    const rawText = await response.text()
    let payload: unknown = null
    if (rawText) {
      try {
        payload = JSON.parse(rawText)
      } catch {
        payload = null
      }
    }

    if (!response.ok) {
      if (response.status === 401) this.onUnauthorized?.()
      const backendError = extractErrorPayload(payload)
      throw new ApiError(
        response.status,
        backendError?.code ?? `http_${response.status}`,
        safeMessageForStatus(response.status, backendError?.message),
      )
    }

    return payload as T
  }

  get<T>(path: string, query?: Query, signal?: AbortSignal): Promise<T> {
    return this.request<T>('GET', path, { query, signal })
  }

  post<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    return this.request<T>('POST', path, { body, signal })
  }

  patch<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
    return this.request<T>('PATCH', path, { body, signal })
  }

  delete<T>(path: string, signal?: AbortSignal): Promise<T> {
    return this.request<T>('DELETE', path, { signal })
  }

  postForm<T>(path: string, formBody: URLSearchParams, signal?: AbortSignal): Promise<T> {
    return this.request<T>('POST', path, { formBody, signal })
  }
}

export function resolveApiBaseUrl(): string {
  return import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
}
