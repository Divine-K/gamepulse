import { cn } from '../../lib/cn'

// Initials stay in the normal text colour (always readable); only the tint identifies the player.
const TINTS = ['bg-series-1/25', 'bg-series-2/25', 'bg-series-3/25', 'bg-violet/25']

/** Initials avatar. The tint is derived from the name, so a player always looks the same. */
export function Avatar({ name, className }: { name: string; className?: string }) {
  let hash = 0
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) >>> 0
  const initials = name.trim().slice(0, 2).toUpperCase() || '?'
  return (
    <span
      aria-hidden
      className={cn(
        'flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold text-fg',
        TINTS[hash % TINTS.length],
        className,
      )}
    >
      {initials}
    </span>
  )
}
