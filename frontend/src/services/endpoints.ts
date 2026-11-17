import type { Developer, Game, LiveStats, Page, TokenResponse } from '../types/api'
import { api } from './api'

export const authApi = {
  register: (body: { email: string; password: string; display_name: string }) =>
    api<Developer>('/api/v1/auth/register', { method: 'POST', body, auth: false }),
  login: (body: { email: string; password: string }) =>
    api<TokenResponse>('/api/v1/auth/login', { method: 'POST', body, auth: false }),
  me: (signal?: AbortSignal) => api<Developer>('/api/v1/developers/me', { signal }),
}

export const gamesApi = {
  list: (signal?: AbortSignal) => api<Page<Game>>('/api/v1/games?limit=100', { signal }),
  create: (body: { name: string; description?: string; genre?: string | null }) =>
    api<Game>('/api/v1/games', { method: 'POST', body }),
  live: (gameId: string, signal?: AbortSignal) =>
    api<LiveStats>(`/api/v1/games/${gameId}/live`, { signal }),
}
