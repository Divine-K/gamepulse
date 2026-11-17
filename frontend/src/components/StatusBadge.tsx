import { Badge } from './ui/Badge'
import type { SessionStatus } from '../types/api'

const TONES = { active: 'success', completed: 'info', abandoned: 'warning' } as const

export function StatusBadge({ status }: { status: SessionStatus }) {
  return (
    <Badge tone={TONES[status]}>
      {status[0]?.toUpperCase()}
      {status.slice(1)}
    </Badge>
  )
}

export function ResultBadge({ result }: { result: 'win' | 'loss' | 'draw' | null }) {
  if (!result) return <span className="text-subtle">–</span>
  return (
    <Badge tone={result === 'win' ? 'success' : result === 'loss' ? 'danger' : 'neutral'}>
      {result}
    </Badge>
  )
}
