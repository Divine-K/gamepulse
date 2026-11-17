import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
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

const SIM_PLAYER = {
  id: 'sp1',
  external_id: 'sim_ab12cd34',
  username: 'Sim ab12',
  metadata: {},
  is_simulated: true,
  created_at: '2026-11-16T00:00:00Z',
  last_active_at: '2026-11-16T00:00:00Z',
  stats: STATS,
}
const SESSION = {
  id: 'sess-1',
  status: 'active',
  result: null,
  score: 0,
  started_at: '2026-11-16T10:00:00Z',
  ended_at: null,
  duration_seconds: null,
  last_heartbeat_at: '',
  is_simulated: true,
  player: { id: 'sp1', external_id: 'sim_ab12cd34', username: 'Sim ab12', is_simulated: true },
}
const SECRET = `gp_abc123def456_${'f'.repeat(64)}`

let routes: Routes
let calls: string[]
const bodyOf = (fn: ReturnType<typeof vi.fn>, index = 0) =>
  JSON.parse(String(fn.mock.calls[index]![0].body))

beforeEach(() => {
  signIn()
  routes = baseRoutes()
  calls = installApi(routes)
})
afterEach(() => vi.unstubAllGlobals())

describe('Simulator page', () => {
  const sim = '/api/v1/games/g1/simulator'
  beforeEach(() => {
    routes['GET /api/v1/games/g1/achievements'] = () => json([])
    routes[`GET ${sim}/summary`] = () => json({ players: 0, sessions: 0, events: 0 })
    routes[`GET ${sim}/players`] = () => json(page([]))
  })

  it('explains what is disabled until a test player exists', async () => {
    renderApp('/simulator')
    expect(await screen.findByRole('button', { name: 'Start session' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Send score update' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'End session' })).toBeDisabled()
    expect(screen.getByText('Create a test player first.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Delete all simulated data' })).toBeDisabled() // nothing to delete
  })

  it('drives a whole session: player, start, score, event, end', async () => {
    let players = [] as unknown[]
    routes[`GET ${sim}/players`] = () => json(page(players))
    const createPlayer = vi.fn(() => {
      players = [SIM_PLAYER]
      return json(SIM_PLAYER, 201)
    })
    const start = vi.fn(() => json(SESSION, 201))
    const score = vi.fn(() => json({ value: 900 }, 201))
    const event = vi.fn(() => json({ id: 'e1' }, 201))
    const end = vi.fn(() =>
      json({ ...SESSION, status: 'completed', unlocked_achievements: [{ name: 'First Game' }] }),
    )
    routes[`POST ${sim}/players`] = createPlayer
    routes[`POST ${sim}/sessions`] = start
    routes[`POST ${sim}/sessions/sess-1/score`] = score
    routes[`POST ${sim}/events`] = event
    routes[`POST ${sim}/sessions/sess-1/end`] = end

    renderApp('/simulator')
    await userEvent.type(await screen.findByLabelText(/New test player name/), 'Tester')
    await userEvent.click(screen.getByRole('button', { name: 'New test player' }))
    await waitFor(() => expect(createPlayer).toHaveBeenCalledOnce())
    expect(bodyOf(createPlayer)).toEqual({ username: 'Tester' })

    const startButton = screen.getByRole('button', { name: 'Start session' })
    await waitFor(() => expect(startButton).toBeEnabled())
    await userEvent.click(startButton)
    await waitFor(() => expect(start).toHaveBeenCalledOnce())
    expect(bodyOf(start)).toEqual({ player_id: 'sp1' })
    expect(await screen.findByText('Active')).toBeInTheDocument()

    await userEvent.clear(screen.getByLabelText('Score'))
    await userEvent.type(screen.getByLabelText('Score'), '900')
    await userEvent.click(screen.getByRole('button', { name: 'Send score update' }))
    await waitFor(() => expect(score).toHaveBeenCalledOnce())
    expect(bodyOf(score)).toEqual({ value: 900 })

    await userEvent.click(screen.getByRole('button', { name: 'Send custom event' }))
    await waitFor(() => expect(event).toHaveBeenCalledOnce())
    expect(bodyOf(event)).toEqual({
      event_type: 'custom_boss_defeated',
      player_id: 'sp1',
      session_id: 'sess-1',
      payload: { boss: 'kraken' },
    })

    await userEvent.click(screen.getByRole('button', { name: 'End session' }))
    await waitFor(() => expect(end).toHaveBeenCalledOnce())
    expect(bodyOf(end)).toEqual({ result: 'win' })
    expect(await screen.findByText('Unlocked: First Game')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'End session' })).toBeDisabled() // the session is over
  })

  it('rejects a payload that is not a JSON object before sending anything', async () => {
    const event = vi.fn(() => json({ id: 'e1' }, 201))
    routes[`POST ${sim}/events`] = event
    renderApp('/simulator')
    const payload = await screen.findByLabelText('Payload (JSON)')
    await userEvent.clear(payload)
    await userEvent.type(payload, 'not json')
    await userEvent.click(screen.getByRole('button', { name: 'Send custom event' }))
    expect(await screen.findByText(/must be a JSON object/i)).toBeInTheDocument()
    expect(event).not.toHaveBeenCalled()
  })

  it('shows the server’s reason when an action is refused', async () => {
    routes[`GET ${sim}/players`] = () => json(page([SIM_PLAYER]))
    routes[`POST ${sim}/sessions`] = () =>
      apiError('session_already_active', 'This player already has an active session.', 409)
    renderApp('/simulator')
    const start = await screen.findByRole('button', { name: 'Start session' })
    await waitFor(() => expect(start).toBeEnabled())
    await userEvent.click(start)
    expect(
      await screen.findByText('This player already has an active session.'),
    ).toBeInTheDocument()
  })

  it('only deletes simulated data, after a confirmation that says so', async () => {
    routes[`GET ${sim}/summary`] = () => json({ players: 2, sessions: 3, events: 14 })
    const clear = vi.fn(() => json({ deleted: { players: 2, sessions: 3, events: 14 } }))
    routes[`DELETE ${sim}/data`] = clear
    renderApp('/simulator')
    expect(await screen.findByText('14')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: 'Delete all simulated data' }))
    expect(clear).not.toHaveBeenCalled() // the first click only asks
    const dialog = await screen.findByRole('dialog', { name: 'Delete all simulated data?' })
    expect(dialog).toHaveAccessibleDescription(
      /2 simulated players, 3 sessions and 14 events.*Real data is not affected/,
    )
    await userEvent.click(within(dialog).getByRole('button', { name: 'Delete simulated data' }))
    await waitFor(() => expect(clear).toHaveBeenCalledOnce())
    expect(await screen.findByText(/Real data was not touched/)).toBeInTheDocument()
  })
})

