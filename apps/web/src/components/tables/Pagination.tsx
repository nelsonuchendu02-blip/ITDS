export function Pagination({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number
  pageSize: number
  total: number
  onPageChange: (page: number) => void
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  if (total === 0) return null

  const start = (page - 1) * pageSize + 1
  const end = Math.min(total, page * pageSize)

  return (
    <nav className="pagination" aria-label="Pagination">
      <span className="pagination-summary">
        Showing {start}–{end} of {total}
      </span>
      <div className="pagination-controls">
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => onPageChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
        >
          Previous
        </button>
        <span className="pagination-page" aria-current="page">
          Page {page} of {totalPages}
        </span>
        <button
          type="button"
          className="btn btn-secondary"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
          aria-label="Next page"
        >
          Next
        </button>
      </div>
    </nav>
  )
}
