import type { ApiClient } from './api'
import type { CurrentUser } from '../types/common'

export type TokenResponse = {
  access_token: string
  token_type: string
}

/**
 * Authenticates against the OAuth2-style `POST /api/v1/auth/token` endpoint.
 * Credentials are sent once as a form body; they are never placed in a URL,
 * query string, or log statement.
 */
export async function login(client: ApiClient, username: string, password: string): Promise<TokenResponse> {
  const form = new URLSearchParams()
  form.set('username', username)
  form.set('password', password)
  return client.postForm<TokenResponse>('/auth/token', form)
}

export async function fetchCurrentUser(client: ApiClient): Promise<CurrentUser> {
  return client.get<CurrentUser>('/auth/me')
}
