import { API, PASSWORD, expect, test, uid } from './fixtures'

/**
 * The whole first-run journey a new developer takes: sign up, register a game, create an API key,
 * connect through the real game API, and see the activity on the dashboard.
 */
test('a new developer goes from sign-up to seeing their first session', async ({
  page,
  request,
}) => {
  const email = `${uid()}@example.com`

  // 1-2. Register and land on the games page.
  await page.goto('/register')
  await page.getByLabel('Name').fill('Ada E2E')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(/\/games$/)
  await expect(page.getByText('Register your first game')).toBeVisible()

  // 3. Register a game.
  await page.getByRole('button', { name: 'New game' }).first().click()
  await page.getByLabel('Name').fill('Onboarding Quest')
  await page.getByRole('button', { name: 'Create game' }).click()
  await expect(page.getByText('Game registered')).toBeVisible()
  await page.getByRole('link', { name: 'Onboarding Quest' }).click()

  // 4. Create an API key; the secret is shown once.
  await page.getByRole('tab', { name: 'API keys' }).click()
  await page.getByRole('button', { name: 'New key' }).click()
  await page.getByLabel('Key name').fill('Server')
  await page.getByRole('button', { name: 'Create key' }).click()
  const dialog = page.getByRole('dialog', { name: 'Copy your API key' })
  await expect(dialog).toBeVisible()
  const secret = (await dialog.locator('code').innerText()).trim()
  expect(secret).toMatch(/^gp_[0-9a-f]{12}_[0-9a-f]{64}$/)
  await dialog.getByRole('button', { name: 'I have saved it' }).click()
  await expect(page.getByText(secret)).toHaveCount(0) // gone from the page for good
  await expect(page.getByRole('row', { name: /Server/ })).toContainText(secret.slice(0, 15)) // only the prefix remains

  // 5-6. Integration instructions with copyable examples.
  await page.getByRole('tab', { name: 'Integration' }).click()
  await expect(page.getByText('1. Verify your key')).toBeVisible()
  await expect(page.getByRole('button', { name: /Copy to clipboard/ }).first()).toBeVisible()

  // 7-9. Send real requests with the key: verify, register a player, create a session.
  const headers = { 'X-API-Key': secret }
  expect((await request.get(`${API}/api/v1/game/me`, { headers })).status()).toBe(200)
  const player = await request.post(`${API}/api/v1/game/players`, {
    data: { external_id: 'e2e-player-1', username: 'Grace' },
    headers,
  })
  expect(player.status()).toBe(201)
  const started = await request.post(`${API}/api/v1/game/sessions`, {
    data: { player_external_id: 'e2e-player-1' },
    headers: { ...headers, 'Idempotency-Key': uid() },
  })
  expect(started.status()).toBe(201)
  const session = await started.json()
  await request.post(`${API}/api/v1/game/scores`, {
    data: { player_external_id: 'e2e-player-1', value: 1200, session_id: session.id },
    headers,
  })
  const ended = await request.post(`${API}/api/v1/game/sessions/${session.id}/end`, {
    data: { result: 'win' },
    headers,
  })
  expect(ended.status()).toBe(200)
  expect((await ended.json()).unlocked_achievements.length).toBeGreaterThan(0)

  // 10. The activity shows up across the dashboard.
  await page.getByRole('link', { name: 'Overview' }).click()
  await expect(page.getByRole('heading', { name: 'Onboarding Quest' })).toBeVisible()
  await expect(page.getByText('1 new in 30 days')).toBeVisible()
  await expect(page.getByRole('table', { name: 'Recent sessions' })).toContainText('Grace')

  await page.getByRole('link', { name: 'Players', exact: true }).click()
  await expect(page).toHaveURL(/\/players$/)
  await expect(page.getByRole('link', { name: 'Grace', exact: true })).toBeVisible()
  await page.getByRole('link', { name: 'Grace', exact: true }).click()
  await expect(page.getByText('Total score')).toBeVisible()
  await expect(page.getByText('1,200').first()).toBeVisible()

  await page.getByRole('link', { name: 'Leaderboards' }).click()
  await expect(page.getByRole('row', { name: /Rank #1.*Grace/ })).toBeVisible()

  await page.getByRole('link', { name: 'Achievements' }).click()
  await expect(page.getByRole('heading', { name: 'First Game' })).toBeVisible()
  await expect(page.getByText('1 players · 100%').first()).toBeVisible()

  await page.getByRole('link', { name: 'Analytics' }).click()
  await expect(page.getByRole('heading', { name: 'Player engagement' })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Score distribution' })).toBeVisible()
})
