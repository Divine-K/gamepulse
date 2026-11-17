import { ChevronDown } from 'lucide-react'
import { useId } from 'react'
import type { SelectHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

/** Native <select> with a visible label: accessible, keyboard- and mobile-friendly by default. */
export function SelectField({
  label,
  options,
  className,
  hideLabel,
  ...rest
}: {
  label: string
  options: { value: string; label: string }[]
  hideLabel?: boolean
} & SelectHTMLAttributes<HTMLSelectElement>) {
  const id = useId()
  return (
    <div className={cn('space-y-1.5', className)}>
      <label
        htmlFor={id}
        className={cn('block text-sm font-medium text-fg', hideLabel && 'sr-only')}
      >
        {label}
      </label>
      <div className="relative">
        <select
          id={id}
          className="h-10 w-full appearance-none rounded-md border border-line bg-canvas pr-9 pl-3 text-sm text-fg transition-colors hover:border-line-strong focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          {...rest}
        >
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown
          aria-hidden
          className="pointer-events-none absolute top-1/2 right-3 size-4 -translate-y-1/2 text-muted"
        />
      </div>
    </div>
  )
}
