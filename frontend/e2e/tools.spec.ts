import {
  API,
  createAccount,
  createGame,
  createKey,
  expect,
  playSession,
  signIn,
  test,
} from './fixtures'

test('the simulator drives the real backend and cleans up only its own data', async ({
  page,
  request,
}) => {
  const account = await createAccount(request)
  const game = await createGame(request, account, 'Sim Quest')
  const key = await createKey(request, account, game.id)
  await playSession(request, key, 'real-player') // real data that must survive the cleanup
  await signIn(page, account)

  await page.goto('/simulator')
  await page.getByRole('button', { name: 'Run a quick demo' }).click()
  await expect(page.getByText('Demo finished')).toBeVisible({ timeout: 20_000 })

  const feed = page.getByRole('list', { name: 'Event feed' })
  await expect(feed).toContainText('Session ended')
  await expect(feed.getByText('Simulated').first()).toBeVisible()
  await expect(page.locator('dl').filter({ hasText: 'Players' })).toContainText('1') // one test player

  // The simulated session is in the database and labelled everywhere.
  await page.goto('/sessions')
  await expect(page.getByRole('row').filter({ hasText: 'Simulated' }).first()).toBeVisible()

  await page.goto('/simulator')
  await page.getByRole('button', { name: 'Delete all simulated data' }).click()
  const dialog = page.getByRole('dialog', { name: 'Delete all simulated data?' })
  await expect(dialog).toContainText('Real data is not affected')
  await dialog.getByRole('button', { name: 'Delete simulated data' }).click()
  await expect(page.getByText(/Real data was not touched/)).toBeVisible()

  // Real player and session are untouched; simulated ones are gone.
  const players = await request.get(`${API}/api/v1/games/${game.id}/players`, {
    headers: { Authorization: `Bearer ${account.token}` },
  })
  const body = await players.json()
  expect(body.total).toBe(1)
  expect(body.items[0].external_id).toBe('real-player')
})

test('the playground sends real requests and never reveals the API key', async ({
  page,
  request,
}) => {
  const account = await createAccount(request)
  const game = await createGame(request, account, 'Playground Quest')
  await signIn(page, account)
  await page.goto('/playground')

  const created = page.waitForResponse(
    (r) => r.url().endsWith(`/games/${game.id}/api-keys`) && r.request().method() === 'POST',
  )
  await page.getByRole('button', { name: 'Create a playground key' }).click()
  const { key } = await (await created).json()
  await expect(page.getByText(/Using gp_[0-9a-f]{12}_••••••••/)).toBeVisible()

  const send = page.getByRole('button', { name: 'Send request' })
  const status = page.getByRole('status', { name: 'Response summary' })
  await send.click()
  await expect(status).toContainText('200')

  // A real chain of calls: register a player, start a session, heartbeat it.
  await page.getByRole('button', { name: /Register a player/ }).click()
  await send.click()
  await expect(status).toContainText('201')
  await page.getByRole('button', { name: /Start a session/ }).click()
  await send.click()
  await expect(status).toContainText('201')
  await page.getByRole('button', { name: /Keep a session alive/ }).click()
  await expect(page.getByLabel('Request preview')).not.toContainText('{{session_id}}') // id carried over automatically
  await send.click()
  await expect(status).toContainText('200')
  await expect(page.getByLabel('Response body')).toContainText('"status": "active"')

  // The secret never reaches the page, the examples or the request preview.
  await page.getByRole('tab', { name: 'Python' }).click()
  expect(await page.content()).not.toContain(key)
  expect(await page.evaluate(() => document.body.innerText)).not.toContain(key.slice(16, 40))
  await expect(page.getByText(/os\.environ\["GAMEPULSE_KEY"\]/)).toBeVisible()
})
