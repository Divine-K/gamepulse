import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

type Tone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info'

const tones: Record<Tone, string> = {
  neutral: 'bg-raised text-muted border-line',
  accent: 'bg-accent-soft text-accent-text border-accent/30',
  success: 'bg-success-soft text-success border-success/30',
  warning: 'bg-warning-soft text-warning border-warning/30',
  danger: 'bg-danger-soft text-danger border-danger/30',
  info: 'bg-info-soft text-info border-info/30',
}

export function Badge({
  tone = 'neutral',
  className,
  ...rest
}: HTMLAttributes<HTMLSpanElement> & { tone?: Tone }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        tones[tone],
        className,
      )}
      {...rest}
    />
  )
}
