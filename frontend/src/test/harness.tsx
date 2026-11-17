import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { vi } from 'vitest'
import App from '../App'
import { ToastProvider } from '../components/ui/Toast'
import { AuthProvider } from '../context/AuthContext'
import { ThemeProvider } from '../context/ThemeContext'
import { tokenStore } from '../services/api'

export const USER = {
  id: 'u1',
  email: 'ada@example.com',
  display_name: 'Ada',
  role: 'developer',
  created_at: '',
}
export const GAME = {
  id: 'g1',
  name: 'Space Runner',
  slug: 'space-runner',
  description: 'An endless runner',
  genre: 'arcade',
  created_at: '',
  updated_at: '',
}
export const STATS = {
  total_sessions: 4,
  completed_sessions: 3,
  total_score: 1200,
  best_score: 700,
  wins: 2,
  total_play_seconds: 400,
  achievements_count: 1,
}
export const page = <T,>(items: T[], total = items.length, limit = 20, offset = 0) => ({
  items,
  total,
  limit,
  offset,
})
export const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })
export const apiError = (code: string, message: string, status: number) =>
  json({ error: { code, message, details: [], request_id: null } }, status)

class IdleSocket {
  close() {}
  send() {}
}

type Handler = (init: RequestInit, url: string) => Response | Promise<Response>
export type Routes = Record<string, Handler>

/** Replace fetch with a router keyed by "METHOD /path?query". Returns the call log. */
export function installApi(routes: Routes) {
  vi.stubGlobal('WebSocket', IdleSocket)
  const calls: string[] = []
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string, init: RequestInit = {}) => {
      const path = url.replace('http://localhost:8000', '')
      const key = `${init.method ?? 'GET'} ${path}`
      calls.push(key)
      const handler = routes[key]
      return Promise.resolve(
        handler ? handler(init, path) : apiError('not_found', `no mock for ${key}`, 404),
      )
    }),
  )
  return calls
}

export function renderApp(path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ThemeProvider>
        <ToastProvider>
          <MemoryRouter initialEntries={[path]}>
            <AuthProvider>
              <App />
            </AuthProvider>
          </MemoryRouter>
        </ToastProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

/** Standard routes for a signed-in developer with one game. */
export function baseRoutes(): Routes {
  return {
    'GET /api/v1/developers/me': () => json(USER),
    'GET /api/v1/games?limit=100': () => json(page([GAME], 1, 100)),
    'GET /api/v1/games/g1/live': () =>
      json({ active_players: 3, source: 'redis', dashboards_connected: 1 }),
  }
}

export function signIn() {
  tokenStore.set('saved')
}
