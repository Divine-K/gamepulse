import { Activity, ArrowLeft, Clock, Medal, Trophy, Zap } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { AchievementIcon } from '../components/AchievementIcon'
import { ChartCard } from '../components/charts/ChartCard'
import { Columns } from '../components/charts/Columns'
import { SessionDetailModal } from '../components/SessionDetailModal'
import { ResultBadge, StatusBadge } from '../components/StatusBadge'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { DataTable } from '../components/ui/DataTable'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { Skeleton } from '../components/ui/Skeleton'
import { StatCard } from '../components/ui/StatCard'
import { TabPanel, Tabs } from '../components/ui/Tabs'
import { useGames } from '../context/GameContext'
import { useGameData } from '../hooks/useGameData'
import { useUrlState } from '../hooks/useUrlState'
import { formatDateTime, formatDuration, formatNumber, formatTime, timeAgo } from '../lib/format'
import { ApiError } from '../services/api'
import { eventsApi, playersApi } from '../services/endpoints'
import type { GameSessionRecord } from '../types/api'
import { useState } from 'react'

const TABS = [
  { id: 'sessions', label: 'Sessions' },
  { id: 'scores', label: 'Score history' },
  { id: 'achievements', label: 'Achievements' },
  { id: 'activity', label: 'Activity' },
]
const LIMIT = 10

