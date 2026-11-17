import { Crown, Medal, Trophy } from 'lucide-react'
import { Link } from 'react-router-dom'
import { NoGame } from '../components/NoGame'
import { Card } from '../components/ui/Card'
import { DataTable } from '../components/ui/DataTable'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { SearchInput } from '../components/ui/SearchInput'
import { Segmented } from '../components/ui/Segmented'
import { SelectField } from '../components/ui/Select'
import { useGames } from '../context/GameContext'
import { useGameData } from '../hooks/useGameData'
import { useUrlState } from '../hooks/useUrlState'
import { cn } from '../lib/cn'
import { formatNumber } from '../lib/format'
import { leaderboardApi } from '../services/endpoints'
import type { LeaderboardEntry } from '../types/api'

const LIMIT = 20
const METRICS = [
  { value: 'total_score', label: 'Total score' },
  { value: 'best_score', label: 'Best single score' },
  { value: 'wins', label: 'Wins' },
  { value: 'achievements', label: 'Achievements' },
  { value: 'completed_sessions', label: 'Sessions completed' },
]

function RankBadge({ rank }: { rank: number }) {
  const Icon = rank === 1 ? Crown : rank <= 3 ? Medal : null
  return (
    <span
      className={cn(
        'inline-flex min-w-10 items-center justify-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold tabular-nums',
        rank <= 3 ? 'border-accent/40 bg-accent-soft text-accent-text' : 'border-line text-muted',
      )}
    >
      {Icon && <Icon aria-hidden className="size-3.5" />}
      <span className="sr-only">Rank </span>#{rank}
    </span>
  )
}

export function LeaderboardsPage() {
  const { game } = useGames()
  const [{ metric, q, order, offset }, update] = useUrlState({
    metric: 'total_score',
    q: '',
    order: 'desc',
    offset: '0',
  })
  const start = Number(offset) || 0
  const board = useGameData(['leaderboard', metric, q, order, start], (id, signal) =>
    leaderboardApi.get(id, metric, { q, order, limit: LIMIT, offset: start }, signal),
  )
  const label = METRICS.find((m) => m.value === metric)?.label ?? metric

  if (!game)
    return (
      <>
        <PageHeader title="Leaderboards" />
        <NoGame what="Leaderboards" />
      </>
    )

  return (
    <>
      <PageHeader
        title="Leaderboards"
        description="Rank players by score, wins and achievements. Ties share a rank, and searching never changes anyone's rank."
      />
      <Card>
        <div className="flex flex-wrap items-end gap-3 border-b border-line p-4">
          <SelectField
            label="Rank by"
            className="w-56"
            value={metric}
            options={METRICS}
            onChange={(e) => update({ metric: e.target.value, offset: '0' })}
          />
          <div className="space-y-1.5">
            <span className="block text-sm font-medium">Search</span>
            <SearchInput
              label="Search the leaderboard"
              placeholder="Player name or ID"
              value={q}
              onChange={(value) => update({ q: value, offset: '0' })}
            />
          </div>
          <div className="space-y-1.5">
            <span className="block text-sm font-medium">Order</span>
            <Segmented
              label="Order"
              value={order}
              onChange={(value) => update({ order: value, offset: '0' })}
              options={[
                { value: 'desc', label: 'Top first' },
                { value: 'asc', label: 'Bottom first' },
              ]}
            />
          </div>
        </div>
        <DataTable
          caption={`Leaderboard by ${label}`}
          loading={board.isLoading}
          rows={board.data?.items}
          rowKey={(e) => e.player.id}
          empty={
            <EmptyState
              icon={Trophy}
              title={q ? 'No players match your search' : 'No rankings yet'}
              description={
                q
                  ? 'Try a different name.'
                  : 'Players appear once they have a score for this ranking.'
              }
            />
          }
          columns={[
            { key: 'rank', header: 'Rank', cell: (e) => <RankBadge rank={e.rank} /> },
            {
              key: 'player',
              header: 'Player',
              cell: (e) => (
                <Link to={`/players/${e.player.id}`} className="font-medium hover:underline">
                  {e.player.username}
                </Link>
              ),
            },
            {
              key: 'value',
              header: label,
              align: 'right',
              cell: (e) => <span className="font-semibold">{formatNumber(e.value)}</span>,
            },
            // When ranking by total score the main value column already shows it.
            ...(metric === 'total_score'
              ? []
              : [
                  {
                    key: 'score',
                    header: 'Total score',
                    align: 'right' as const,
                    cell: (e: LeaderboardEntry) => formatNumber(e.stats.total_score),
                  },
                ]),
            {
              key: 'wins',
              header: 'Wins',
              align: 'right',
              cell: (e) => formatNumber(e.stats.wins),
            },
            {
              key: 'ach',
              header: 'Achievements',
              align: 'right',
              cell: (e) => formatNumber(e.stats.achievements_count),
            },
          ]}
        />
        {board.data && (
          <Pagination
            total={board.data.total}
            limit={LIMIT}
            offset={start}
            onChange={(o) => update({ offset: String(o) })}
          />
        )}
      </Card>
    </>
  )
}
