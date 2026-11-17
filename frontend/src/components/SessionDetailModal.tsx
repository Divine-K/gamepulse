import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { formatDateTime, formatDuration, formatNumber, formatTime } from '../lib/format'
import { eventsApi } from '../services/endpoints'
import type { GameSessionRecord } from '../types/api'
import { ResultBadge, StatusBadge } from './StatusBadge'
import { Badge } from './ui/Badge'
import { Modal } from './ui/Modal'
import { Skeleton } from './ui/Skeleton'

export function SessionDetailModal({
  gameId,
  session,
  onClose,
}: {
  gameId: string
  session: GameSessionRecord | null
  onClose: () => void
}) {
  const events = useQuery({
    queryKey: ['game', gameId, 'session-events', session?.id],
    queryFn: ({ signal }) => eventsApi.list(gameId, { session_id: session!.id, limit: 50 }, signal),
    enabled: !!session,
  })

  return (
    <Modal
      open={session !== null}
      onClose={onClose}
      title="Session details"
      description={session ? `Session ${session.id.slice(0, 8)}` : undefined}
      className="w-[min(40rem,calc(100vw-2rem))]"
    >
      {session && (
        <div className="space-y-5">
          <dl className="grid grid-cols-2 gap-x-6 gap-y-3 text-sm">
            <Item label="Player">
              <Link
                to={`/players/${session.player.id}`}
                className="font-medium text-accent-text hover:underline"
              >
                {session.player.username}
              </Link>
            </Item>
            <Item label="Status">
              <StatusBadge status={session.status} />
            </Item>
            <Item label="Score">{formatNumber(session.score)}</Item>
            <Item label="Result">
              <ResultBadge result={session.result} />
            </Item>
            <Item label="Started">{formatDateTime(session.started_at)}</Item>
            <Item label="Ended">{formatDateTime(session.ended_at)}</Item>
            <Item label="Duration">{formatDuration(session.duration_seconds)}</Item>
            <Item label="Source">
              {session.is_simulated ? <Badge tone="warning">Simulated</Badge> : 'Game API'}
            </Item>
          </dl>
          <div>
            <h3 className="mb-2 text-sm font-semibold">Events in this session</h3>
            {events.isLoading ? (
              <Skeleton className="h-16" />
            ) : (events.data?.items.length ?? 0) === 0 ? (
              <p className="text-sm text-muted">No events recorded.</p>
            ) : (
              <ul className="max-h-56 divide-y divide-line overflow-auto rounded-md border border-line">
                {events.data!.items.map((e) => (
                  <li key={e.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                    <code className="font-mono text-xs">{e.event_type}</code>
                    <span className="min-w-0 flex-1 truncate text-xs text-muted">
                      {Object.keys(e.payload).length ? JSON.stringify(e.payload) : ''}
                    </span>
                    <time dateTime={e.occurred_at} className="font-mono text-xs text-subtle">
                      {formatTime(e.occurred_at)}
                    </time>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}
    </Modal>
  )
}

function Item({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-muted">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  )
}
