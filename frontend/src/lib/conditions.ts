import { formatDuration } from './format'
import type { ConditionType } from '../types/api'

export const CONDITION_OPTIONS: { value: ConditionType; label: string; unit: string }[] = [
  { value: 'sessions_completed', label: 'Sessions completed', unit: 'sessions' },
  { value: 'score_reached', label: 'Score in a single session', unit: 'points' },
  { value: 'total_play_seconds', label: 'Total play time', unit: 'seconds' },
  { value: 'wins', label: 'Wins', unit: 'wins' },
  { value: 'leaderboard_rank', label: 'Leaderboard rank (total score)', unit: 'rank' },
]

/** Plain-English description of an achievement condition. */
export function describeCondition(type: ConditionType, threshold: number): string {
  switch (type) {
    case 'sessions_completed':
      return `Complete ${threshold} session${threshold === 1 ? '' : 's'}`
    case 'score_reached':
      return `Score ${threshold.toLocaleString()} or more in one session`
    case 'total_play_seconds':
      return `Play for ${formatDuration(threshold)} in total`
    case 'wins':
      return `Win ${threshold} session${threshold === 1 ? '' : 's'}`
    case 'leaderboard_rank':
      return threshold === 1
        ? 'Reach #1 on the leaderboard'
        : `Reach the top ${threshold} on the leaderboard`
  }
}
