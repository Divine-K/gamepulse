import { API_ORIGIN } from '../services/api'

export type Method = 'GET' | 'POST' | 'PATCH' | 'DELETE'

export interface Param {
  name: string
  description: string
  example: string
  required?: boolean
}

export interface PlaygroundEndpoint {
  id: string
  group: string
  method: Method
  /** Path template, e.g. /api/v1/game/sessions/{session_id}/end */
  path: string
  summary: string
  description: string
  pathParams: Param[]
  queryParams: Param[]
  headers: Param[]
  /** JSON body template. May contain {{variables}} filled from the session variables. */
  body?: string
  successStatus: number
}

const IDEMPOTENCY: Param = {
  name: 'Idempotency-Key',
  description: 'Makes retries safe: repeating the same key returns the original result.',
  example: '{{idempotency_key}}',
}

export const ENDPOINTS: PlaygroundEndpoint[] = [
  {
    id: 'me',
    group: 'Setup',
    method: 'GET',
    path: '/api/v1/game/me',
    summary: 'Verify your API key',
    description:
      'Returns the game your key belongs to. A good first request: 200 means the key works.',
    pathParams: [],
    queryParams: [],
    headers: [],
    successStatus: 200,
  },
  {
    id: 'register-player',
    group: 'Players',
    method: 'POST',
    path: '/api/v1/game/players',
    summary: 'Register a player',
    description:
      'Creates a player, or returns the existing one for the same external_id (safe to call on every login).',
    pathParams: [],
    queryParams: [],
    headers: [],
    successStatus: 201,
    body: '{\n  "external_id": "{{player_external_id}}",\n  "username": "Ada"\n}',
  },
  {
    id: 'get-player',
    group: 'Players',
    method: 'GET',
    path: '/api/v1/game/players/{external_id}',
    summary: 'Get a player',
    description: 'A player profile with their statistics.',
    pathParams: [
      {
        name: 'external_id',
        description: 'Your game’s id for the player',
        example: '{{player_external_id}}',
        required: true,
      },
    ],
    queryParams: [],
    headers: [],
    successStatus: 200,
  },
  {
    id: 'player-achievements',
    group: 'Players',
    method: 'GET',
    path: '/api/v1/game/players/{external_id}/achievements',
    summary: 'A player’s achievements',
    description: 'Achievements this player has unlocked, newest first.',
    pathParams: [
      {
        name: 'external_id',
        description: 'Your game’s id for the player',
        example: '{{player_external_id}}',
        required: true,
      },
    ],
    queryParams: [{ name: 'limit', description: 'Page size (1-100)', example: '20' }],
    headers: [],
    successStatus: 200,
  },
  {
    id: 'start-session',
    group: 'Sessions',
    method: 'POST',
    path: '/api/v1/game/sessions',
    summary: 'Start a session',
    description:
      'Begins a play session for a registered player. The response id feeds the next requests automatically.',
    pathParams: [],
    queryParams: [],
    headers: [IDEMPOTENCY],
    successStatus: 201,
    body: '{\n  "player_external_id": "{{player_external_id}}"\n}',
  },
  {
    id: 'heartbeat',
    group: 'Sessions',
    method: 'POST',
    path: '/api/v1/game/sessions/{session_id}/heartbeat',
    summary: 'Keep a session alive',
    description: 'Sessions with no heartbeat for 15 minutes are marked abandoned.',
    pathParams: [
      {
        name: 'session_id',
        description: 'From the start-session response',
        example: '{{session_id}}',
        required: true,
      },
    ],
    queryParams: [],
    headers: [],
    successStatus: 200,
  },
  {
    id: 'end-session',
    group: 'Sessions',
    method: 'POST',
    path: '/api/v1/game/sessions/{session_id}/end',
    summary: 'End a session',
    description:
      'Completes the session, updates the player’s stats and awards achievements. Ending twice is safe.',
    pathParams: [
      {
        name: 'session_id',
        description: 'From the start-session response',
        example: '{{session_id}}',
        required: true,
      },
    ],
    queryParams: [],
    headers: [],
    successStatus: 200,
    body: '{\n  "score": 1500,\n  "result": "win"\n}',
  },
  {
    id: 'submit-score',
    group: 'Scores & events',
    method: 'POST',
    path: '/api/v1/game/scores',
    summary: 'Submit a score',
    description:
      'With a session_id it updates the session’s live score. Another category name creates a separate ranking.',
    pathParams: [],
    queryParams: [],
    headers: [],
    successStatus: 201,
    body: '{\n  "player_external_id": "{{player_external_id}}",\n  "value": 750,\n  "session_id": "{{session_id}}"\n}',
  },
  {
    id: 'ingest-event',
    group: 'Scores & events',
    method: 'POST',
    path: '/api/v1/game/events',
    summary: 'Send a custom event',
    description:
      'player_level_up or any custom_<name> event with a free-form JSON payload (max 8 KB).',
    pathParams: [],
    queryParams: [],
    headers: [IDEMPOTENCY],
    successStatus: 201,
    body: '{\n  "event_type": "custom_boss_defeated",\n  "player_external_id": "{{player_external_id}}",\n  "payload": { "boss": "kraken" }\n}',
  },
  {
    id: 'leaderboard',
    group: 'Leaderboards',
    method: 'GET',
    path: '/api/v1/game/leaderboards/{metric}',
    summary: 'Get a leaderboard',
    description:
      'Ranked players. Metrics: total_score, best_score, wins, achievements, completed_sessions, or category:<name>.',
    pathParams: [
      { name: 'metric', description: 'What to rank by', example: 'total_score', required: true },
    ],
    queryParams: [
      { name: 'limit', description: 'Page size (1-100)', example: '10' },
      { name: 'offset', description: 'Where to start', example: '0' },
    ],
    headers: [],
    successStatus: 200,
  },
  {
    id: 'achievements',
    group: 'Achievements',
    method: 'GET',
    path: '/api/v1/game/achievements',
    summary: 'List achievements',
    description: 'The enabled achievements for this game.',
    pathParams: [],
    queryParams: [],
    headers: [],
    successStatus: 200,
  },
  {
    id: 'analytics',
    group: 'Analytics',
    method: 'GET',
    path: '/api/v1/game/analytics/overview',
    summary: 'Analytics overview',
    description: 'Totals, active players and period comparison, calculated from real records.',
    pathParams: [],
    queryParams: [{ name: 'days', description: 'Period length (1-365)', example: '30' }],
    headers: [],
    successStatus: 200,
  },
]

