import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { usePolledResource } from './usePolledResource'

describe('usePolledResource', () => {
  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('fetches once on mount and again on each poll interval', async () => {
    const fetcher = vi.fn(async () => 'value')
    const { result } = renderHook(() => usePolledResource(fetcher, { intervalMs: 1000 }))

    await waitFor(() => expect(result.current.loading).toBe(false))
    expect(fetcher).toHaveBeenCalledTimes(1)

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(fetcher).toHaveBeenCalledTimes(2)

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(fetcher).toHaveBeenCalledTimes(3)
  })

  it('stops polling and aborts the in-flight request after unmount', async () => {
    let lastSignal: AbortSignal | undefined
    const fetcher = vi.fn(async (signal: AbortSignal) => {
      lastSignal = signal
      return 'value'
    })
    const { result, unmount } = renderHook(() => usePolledResource(fetcher, { intervalMs: 1000 }))

    await waitFor(() => expect(result.current.loading).toBe(false))
    const callsBeforeUnmount = fetcher.mock.calls.length

    unmount()
    expect(lastSignal?.aborted).toBe(true)

    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    expect(fetcher.mock.calls.length).toBe(callsBeforeUnmount)
  })

  it('does not poll while disabled', async () => {
    const fetcher = vi.fn(async () => 'value')
    renderHook(() => usePolledResource(fetcher, { intervalMs: 1000, enabled: false }))

    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    expect(fetcher).not.toHaveBeenCalled()
  })

  it('preserves stale data and surfaces an error when a background refresh fails', async () => {
    const fetcher = vi.fn()
    fetcher.mockResolvedValueOnce('first').mockRejectedValueOnce(new Error('boom'))
    const { result } = renderHook(() => usePolledResource(fetcher, { intervalMs: 1000 }))

    await waitFor(() => expect(result.current.data).toBe('first'))

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })

    await waitFor(() => expect(result.current.error).not.toBeNull())
    expect(result.current.data).toBe('first')
  })
})
