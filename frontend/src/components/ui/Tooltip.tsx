import { useId } from 'react'
import type { ReactElement, ReactNode } from 'react'
import { cloneElement } from 'react'

/** Text tooltip shown on hover and keyboard focus. `children` must be a focusable element. */
export function Tooltip({
  label,
  children,
}: {
  label: ReactNode
  children: ReactElement<{ 'aria-describedby'?: string }>
}) {
  const id = useId()
  return (
    <span className="group relative inline-flex">
      {cloneElement(children, { 'aria-describedby': id })}
      <span
        id={id}
        role="tooltip"
        className="pointer-events-none absolute top-full left-1/2 z-50 mt-2 -translate-x-1/2 rounded-md border border-line-strong bg-overlay px-2 py-1 text-xs whitespace-nowrap text-fg opacity-0 shadow-pop transition-opacity duration-150 group-focus-within:opacity-100 group-hover:opacity-100"
      >
        {label}
      </span>
    </span>
  )
}
