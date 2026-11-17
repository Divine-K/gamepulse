import type { ApiErrorBody } from '../types/api'

/**
 * Base URL of the API. Leave VITE_API_BASE_URL empty to talk to the page's own origin, which is how
 * the Docker image works: nginx serves the dashboard and proxies /api to the backend.
 */
export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

/** Absolute API origin (needed for WebSocket URLs and copy-ready examples). */
export const API_ORIGIN: string = API_BASE_URL || window.location.origin

const TOKEN_KEY = 'gp-token'

/** The JWT lives in sessionStorage: it survives a refresh but not closing the tab. */
export const tokenStore = {
  get(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set(token: string): void {
    try {
      sessionStorage.setItem(TOKEN_KEY, token)
    } catch {
      /* storage unavailable: the session just won't survive a refresh */
    }
  },
  clear(): void {
    try {
      sessionStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  },
}

export class ApiError extends Error {
  readonly status: number
  readonly code: string
  readonly details: { field?: string; message?: string }[]
  readonly requestId: string | null

  constructor(
    status: number,
    code: string,
    message: string,
    details: ApiError['details'] = [],
    requestId: string | null = null,
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }

  /** Message for a specific form field, if the server reported one. */
  fieldMessage(field: string): string | undefined {
    return this.details.find((d) => d.field?.endsWith(field))?.message
  }
}

type UnauthorizedHandler = () => void
let onUnauthorized: UnauthorizedHandler | null = null

/** Called when an authenticated request gets 401, so the app can sign the user out. */
export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  onUnauthorized = handler
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE'
  body?: unknown
  signal?: AbortSignal
  /** Set false for endpoints that must not send the token (login, register). */
  auth?: boolean
}

export async function api<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, auth = true } = options
  const headers: Record<string, string> = { Accept: 'application/json' }
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = auth ? tokenStore.get() : null
  if (token) headers.Authorization = `Bearer ${token}`

  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal,
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error
    throw new ApiError(0, 'network_error', 'Cannot reach the GamePulse server. Is it running?')
  }

  if (response.status === 204) return undefined as T

  const payload: unknown = await response.json().catch(() => null)
  if (!response.ok) {
    const envelope = (payload as ApiErrorBody | null)?.error
    const error = new ApiError(
      response.status,
      envelope?.code ?? 'http_error',
      envelope?.message ?? `Request failed (${response.status})`,
      envelope?.details ?? [],
      envelope?.request_id ?? null,
    )
    if (response.status === 401 && auth && token) onUnauthorized?.()
    throw error
  }
  return payload as T
}
