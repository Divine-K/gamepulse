/** Shapes returned by the GamePulse API (see docs/api-guide.md). */

export interface Developer {
  id: string
  email: string
  display_name: string
  role: 'developer' | 'admin'
  created_at: string
}

export interface TokenResponse {
  access_token: string
  token_type: 'bearer'
  expires_in: number
}

export interface Game {
  id: string
  name: string
  slug: string
  description: string
  genre: string | null
  created_at: string
  updated_at: string
}

export interface Page<T> {
  items: T[]
  total: number
  limit: number
  offset: number
}

export interface LiveStats {
  active_players: number
  source: 'redis' | 'postgres'
  dashboards_connected: number
}

export interface ApiErrorBody {
  error: {
    code: string
    message: string
    details: { field?: string; message?: string }[]
    request_id: string | null
  }
}

export type GameEventType =
  | 'player.registered'
  | 'session.started'
  | 'session.ended'
  | 'session.abandoned'
  | 'score.submitted'
  | 'achievement.unlocked'
  | 'leaderboard.updated'
  | 'event.received'

export interface PlayerBrief {
  id: string
  external_id: string
  username: string
}

export interface SessionPayload {
  id: string
  status: string
  result: string | null
  score: number
  player: PlayerBrief
}

/** Real-time event envelope pushed over the game WebSocket. */
export interface GameEvent {
  id: string
  type: GameEventType
  game_id: string
  ts: string
  is_simulated: boolean
  data: {
    player?: PlayerBrief
    session?: SessionPayload
    active_players?: number | null
    category?: string
    value?: number
    achievement?: { id: string; key: string; name: string; icon: string }
    metric?: string
    rank?: number | null
    event?: {
      id: string
      event_type: string
      player_id: string | null
      payload: Record<string, unknown>
    }
  }
}

// --- Phase 9 resources ---------------------------------------------------------------

export interface ApiKey {
  id: string
  name: string
  key_prefix: string
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

/** Returned only when a key is created or rotated: the secret is never shown again. */
export interface ApiKeyCreated extends ApiKey {
  key: string
}

export interface PlayerStats {
  total_sessions: number
  completed_sessions: number
  total_score: number
  best_score: number
  wins: number
  total_play_seconds: number
  achievements_count: number
}

export interface Player extends PlayerBrief {
  metadata: Record<string, unknown>
  is_simulated: boolean
  created_at: string
  last_active_at: string
  stats: PlayerStats
}

export type SessionStatus = 'active' | 'completed' | 'abandoned'

export interface GameSessionRecord {
  id: string
  status: SessionStatus
  result: 'win' | 'loss' | 'draw' | null
  score: number
  started_at: string
  ended_at: string | null
  duration_seconds: number | null
  last_heartbeat_at: string
  is_simulated: boolean
  player: PlayerBrief
}

export type LeaderboardMetric =
  'total_score' | 'best_score' | 'wins' | 'achievements' | 'completed_sessions'

export interface LeaderboardEntry {
  rank: number
  value: number
  player: PlayerBrief
  stats: PlayerStats
}

export interface LeaderboardPage extends Page<LeaderboardEntry> {
  metric: string
  period: string
}

export type ConditionType =
  'sessions_completed' | 'score_reached' | 'total_play_seconds' | 'wins' | 'leaderboard_rank'

export interface Achievement {
  id: string
  key: string
  name: string
  icon: string
  description: string
  condition_type: ConditionType
  threshold: number
  is_enabled: boolean
  created_at: string
  unlock_count: number
  unlock_rate: number
}

export interface Unlock {
  id: string
  unlocked_at: string
  session_id: string | null
  achievement: { id: string; key: string; name: string; icon: string }
  player: PlayerBrief
}

export interface EventRecord {
  id: string
  event_type: string
  player_id: string | null
  session_id: string | null
  occurred_at: string
  received_at: string
  payload: Record<string, unknown>
  is_simulated: boolean
  player: PlayerBrief | null
}

export interface WindowStats {
  new_players: number
  sessions: number
  active_players: number
  events: number
  avg_session_duration_seconds: number | null
}

export interface Overview {
  total_players: number
  total_sessions: number
  completed_sessions: number
  total_events: number
  avg_session_duration_seconds: number | null
  daily_active_players: number
  monthly_active_players: number
  currently_active_players: number
  currently_active_source: string
  period_days: number
  current: WindowStats
  previous: WindowStats
  include_simulated: boolean
}

export interface EngagementPoint {
  date: string
  active_players: number
  new_players: number
  sessions_started: number
  sessions_completed: number
  avg_session_duration_seconds: number | null
  events: number
}

export interface RetentionPoint {
  day: number
  eligible_players: number
  retained_players: number
  rate: number | null
}

export interface ScoreBucket {
  start: number
  end: number
  count: number
}

export interface ScoreDistribution {
  completed_sessions: number
  average: number | null
  median: number | null
  p90: number | null
  min: number | null
  max: number | null
  buckets: ScoreBucket[]
}

export interface AchievementAnalytics {
  total_unlocks: number
  achievements: {
    key: string
    name: string
    icon: string
    is_enabled: boolean
    unlock_count: number
    unlock_rate: number
  }[]
  unlocks_by_day: { date: string; count: number }[]
  days: number
}
