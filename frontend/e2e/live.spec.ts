import { API, auth, createAccount, createGame, createKey, expect, signIn, test } from './fixtures'

test('events from the game API appear on the live feed without a refresh', async ({
  page,
  request,
}) => {
  const account = await createAccount(request)
  const game = await createGame(request, account, 'Live Quest')
  const key = await createKey(request, account, game.id)
  await signIn(page, account)

  await page.goto('/live')
  await expect(page.getByRole('status', { name: '' }).filter({ hasText: 'Live' })).toBeVisible() // WebSocket connected
  await expect(page.getByText('No events yet')).toBeVisible()

  const headers = { 'X-API-Key': key }
  await request.post(`${API}/api/v1/game/players`, {
    data: { external_id: 'live-1', username: 'Linus' },
    headers,
  })
  await request.post(`${API}/api/v1/game/sessions`, {
    data: { player_external_id: 'live-1' },
    headers,
  })

  const feed = page.getByRole('list', { name: 'Event feed' })
  await expect(feed).toContainText('Player registered')
  await expect(feed).toContainText('Session started')
  await expect(feed).toContainText('Linus')

  // A custom event shows up too.
  await request.post(`${API}/api/v1/game/events`, {
    data: {
      event_type: 'custom_boss_defeated',
      player_external_id: 'live-1',
      payload: { boss: 'kraken' },
    },
    headers,
  })
  await expect(feed).toContainText('custom_boss_defeated')
  void auth
})
