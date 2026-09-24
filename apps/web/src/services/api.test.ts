import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiClient, ApiError } from './api'

describe('ApiClient', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    fetchMock.mockReset()
    vi.stubGlobal('fetch', fetchMock)
  })

  it('applies /api/v1 prefix and query parameters', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ items: [] }), { status: 200 }))
    const client = new ApiClient('https://example.com/', () => null)

    await client.get('/devices', { page: 2, page_size: 25, search: 'abc' })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url] = fetchMock.mock.calls[0]
    expect(String(url)).toBe('https://example.com/api/v1/devices?page=2&page_size=25&search=abc')
  })

  it('sends bearer auth when a token exists', async () => {
    fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    const client = new ApiClient('https://example.com', () => 'token-123')

    await client.get('/monitoring/summary')

    const [, init] = fetchMock.mock.calls[0]
    expect((init?.headers as Record<string, string>).Authorization).toBe('Bearer token-123')
  })

  it('invokes onUnauthorized and throws on 401', async () => {
    fetchMock.mockResolvedValue(
      new Response(JSON.stringify({ error: { code: 'unauthorized', message: 'bad credentials' } }), { status: 401 }),
    )
    const onUnauthorized = vi.fn()
    const client = new ApiClient('https://example.com', () => 't', onUnauthorized)

    await expect(client.get('/devices')).rejects.toMatchObject({
      name: 'ApiError',
      status: 401,
      code: 'unauthorized',
      message: 'bad credentials',
    })
    expect(onUnauthorized).toHaveBeenCalledTimes(1)
  })

  it('maps network failures to ApiError', async () => {
    fetchMock.mockRejectedValue(new TypeError('network down'))
    const client = new ApiClient('https://example.com', () => null)

    await expect(client.get('/devices')).rejects.toMatchObject({
      name: 'ApiError',
      code: 'network_error',
    })
  })
})
