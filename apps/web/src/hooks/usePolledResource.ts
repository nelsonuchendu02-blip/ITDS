import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiError } from '../services/api'

export type ResourceState<T> = {
  data: T | null
  /** True only for the very first load (or when `reloadKey` changes). */
  loading: boolean
  /** True while a manual or background refresh is in flight after data has loaded once. */
  refreshing: boolean
  error: string | null
  lastUpdated: Date | null
  refresh: () => Promise<void>
}

const DEFAULT_INTERVAL_MS = 30_000

/**
 * Fetches a resource once, then polls on a fixed interval until the
 * component unmounts. Guarantees a single in-flight request at a time,
 * clears its timer on unmount, and preserves the last good `data` value if
 * a background refresh fails (the `error` field is set, but stale data is
 * not discarded).
 */
export function usePolledResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  options: { intervalMs?: number; enabled?: boolean; reloadKey?: unknown } = {},
): ResourceState<T> {
  const { intervalMs = DEFAULT_INTERVAL_MS, enabled = true, reloadKey } = options
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher
  const inFlightRef = useRef(false)
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(async (isManual: boolean) => {
    if (inFlightRef.current) return
    inFlightRef.current = true
    if (isManual) setRefreshing(true)
    const controller = new AbortController()
    abortRef.current = controller
    try {
      const result = await fetcherRef.current(controller.signal)
      setData(result)
      setError(null)
      setLastUpdated(new Date())
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      setError(err instanceof ApiError ? err.message : 'Unable to load data.')
    } finally {
      setLoading(false)
      setRefreshing(false)
      inFlightRef.current = false
    }
  }, [])

  useEffect(() => {
    if (!enabled) return undefined
    let cancelled = false
    setLoading(true)
    void load(false)
    const timer = window.setInterval(() => {
      if (!cancelled) void load(false)
    }, intervalMs)
    return () => {
      cancelled = true
      window.clearInterval(timer)
      abortRef.current?.abort()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, intervalMs, load, reloadKey])

  const refresh = useCallback(() => load(true), [load])

  return { data, loading, refreshing, error, lastUpdated, refresh }
}
