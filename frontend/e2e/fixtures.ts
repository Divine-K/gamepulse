import { expect, test as base } from '@playwright/test'
import type { APIRequestContext, Page } from '@playwright/test'

export const API = process.env.E2E_BASE_URL ?? 'http://localhost:8100'
export const PASSWORD = 'e2e-password-123'

let counter = 0
export const uid = () => `${Date.now().toString(36)}${(counter++).toString(36)}`

/** Expected "client error" noise (401/404/409/422 responses the test provokes on purpose). */
const IGNORED_CONSOLE = /Failed to load resource: the server responded with a status of 4\d\d/

/**
 * Every test fails if the page logs a console error, throws an uncaught exception, or the API
 * answers with a 5xx. That turns "check the browser console and network" into an automatic gate.
 */
export const test = base.extend<{ page: Page }>({
  page: async ({ page }, use) => {
    const problems: string[] = []
    page.on('console', (message) => {
      if (message.type() === 'error' && !IGNORED_CONSOLE.test(message.text())) {
        problems.push(`console: ${message.text()}`)
      }
    })
    page.on('pageerror', (error) => problems.push(`uncaught: ${error.message}`))
    page.on('response', (response) => {
      if (response.status() >= 500) problems.push(`${response.status()} ${response.url()}`)
    })
    await use(page)
    expect(problems, 'browser console / network problems').toEqual([])
  },
})
export { expect }

export interface Account {
  email: string
  password: string
  name: string
  token: string
}

/** Register a developer through the API and return a ready-to-use session token. */
export async function createAccount(
  request: APIRequestContext,
  name = 'E2E Dev',
): Promise<Account> {
  const email = `${uid()}@example.com`
  const registered = await request.post(`${API}/api/v1/auth/register`, {
    data: { email, password: PASSWORD, display_name: name },
  })
  expect(registered.status()).toBe(201)
  const login = await request.post(`${API}/api/v1/auth/login`, {
    data: { email, password: PASSWORD },
  })
  const { access_token } = await login.json()
  return { email, password: PASSWORD, name, token: access_token }
}

/** Skip the login form: start the page already signed in as `account`. */
export async function signIn(page: Page, account: Account) {
  await page.addInitScript((token) => sessionStorage.setItem('gp-token', token), account.token)
}

export const auth = (account: Account) => ({ Authorization: `Bearer ${account.token}` })

export async function createGame(request: APIRequestContext, account: Account, name = 'E2E Game') {
  const response = await request.post(`${API}/api/v1/games`, {
    data: { name },
    headers: auth(account),
  })
  expect(response.status()).toBe(201)
  return (await response.json()) as { id: string; name: string }
}

export async function createKey(request: APIRequestContext, account: Account, gameId: string) {
  const response = await request.post(`${API}/api/v1/games/${gameId}/api-keys`, {
    data: { name: 'e2e' },
    headers: auth(account),
  })
  expect(response.status()).toBe(201)
  return ((await response.json()) as { key: string }).key
}

/** One complete play session through the game API. */
export async function playSession(
  request: APIRequestContext,
  key: string,
  externalId: string,
  score = 1500,
) {
  const headers = { 'X-API-Key': key }
  await request.post(`${API}/api/v1/game/players`, {
    data: { external_id: externalId, username: externalId },
    headers,
  })
  const started = await request.post(`${API}/api/v1/game/sessions`, {
    data: { player_external_id: externalId },
    headers,
  })
  const session = await started.json()
  const ended = await request.post(`${API}/api/v1/game/sessions/${session.id}/end`, {
    data: { score, result: 'win' },
    headers,
  })
  expect(ended.status()).toBe(200)
  return session.id as string
}
