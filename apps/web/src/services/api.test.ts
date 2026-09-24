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

  describe('timeout and cancellation', () => {
    it('aborts the request and reports a timeout ApiError when the timeout elapses', async () => {
      fetchMock.mockImplementation((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => {
            const error = new DOMException('Aborted', 'AbortError')
            reject(error)
          })
        })
      })
      const client = new ApiClient('https://example.com', () => null)

      const promise = client.request('GET', '/devices', { timeoutMs: 5 })

      await expect(promise).rejects.toMatchObject({ name: 'ApiError', code: 'timeout' })
    })

    it('cancels the request when the caller aborts, without reporting a timeout', async () => {
      const callerController = new AbortController()
      fetchMock.mockImplementation((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => {
            reject(new DOMException('Aborted', 'AbortError'))
          })
        })
      })
      const client = new ApiClient('https://example.com', () => null)

      const promise = client.request('GET', '/devices', { signal: callerController.signal, timeoutMs: 60_000 })
      callerController.abort()

      await expect(promise).rejects.toMatchObject({ name: 'ApiError', code: 'cancelled' })
    })

    it('does not report caller cancellation as a timeout', async () => {
      const callerController = new AbortController()
      fetchMock.mockImplementation((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        })
      })
      const client = new ApiClient('https://example.com', () => null)

      const promise = client.request('GET', '/devices', { signal: callerController.signal, timeoutMs: 60_000 })
      callerController.abort()

      const error = (await promise.catch((err: unknown) => err)) as ApiError
      expect(error.code).not.toBe('timeout')
      expect(error.code).toBe('cancelled')
    })

    it('does not report a genuine timeout as a cancellation', async () => {
      fetchMock.mockImplementation((_url: string, init: RequestInit) => {
        return new Promise((_resolve, reject) => {
          init.signal?.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')))
        })
      })
      const client = new ApiClient('https://example.com', () => null)

      const error = (await client.request('GET', '/devices', { timeoutMs: 5 }).catch((err: unknown) => err)) as ApiError
      expect(error.code).not.toBe('cancelled')
      expect(error.code).toBe('timeout')
    })

    it('cleans up the timeout timer and the caller-abort listener after the request settles', async () => {
      const clearTimeoutSpy = vi.spyOn(globalThis, 'clearTimeout')
      const callerController = new AbortController()
      const removeEventListenerSpy = vi.spyOn(callerController.signal, 'removeEventListener')
      fetchMock.mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
      const client = new ApiClient('https://example.com', () => null)

      await client.request('GET', '/devices', { signal: callerController.signal })

      expect(clearTimeoutSpy).toHaveBeenCalled()
      expect(removeEventListenerSpy).toHaveBeenCalledWith('abort', expect.any(Function))

      clearTimeoutSpy.mockRestore()
      removeEventListenerSpy.mockRestore()
    })
  })
})
