import { ArrowDownRight, ArrowUpRight, Minus } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Card, CardBody } from './Card'
import { Skeleton } from './Skeleton'

/**
 * Percentage change vs the previous period. Returns null when there is no baseline: a jump
 * from 0 has no meaningful percentage, so we show nothing rather than an invented number.
 */
export function percentChange(current: number, previous: number): number | null {
  if (previous === 0) return null
  return (current - previous) / previous
}

export function StatCard({
  label,
  value,
  icon: Icon,
  loading,
  hint,
  change,
  comparedTo,
}: {
  label: string
  value: string
  icon: LucideIcon
  loading?: boolean
  hint?: string
  /** Fractional change vs the previous period (0.12 = +12%). */
  change?: number | null
  comparedTo?: string
}) {
  const direction =
    change === undefined || change === null
      ? null
      : change > 0.0005
        ? 'up'
        : change < -0.0005
          ? 'down'
          : 'flat'
  const DeltaIcon =
    direction === 'up' ? ArrowUpRight : direction === 'down' ? ArrowDownRight : Minus
  return (
    <Card>
      <CardBody>
        <div className="flex items-center justify-between gap-2 text-sm text-muted">
          <span>{label}</span>
          <Icon aria-hidden className="size-4 text-subtle" />
        </div>
        {loading ? (
          <Skeleton className="mt-3 h-9 w-24" />
        ) : (
          <p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p>
        )}
        {!loading && (direction || hint) && (
          <div className="mt-2 space-y-0.5 text-xs text-subtle">
            {direction && change !== null && change !== undefined && (
              <p className="flex items-center gap-1.5">
                <span
                  className={cn(
                    'inline-flex items-center gap-0.5 font-medium',
                    direction === 'up' && 'text-success',
                    direction === 'down' && 'text-danger',
                    direction === 'flat' && 'text-muted',
                  )}
                >
                  <DeltaIcon aria-hidden className="size-3.5" />
                  <span className="sr-only">
                    {direction === 'up' ? 'Up' : direction === 'down' ? 'Down' : 'Unchanged'}{' '}
                  </span>
                  {Math.abs(change * 100).toFixed(0)}%
                </span>
                {comparedTo && <span>{comparedTo}</span>}
              </p>
            )}
            {hint && <p>{hint}</p>}
          </div>
        )}
      </CardBody>
    </Card>
  )
}
