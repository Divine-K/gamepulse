import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import App from './App'
import { ToastProvider } from './components/ui/Toast'
import { AuthProvider } from './context/AuthContext'
import { ThemeProvider } from './context/ThemeContext'
import { tokenStore } from './services/api'

const USER = {
  id: 'u1',
  email: 'ada@example.com',
  display_name: 'Ada',
  role: 'developer',
  created_at: '',
}
const GAME = {
  id: 'g1',
  name: 'Space Runner',
  slug: 'space-runner',
  description: '',
  genre: null,
  created_at: '',
  updated_at: '',
}

class IdleSocket {
  close() {}
  send() {}
}

type Handler = (init: RequestInit) => Response | Promise<Response>
let routes: Record<string, Handler>

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status })

function renderApp(path = '/') {
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

describe('app auth flow', () => {
  beforeEach(() => {
    vi.stubGlobal('WebSocket', IdleSocket)
    routes = {
      'POST /api/v1/auth/login': () =>
        json({ access_token: 'tok', token_type: 'bearer', expires_in: 3600 }),
      'GET /api/v1/developers/me': () => json(USER),
      'GET /api/v1/games?limit=100': () => json({ items: [GAME], total: 1, limit: 100, offset: 0 }),
      'GET /api/v1/games/g1/live': () =>
        json({ active_players: 3, source: 'redis', dashboards_connected: 1 }),
    }
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string, init: RequestInit = {}) => {
        const path = url.replace('http://localhost:8000', '')
        const handler = routes[`${init.method ?? 'GET'} ${path}`]
        return Promise.resolve(
          handler
            ? handler(init)
            : json({ error: { code: 'not_found', message: 'nope', details: [] } }, 404),
        )
      }),
    )
  })
  afterEach(() => vi.unstubAllGlobals())

  it('redirects anonymous visitors to the login page', async () => {
    renderApp('/games')
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
  })

  it('logs in and shows the dashboard with live data', async () => {
    renderApp('/')
    await userEvent.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'correct-horse')
    await userEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByRole('navigation', { name: 'Main' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: 'Space Runner' })).toBeInTheDocument()
    expect(await screen.findByText('3')).toBeInTheDocument() // players online
    expect(tokenStore.get()).toBe('tok')
  })

  it('shows the server message for wrong credentials and stays on the form', async () => {
    routes['POST /api/v1/auth/login'] = () =>
      json(
        {
          error: {
            code: 'invalid_credentials',
            message: 'Incorrect email or password.',
            details: [],
          },
        },
        401,
      )
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
      json(
        { error: { code: 'invalid_token', message: 'Invalid or expired token.', details: [] } },
        401,
      )
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Welcome back' })).toBeInTheDocument()
    await waitFor(() => expect(tokenStore.get()).toBeNull())
  })

  it('marks unbuilt pages honestly instead of faking them', async () => {
    tokenStore.set('saved')
    renderApp('/players')
    expect(await screen.findByText('Not built yet')).toBeInTheDocument()
  })
})
