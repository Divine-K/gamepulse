import { cn } from '../../lib/cn'

const TINTS = [
  'bg-series-1/20 text-series-1',
  'bg-series-2/20 text-series-2',
  'bg-series-3/20 text-series-3',
  'bg-violet/20 text-violet',
]

/** Initials avatar. The tint is derived from the name, so a player always looks the same. */
export function Avatar({ name, className }: { name: string; className?: string }) {
  let hash = 0
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  const initials = name.trim().slice(0, 2).toUpperCase() || '?'
  return (
    <span
      aria-hidden
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold',
        TINTS[hash % TINTS.length],
        className,
      )}
    >
      {initials}
    </span>
  )
}
