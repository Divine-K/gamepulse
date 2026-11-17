import { Activity, ChevronsLeft, ChevronsRight, Palette } from 'lucide-react'
import { Fragment } from 'react'
import { NavLink } from 'react-router-dom'
import { Badge } from '../components/ui/Badge'
import { cn } from '../lib/cn'
import { NAV_ITEMS } from '../lib/nav'
import type { NavGroup } from '../lib/nav'

interface SidebarProps {
  collapsed: boolean
  onToggleCollapsed: () => void
  /** Called after navigating, so the mobile drawer can close. */
  onNavigate: () => void
  /** On mobile the sidebar is always expanded. */
  forceExpanded?: boolean
}

const GROUPS: NavGroup[] = ['Core', 'Insights', 'Developer', 'System']

export function Sidebar({ collapsed, onToggleCollapsed, onNavigate, forceExpanded }: SidebarProps) {
  const compact = collapsed && !forceExpanded

  return (
    <div className="flex h-full flex-col border-r border-line bg-surface">
      <div className={cn('flex h-16 items-center gap-2.5 px-5', compact && 'justify-center px-0')}>
        <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-accent text-accent-fg">
          <Activity aria-hidden className="size-5" strokeWidth={2.5} />
        </span>
        {!compact && <span className="text-base font-semibold tracking-tight">GamePulse</span>}
      </div>

      <nav aria-label="Main" className="flex-1 overflow-y-auto px-3 pb-2">
        {GROUPS.map((group, groupIndex) => (
          <Fragment key={group}>
            {compact ? (
              groupIndex > 0 && <div aria-hidden className="mx-2 my-3 border-t border-line" />
            ) : (
              <p className="px-3 pt-4 pb-1.5 text-[11px] font-semibold tracking-wider text-subtle uppercase">
                {group}
              </p>
            )}
            <div className="space-y-0.5">
              {NAV_ITEMS.filter((item) => item.group === group).map(
                ({ to, label, icon: Icon, built }) => (
                  <NavLink
                    key={to}
                    to={to}
                    end={to === '/'}
                    onClick={onNavigate}
                    aria-label={compact ? label : undefined}
                    title={compact ? label : undefined}
                    className={({ isActive }) =>
                      cn(
                        'flex h-10 items-center gap-3 rounded-lg px-3 text-sm font-medium transition-colors',
                        compact && 'justify-center px-0',
                        isActive
                          ? 'bg-accent text-accent-fg shadow-card'
                          : 'text-muted hover:bg-raised hover:text-fg',
                      )
                    }
                  >
                    <Icon aria-hidden className="size-[18px] shrink-0" />
                    {!compact && (
                      <>
                        <span className="flex-1 truncate">{label}</span>
                        {!built && <Badge className="px-1.5 py-0 text-[10px]">Soon</Badge>}
                      </>
                    )}
                  </NavLink>
                ),
              )}
            </div>
          </Fragment>
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
              'flex h-9 items-center gap-3 rounded-lg px-3 text-sm transition-colors',
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
              'flex h-9 w-full items-center gap-3 rounded-lg px-3 text-sm text-subtle transition-colors hover:text-fg',
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
