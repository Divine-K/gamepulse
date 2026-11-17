import type { GameEvent } from '../types/api'

export interface EventView {
  title: string
  detail: string
  tone: 'accent' | 'success' | 'warning' | 'danger' | 'info' | 'neutral'
}

/** Human-readable summary of a real-time event. */
export function describeEvent(event: GameEvent): EventView {
  const d = event.data
  const who = d.player?.username ?? d.session?.player.username ?? 'A player'
  switch (event.type) {
    case 'player.registered':
      return { title: 'Player registered', detail: who, tone: 'neutral' }
    case 'session.started':
      return { title: 'Session started', detail: who, tone: 'success' }
    case 'session.ended': {
      const s = d.session
      const result = s?.result ? ` · ${s.result}` : ''
      return {
        title: 'Session ended',
        detail: `${who} · score ${s?.score ?? 0}${result}`,
        tone: 'info',
      }
    }
    case 'session.abandoned':
      return { title: 'Session abandoned', detail: `${who} timed out`, tone: 'danger' }
    case 'score.submitted':
      return {
        title: 'Score submitted',
        detail: `${who} · ${d.category} ${d.value}`,
        tone: 'warning',
      }
    case 'achievement.unlocked':
      return {
        title: 'Achievement unlocked',
        detail: `${who} · ${d.achievement?.name ?? ''}`,
        tone: 'accent',
      }
    case 'leaderboard.updated':
      return {
        title: 'Leaderboard updated',
        detail: `${who} is now #${d.rank ?? '?'} on ${d.metric ?? 'total_score'}`,
        tone: 'neutral',
      }
    default:
      return { title: event.type, detail: '', tone: 'neutral' }
  }
}
