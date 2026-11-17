import { cn } from '../../lib/cn'

/** Small pulsing status dot. The pulse is removed for reduced-motion users via global CSS. */
export function LiveDot({ active, className }: { active: boolean; className?: string }) {
  return (
    <span
      aria-hidden
      className={cn(
        'inline-block size-2 rounded-full',
        active ? 'live-dot bg-success' : 'bg-subtle',
        className,
      )}
    />
  )
}
