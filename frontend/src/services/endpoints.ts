import type {
  Achievement,
  AchievementAnalytics,
  ApiKey,
  ApiKeyCreated,
  Developer,
  EngagementPoint,
  EventRecord,
  Game,
  GameSessionRecord,
  LeaderboardPage,
  LiveStats,
  Overview,
  Page,
  Player,
  RetentionPoint,
  ScoreDistribution,
  TokenResponse,
  Unlock,
} from '../types/api'
import { api } from './api'

type Query = Record<string, string | number | boolean | null | undefined>

/** Build a query string, skipping empty values. */
export function qs(params: Query): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') search.set(key, String(value))
  }
  const text = search.toString()
  return text ? `?${text}` : ''
}

const game = (id: string) => `/api/v1/games/${id}`

export const authApi = {
  register: (body: { email: string; password: string; display_name: string }) =>
    api<Developer>('/api/v1/auth/register', { method: 'POST', body, auth: false }),
  login: (body: { email: string; password: string }) =>
    api<TokenResponse>('/api/v1/auth/login', { method: 'POST', body, auth: false }),
  me: (signal?: AbortSignal) => api<Developer>('/api/v1/developers/me', { signal }),
  updateMe: (body: { display_name?: string; current_password?: string; new_password?: string }) =>
    api<Developer>('/api/v1/developers/me', { method: 'PATCH', body }),
}

export const gamesApi = {
  list: (signal?: AbortSignal) => api<Page<Game>>('/api/v1/games?limit=100', { signal }),
  get: (id: string, signal?: AbortSignal) => api<Game>(game(id), { signal }),
  create: (body: { name: string; description?: string; genre?: string | null }) =>
    api<Game>('/api/v1/games', { method: 'POST', body }),
  update: (id: string, body: { name?: string; description?: string; genre?: string | null }) =>
    api<Game>(game(id), { method: 'PATCH', body }),
  remove: (id: string) => api<void>(game(id), { method: 'DELETE' }),
  live: (id: string, signal?: AbortSignal) => api<LiveStats>(`${game(id)}/live`, { signal }),
}

export const keysApi = {
  list: (gameId: string, signal?: AbortSignal) =>
    api<ApiKey[]>(`${game(gameId)}/api-keys`, { signal }),
  create: (gameId: string, name: string) =>
    api<ApiKeyCreated>(`${game(gameId)}/api-keys`, { method: 'POST', body: { name } }),
  rotate: (gameId: string, keyId: string) =>
    api<ApiKeyCreated>(`${game(gameId)}/api-keys/${keyId}/rotate`, { method: 'POST' }),
  revoke: (gameId: string, keyId: string) =>
    api<void>(`${game(gameId)}/api-keys/${keyId}`, { method: 'DELETE' }),
}

export const playersApi = {
  list: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<Page<Player>>(`${game(gameId)}/players${qs(query)}`, { signal }),
  get: (gameId: string, playerId: string, signal?: AbortSignal) =>
    api<Player>(`${game(gameId)}/players/${playerId}`, { signal }),
  sessions: (gameId: string, playerId: string, query: Query, signal?: AbortSignal) =>
    api<Page<GameSessionRecord>>(`${game(gameId)}/players/${playerId}/sessions${qs(query)}`, {
      signal,
    }),
  achievements: (gameId: string, playerId: string, query: Query, signal?: AbortSignal) =>
    api<Page<Unlock>>(`${game(gameId)}/players/${playerId}/achievements${qs(query)}`, { signal }),
}

export const sessionsApi = {
  list: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<Page<GameSessionRecord>>(`${game(gameId)}/sessions${qs(query)}`, { signal }),
}

export const eventsApi = {
  list: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<Page<EventRecord>>(`${game(gameId)}/events${qs(query)}`, { signal }),
}

export const leaderboardApi = {
  get: (gameId: string, metric: string, query: Query, signal?: AbortSignal) =>
    api<LeaderboardPage>(`${game(gameId)}/leaderboards/${metric}${qs(query)}`, { signal }),
}

export const achievementsApi = {
  list: (gameId: string, signal?: AbortSignal) =>
    api<Achievement[]>(`${game(gameId)}/achievements`, { signal }),
  create: (
    gameId: string,
    body: {
      key: string
      name: string
      description?: string
      condition_type: string
      threshold: number
      icon?: string
    },
  ) => api<Achievement>(`${game(gameId)}/achievements`, { method: 'POST', body }),
  update: (
    gameId: string,
    id: string,
    body: { name?: string; description?: string; threshold?: number; is_enabled?: boolean },
  ) => api<Achievement>(`${game(gameId)}/achievements/${id}`, { method: 'PATCH', body }),
  unlocks: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<Page<Unlock>>(`${game(gameId)}/achievements/unlocks${qs(query)}`, { signal }),
}

export const analyticsApi = {
  overview: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<Overview>(`${game(gameId)}/analytics/overview${qs(query)}`, { signal }),
  engagement: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<{ days: number; points: EngagementPoint[] }>(
      `${game(gameId)}/analytics/engagement${qs(query)}`,
      { signal },
    ),
  retention: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<{ points: RetentionPoint[] }>(`${game(gameId)}/analytics/retention${qs(query)}`, {
      signal,
    }),
  scores: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<ScoreDistribution>(`${game(gameId)}/analytics/scores${qs(query)}`, { signal }),
  achievements: (gameId: string, query: Query, signal?: AbortSignal) =>
    api<AchievementAnalytics>(`${game(gameId)}/analytics/achievements${qs(query)}`, { signal }),
}
