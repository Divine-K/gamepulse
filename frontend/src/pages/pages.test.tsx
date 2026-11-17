import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  GAME,
  STATS,
  apiError,
  baseRoutes,
  installApi,
  json,
  page,
  renderApp,
  signIn,
} from '../test/harness'
import type { Routes } from '../test/harness'

const PLAYER = {
  id: 'p1',
  external_id: 'steam-1',
  username: 'ada',
  metadata: {},
  is_simulated: false,
  created_at: '2026-11-01T00:00:00Z',
  last_active_at: '2026-11-16T00:00:00Z',
  stats: STATS,
}
const SESSION = {
  id: 's1abcdef-0000',
  status: 'completed',
  result: 'win',
  score: 700,
  started_at: '2026-11-16T10:00:00Z',
  ended_at: '2026-11-16T10:05:00Z',
  duration_seconds: 300,
  last_heartbeat_at: '',
  is_simulated: false,
  player: { id: 'p1', external_id: 'steam-1', username: 'ada' },
}
const ACH = {
  id: 'a1',
  key: 'first_game',
  name: 'First Game',
  icon: 'play',
  description: 'Complete a session.',
  condition_type: 'sessions_completed',
  threshold: 1,
  is_enabled: true,
  created_at: '',
  unlock_count: 2,
  unlock_rate: 0.5,
}

let routes: Routes
let calls: string[]
beforeEach(() => {
  signIn()
  routes = baseRoutes()
  calls = installApi(routes)
})
afterEach(() => vi.unstubAllGlobals())

