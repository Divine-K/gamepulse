import { cn } from '../../lib/cn'

/** Accessible on/off switch. `label` is required: it is the control's accessible name. */
export function Switch({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange: (next: boolean) => void
  label: string
  disabled?: boolean
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cn(
        'relative inline-flex h-6 w-11 shrink-0 items-center rounded-full border transition-colors duration-150',
        'disabled:cursor-not-allowed disabled:opacity-50',
        checked ? 'border-accent bg-accent' : 'border-line-strong bg-raised',
      )}
    >
      <span
        aria-hidden
        className={cn(
          'inline-block size-4 rounded-full transition-transform duration-150',
          checked ? 'translate-x-6 bg-accent-fg' : 'translate-x-1 bg-muted',
        )}
      />
    </button>
  )
}
