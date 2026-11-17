import { motion } from 'motion/react'
import { Activity, ChevronsLeft, ChevronsRight, Palette } from 'lucide-react'
import { NavLink } from 'react-router-dom'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/cn'
import { NAV_ITEMS } from '../lib/nav'

interface SidebarProps {
  collapsed: boolean
  onToggleCollapsed: () => void
  /** Called after navigating, so the mobile drawer can close. */
  onNavigate: () => void
  /** On mobile the sidebar is always expanded. */
  forceExpanded?: boolean
}

export function Sidebar({ collapsed, onToggleCollapsed, onNavigate, forceExpanded }: SidebarProps) {
  const compact = collapsed && !forceExpanded

  return (
    <div className="flex h-full flex-col border-r border-line bg-surface">
      <div className={cn('flex h-16 items-center gap-2 px-4', compact && 'justify-center px-0')}>
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-fg">
          <Activity aria-hidden className="size-5" strokeWidth={2.5} />
        </span>
        {!compact && <span className="text-base font-semibold tracking-tight">GamePulse</span>}
      </div>

      <nav aria-label="Main" className="flex-1 space-y-0.5 overflow-y-auto px-3 py-2">
        {NAV_ITEMS.map(({ to, label, icon: Icon, built }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            onClick={onNavigate}
            aria-label={compact ? label : undefined}
            title={compact ? label : undefined}
            className={({ isActive }) =>
              cn(
                'relative flex h-10 items-center gap-3 rounded-md px-3 text-sm font-medium transition-colors',
                compact && 'justify-center px-0',
                isActive
                  ? 'bg-accent-soft text-accent-text'
                  : 'text-muted hover:bg-raised hover:text-fg',
              )
            }
          >
            {({ isActive }) => (
              <>
                {isActive && (
                  <motion.span
                    layoutId="nav-active"
                    aria-hidden
                    className="absolute top-2 bottom-2 left-0 w-0.5 rounded-full bg-accent"
                    transition={{ type: 'spring', stiffness: 500, damping: 40 }}
                  />
                )}
                <Icon aria-hidden className="size-[18px] shrink-0" />
                {!compact && (
                  <>
                    <span className="flex-1 truncate">{label}</span>
                    {!built && <Badge className="px-1.5 py-0 text-[10px]">Soon</Badge>}
                  </>
                )}
              </>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="space-y-0.5 border-t border-line p-3">
        <NavLink
          to="/design"
          onClick={onNavigate}
          aria-label={compact ? 'Design system' : undefined}
          title={compact ? 'Design system' : undefined}
          className={({ isActive }) =>
            cn(
              'flex h-9 items-center gap-3 rounded-md px-3 text-sm transition-colors',
              compact && 'justify-center px-0',
              isActive ? 'text-accent-text' : 'text-subtle hover:text-fg',
            )
          }
        >
          <Palette aria-hidden className="size-4 shrink-0" />
          {!compact && 'Design system'}
        </NavLink>
        {!forceExpanded && (
          <button
            type="button"
            onClick={onToggleCollapsed}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            aria-expanded={!collapsed}
            className={cn(
              'flex h-9 w-full items-center gap-3 rounded-md px-3 text-sm text-subtle transition-colors hover:text-fg',
              compact && 'justify-center px-0',
            )}
          >
            {collapsed ? (
              <ChevronsRight aria-hidden className="size-4" />
            ) : (
              <>
                <ChevronsLeft aria-hidden className="size-4" />
                Collapse
              </>
            )}
          </button>
        )}
      </div>
    </div>
  )
}
