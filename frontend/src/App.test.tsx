import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { tokenStore } from './services/api'
import {
  GAME,
  STATS,
  apiError,
  baseRoutes,
  installApi,
  json,
  page,
  renderApp,
} from './test/harness'
import type { Routes } from './test/harness'

const overview = {
  total_players: 5,
  total_sessions: 12,
  completed_sessions: 10,
  total_events: 80,
  avg_session_duration_seconds: 90,
  daily_active_players: 2,
  monthly_active_players: 4,
  currently_active_players: 3,
  currently_active_source: 'redis',
  period_days: 30,
  current: {
    new_players: 2,
    sessions: 12,
    active_players: 4,
    events: 80,
    avg_session_duration_seconds: 90,
  },
  previous: {
    new_players: 1,
    sessions: 6,
    active_players: 2,
    events: 40,
    avg_session_duration_seconds: 60,
  },
  include_simulated: true,
}

function dashboardRoutes(): Routes {
  return {
    ...baseRoutes(),
    'POST /api/v1/auth/login': () =>
      json({ access_token: 'tok', token_type: 'bearer', expires_in: 3600 }),
    'GET /api/v1/games/g1/analytics/overview?days=30': () => json(overview),
    'GET /api/v1/games/g1/analytics/engagement?days=30': () => json({ days: 30, points: [] }),
    'GET /api/v1/games/g1/leaderboards/total_score?limit=5': () =>
      json({
        ...page([
          {
            rank: 1,
            value: 700,
            player: { id: 'p1', external_id: 'x', username: 'ada' },
            stats: STATS,
          },
        ]),
        metric: 'total_score',
        period: 'all',
      }),
    'GET /api/v1/games/g1/achievements/unlocks?limit=5': () => json(page([])),
    'GET /api/v1/games/g1/sessions?limit=6': () => json(page([])),
    'GET /api/v1/games/g1/achievements': () => json([]),
  }
}

describe('app auth flow', () => {
  let routes: Routes
  beforeEach(() => {
    routes = dashboardRoutes()
    installApi(routes)
  })
  afterEach(() => vi.unstubAllGlobals())

  it('redirects anonymous visitors to the login page', async () => {
    renderApp('/games')
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('logs in and shows the overview with real numbers from the API', async () => {
    renderApp('/')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Space Runner' })).toBeInTheDocument()
    expect(await screen.findByText('3 online now')).toBeInTheDocument()
    expect(await screen.findByText('ada')).toBeInTheDocument() // top player
    expect(tokenStore.get()).toBe('tok')
  })

  it('shows the server message for wrong credentials and stays on the form', async () => {
    routes['POST /api/v1/auth/login'] = () =>
      apiError('invalid_credentials', 'Incorrect email or password.', 401)
    renderApp('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
    expect(tokenStore.get()).toBeNull()
  })

  it('validates the form before calling the API', async () => {
    renderApp('/login')
    await userEvent.click(await screen.findByRole('button', { name: 'Log in' }))
    expect(await screen.findByText('Enter a valid email address')).toBeInTheDocument()
    expect(fetch).not.toHaveBeenCalled()
  })

  it('restores a saved session after a refresh', async () => {
    tokenStore.set('saved')
    renderApp('/')
    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument()
  })

  it('signs out when the saved token is rejected', async () => {
    tokenStore.set('expired')
    routes['GET /api/v1/developers/me'] = () =>
      apiError('invalid_token', 'Invalid or expired token.', 401)
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    await waitFor(() => expect(tokenStore.get()).toBeNull())
  })

  it('marks unbuilt pages honestly instead of faking them', async () => {
    tokenStore.set('saved')
    renderApp('/playground')
    expect(await screen.findByText('Not built yet')).toBeInTheDocument()
  })

  it('shows a register-first message when the developer has no games', async () => {
    tokenStore.set('saved')
    routes['GET /api/v1/games?limit=100'] = () => json(page([], 0, 100))
    renderApp('/players')
    expect(await screen.findByText('Register a game first')).toBeInTheDocument()
  })
})

export { GAME }
