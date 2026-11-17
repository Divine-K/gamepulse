import { Link } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { EmptyState } from '../components/ui/EmptyState'

export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      description="The page you are looking for does not exist or has moved."
      action={
        <Link to="/">
          <Button variant="primary">Back to overview</Button>
        </Link>
      }
    />
  )
}
