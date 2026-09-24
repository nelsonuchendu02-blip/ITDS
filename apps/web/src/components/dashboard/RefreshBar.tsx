export function RefreshBar({
  lastUpdated,
  refreshing,
  onRefresh,
}: {
  lastUpdated: Date | null
  refreshing: boolean
  onRefresh: () => void
}) {
  return (
    <div className="refresh-bar">
      <span className="refresh-meta">
        {lastUpdated ? `Last updated ${lastUpdated.toLocaleTimeString()}` : 'Not yet loaded'}
      </span>
      <button type="button" className="btn btn-secondary" onClick={onRefresh} disabled={refreshing} aria-busy={refreshing}>
        {refreshing ? 'Refreshing…' : 'Refresh'}
      </button>
    </div>
  )
}
