export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="state-panel state-loading" role="status" aria-live="polite">
      <span className="spinner" aria-hidden="true" />
      <span>{label}</span>
    </div>
  )
}
