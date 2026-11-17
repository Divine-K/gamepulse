import { Users } from 'lucide-react'
import { Link } from 'react-router-dom'
import { NoGame } from '../components/NoGame'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { DataTable } from '../components/ui/DataTable'
import type { SortState } from '../components/ui/DataTable'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { SearchInput } from '../components/ui/SearchInput'
import { useGames } from '../context/GameContext'
import { useGameData } from '../hooks/useGameData'
import { useUrlState } from '../hooks/useUrlState'
import { formatNumber, timeAgo } from '../lib/format'
import { playersApi } from '../services/endpoints'

const LIMIT = 20

export function PlayersPage() {
  const { game } = useGames()
  const [{ q, sort, offset }, update] = useUrlState({ q: '', sort: '-last_active_at', offset: '0' })
  const sortState: SortState = { key: sort.replace(/^-/, ''), descending: sort.startsWith('-') }
  const start = Number(offset) || 0

  const players = useGameData(['players', q, sort, start], (id, signal) =>
    playersApi.list(id, { q, sort, limit: LIMIT, offset: start }, signal),
  )

  if (!game)
    return (
      <>
        <PageHeader title="Players" />
        <NoGame what="Players" />
      </>
    )

  return (
    <>
      <PageHeader
        title="Players"
        description="Everyone who has played your game. Click a player to see their profile."
      />
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
          <SearchInput
            label="Search players"
            placeholder="Search by name or ID"
            value={q}
            onChange={(value) => update({ q: value, offset: '0' })}
          />
          <p className="text-sm text-muted" aria-live="polite">
            {players.data
              ? `${formatNumber(players.data.total)} player${players.data.total === 1 ? '' : 's'}`
              : ''}
          </p>
        </div>
        <DataTable
          caption="Players"
          loading={players.isLoading}
          rows={players.data?.items}
          rowKey={(p) => p.id}
          sort={sortState}
          onSortChange={(s) => update({ sort: `${s.descending ? '-' : ''}${s.key}`, offset: '0' })}
          empty={
            <EmptyState
              icon={Users}
              title={q ? 'No players match your search' : 'No players yet'}
              description={
                q
                  ? 'Try a different name or ID.'
                  : 'Players appear here when your game registers them through the API.'
              }
            />
          }
          columns={[
            {
              key: 'username',
              header: 'Player',
              sortKey: 'username',
              cell: (p) => (
                <div className="flex items-center gap-2">
                  <Link to={`/players/${p.id}`} className="font-medium hover:underline">
                    {p.username}
                  </Link>
                  {p.is_simulated && <Badge tone="warning">Simulated</Badge>}
                </div>
              ),
            },
            {
              key: 'external',
              header: 'ID',
              cell: (p) => <code className="font-mono text-xs text-muted">{p.external_id}</code>,
            },
            {
              key: 'sessions',
              header: 'Sessions',
              sortKey: 'total_sessions',
              align: 'right',
              cell: (p) => formatNumber(p.stats.total_sessions),
            },
            {
              key: 'score',
              header: 'Total score',
              sortKey: 'total_score',
              align: 'right',
              cell: (p) => formatNumber(p.stats.total_score),
            },
            {
              key: 'best',
              header: 'Best',
              sortKey: 'best_score',
              align: 'right',
              cell: (p) => formatNumber(p.stats.best_score),
            },
            {
              key: 'active',
              header: 'Last active',
              sortKey: 'last_active_at',
              cell: (p) => timeAgo(p.last_active_at),
            },
          ]}
        />
        {players.data && (
          <Pagination
            total={players.data.total}
            limit={LIMIT}
            offset={start}
            onChange={(o) => update({ offset: String(o) })}
          />
        )}
      </Card>
    </>
  )
}
