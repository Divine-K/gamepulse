import { cn } from '../../lib/cn'

/** Loading placeholder. Decorative: pair it with an aria-busy region or a status message. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn('skeleton rounded-md', className)} />
}