describe('API Playground', () => {
  const sessionResponse = { id: 'sess-42', status: 'active' }

  const send = async () => userEvent.click(screen.getByRole('button', { name: 'Send request' }))
  const useKey = async (key = SECRET) => {
    await userEvent.type(await screen.findByLabelText('Paste an API key'), key)
    await userEvent.click(screen.getByRole('button', { name: 'Use key' }))
  }

  it('lists the endpoints with their method and description', async () => {
    renderApp('/playground')
    const list = await screen.findByRole('navigation', { name: 'Endpoints' })
    expect(within(list).getByRole('button', { name: /Start a session/ })).toBeInTheDocument()
    await userEvent.click(within(list).getByRole('button', { name: /Submit a score/ }))
    expect(screen.getByText('/api/v1/game/scores')).toBeInTheDocument()
    expect(screen.getByText(/separate ranking/)).toBeInTheDocument()
  })

  it('cannot send without a key, and never shows the secret once it has one', async () => {
    renderApp('/playground')
    expect(await screen.findByRole('button', { name: 'Send request' })).toBeDisabled()
    await useKey()
    expect(screen.getByText('gp_abc123def456_••••••••')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send request' })).toBeEnabled()
    expect(document.body.innerHTML).not.toContain(SECRET)
    expect(document.body.innerHTML).not.toContain('f'.repeat(20))
  })

  it('sends a real request with the key header and shows status, timing and formatted JSON', async () => {
    const me = vi.fn((_init: RequestInit) => json({ id: 'g1', name: 'Space Runner' }))
    routes['GET /api/v1/game/me'] = me
    renderApp('/playground')
    await useKey()
    await send()

    const status = await screen.findByRole('status', { name: 'Response summary' })
    expect(status).toHaveTextContent('200')
    expect(status).toHaveTextContent(/\d+ ms/)
    expect(me.mock.calls[0]![0].headers).toMatchObject({ 'X-API-Key': SECRET })
    const body = screen.getByLabelText('Response body')
    expect(body).toHaveTextContent('"name": "Space Runner"') // pretty-printed
    expect(document.body.innerHTML).not.toContain(SECRET)
  })

  it('shows error responses as such', async () => {
    routes['GET /api/v1/game/me'] = () =>
      apiError('invalid_api_key', 'Missing or invalid API key.', 401)
    renderApp('/playground')
    await useKey()
    await send()
    expect(await screen.findByRole('status', { name: 'Response summary' })).toHaveTextContent('401')
    expect(screen.getByLabelText('Response body')).toHaveTextContent('invalid_api_key')
  })

  it('reports an unreachable server', async () => {
    routes['GET /api/v1/game/me'] = () => {
      throw new TypeError('Failed to fetch') // what fetch does when the server is down
    }
    renderApp('/playground')
    await useKey()
    await send()
    expect(await screen.findByRole('alert')).toHaveTextContent(/could not reach the server/i)
  })

  it('blocks invalid JSON bodies before sending', async () => {
    renderApp('/playground')
    await userEvent.click(await screen.findByRole('button', { name: /Register a player/ }))
    await useKey()
    const body = screen.getByLabelText('Request body (JSON)')
    await userEvent.clear(body)
    await userEvent.type(body, '{{"external_id": ')
    expect(await screen.findByText(/Invalid JSON/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Send request' })).toBeDisabled()
  })

  it('carries a new session id into the next request automatically', async () => {
    routes['POST /api/v1/game/sessions'] = () => json(sessionResponse, 201)
    renderApp('/playground')
    await userEvent.click(await screen.findByRole('button', { name: /Start a session/ }))
    await useKey()
    await send()
    await screen.findByRole('status', { name: 'Response summary' })

    await userEvent.click(screen.getByRole('button', { name: /Keep a session alive/ }))
    expect(screen.getByLabelText('Request preview')).toHaveTextContent(
      '/api/v1/game/sessions/sess-42/heartbeat',
    )
  })

  it('offers copy-ready examples that use a placeholder instead of the key', async () => {
    renderApp('/playground')
    await useKey()
    expect(screen.getByLabelText('Request preview')).toHaveTextContent(
      'X-API-Key: gp_abc123def456_••••••••',
    )
    expect(await screen.findByText(/\$GAMEPULSE_KEY/)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('tab', { name: 'Python' }))
    expect(screen.getByText(/os\.environ\["GAMEPULSE_KEY"\]/)).toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(SECRET)
  })

  it('can create a throwaway key through the dashboard API', async () => {
    const create = vi.fn((_init: RequestInit) =>
      json(
        {
          id: 'k9',
          name: 'Playground',
          key_prefix: 'abc123def456',
          created_at: '',
          last_used_at: null,
          revoked_at: null,
          key: SECRET,
        },
        201,
      ),
    )
    routes['POST /api/v1/games/g1/api-keys'] = create
    renderApp('/playground')
    await userEvent.click(await screen.findByRole('button', { name: 'Create a playground key' }))
    await waitFor(() => expect(create).toHaveBeenCalledOnce())
    expect(JSON.parse(String(create.mock.calls[0]![0].body))).toEqual({ name: 'Playground' })
    expect(await screen.findByText('gp_abc123def456_••••••••')).toBeInTheDocument()
    expect(document.body.innerHTML).not.toContain(SECRET)
    expect(calls).toContain('POST /api/v1/games/g1/api-keys')
  })
})
