import { Loader2 } from 'lucide-react'
import { cn } from '../../lib/cn'

export function Spinner({ className, label }: { className?: string; label?: string }) {
  return (
    <span role={label ? 'status' : undefined} aria-label={label}>
      <Loader2 aria-hidden className={cn('animate-spin', className)} />
    </span>
  )
}
