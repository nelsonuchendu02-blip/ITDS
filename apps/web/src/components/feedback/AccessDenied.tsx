export function AccessDenied({ resource }: { resource: string }) {
  return (
    <div className="state-panel state-denied" role="alert">
      <p className="state-title">Access denied</p>
      <p className="state-description">
        You do not have permission to view {resource}. Contact an organization administrator if you believe this is
        incorrect.
      </p>
    </div>
  )
}