export function PlayerPage() {
  const { playerId = '' } = useParams()
  const { game } = useGames()
  const [{ tab, offset }, update] = useUrlState({ tab: 'sessions', offset: '0' })
  const start = Number(offset) || 0
  const [selected, setSelected] = useState<GameSessionRecord | null>(null)

  const player = useGameData(['player', playerId], (id, signal) =>
    playersApi.get(id, playerId, signal),
  )
  const sessions = useGameData(
    ['player', playerId, 'sessions', start],
    (id, signal) => playersApi.sessions(id, playerId, { limit: LIMIT, offset: start }, signal),
    { enabled: tab === 'sessions' },
  )
  const scores = useGameData(
    ['player', playerId, 'scores'],
    (id, signal) => playersApi.sessions(id, playerId, { status: 'completed', limit: 30 }, signal),
    { enabled: tab === 'scores' },
  )
  const unlocks = useGameData(
    ['player', playerId, 'achievements', start],
    (id, signal) => playersApi.achievements(id, playerId, { limit: LIMIT, offset: start }, signal),
    { enabled: tab === 'achievements' },
  )
  const activity = useGameData(
    ['player', playerId, 'events', start],
    (id, signal) => eventsApi.list(id, { player_id: playerId, limit: 20, offset: start }, signal),
    { enabled: tab === 'activity' },
  )

  if (player.isError) {
    const notFound = player.error instanceof ApiError && player.error.status === 404
    return (
      <Card>
        <EmptyState
          title={notFound ? 'Player not found' : 'Could not load this player'}
          action={
            <Link to="/players">
              <Button variant="primary">Back to players</Button>
            </Link>
          }
        />
      </Card>
    )
  }
  if (player.isLoading || !player.data || !game) return <Skeleton className="h-64" />

  const p = player.data
  const s = p.stats
  const changeTab = (id: string) => update({ tab: id, offset: '0' })

  // Oldest to newest, so the chart reads left to right in time.
  const history = [...(scores.data?.items ?? [])]
    .reverse()
    .map((x, i) => ({ n: String(i + 1), score: x.score, when: x.ended_at }))

  return (
    <>
      <Link
        to="/players"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-fg"
      >
        <ArrowLeft aria-hidden className="size-4" /> All players
      </Link>
      <PageHeader
        title={p.username}
        description={`ID ${p.external_id} · joined ${formatDateTime(p.created_at)} · last active ${timeAgo(p.last_active_at)}`}
        actions={p.is_simulated ? <Badge tone="warning">Simulated</Badge> : undefined}
      />

      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <StatCard
          icon={Zap}
          label="Sessions"
          value={formatNumber(s.total_sessions)}
          hint={`${formatNumber(s.completed_sessions)} completed`}
        />
        <StatCard
          icon={Trophy}
          label="Total score"
          value={formatNumber(s.total_score)}
          hint={`Best ${formatNumber(s.best_score)}`}
        />
        <StatCard icon={Activity} label="Wins" value={formatNumber(s.wins)} />
        <StatCard
          icon={Clock}
          label="Time played"
          value={formatDuration(s.total_play_seconds)}
          hint={`${formatNumber(s.achievements_count)} achievements`}
        />
      </div>

      <Tabs
        tabs={TABS}
        active={tab}
        onChange={changeTab}
        label="Player sections"
        idPrefix="player"
      />

      <TabPanel id="sessions" active={tab} idPrefix="player">
        <Card>
          <DataTable
            caption="Session history"
            loading={sessions.isLoading}
            rows={sessions.data?.items}
            rowKey={(x) => x.id}
            empty={<EmptyState title="No sessions yet" />}
            columns={[
              { key: 'status', header: 'Status', cell: (x) => <StatusBadge status={x.status} /> },
              { key: 'score', header: 'Score', align: 'right', cell: (x) => formatNumber(x.score) },
              { key: 'result', header: 'Result', cell: (x) => <ResultBadge result={x.result} /> },
              {
                key: 'duration',
                header: 'Duration',
                cell: (x) => formatDuration(x.duration_seconds),
              },
              { key: 'started', header: 'Started', cell: (x) => formatDateTime(x.started_at) },
              {
                key: 'open',
                header: '',
                align: 'right',
                cell: (x) => (
                  <Button
                    size="sm"
                    onClick={() => setSelected(x)}
                    aria-label={`Details for session ${x.id.slice(0, 8)}`}
                  >
                    Details
                  </Button>
                ),
              },
            ]}
          />
          {sessions.data && (
            <Pagination
              total={sessions.data.total}
              limit={LIMIT}
              offset={start}
              onChange={(o) => update({ offset: String(o) })}
            />
          )}
        </Card>
      </TabPanel>

      <TabPanel id="scores" active={tab} idPrefix="player">
        <ChartCard
          title="Score per completed session"
          description="The last 30 completed sessions, oldest to newest."
          loading={scores.isLoading}
          emptyMessage={history.length === 0 ? 'No completed sessions yet.' : undefined}
          table={{
            columns: ['#', 'Score', 'Finished'],
            rows: history.map((h) => [h.n, h.score, formatDateTime(h.when)]),
          }}
        >
          <Columns
            data={history}
            xKey="n"
            series={[{ key: 'score', label: 'Score', color: 'var(--series-1)' }]}
          />
        </ChartCard>
      </TabPanel>

      <TabPanel id="achievements" active={tab} idPrefix="player">
        <Card>
          {unlocks.isLoading ? (
            <Skeleton className="m-5 h-24" />
          ) : (unlocks.data?.items.length ?? 0) === 0 ? (
            <EmptyState
              icon={Medal}
              title="No achievements yet"
              description="They unlock automatically as this player meets the conditions."
            />
          ) : (
            <ul className="divide-y divide-line">
              {unlocks.data!.items.map((u) => (
                <li key={u.id} className="flex items-center gap-3 px-5 py-3 text-sm">
                  <span className="flex size-9 items-center justify-center rounded-full bg-accent-soft text-accent-text">
                    <AchievementIcon name={u.achievement.icon} className="size-4" />
                  </span>
                  <span className="flex-1 font-medium">{u.achievement.name}</span>
                  <time dateTime={u.unlocked_at} className="text-xs text-muted">
                    {formatDateTime(u.unlocked_at)}
                  </time>
                </li>
              ))}
            </ul>
          )}
          {unlocks.data && (
            <Pagination
              total={unlocks.data.total}
              limit={LIMIT}
              offset={start}
              onChange={(o) => update({ offset: String(o) })}
            />
          )}
        </Card>
      </TabPanel>

      <TabPanel id="activity" active={tab} idPrefix="player">
        <Card>
          {activity.isLoading ? (
            <Skeleton className="m-5 h-24" />
          ) : (activity.data?.items.length ?? 0) === 0 ? (
            <EmptyState title="No activity yet" />
          ) : (
            <ol aria-label="Activity timeline" className="divide-y divide-line">
              {activity.data!.items.map((e) => (
                <li key={e.id} className="flex items-center gap-3 px-5 py-3 text-sm">
                  <code className="w-44 shrink-0 font-mono text-xs">{e.event_type}</code>
                  <span className="min-w-0 flex-1 truncate text-xs text-muted">
                    {Object.keys(e.payload).length ? JSON.stringify(e.payload) : ''}
                  </span>
                  <time
                    dateTime={e.occurred_at}
                    className="shrink-0 font-mono text-xs text-subtle"
                    title={formatDateTime(e.occurred_at)}
                  >
                    {formatTime(e.occurred_at)}
                  </time>
                </li>
              ))}
            </ol>
          )}
          {activity.data && (
            <Pagination
              total={activity.data.total}
              limit={20}
              offset={start}
              onChange={(o) => update({ offset: String(o) })}
            />
          )}
        </Card>
      </TabPanel>

      <SessionDetailModal gameId={game.id} session={selected} onClose={() => setSelected(null)} />
    </>
  )
}
