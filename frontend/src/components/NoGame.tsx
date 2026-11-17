import { Gamepad2 } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Button } from './ui/Button'
import { Card } from './ui/Card'
import { EmptyState } from './ui/EmptyState'

/** Shown by pages that need an active game when the developer has none yet. */
export function NoGame({ what }: { what: string }) {
  return (
    <Card>
      <EmptyState
        icon={Gamepad2}
        title="Register a game first"
        description={`${what} belong to a game. Create one and they will show up here.`}
        action={
          <Link to="/games">
            <Button variant="primary">Go to Games</Button>
          </Link>
        }
      />
    </Card>
  )
}
