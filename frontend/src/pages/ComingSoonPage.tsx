import { Hammer } from 'lucide-react'
import { useLocation } from 'react-router-dom'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { findNavItem } from '../lib/nav'

/** Honest placeholder for pages on the roadmap that are not built yet. */
export function ComingSoonPage() {
  const { pathname } = useLocation()
  const item = findNavItem(pathname)
  return (
    <>
      <PageHeader
        title={item?.label ?? 'Coming soon'}
        actions={<Badge tone="warning">Not built yet</Badge>}
      />
      <Card>
        <EmptyState
          icon={item?.icon ?? Hammer}
          title={`${item?.label ?? 'This page'} is on the roadmap`}
          description={item?.description}
        />
      </Card>
    </>
  )
}
