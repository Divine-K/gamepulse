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
