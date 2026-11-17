import { useQuery } from '@tanstack/react-query'
import { Gamepad2, Users, Zap } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { Skeleton } from '../components/ui/Skeleton'
import { useAuth } from '../context/AuthContext'
import { useGames } from '../context/GameContext'
import { useStream } from '../context/StreamContext'
import { describeEvent } from '../lib/events'
import { formatNumber, formatTime } from '../lib/format'
import { gamesApi } from '../services/endpoints'

export function OverviewPage() {
  const { user } = useAuth()
  const { game, isLoading } = useGames()
  const { events, status } = useStream()

  const live = useQuery({
    queryKey: ['live', game?.id],
    queryFn: ({ signal }) => gamesApi.live(game!.id, signal),
    enabled: !!game,
    refetchInterval: 15_000,
  })

  if (!isLoading && !game) {
    return (
      <>
        <PageHeader title={`Welcome, ${user?.display_name ?? ''}`} />
        <Card>
          <EmptyState
            icon={Gamepad2}
            title="Start by registering a game"
            description="Once you have a game, this page shows who is playing right now and what they are doing."
            action={
              <Link to="/games">
                <Button variant="primary">Register a game</Button>
              </Link>
            }
          />
        </Card>
      </>
    )
  }

  return (
    <>
      <PageHeader
        title={game ? game.name : 'Overview'}
        description="Live status of your game. Charts and trends arrive with the analytics release."
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <Card>
          <CardBody>
            <div className="flex items-center gap-2 text-sm text-muted">
              <Users aria-hidden className="size-4" /> Players online now
            </div>
            {live.isLoading || !game ? (
              <Skeleton className="mt-3 h-10 w-24" />
            ) : (
              <p className="mt-2 text-4xl font-semibold tracking-tight tabular-nums">
                {formatNumber(live.data?.active_players ?? 0)}
              </p>
            )}
            {live.data && (
              <p className="mt-2 text-xs text-subtle">
                Counted from{' '}
                {live.data.source === 'redis' ? 'live tracking' : 'the database (fallback)'}
              </p>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardBody>
            <div className="flex items-center gap-2 text-sm text-muted">
              <Zap aria-hidden className="size-4" /> Events this visit
            </div>
            <p className="mt-2 text-4xl font-semibold tracking-tight tabular-nums">
              {formatNumber(events.length)}
            </p>
            <p className="mt-2 text-xs text-subtle">
              Stream: <Badge tone={status === 'live' ? 'accent' : 'neutral'}>{status}</Badge>
            </p>
          </CardBody>
        </Card>
      </div>

      <Card className="mt-4">
        <CardHeader
          title="Recent activity"
          action={
            <Link to="/live" className="text-sm text-accent-text hover:underline">
              Open live feed
            </Link>
          }
        />
        <CardBody>
          {events.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">
              Nothing yet. Activity from your game appears here instantly.
            </p>
          ) : (
            <ul className="divide-y divide-line">
              {events.slice(0, 6).map((event) => {
                const view = describeEvent(event)
                return (
                  <li key={event.id} className="flex items-center gap-3 py-2.5 text-sm">
                    <Badge tone={view.tone} className="w-44 shrink-0 justify-center">
                      {view.title}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate">{view.detail}</span>
                    <time dateTime={event.ts} className="font-mono text-xs text-subtle">
                      {formatTime(event.ts)}
                    </time>
                  </li>
                )
              })}
            </ul>
          )}
        </CardBody>
      </Card>
    </>
  )
}
