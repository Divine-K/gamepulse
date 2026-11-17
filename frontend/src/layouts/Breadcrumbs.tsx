import { ChevronRight } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { findNavItem } from '../lib/nav'

export function Breadcrumbs() {
  const { pathname } = useLocation()
  const current = pathname === '/design' ? 'Design system' : findNavItem(pathname)?.label
  return (
    <nav aria-label="Breadcrumb">
      <ol className="flex items-center gap-1.5 text-sm text-muted">
        <li>
          <Link to="/" className="rounded transition-colors hover:text-fg">
            GamePulse
          </Link>
        </li>
        {current && pathname !== '/' && (
          <>
            <li aria-hidden>
              <ChevronRight className="size-3.5" />
            </li>
            <li aria-current="page" className="font-medium text-fg">
              {current}
            </li>
          </>
        )}
        {pathname === '/' && (
          <>
            <li aria-hidden>
              <ChevronRight className="size-3.5" />
            </li>
            <li aria-current="page" className="font-medium text-fg">
              Overview
            </li>
          </>
        )}
      </ol>
    </nav>
  )
}
