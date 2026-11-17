// Builds the README screenshots from a local stack: node scripts/screenshots.mjs
//
// It registers a throwaway developer, creates a game, plays the example game through the real API,
// spreads the timestamps over two weeks (backend/scripts/seed_demo.py) and photographs each page.
// Needs the API on :8000 and the dashboard on :5173 (or set API_URL and WEB_URL).
import { execFileSync, spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { mkdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { chromium } from '@playwright/test'

const ROOT = join(dirname(fileURLToPath(import.meta.url)), '..', '..')
const API = process.env.API_URL ?? 'http://localhost:8000'
const WEB = process.env.WEB_URL ?? 'http://localhost:5173'
const OUT = join(ROOT, 'docs', 'screenshots')
const PY = join(ROOT, 'backend', '.venv', 'bin', 'python')
mkdirSync(OUT, { recursive: true })

const password = randomBytes(12).toString('hex') // throwaway, never printed or stored
const email = `docs-${Date.now()}@example.com`

async function api(path, init = {}, token) {
  const res = await fetch(`${API}/api/v1${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  if (!res.ok) throw new Error(`${path} -> ${res.status} ${await res.text()}`)
  return res.json()
}

// 1. Data: a developer, a game, an API key
await api('/auth/register', {
  method: 'POST',
  body: JSON.stringify({ email, password, display_name: 'Alex Rivera' }),
})
const { access_token: token } = await api('/auth/login', {
  method: 'POST',
  body: JSON.stringify({ email, password }),
})
const game = await api(
  '/games',
  {
    method: 'POST',
    body: JSON.stringify({
      name: 'Surfer Cove',
      genre: 'Arcade',
      description: 'Endless wave-riding arcade game.',
    }),
  },
  token,
)
const { key } = await api(
  `/games/${game.id}/api-keys`,
  { method: 'POST', body: JSON.stringify({ name: 'Game server' }) },
  token,
)

// 2. Play the example game, then spread its timestamps over two weeks
const play = (players) =>
  spawn(PY, [join(ROOT, 'examples/surfer/play.py'), '--players', String(players), '--seed', '3'], {
    env: { ...process.env, GAMEPULSE_URL: API, GAMEPULSE_KEY: key },
    stdio: 'ignore',
  })
execFileSync(
  PY,
  [join(ROOT, 'examples/surfer/play.py'), '--players', '36', '--rounds', '4', '--seed', '11'],
  {
    env: { ...process.env, GAMEPULSE_URL: API, GAMEPULSE_KEY: key },
    stdio: 'inherit',
  },
)
execFileSync(
  PY,
  [join(ROOT, 'backend/scripts/seed_demo.py'), '--game-id', game.id, '--days', '14'],
  {
    cwd: join(ROOT, 'backend'),
    stdio: 'inherit',
  },
)

// 3. Photograph the dashboard
const browser = await chromium.launch({ channel: 'chrome' })
const context = await browser.newContext({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 1,
})
const page = await context.newPage()
await page.goto(`${WEB}/login`)
await page.getByLabel('Email').fill(email)
await page.getByLabel('Password').fill(password)
await page.getByRole('button', { name: 'Log in' }).click()
await page.waitForURL((url) => !url.pathname.startsWith('/login'))
await page.evaluate((id) => localStorage.setItem('gamepulse.game', id), game.id) // harmless if unused

async function shoot(name, path, { settle = 1500, full = false, before } = {}) {
  await page.goto(`${WEB}${path}`)
  await page.waitForLoadState('networkidle')
  await before?.()
  await page.waitForTimeout(settle) // let chart animations finish
  if (full) {
    // The sidebar is pinned to the viewport, so grow the viewport instead of using fullPage.
    const height = await page.evaluate(() => document.documentElement.scrollHeight)
    await page.setViewportSize({ width: 1440, height })
    await page.waitForTimeout(600)
  }
  await page.screenshot({ path: join(OUT, `${name}.png`) })
  if (full) await page.setViewportSize({ width: 1440, height: 900 })
  console.log('captured', name)
}

await shoot('overview', '/', { full: true })
await shoot('players', '/players')
await shoot('leaderboards', '/leaderboards')
await shoot('achievements', '/achievements')
await shoot('analytics', '/analytics', { full: true, settle: 2000 })
await shoot('sessions', '/sessions')
await shoot('playground', '/playground')
await shoot('games', '/games')

// Live events: keep the page open while a few more surfers play, so the feed fills in real time
await page.goto(`${WEB}/live`)
await page.waitForLoadState('networkidle')
const live = play(5)
await page.waitForTimeout(6000)
await page.screenshot({ path: join(OUT, 'live-events.png') })
console.log('captured live-events')
live.kill()

await browser.close()
