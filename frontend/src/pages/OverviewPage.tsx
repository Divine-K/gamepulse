import { Activity, Clock, Gauge, Users, Zap } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { AchievementIcon } from '../components/AchievementIcon'
import { ChartCard } from '../components/charts/ChartCard'
import { TimeSeries } from '../components/charts/TimeSeries'
import { NoGame } from '../components/NoGame'
import { Badge } from '../components/ui/Badge'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { Segmented } from '../components/ui/Segmented'
import { Skeleton } from '../components/ui/Skeleton'
import { StatCard, percentChange } from '../components/ui/StatCard'
import { useAuth } from '../context/AuthContext'
import { useGames } from '../context/GameContext'
import { useStream } from '../context/StreamContext'
import { useGameData } from '../hooks/useGameData'
import { describeEvent } from '../lib/events'
import {
  formatDuration,
  formatNumber,
  formatPercent,
  formatShortDate,
  formatTime,
  timeAgo,
} from '../lib/format'
import { achievementsApi, analyticsApi, leaderboardApi } from '../services/endpoints'

const RANGES = [
  { value: 7, label: '7 days' },
  { value: 30, label: '30 days' },
  { value: 90, label: '90 days' },
]

export function OverviewPage() {
  const { user } = useAuth()
  const { game, isLoading: gamesLoading } = useGames()
  const { events } = useStream()
  const [days, setDays] = useState(30)

  const overview = useGameData(['overview', days], (id, signal) =>
    analyticsApi.overview(id, { days }, signal),
  )
  const engagement = useGameData(['engagement', days], (id, signal) =>
    analyticsApi.engagement(id, { days }, signal),
  )
  const top = useGameData(['leaderboard', 'preview'], (id, signal) =>
    leaderboardApi.get(id, 'total_score', { limit: 5 }, signal),
  )
  const unlocks = useGameData(['unlocks', 'preview'], (id, signal) =>
    achievementsApi.unlocks(id, { limit: 5 }, signal),
  )

  if (!gamesLoading && !game) {
    return (
      <>
        <PageHeader title={`Welcome, ${user?.display_name ?? ''}`} />
        <NoGame what="Players, sessions and analytics" />
      </>
    )
  }

  const o = overview.data
  const loading = overview.isLoading
  const points = engagement.data?.points ?? []
  const hasActivity = points.some((p) => p.events > 0)
  const stickiness =
    o && o.monthly_active_players > 0 ? o.daily_active_players / o.monthly_active_players : null
  const label = `vs previous ${days} days`

  return (
    <>
      <PageHeader
        title={game?.name ?? 'Overview'}
        description="How your game is doing right now and over time. Updates live as players play."
        actions={<Segmented label="Date range" options={RANGES} value={days} onChange={setDays} />}
      />

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard
          icon={Users}
          label="Total players"
          loading={loading}
          value={formatNumber(o?.total_players ?? 0)}
          hint={o ? `${formatNumber(o.current.new_players)} new in ${days} days` : undefined}
        />
        <StatCard
          icon={Activity}
          label="Active players"
          loading={loading}
          value={formatNumber(o?.current.active_players ?? 0)}
          change={o ? percentChange(o.current.active_players, o.previous.active_players) : null}
          comparedTo={label}
          hint={o ? `${formatNumber(o.currently_active_players)} online now` : undefined}
        />
        <StatCard
          icon={Zap}
          label="Sessions"
          loading={loading}
          value={formatNumber(o?.current.sessions ?? 0)}
          change={o ? percentChange(o.current.sessions, o.previous.sessions) : null}
          comparedTo={label}
          hint={o ? `${formatNumber(o.total_sessions)} all time` : undefined}
        />
        <StatCard
          icon={Clock}
          label="Avg session length"
          loading={loading}
          value={formatDuration(
            o?.current.avg_session_duration_seconds ?? o?.avg_session_duration_seconds,
          )}
          change={
            o?.current.avg_session_duration_seconds != null &&
            o.previous.avg_session_duration_seconds != null
              ? percentChange(
                  o.current.avg_session_duration_seconds,
                  o.previous.avg_session_duration_seconds,
                )
              : null
          }
          comparedTo={label}
          hint="Completed sessions"
        />
        <StatCard
          icon={Gauge}
          label="Events"
          loading={loading}
          value={formatNumber(o?.current.events ?? 0)}
          change={o ? percentChange(o.current.events, o.previous.events) : null}
          comparedTo={label}
          hint={o ? `${formatNumber(o.total_events)} all time` : undefined}
        />
        <StatCard
          icon={Activity}
          label="Engagement"
          loading={loading}
          value={formatPercent(stickiness)}
          hint="Daily ÷ monthly active players"
        />
      </div>

      <div className="mt-4">
        <ChartCard
          title="Player activity"
          description={`Daily active players, new players and sessions started, last ${days} days.`}
          loading={engagement.isLoading}
          emptyMessage={hasActivity ? undefined : 'No activity in this period yet.'}
          legend={[
            { label: 'Active players', color: 'var(--series-1)' },
            { label: 'New players', color: 'var(--series-2)' },
            { label: 'Sessions started', color: 'var(--series-3)' },
          ]}
          table={{
            columns: ['Date', 'Active players', 'New players', 'Sessions started'],
            rows: points.map((p) => [
              formatShortDate(p.date),
              p.active_players,
              p.new_players,
              p.sessions_started,
            ]),
          }}
        >
          <TimeSeries
            data={points as unknown as { date: string }[]}
            series={[
              { key: 'active_players', label: 'Active players', color: 'var(--series-1)' },
              { key: 'new_players', label: 'New players', color: 'var(--series-2)' },
              { key: 'sessions_started', label: 'Sessions started', color: 'var(--series-3)' },
            ]}
          />
        </ChartCard>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <Card>
          <CardHeader
            title="Top players"
            action={
              <Link to="/leaderboards" className="text-sm text-accent-text hover:underline">
                Leaderboard
              </Link>
            }
          />
          <CardBody>
            {top.isLoading ? (
              <Skeleton className="h-32" />
            ) : (top.data?.items.length ?? 0) === 0 ? (
              <p className="py-6 text-center text-sm text-muted">No scores yet.</p>
            ) : (
              <ol className="divide-y divide-line">
                {top.data!.items.map((entry) => (
                  <li key={entry.player.id} className="flex items-center gap-3 py-2.5 text-sm">
                    <span className="w-6 text-muted tabular-nums">#{entry.rank}</span>
                    <Link
                      to={`/players/${entry.player.id}`}
                      className="min-w-0 flex-1 truncate font-medium hover:underline"
                    >
                      {entry.player.username}
                    </Link>
                    <span className="font-medium tabular-nums">{formatNumber(entry.value)}</span>
                  </li>
                ))}
              </ol>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Recent achievements"
            action={
              <Link to="/achievements" className="text-sm text-accent-text hover:underline">
                All
              </Link>
            }
          />
          <CardBody>
            {unlocks.isLoading ? (
              <Skeleton className="h-32" />
            ) : (unlocks.data?.items.length ?? 0) === 0 ? (
              <p className="py-6 text-center text-sm text-muted">Nothing unlocked yet.</p>
            ) : (
              <ul className="divide-y divide-line">
                {unlocks.data!.items.map((u) => (
                  <li key={u.id} className="flex items-center gap-3 py-2.5 text-sm">
                    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent-text">
                      <AchievementIcon name={u.achievement.icon} className="size-4" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate font-medium">{u.achievement.name}</span>
                      <span className="block truncate text-xs text-muted">{u.player.username}</span>
                    </span>
                    <span className="shrink-0 text-xs text-subtle">{timeAgo(u.unlocked_at)}</span>
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Live activity"
            action={
              <Link to="/live" className="text-sm text-accent-text hover:underline">
                Open feed
              </Link>
            }
          />
          <CardBody>
            {events.length === 0 ? (
              <p className="py-6 text-center text-sm text-muted">
                Waiting for activity. Events appear here instantly.
              </p>
            ) : (
              <ul className="divide-y divide-line">
                {events.slice(0, 5).map((event) => {
                  const view = describeEvent(event)
                  return (
                    <li key={event.id} className="flex items-center gap-2 py-2.5 text-sm">
                      <Badge tone={view.tone} className="shrink-0">
                        {view.title}
                      </Badge>
                      <span className="min-w-0 flex-1 truncate text-muted">{view.detail}</span>
                      <time dateTime={event.ts} className="shrink-0 font-mono text-xs text-subtle">
                        {formatTime(event.ts)}
                      </time>
                    </li>
                  )
                })}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  )
}
