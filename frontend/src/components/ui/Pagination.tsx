import { ChevronLeft, ChevronRight } from 'lucide-react'
import { formatNumber } from '../../lib/format'
import { Button } from './Button'

export function Pagination({
  total,
  limit,
  offset,
  onChange,
}: {
  total: number
  limit: number
  offset: number
  onChange: (offset: number) => void
}) {
  if (total === 0) return null
  const from = offset + 1
  const to = Math.min(offset + limit, total)
  return (
    <nav
      aria-label="Pagination"
      className="flex items-center justify-between gap-4 px-5 py-3 text-sm"
    >
      <p className="text-muted" aria-live="polite">
        {formatNumber(from)}–{formatNumber(to)} of {formatNumber(total)}
      </p>
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={offset === 0}
          onClick={() => onChange(Math.max(0, offset - limit))}
          icon={<ChevronLeft aria-hidden className="size-4" />}
        >
          Previous
        </Button>
        <Button
          size="sm"
          disabled={offset + limit >= total}
          onClick={() => onChange(offset + limit)}
        >
          Next <ChevronRight aria-hidden className="size-4" />
        </Button>
      </div>
    </nav>
  )
}
