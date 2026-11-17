import { useId } from 'react'
import type { InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from 'react'
import { cn } from '../../lib/cn'

interface FieldChromeProps {
  label: string
  error?: string
  hint?: ReactNode
}

const control =
  'w-full rounded-md border bg-canvas px-3 text-sm text-fg placeholder:text-subtle ' +
  'transition-colors duration-150 hover:border-line-strong focus-visible:border-accent ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent/40 ' +
  'disabled:cursor-not-allowed disabled:opacity-60'

function Chrome({
  id,
  label,
  error,
  hint,
  children,
}: FieldChromeProps & { id: string; children: ReactNode }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-fg">
        {label}
      </label>
      {children}
      {hint && !error && (
        <p id={`${id}-hint`} className="text-xs text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={`${id}-error`} role="alert" className="text-xs text-danger">
          {error}
        </p>
      )}
    </div>
  )
}

function describedBy(id: string, error?: string, hint?: ReactNode) {
  if (error) return `${id}-error`
  return hint ? `${id}-hint` : undefined
}

export function TextField({
  label,
  error,
  hint,
  className,
  ...rest
}: FieldChromeProps & InputHTMLAttributes<HTMLInputElement>) {
  const id = useId()
  return (
    <Chrome id={id} label={label} error={error} hint={hint}>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, error, hint)}
        className={cn(control, 'h-10', error ? 'border-danger' : 'border-line', className)}
        {...rest}
      />
    </Chrome>
  )
}

export function TextAreaField({
  label,
  error,
  hint,
  className,
  ...rest
}: FieldChromeProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const id = useId()
  return (
    <Chrome id={id} label={label} error={error} hint={hint}>
      <textarea
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy(id, error, hint)}
        className={cn(control, 'min-h-24 py-2', error ? 'border-danger' : 'border-line', className)}
        {...rest}
      />
    </Chrome>
  )
}
