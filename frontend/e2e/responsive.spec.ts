import { createAccount, createGame, createKey, expect, playSession, signIn, test } from './fixtures'

const ROUTES = [
  '/',
  '/games',
  '/players',
  '/sessions',
  '/leaderboards',
  '/achievements',
  '/analytics',
  '/live',
  '/simulator',
  '/playground',
  '/settings',
  '/design',
]

test('every page fits a phone screen without sideways page scrolling', async ({
  page,
  request,
}) => {
  const account = await createAccount(request)
  const game = await createGame(request, account, 'Phone Quest')
  const key = await createKey(request, account, game.id)
  await playSession(request, key, 'phone-player')
  await signIn(page, account)

  for (const route of ROUTES) {
    await page.goto(route)
    await expect(page.locator('main')).toBeVisible()
    await page.waitForLoadState('networkidle')
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    )
    expect(overflow, `${route} overflows the viewport by ${overflow}px`).toBeLessThanOrEqual(1)
  }
})

test('the mobile drawer opens, navigates and closes', async ({ page, request }) => {
  const account = await createAccount(request)
  await createGame(request, account, 'Drawer Quest')
  await signIn(page, account)
  await page.goto('/')

  await expect(page.getByRole('navigation', { name: 'Main' })).toBeHidden() // collapsed by default on phones
  await page.getByRole('button', { name: 'Open navigation' }).click()
  const nav = page.getByRole('navigation', { name: 'Main' })
  await expect(nav).toBeVisible()
  await nav.getByRole('link', { name: 'Players' }).click()
  await expect(page).toHaveURL(/\/players$/)
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeHidden() // drawer closed after navigating

  await page.getByRole('button', { name: 'Open navigation' }).click()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('navigation', { name: 'Main' })).toBeHidden()
})

test('tables scroll inside their card instead of stretching the page', async ({
  page,
  request,
}) => {
  const account = await createAccount(request)
  const game = await createGame(request, account, 'Table Quest')
  const key = await createKey(request, account, game.id)
  await playSession(request, key, 'table-player')
  await signIn(page, account)
  await page.goto('/sessions')
  const table = page.getByRole('table', { name: 'Sessions' })
  await expect(table).toBeVisible()
  const wrapper = table.locator('xpath=..')
  expect(await wrapper.evaluate((el) => el.scrollWidth > el.clientWidth)).toBe(true) // scrolls within the card
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth),
  ).toBeLessThanOrEqual(1)
})
