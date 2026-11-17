import {
  API,
  auth,
  createAccount,
  createGame,
  createKey,
  expect,
  playSession,
  signIn,
  test,
} from './fixtures'

test('one developer cannot see or reach another developer’s game', async ({ page, request }) => {
  const alice = await createAccount(request, 'Alice')
  const bob = await createAccount(request, 'Bob')
  const aliceGame = await createGame(request, alice, 'Alice Secret Game')
  const aliceKey = await createKey(request, alice, aliceGame.id)
  await playSession(request, aliceKey, 'alice-player')

  // Bob's dashboard has none of Alice's data.
  await signIn(page, bob)
  await page.goto('/games')
  await expect(page.getByText('Register your first game')).toBeVisible()
  await expect(page.getByText('Alice Secret Game')).toHaveCount(0)
  await page.goto('/players')
  await expect(page.getByText('Register a game first')).toBeVisible()

  // Opening Alice's game by URL looks exactly like a game that does not exist.
  await page.goto(`/games/${aliceGame.id}`)
  await expect(page.getByText('Game not found')).toBeVisible()
  await expect(page.getByText('Alice Secret Game')).toHaveCount(0)

  // The API agrees, for every kind of resource.
  const base = `${API}/api/v1/games/${aliceGame.id}`
  for (const path of [
    '',
    '/players',
    '/sessions',
    '/events',
    '/analytics/overview',
    '/leaderboards/total_score',
    '/achievements',
    '/api-keys',
    '/simulator/summary',
  ]) {
    const response = await request.get(`${base}${path}`, { headers: auth(bob) })
    expect(response.status(), path).toBe(404)
  }
  const wipe = await request.delete(`${base}/simulator/data`, { headers: auth(bob) })
  expect(wipe.status()).toBe(404)
  const rename = await request.patch(base, { data: { name: 'Hijacked' }, headers: auth(bob) })
  expect(rename.status()).toBe(404)

  // Alice's data is intact.
  const intact = await request.get(`${base}/players`, { headers: auth(alice) })
  expect((await intact.json()).total).toBe(1)
})

test('a game API key only works for its own game', async ({ request }) => {
  const alice = await createAccount(request, 'Alice')
  const bob = await createAccount(request, 'Bob')
  const aliceKey = await createKey(request, alice, (await createGame(request, alice, 'A')).id)
  const bobKey = await createKey(request, bob, (await createGame(request, bob, 'B')).id)
  await playSession(request, aliceKey, 'only-in-a')

  const asBob = await request.get(`${API}/api/v1/game/players/only-in-a`, {
    headers: { 'X-API-Key': bobKey },
  })
  expect(asBob.status()).toBe(404)
  const me = await request.get(`${API}/api/v1/game/me`, { headers: { 'X-API-Key': bobKey } })
  expect((await me.json()).name).toBe('B')
})
