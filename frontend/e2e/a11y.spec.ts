import AxeBuilder from '@axe-core/playwright'
import type { Page } from '@playwright/test'
import { createAccount, createGame, createKey, expect, playSession, signIn, test } from './fixtures'

async function violations(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'])
    .analyze()
  return results.violations
    .filter((v) => v.impact === 'serious' || v.impact === 'critical')
    .map(
      (v) =>
        `${v.id} (${v.impact}): ${v.nodes
          .slice(0, 3)
          .map((n) => n.target.join(' '))
          .join(' | ')}`,
    )
}

for (const theme of ['dark', 'light']) {
  test(`signed-out pages have no serious accessibility problems (${theme})`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem('gp-theme', t), theme)
    for (const route of ['/login', '/register']) {
      await page.goto(route)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      expect(await violations(page), route).toEqual([])
    }
  })

  test(`dashboard pages have no serious accessibility problems (${theme})`, async ({
    page,
    request,
  }) => {
    const account = await createAccount(request)
    const game = await createGame(request, account, 'A11y Quest')
    const key = await createKey(request, account, game.id)
    await playSession(request, key, 'a11y-player')
    await page.addInitScript((t) => localStorage.setItem('gp-theme', t), theme)
    await signIn(page, account)

    for (const route of [
      '/',
      '/games',
      `/games/${game.id}?tab=keys`,
      '/players',
      '/sessions',
      '/leaderboards',
      '/achievements',
      '/analytics',
      '/simulator',
      '/playground',
      '/settings',
    ]) {
      await page.goto(route)
      await expect(page.getByRole('heading', { level: 1 })).toBeVisible()
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(700) // let chart/entrance animations finish before measuring contrast
      expect(await violations(page), `${route} (${theme})`).toEqual([])
    }
  })
}
