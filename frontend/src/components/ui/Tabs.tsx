import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'

export interface TabItem {
  id: string
  label: string
}

/** Tab list with arrow-key navigation. Render the panel yourself with `tabPanelProps`. */
export function Tabs({
  tabs,
  active,
  onChange,
  label,
  idPrefix,
}: {
  tabs: TabItem[]
  active: string
  onChange: (id: string) => void
  label: string
  /** Shared with <TabPanel> so tabs and panels reference each other. */
  idPrefix: string
}) {
  const base = idPrefix
  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
    const index = tabs.findIndex((t) => t.id === active)
    const next = tabs[(index + (event.key === 'ArrowRight' ? 1 : -1) + tabs.length) % tabs.length]
    if (next) {
      onChange(next.id)
      document.getElementById(`${base}-tab-${next.id}`)?.focus()
    }
  }
  return (
    // arrow keys bubble up from the focused tab button
    // eslint-disable-next-line jsx-a11y/interactive-supports-focus
    <div
      role="tablist"
      aria-label={label}
      onKeyDown={onKeyDown}
      className="flex gap-1 overflow-x-auto border-b border-line"
    >
      {tabs.map((tab) => {
        const selected = tab.id === active
        return (
          <button
            key={tab.id}
            id={`${base}-tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={selected}
            aria-controls={`${base}-panel-${tab.id}`}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(tab.id)}
            className={cn(
              '-mb-px shrink-0 border-b-2 px-4 py-2.5 text-sm font-medium whitespace-nowrap transition-colors',
              selected ? 'border-accent text-fg' : 'border-transparent text-muted hover:text-fg',
            )}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}

export function TabPanel({
  id,
  active,
  idPrefix,
  children,
}: {
  id: string
  active: string
  idPrefix: string
  children: ReactNode
}) {
  if (id !== active) return null
  return (
    <div
      role="tabpanel"
      id={`${idPrefix}-panel-${id}`}
      aria-labelledby={`${idPrefix}-tab-${id}`}
      className="pt-6"
    >
      {children}
    </div>
  )
}
