import { AnimatePresence, motion } from 'motion/react'
import { useEffect, useId, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface MenuItem {
  id: string
  label: string
  icon?: ReactNode
  /** Render as a selectable option (radio semantics) and show a check when true. */
  selected?: boolean
  danger?: boolean
  onSelect: () => void
}

interface MenuProps {
  /** Renders the trigger; spread `props` onto a <button>. */
  trigger: (props: {
    'aria-haspopup': 'menu'
    'aria-expanded': boolean
    'aria-controls': string
    onClick: () => void
  }) => ReactNode
  items: MenuItem[]
  align?: 'left' | 'right'
  label: string
  footer?: ReactNode
}

/** Dropdown menu: Esc closes, arrows move, Enter/Space selects, click outside dismisses. */
export function Menu({ trigger, items, align = 'left', label, footer }: MenuProps) {
  const [open, setOpen] = useState(false)
  const rootRef = useRef<HTMLDivElement>(null)
  const listRef = useRef<HTMLDivElement>(null)
  const id = useId()

  useEffect(() => {
    if (!open) return
    const onPointer = (event: PointerEvent) => {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener('pointerdown', onPointer)
    // Focus the selected item (or the first) when the menu opens.
    const buttons = listRef.current?.querySelectorAll<HTMLButtonElement>('[role^="menuitem"]')
    const selected = listRef.current?.querySelector<HTMLButtonElement>('[aria-checked="true"]')
    ;(selected ?? buttons?.[0])?.focus()
    return () => document.removeEventListener('pointerdown', onPointer)
  }, [open])

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === 'Escape') {
      setOpen(false)
      rootRef.current?.querySelector<HTMLElement>('[aria-haspopup]')?.focus()
      return
    }
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
    event.preventDefault()
    const buttons = [
      ...(listRef.current?.querySelectorAll<HTMLButtonElement>('[role^="menuitem"]') ?? []),
    ]
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement)
    const next = event.key === 'ArrowDown' ? index + 1 : index - 1
    buttons[(next + buttons.length) % buttons.length]?.focus()
  }

  return (
    // The wrapper only forwards Esc/arrow keys bubbling up from the menu buttons inside it.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <div ref={rootRef} className="relative" onKeyDown={onKeyDown}>
      {trigger({
        'aria-haspopup': 'menu',
        'aria-expanded': open,
        'aria-controls': id,
        onClick: () => setOpen((o) => !o),
      })}
      <AnimatePresence>
        {open && (
          <motion.div
            id={id}
            ref={listRef}
            role="menu"
            aria-label={label}
            initial={{ opacity: 0, y: -4, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.97 }}
            transition={{ duration: 0.14, ease: [0.16, 1, 0.3, 1] }}
            className={cn(
              'absolute z-50 mt-2 min-w-56 origin-top rounded-lg border border-line-strong bg-overlay p-1 shadow-pop',
              align === 'right' ? 'right-0' : 'left-0',
            )}
          >
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                role={item.selected === undefined ? 'menuitem' : 'menuitemradio'}
                aria-checked={item.selected}
                onClick={() => {
                  setOpen(false)
                  item.onSelect()
                }}
                className={cn(
                  'flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm transition-colors',
                  'hover:bg-raised focus-visible:bg-raised focus-visible:outline-none',
                  item.danger ? 'text-danger' : 'text-fg',
                  item.selected && 'bg-accent-soft text-accent-text',
                )}
              >
                {item.icon}
                <span className="truncate">{item.label}</span>
              </button>
            ))}
            {footer && <div className="mt-1 border-t border-line pt-1">{footer}</div>}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