export type Variables = Record<string, string>

export function newVariables(): Variables {
  const id = Math.random().toString(36).slice(2, 8)
  return {
    player_external_id: `playground-${id}`,
    session_id: '',
    idempotency_key: crypto.randomUUID(),
  }
}

/** Replace {{name}} with the matching variable (unknown names are left as written). */
export function fillTemplate(template: string, variables: Variables): string {
  return template.replace(/\{\{(\w+)\}\}/g, (match, name: string) => variables[name] ?? match)
}

export interface RequestInput {
  endpoint: PlaygroundEndpoint
  pathValues: Record<string, string>
  queryValues: Record<string, string>
  headerValues: Record<string, string>
  body: string
}

export interface BuiltRequest {
  method: Method
  url: string
  headers: Record<string, string>
  body?: string
}

/** The request exactly as it will be sent, except the API key (added separately). */
export function buildRequest(input: RequestInput): BuiltRequest {
  const { endpoint, pathValues, queryValues, headerValues, body } = input
  let path = endpoint.path
  for (const param of endpoint.pathParams) {
    path = path.replace(`{${param.name}}`, encodeURIComponent(pathValues[param.name] ?? ''))
  }
  const query = new URLSearchParams()
  for (const param of endpoint.queryParams) {
    const value = queryValues[param.name]
    if (value) query.set(param.name, value)
  }
  const headers: Record<string, string> = {}
  for (const param of endpoint.headers) {
    const value = headerValues[param.name]
    if (value) headers[param.name] = value
  }
  const hasBody = endpoint.body !== undefined && body.trim() !== ''
  if (hasBody) headers['Content-Type'] = 'application/json'
  const search = query.toString()
  return {
    method: endpoint.method,
    url: `${API_ORIGIN}${path}${search ? `?${search}` : ''}`,
    headers,
    body: hasBody ? body : undefined,
  }
}

/** Show only the key's public prefix: gp_abc123def456_•••• */
export function redactKey(key: string): string {
  const match = /^(gp_[0-9a-f]{12})_/.exec(key)
  return match ? `${match[1]}_••••••••` : '••••••••'
}

