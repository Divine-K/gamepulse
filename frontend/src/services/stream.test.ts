import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { GameStream, backoffDelay, toWebSocketUrl } from './stream'
import type { StreamStatus } from './stream'
import type { GameEvent } from '../types/api'

class FakeSocket {
  static instances: FakeSocket[] = []
  readyState = 1
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((e: { data: string }) => void) | null = null
  onclose: ((e: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  url: string
  constructor(url: string) {
    this.url = url
    FakeSocket.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close(code = 1000) {
    this.readyState = 3
    this.onclose?.({ code })
  }
  // helpers used by tests
  open() {
    this.onopen?.()
  }
  receive(payload: unknown) {
    this.onmessage?.({ data: JSON.stringify(payload) })
  }
  serverClose(code: number) {
    this.readyState = 3
    this.onclose?.({ code })
  }
}

const EVENT = {
  id: 'e1',
  type: 'session.started',
  game_id: 'g',
  ts: '',
  is_simulated: false,
  data: {},
}

function setup(overrides = {}) {
  const statuses: StreamStatus[] = []
  const events: GameEvent[] = []
  const onReconnected = vi.fn()
  const stream = new GameStream({
    gameId: 'game-1',
    token: 'tok',
    baseUrl: 'http://api.test',
    WebSocketImpl: FakeSocket as unknown as typeof WebSocket,
    onStatus: (s) => statuses.push(s),
    onEvent: (e) => events.push(e),
    onReconnected,
    ...overrides,
  })
  return { stream, statuses, events, onReconnected, socket: () => FakeSocket.instances.at(-1)! }
}

describe('helpers', () => {
  it('builds the websocket url from the http base', () => {
    expect(toWebSocketUrl('http://localhost:8000', 'g1')).toBe(
      'ws://localhost:8000/api/v1/ws/games/g1',
    )
    expect(toWebSocketUrl('https://api.x.dev', 'g1')).toBe('wss://api.x.dev/api/v1/ws/games/g1')
  })

  it('backs off exponentially with jitter and a cap', () => {
    expect(backoffDelay(0, () => 1)).toBe(500)
    expect(backoffDelay(0, () => 0)).toBe(250)
    expect(backoffDelay(3, () => 1)).toBe(4000)
    expect(backoffDelay(20, () => 1)).toBe(30_000)
    expect(backoffDelay(20, () => 0)).toBe(15_000)
  })
})

describe('GameStream', () => {
  beforeEach(() => {
    FakeSocket.instances = []
    vi.useFakeTimers()
  })
  afterEach(() => vi.useRealTimers())

  it('authenticates with the first message, never via the url', () => {
    const { stream, socket } = setup()
    stream.start()
    socket().open()
    expect(socket().url).toBe('ws://api.test/api/v1/ws/games/game-1')
    expect(socket().url).not.toContain('tok')
    expect(JSON.parse(socket().sent[0]!)).toEqual({ type: 'auth', token: 'tok' })
  })

  it('goes live on ready and forwards events but not pongs', () => {
    const { stream, statuses, events, socket } = setup()
    stream.start()
    socket().open()
    socket().receive({ type: 'ready', active_players: 0 })
    socket().receive(EVENT)
    socket().receive({ type: 'pong' })
    expect(statuses).toEqual(['connecting', 'live'])
    expect(events).toEqual([EVENT])
  })

  it('reconnects with backoff and signals onReconnected only after a re-connect', () => {
    const { stream, statuses, onReconnected, socket } = setup()
    stream.start()
    socket().open()
    socket().receive({ type: 'ready' })
    expect(onReconnected).not.toHaveBeenCalled() // first connect

    socket().serverClose(1006) // network drop
    expect(statuses.at(-1)).toBe('reconnecting')
    expect(FakeSocket.instances).toHaveLength(1)
    vi.advanceTimersByTime(600)
    expect(FakeSocket.instances).toHaveLength(2)

    socket().open()
    socket().receive({ type: 'ready' })
    expect(statuses.at(-1)).toBe('live')
    expect(onReconnected).toHaveBeenCalledTimes(1) // caller refetches REST data
  })

  it.each([4401, 4404, 4429, 4400])('does not retry fatal close code %i', (code) => {
    const { stream, statuses, socket } = setup()
    stream.start()
    socket().open()
    socket().serverClose(code)
    vi.advanceTimersByTime(60_000)
    expect(statuses.at(-1)).toBe('failed')
    expect(FakeSocket.instances).toHaveLength(1)
  })

  it('reconnects immediately when dropped as a slow consumer (1013)', () => {
    const { stream, socket } = setup()
    stream.start()
    socket().open()
    socket().receive({ type: 'ready' })
    socket().serverClose(1013)
    vi.advanceTimersByTime(1)
    expect(FakeSocket.instances).toHaveLength(2)
  })

  it('stop() closes cleanly and never reconnects', () => {
    const { stream, statuses, socket } = setup()
    stream.start()
    socket().open()
    socket().receive({ type: 'ready' })
    stream.stop()
    vi.advanceTimersByTime(60_000)
    expect(statuses.at(-1)).toBe('closed')
    expect(FakeSocket.instances).toHaveLength(1)
  })

  it('pings regularly and forces a reconnect if no reply arrives', () => {
    const { stream, socket } = setup({ pingIntervalMs: 1000, pongTimeoutMs: 500 })
    stream.start()
    socket().open()
    socket().receive({ type: 'ready' })

    vi.advanceTimersByTime(1000)
    expect(JSON.parse(socket().sent.at(-1)!)).toEqual({ type: 'ping' })
    vi.advanceTimersByTime(500) // no pong: half-open connection
    expect(socket().readyState).toBe(3)
    vi.advanceTimersByTime(600)
    expect(FakeSocket.instances).toHaveLength(2)
  })

  it('does not drop a healthy idle connection that answers pings', () => {
    const { stream, socket } = setup({ pingIntervalMs: 1000, pongTimeoutMs: 500 })
    stream.start()
    socket().open()
    socket().receive({ type: 'ready' })
    for (let i = 0; i < 5; i++) {
      vi.advanceTimersByTime(1000)
      socket().receive({ type: 'pong' })
    }
    expect(FakeSocket.instances).toHaveLength(1)
    expect(socket().readyState).toBe(1)
  })
})
