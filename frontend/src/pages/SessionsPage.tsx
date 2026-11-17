import { Swords } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { NoGame } from '../components/NoGame'
import { SessionDetailModal } from '../components/SessionDetailModal'
import { ResultBadge, StatusBadge } from '../components/StatusBadge'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { DataTable } from '../components/ui/DataTable'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { Pagination } from '../components/ui/Pagination'
import { Segmented } from '../components/ui/Segmented'
import { useGames } from '../context/GameContext'
import { useGameData } from '../hooks/useGameData'
import { useUrlState } from '../hooks/useUrlState'
import { formatDateTime, formatDuration, formatNumber } from '../lib/format'
import { sessionsApi } from '../services/endpoints'
import type { GameSessionRecord } from '../types/api'

const LIMIT = 20
const STATUS = [
  { value: 'all', label: 'All' },
  { value: 'active', label: 'Active' },
  { value: 'completed', label: 'Completed' },
  { value: 'abandoned', label: 'Abandoned' },
]

export function SessionsPage() {
  const { game } = useGames()
  const [{ status, offset }, update] = useUrlState({ status: 'all', offset: '0' })
  const start = Number(offset) || 0
  const [selected, setSelected] = useState<GameSessionRecord | null>(null)

  const sessions = useGameData(['sessions', status, start], (id, signal) =>
    sessionsApi.list(
      id,
      { status: status === 'all' ? undefined : status, limit: LIMIT, offset: start },
      signal,
    ),
  )

  if (!game)
    return (
      <>
        <PageHeader title="Sessions" />
        <NoGame what="Sessions" />
      </>
    )

  return (
    <>
      <PageHeader
        title="Sessions"
        description="Every play session, live and historical. Active sessions update as they happen."
      />
      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line p-4">
          <Segmented
            label="Filter by status"
            options={STATUS}
            value={status}
            onChange={(value) => update({ status: value, offset: '0' })}
          />
          <p className="text-sm text-muted" aria-live="polite">
            {sessions.data
              ? `${formatNumber(sessions.data.total)} session${sessions.data.total === 1 ? '' : 's'}`
              : ''}
          </p>
        </div>
        <DataTable
          caption="Sessions"
          loading={sessions.isLoading}
          rows={sessions.data?.items}
          rowKey={(s) => s.id}
          empty={
            <EmptyState
              icon={Swords}
              title="No sessions"
              description={
                status === 'all'
                  ? 'Sessions appear when players start playing.'
                  : `There are no ${status} sessions.`
              }
            />
          }
          columns={[
            {
              key: 'player',
              header: 'Player',
              cell: (s) => (
                <div className="flex items-center gap-2">
                  <Link to={`/players/${s.player.id}`} className="font-medium hover:underline">
                    {s.player.username}
                  </Link>
                  {s.is_simulated && <Badge tone="warning">Simulated</Badge>}
                </div>
              ),
            },
            { key: 'status', header: 'Status', cell: (s) => <StatusBadge status={s.status} /> },
            { key: 'score', header: 'Score', align: 'right', cell: (s) => formatNumber(s.score) },
            { key: 'result', header: 'Result', cell: (s) => <ResultBadge result={s.result} /> },
            {
              key: 'duration',
              header: 'Duration',
              cell: (s) => formatDuration(s.duration_seconds),
            },
            { key: 'started', header: 'Started', cell: (s) => formatDateTime(s.started_at) },
            { key: 'ended', header: 'Ended', cell: (s) => formatDateTime(s.ended_at) },
            {
              key: 'open',
              header: '',
              align: 'right',
              cell: (s) => (
                <Button
                  size="sm"
                  onClick={() => setSelected(s)}
                  aria-label={`Details for session ${s.id.slice(0, 8)}`}
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
      <SessionDetailModal gameId={game.id} session={selected} onClose={() => setSelected(null)} />
    </>
  )
}
