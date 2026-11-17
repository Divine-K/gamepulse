import { createAccount, createGame, expect, signIn, test } from './fixtures'

test('the first page load is small and fast', async ({ page }) => {
  const scripts: { url: string; bytes: number }[] = []
  page.on('response', async (response) => {
    if (response.request().resourceType() === 'script') {
      scripts.push({ url: response.url(), bytes: (await response.body()).length })
    }
  })
  const start = Date.now()
  await page.goto('/login', { waitUntil: 'load' })
  const loadMs = Date.now() - start
  const total = scripts.reduce((sum, s) => sum + s.bytes, 0)

  // Uncompressed JavaScript needed to show the login page. The charting library must not be in it.
  expect(total, `JS on first load: ${(total / 1024).toFixed(0)} kB`).toBeLessThan(700 * 1024)
  expect(
    scripts.some((s) => /ChartTooltip-/.test(s.url)),
    'charts library loaded on the login page',
  ).toBe(false)
  expect(loadMs, `load took ${loadMs} ms`).toBeLessThan(3000)
})

test('the charting library loads only when a chart page is opened', async ({ page, request }) => {
  const account = await createAccount(request)
  await createGame(request, account, 'Perf Quest')
  await signIn(page, account)
  const loaded: string[] = []
  page.on('request', (r) => r.resourceType() === 'script' && loaded.push(r.url()))

  await page.goto('/settings')
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  expect(loaded.some((u) => /ChartTooltip-/.test(u))).toBe(false)

  await page.getByRole('link', { name: 'Analytics' }).click()
  await expect(page.getByRole('heading', { name: 'Player engagement' })).toBeVisible()
  expect(loaded.some((u) => /ChartTooltip-/.test(u))).toBe(true)
})