export function jsonProblem(body: string): string | null {
  if (body.trim() === '') return null
  try {
    JSON.parse(body)
    return null
  } catch (error) {
    return error instanceof Error ? error.message : 'Invalid JSON'
  }
}

const singleQuote = (text: string) => `'${text.replace(/'/g, `'\\''`)}'`

export interface Examples {
  curl: string
  javascript: string
  python: string
}

/** Copy-ready examples. The key is always a placeholder: secrets never enter examples. */
export function buildExamples(request: BuiltRequest): Examples {
  const headers = { 'X-API-Key': '$GAMEPULSE_KEY', ...request.headers }
  const curlHeaders = Object.entries(headers).map(([k, v]) => `  -H ${singleQuote(`${k}: ${v}`)}`)
  const curl = [
    `curl -X ${request.method} ${singleQuote(request.url)}`,
    ...curlHeaders,
    ...(request.body ? [`  -d ${singleQuote(request.body)}`] : []),
  ].join(' \\\n')

  const jsHeaders = { 'X-API-Key': '__KEY__', ...request.headers }
  const jsHeaderText = JSON.stringify(jsHeaders, null, 2).replace(
    '"__KEY__"',
    'process.env.GAMEPULSE_KEY',
  )
  const javascript = [
    `const response = await fetch(${JSON.stringify(request.url)}, {`,
    `  method: ${JSON.stringify(request.method)},`,
    `  headers: ${jsHeaderText.replace(/\n/g, '\n  ')},`,
    ...(request.body ? [`  body: JSON.stringify(${request.body.replace(/\n/g, '\n  ')}),`] : []),
    '})',
    'console.log(response.status, await response.json())',
  ].join('\n')

  const pyHeaders = Object.entries({ ...request.headers })
    .map(([k, v]) => `        ${JSON.stringify(k)}: ${JSON.stringify(v)},`)
    .join('\n')
  const python = [
    'import os',
    'import requests',
    '',
    'response = requests.request(',
    `    ${JSON.stringify(request.method)},`,
    `    ${JSON.stringify(request.url)},`,
    '    headers={',
    '        "X-API-Key": os.environ["GAMEPULSE_KEY"],',
    ...(pyHeaders ? [pyHeaders] : []),
    '    },',
    ...(request.body ? [`    json=${request.body.replace(/\n/g, '\n    ')},`] : []),
    ')',
    'print(response.status_code, response.json())',
  ].join('\n')

  return { curl, javascript, python }
}

export interface PlaygroundResponse {
  status: number
  statusText: string
  durationMs: number
  sizeBytes: number
  headers: Record<string, string>
  bodyText: string
  json: unknown
}

const SHOWN_HEADERS = ['content-type', 'x-request-id', 'retry-after', 'x-ratelimit-remaining']

/** Send the request to the real backend and measure how long it took. */
export async function sendRequest(
  request: BuiltRequest,
  apiKey: string,
): Promise<PlaygroundResponse> {
  const started = performance.now()
  const response = await fetch(request.url, {
    method: request.method,
    headers: { 'X-API-Key': apiKey, ...request.headers },
    body: request.body,
  })
  const bodyText = await response.text()
  const durationMs = Math.round(performance.now() - started)
  let json: unknown = null
  try {
    json = bodyText ? JSON.parse(bodyText) : null
  } catch {
    /* not JSON: shown as text */
  }
  const headers: Record<string, string> = {}
  response.headers.forEach((value, name) => {
    if (SHOWN_HEADERS.includes(name.toLowerCase())) headers[name.toLowerCase()] = value
  })
  return {
    status: response.status,
    statusText: response.statusText,
    durationMs,
    sizeBytes: new TextEncoder().encode(bodyText).length,
    headers,
    bodyText,
    json,
  }
}

/** Pull values out of a response so later requests can use them (session id, player id). */
export function captureVariables(
  endpoint: PlaygroundEndpoint,
  response: PlaygroundResponse,
  current: Variables,
): Variables {
  const data = response.json as Record<string, unknown> | null
  if (!data || response.status >= 300) return current
  if (endpoint.id === 'start-session' && typeof data.id === 'string') {
    return { ...current, session_id: data.id, idempotency_key: crypto.randomUUID() }
  }
  if (endpoint.id === 'register-player' && typeof data.external_id === 'string') {
    return { ...current, player_external_id: data.external_id }
  }
  return current
}
