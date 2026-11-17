import { useId } from 'react'
import { cn } from '../../lib/cn'

export interface SegmentOption<T extends string | number> {
  value: T
  label: string
}

/** A compact single-choice control (date ranges, status filters). Arrow keys move the choice. */
export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  label,
}: {
  options: SegmentOption<T>[]
  value: T
  onChange: (value: T) => void
  label: string
}) {
  const name = useId()
  const onKeyDown = (event: React.KeyboardEvent<HTMLDivElement>) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
    event.preventDefault()
    const index = options.findIndex((o) => o.value === value)
    const next = (index + (event.key === 'ArrowRight' ? 1 : -1) + options.length) % options.length
    const target = options[next]
    if (target) onChange(target.value)
  }
  return (
    // radiogroup keyboard handling lives on the group; each option is a real radio button
    // eslint-disable-next-line jsx-a11y/interactive-supports-focus
    <div
      role="radiogroup"
      aria-label={label}
      onKeyDown={onKeyDown}
      className="inline-flex rounded-md border border-line bg-surface p-0.5"
    >
      {options.map((option) => {
        const selected = option.value === value
        return (
          <button
            key={`${name}-${option.value}`}
            type="button"
            role="radio"
            aria-checked={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(option.value)}
            className={cn(
              'rounded-[5px] px-3 py-1 text-sm font-medium transition-colors duration-150',
              selected ? 'bg-raised text-fg shadow-card' : 'text-muted hover:text-fg',
            )}
          >
            {option.label}
          </button>
        )
      })}
    </div>
  )
}
