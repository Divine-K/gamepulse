import type { GameEvent } from '../types/api'
import { API_BASE_URL } from './api'

export type StreamStatus = 'connecting' | 'live' | 'reconnecting' | 'failed' | 'closed'

export interface StreamOptions {
  gameId: string
  token: string
  onEvent: (event: GameEvent) => void
  onStatus: (status: StreamStatus) => void
  /** Called after every reconnect (not the first connect): refetch REST data, events may be missed. */
  onReconnected?: () => void
  /** Test hook. */
  WebSocketImpl?: typeof WebSocket
  baseUrl?: string
  pingIntervalMs?: number
  pongTimeoutMs?: number
}

// Server close codes (see docs/architecture.md). These mean "do not retry".
const FATAL_CLOSE_CODES = new Set([4400, 4401, 4404, 4429])

export function toWebSocketUrl(httpBase: string, gameId: string): string {
  return `${httpBase.replace(/^http/, 'ws')}/api/v1/ws/games/${gameId}`
}

/** Reconnect delay: exponential backoff with jitter, capped at 30 s. */
export function backoffDelay(attempt: number, random = Math.random): number {
  const base = Math.min(30_000, 500 * 2 ** attempt)
  return Math.round(base * (0.5 + random() * 0.5))
}

/**
 * A resilient connection to a game's live event stream.
 * Authenticates with the first message, reconnects with backoff, and detects dead
 * connections with a ping/pong heartbeat.
 */
export class GameStream {
  private socket: WebSocket | null = null
  private attempt = 0
  private hasConnectedBefore = false
  private stopped = false
  private retryTimer: ReturnType<typeof setTimeout> | undefined
  private pingTimer: ReturnType<typeof setInterval> | undefined
  private pongTimer: ReturnType<typeof setTimeout> | undefined

  private readonly options: StreamOptions

  constructor(options: StreamOptions) {
    this.options = options
  }

  start(): void {
    this.stopped = false
    this.options.onStatus(this.hasConnectedBefore ? 'reconnecting' : 'connecting')
    this.connect()
  }

  stop(): void {
    this.stopped = true
    clearTimeout(this.retryTimer)
    this.clearHeartbeat()
    this.socket?.close(1000)
    this.socket = null
    this.options.onStatus('closed')
  }

  private connect(): void {
    const Impl = this.options.WebSocketImpl ?? WebSocket
    const url = toWebSocketUrl(this.options.baseUrl ?? API_BASE_URL, this.options.gameId)
    const socket = new Impl(url)
    this.socket = socket

    socket.onopen = () => {
      socket.send(JSON.stringify({ type: 'auth', token: this.options.token }))
    }

    socket.onmessage = (message: MessageEvent<string>) => {
      clearTimeout(this.pongTimer) // any traffic proves the connection is alive
      let parsed: { type?: string }
      try {
        parsed = JSON.parse(message.data)
      } catch {
        return
      }
      if (parsed.type === 'ready') {
        const reconnected = this.hasConnectedBefore
        this.hasConnectedBefore = true
        this.attempt = 0
        this.options.onStatus('live')
        this.startHeartbeat()
        if (reconnected) this.options.onReconnected?.()
      } else if (parsed.type && parsed.type !== 'pong') {
        this.options.onEvent(parsed as unknown as GameEvent)
      }
    }

    socket.onclose = (event: CloseEvent) => {
      if (this.socket !== socket) return // an old socket we already replaced
      this.clearHeartbeat()
      if (this.stopped) return
      if (FATAL_CLOSE_CODES.has(event.code)) {
        this.options.onStatus('failed')
        return
      }
      this.scheduleReconnect(event.code === 1013 ? 0 : backoffDelay(this.attempt++))
    }

    socket.onerror = () => {
      // onclose always follows; reconnect logic lives there.
    }
  }

  private scheduleReconnect(delayMs: number): void {
    this.options.onStatus('reconnecting')
    clearTimeout(this.retryTimer)
    this.retryTimer = setTimeout(() => {
      if (!this.stopped) this.connect()
    }, delayMs)
  }

  private startHeartbeat(): void {
    this.clearHeartbeat()
    const every = this.options.pingIntervalMs ?? 25_000
    this.pingTimer = setInterval(() => {
      if (this.socket?.readyState === 1) {
        this.socket.send(JSON.stringify({ type: 'ping' }))
        this.armPongTimeout()
      }
    }, every)
  }

  /** Armed only when a ping is sent: no reply in time means a half-open connection. */
  private armPongTimeout(): void {
    clearTimeout(this.pongTimer)
    this.pongTimer = setTimeout(
      () => this.socket?.close(4000),
      this.options.pongTimeoutMs ?? 10_000,
    )
  }

  private clearHeartbeat(): void {
    clearInterval(this.pingTimer)
    clearTimeout(this.pongTimer)
  }
}