describe('Players page', () => {
  beforeEach(() => {
    routes['GET /api/v1/games/g1/players?sort=-last_active_at&limit=20&offset=0'] = () =>
      json(page([PLAYER], 45))
    routes['GET /api/v1/games/g1/players?q=ad&sort=-last_active_at&limit=20&offset=0'] = () =>
      json(page([PLAYER], 1))
    routes['GET /api/v1/games/g1/players?sort=-total_score&limit=20&offset=0'] = () =>
      json(page([PLAYER], 45))
    routes['GET /api/v1/games/g1/players?sort=-last_active_at&limit=20&offset=20'] = () =>
      json(page([], 45, 20, 20))
  })

  it('lists players with their stats and links to profiles', async () => {
    renderApp('/players')
    const link = await screen.findByRole('link', { name: 'ada' })
    expect(link).toHaveAttribute('href', '/players/p1')
    expect(screen.getByText('1,200')).toBeInTheDocument() // total score
    expect(screen.getByText('1–20 of 45')).toBeInTheDocument()
  })

  it('searches after a short pause instead of on every keystroke', async () => {
    renderApp('/players')
    await screen.findByRole('link', { name: 'ada' })
    await userEvent.type(screen.getByLabelText('Search players'), 'ad')
    await waitFor(() =>
      expect(calls).toContain(
        'GET /api/v1/games/g1/players?q=ad&sort=-last_active_at&limit=20&offset=0',
      ),
    )
    expect(calls.filter((c) => c.includes('q=a&'))).toHaveLength(0) // no request for the partial "a"
  })

  it('sorts by a column and reports it with aria-sort', async () => {
    renderApp('/players')
    await screen.findByRole('link', { name: 'ada' })
    expect(screen.getByRole('columnheader', { name: /last active/i })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
    await userEvent.click(screen.getByRole('button', { name: /total score/i }))
    await waitFor(() =>
      expect(calls).toContain('GET /api/v1/games/g1/players?sort=-total_score&limit=20&offset=0'),
    )
    expect(await screen.findByRole('columnheader', { name: /total score/i })).toHaveAttribute(
      'aria-sort',
      'descending',
    )
  })

  it('pages through results', async () => {
    renderApp('/players')
    await screen.findByRole('link', { name: 'ada' })
    await userEvent.click(screen.getByRole('button', { name: /next/i }))
    await waitFor(() =>
      expect(calls).toContain(
        'GET /api/v1/games/g1/players?sort=-last_active_at&limit=20&offset=20',
      ),
    )
  })

  it('shows a helpful empty state', async () => {
    routes['GET /api/v1/games/g1/players?sort=-last_active_at&limit=20&offset=0'] = () =>
      json(page([], 0))
    renderApp('/players')
    expect(await screen.findByText('No players yet')).toBeInTheDocument()
  })
})

describe('Game API keys', () => {
  const KEY = {
    id: 'k1',
    name: 'Server',
    key_prefix: 'abc123def456',
    created_at: '2026-11-01T00:00:00Z',
    last_used_at: null,
    revoked_at: null,
  }
  const SECRET = 'gp_abc123def456_' + 'f'.repeat(64)

  beforeEach(() => {
    routes['GET /api/v1/games/g1'] = () => json(GAME)
    routes['GET /api/v1/games/g1/api-keys'] = () => json([KEY])
    routes['GET /api/v1/games/g1/analytics/overview?days=30'] = () =>
      json({ total_players: 1, total_sessions: 1, total_events: 1 })
  })

  it('lists keys masked, never showing a secret', async () => {
    renderApp('/games/g1?tab=keys')
    expect(await screen.findByText(/gp_abc123def456_/)).toBeInTheDocument()
    expect(screen.queryByText(SECRET)).not.toBeInTheDocument()
  })

  it('shows the new secret exactly once', async () => {
    routes['POST /api/v1/games/g1/api-keys'] = () =>
      json({ ...KEY, id: 'k2', name: 'Prod', key: SECRET }, 201)
    renderApp('/games/g1?tab=keys')
    await userEvent.click(await screen.findByRole('button', { name: 'New key' }))
    await userEvent.type(screen.getByLabelText('Key name'), 'Prod')
    await userEvent.click(screen.getByRole('button', { name: 'Create key' }))

    const dialog = await screen.findByRole('dialog', { name: 'Copy your API key' })
    expect(within(dialog).getByText(SECRET)).toBeInTheDocument()
    expect(within(dialog).getByText(/only time the full key is shown/i)).toBeInTheDocument()

    await userEvent.click(within(dialog).getByRole('button', { name: 'I have saved it' }))
    await waitFor(() => expect(screen.queryByText(SECRET)).not.toBeInTheDocument()) // gone for good
  })

  it('asks for confirmation before revoking, then calls the API', async () => {
    const revoke = vi.fn(() => new Response(null, { status: 204 }))
    routes['DELETE /api/v1/games/g1/api-keys/k1'] = revoke
    renderApp('/games/g1?tab=keys')
    await userEvent.click(await screen.findByRole('button', { name: 'Revoke key Server' }))
    expect(revoke).not.toHaveBeenCalled() // the first click only opens the confirmation
    const dialog = await screen.findByRole('dialog', { name: 'Revoke this key?' })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Revoke key' }))
    await waitFor(() => expect(revoke).toHaveBeenCalledOnce())
  })

  it('deleting a game requires typing its name', async () => {
    const remove = vi.fn(() => new Response(null, { status: 204 }))
    routes['DELETE /api/v1/games/g1'] = remove
    renderApp('/games/g1?tab=danger')
    await userEvent.click(await screen.findByRole('button', { name: 'Delete game' }))
    const dialog = await screen.findByRole('dialog')
    const confirm = within(dialog).getByRole('button', { name: 'Delete permanently' })
    expect(confirm).toBeDisabled()
    await userEvent.type(within(dialog).getByLabelText(/Type/), 'Space Runner')
    expect(confirm).toBeEnabled()
    await userEvent.click(confirm)
    await waitFor(() => expect(remove).toHaveBeenCalledOnce())
  })

  it('shows a not-found state for a game that does not exist', async () => {
    routes['GET /api/v1/games/nope'] = () => apiError('game_not_found', 'Game not found.', 404)
    renderApp('/games/nope')
    expect(await screen.findByText('Game not found')).toBeInTheDocument()
  })
})

describe('Leaderboards page', () => {
  const entry = (rank: number, name: string, value: number) => ({
    rank,
    value,
    player: { id: name, external_id: name, username: name },
    stats: STATS,
  })
  beforeEach(() => {
    routes['GET /api/v1/games/g1/leaderboards/total_score?order=desc&limit=20&offset=0'] = () =>
      json({
        ...page([
          entry(1, 'linus', 900),
          entry(2, 'ada', 500),
          entry(2, 'bob', 500),
          entry(4, 'cy', 100),
        ]),
        metric: 'total_score',
        period: 'all',
      })
    routes['GET /api/v1/games/g1/leaderboards/wins?order=desc&limit=20&offset=0'] = () =>
      json({ ...page([entry(1, 'ada', 7)]), metric: 'wins', period: 'all' })
  })

  it('shows ranks with ties sharing a rank, readable by screen readers', async () => {
    renderApp('/leaderboards')
    await screen.findByText('linus') // wait for data, not the loading skeleton
    const rows = screen.getAllByRole('row')
    expect(rows).toHaveLength(5) // header + 4
    expect(within(rows[2]!).getByText(/#2/)).toBeInTheDocument()
    expect(within(rows[3]!).getByText(/#2/)).toBeInTheDocument()
    expect(within(rows[4]!).getByText(/#4/)).toBeInTheDocument()
    expect(within(rows[1]!).getByText('Rank')).toHaveClass('sr-only')
  })

  it('switches the ranking metric', async () => {
    renderApp('/leaderboards')
    await screen.findByText('linus')
    await userEvent.selectOptions(screen.getByLabelText('Rank by'), 'wins')
    await waitFor(() =>
      expect(calls).toContain(
        'GET /api/v1/games/g1/leaderboards/wins?order=desc&limit=20&offset=0',
      ),
    )
    expect(await screen.findByText('7')).toBeInTheDocument()
  })
})

describe('Sessions page', () => {
  beforeEach(() => {
    routes['GET /api/v1/games/g1/sessions?limit=20&offset=0'] = () => json(page([SESSION], 1))
    routes['GET /api/v1/games/g1/sessions?status=active&limit=20&offset=0'] = () =>
      json(page([], 0))
    routes['GET /api/v1/games/g1/events?session_id=s1abcdef-0000&limit=50'] = () =>
      json(
        page([
          {
            id: 'e1',
            event_type: 'session_started',
            player_id: 'p1',
            session_id: 's1',
            occurred_at: '2026-11-16T10:00:00Z',
            received_at: '',
            payload: {},
            is_simulated: false,
            player: null,
          },
        ]),
      )
  })

  it('filters by status', async () => {
    renderApp('/sessions')
    await screen.findByText('ada')
    await userEvent.click(screen.getByRole('radio', { name: 'Active' }))
    await waitFor(() =>
      expect(calls).toContain('GET /api/v1/games/g1/sessions?status=active&limit=20&offset=0'),
    )
    expect(await screen.findByText('There are no active sessions.')).toBeInTheDocument()
  })

  it('opens a detail view with the session’s events', async () => {
    renderApp('/sessions')
    await userEvent.click(
      await screen.findByRole('button', { name: /details for session s1abcdef/i }),
    )
    const dialog = await screen.findByRole('dialog', { name: 'Session details' })
    expect(within(dialog).getByText('Completed')).toBeInTheDocument()
    expect(await within(dialog).findByText('session_started')).toBeInTheDocument()
  })
})

describe('Achievements page', () => {
  beforeEach(() => {
    routes['GET /api/v1/games/g1/achievements'] = () => json([ACH])
    routes['GET /api/v1/games/g1/achievements/unlocks?limit=8'] = () => json(page([]))
  })

  it('shows unlock stats and plain-English conditions', async () => {
    renderApp('/achievements')
    expect(await screen.findByText('First Game')).toBeInTheDocument()
    expect(screen.getByText('Complete 1 session')).toBeInTheDocument()
    expect(screen.getByText('2 players · 50%')).toBeInTheDocument()
    expect(screen.getByText('1 session')).toBeInTheDocument() // singular unit
  })

  it('disables an achievement with the switch', async () => {
    const patch = vi.fn((init: RequestInit) =>
      json({ ...ACH, is_enabled: JSON.parse(String(init.body)).is_enabled }),
    )
    routes['PATCH /api/v1/games/g1/achievements/a1'] = patch
    renderApp('/achievements')
    await userEvent.click(await screen.findByRole('switch', { name: 'Disable First Game' }))
    await waitFor(() => expect(patch).toHaveBeenCalledOnce())
    expect(JSON.parse(String(patch.mock.calls[0]![0].body))).toEqual({ is_enabled: false })
  })

  it('validates the create form and reports a duplicate key from the server', async () => {
    routes['POST /api/v1/games/g1/achievements'] = () =>
      apiError('achievement_key_taken', 'An achievement with this key exists.', 409)
    renderApp('/achievements')
    await userEvent.click(await screen.findByRole('button', { name: 'New achievement' }))
    const dialog = await screen.findByRole('dialog', { name: 'New achievement' })
    await userEvent.type(within(dialog).getByLabelText('Name'), 'Big Spender')
    await userEvent.type(within(dialog).getByLabelText('Key'), 'Bad Key!')
    await userEvent.type(within(dialog).getByLabelText('Threshold'), '5')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))
    expect(await within(dialog).findByText(/lowercase letters, digits/i)).toBeInTheDocument()

    await userEvent.clear(within(dialog).getByLabelText('Key'))
    await userEvent.type(within(dialog).getByLabelText('Key'), 'first_game')
    await userEvent.click(within(dialog).getByRole('button', { name: 'Create' }))
    expect(await within(dialog).findByText('This key is already used')).toBeInTheDocument()
  })
})

describe('Analytics page', () => {
  it('explains missing retention data instead of drawing an empty chart', async () => {
    const points = Array.from({ length: 30 }, (_, i) => ({
      date: `2026-10-${String((i % 28) + 1).padStart(2, '0')}`,
      active_players: 1,
      new_players: 0,
      sessions_started: 1,
      sessions_completed: 1,
      avg_session_duration_seconds: 60,
      events: 3,
    }))
    routes['GET /api/v1/games/g1/analytics/engagement?days=30&include_simulated=true'] = () =>
      json({ days: 30, points })
    routes['GET /api/v1/games/g1/analytics/retention?include_simulated=true'] = () =>
      json({
        points: [1, 7, 30].map((day) => ({
          day,
          eligible_players: 0,
          retained_players: 0,
          rate: null,
        })),
      })
    routes['GET /api/v1/games/g1/analytics/scores?include_simulated=true'] = () =>
      json({
        completed_sessions: 0,
        average: null,
        median: null,
        p90: null,
        min: null,
        max: null,
        buckets: [],
      })
    routes['GET /api/v1/games/g1/analytics/achievements?days=30&include_simulated=true'] = () =>
      json({ total_unlocks: 0, achievements: [], unlocks_by_day: [], days: 30 })
    renderApp('/analytics')
    expect(await screen.findByText(/not enough history yet/i)).toBeInTheDocument()
    expect(await screen.findByText('No completed sessions yet.')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Table' }).length).toBeGreaterThanOrEqual(6) // every chart has a table view
  })

  it('reveals a chart’s exact values in a table', async () => {
    routes['GET /api/v1/games/g1/analytics/engagement?days=30&include_simulated=true'] = () =>
      json({
        days: 30,
        points: [
          {
            date: '2026-11-16',
            active_players: 7,
            new_players: 2,
            sessions_started: 9,
            sessions_completed: 8,
            avg_session_duration_seconds: 30,
            events: 40,
          },
        ],
      })
    routes['GET /api/v1/games/g1/analytics/retention?include_simulated=true'] = () =>
      json({ points: [] })
    routes['GET /api/v1/games/g1/analytics/scores?include_simulated=true'] = () =>
      json({
        completed_sessions: 0,
        average: null,
        median: null,
        p90: null,
        min: null,
        max: null,
        buckets: [],
      })
    routes['GET /api/v1/games/g1/analytics/achievements?days=30&include_simulated=true'] = () =>
      json({ total_unlocks: 0, achievements: [], unlocks_by_day: [], days: 30 })
    renderApp('/analytics')
    const [first] = await screen.findAllByRole('button', { name: 'Table' })
    await userEvent.click(first!)
    const table = await screen.findByRole('table', { name: 'Player engagement' })
    expect(within(table).getByText('7')).toBeInTheDocument()
  })
})

describe('Settings page', () => {
  it('rejects mismatched new passwords before calling the API', async () => {
    renderApp('/settings')
    await userEvent.type(await screen.findByLabelText('Current password'), 'old-password')
    await userEvent.type(screen.getByLabelText('New password'), 'new-password-1')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'different')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
    expect(calls.some((c) => c.startsWith('PATCH'))).toBe(false)
  })

  it('reports a wrong current password on the field', async () => {
    routes['PATCH /api/v1/developers/me'] = () =>
      apiError('invalid_credentials', 'Current password is incorrect.', 403)
    renderApp('/settings')
    await userEvent.type(await screen.findByLabelText('Current password'), 'wrong-wrong')
    await userEvent.type(screen.getByLabelText('New password'), 'new-password-1')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'new-password-1')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Current password is incorrect')).toBeInTheDocument()
  })

  it('signs out after a successful password change, because old tokens stop working', async () => {
    const patch = vi.fn((_init: RequestInit) =>
      json({
        id: 'u1',
        email: 'ada@example.com',
        display_name: 'Ada',
        role: 'developer',
        created_at: '',
      }),
    )
    routes['PATCH /api/v1/developers/me'] = patch
    renderApp('/settings')
    await userEvent.type(await screen.findByLabelText('Current password'), 'old-password')
    await userEvent.type(screen.getByLabelText('New password'), 'new-password-1')
    await userEvent.type(screen.getByLabelText('Confirm new password'), 'new-password-1')
    await userEvent.click(screen.getByRole('button', { name: 'Change password' }))
    await waitFor(() => expect(patch).toHaveBeenCalledOnce())
    expect(JSON.parse(String(patch.mock.calls[0]![0].body))).toEqual({
      current_password: 'old-password',
      new_password: 'new-password-1',
    })
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('updates the display name', async () => {
    const patch = vi.fn((init: RequestInit) =>
      json({
        ...JSON.parse(String(init.body)),
        id: 'u1',
        email: 'ada@example.com',
        role: 'developer',
        created_at: '',
      }),
    )
    routes['PATCH /api/v1/developers/me'] = patch
    renderApp('/settings')
    const field = await screen.findByLabelText('Display name')
    await userEvent.clear(field)
    await userEvent.type(field, 'Ada L.')
    await userEvent.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patch).toHaveBeenCalledOnce())
    expect(JSON.parse(String(patch.mock.calls[0]![0].body))).toEqual({ display_name: 'Ada L.' })
  })
})
