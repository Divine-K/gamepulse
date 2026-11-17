import { describe, expect, it } from 'vitest'
import {
  ENDPOINTS,
  buildExamples,
  buildRequest,
  captureVariables,
  fillTemplate,
  jsonProblem,
  redactKey,
} from './playground'

const endpoint = (id: string) => ENDPOINTS.find((e) => e.id === id)!

describe('fillTemplate', () => {
  it('fills known variables and leaves unknown ones visible', () => {
    expect(fillTemplate('{"id": "{{a}}", "x": "{{missing}}"}', { a: '42' })).toBe(
      '{"id": "42", "x": "{{missing}}"}',
    )
  })
})

describe('buildRequest', () => {
  it('substitutes and encodes path params and skips empty query params', () => {
    const request = buildRequest({
      endpoint: endpoint('leaderboard'),
      pathValues: { metric: 'category:speed ms' },
      queryValues: { limit: '5', offset: '' },
      headerValues: {},
      body: '',
    })
    expect(request.url).toBe(
      'http://localhost:8000/api/v1/game/leaderboards/category%3Aspeed%20ms?limit=5',
    )
    expect(request.method).toBe('GET')
    expect(request.body).toBeUndefined()
  })

  it('adds content-type only when there is a body, and passes chosen headers', () => {
    const request = buildRequest({
      endpoint: endpoint('start-session'),
      pathValues: {},
      queryValues: {},
      headerValues: { 'Idempotency-Key': 'abc' },
      body: '{"player_external_id": "p1"}',
    })
    expect(request.headers).toEqual({
      'Idempotency-Key': 'abc',
      'Content-Type': 'application/json',
    })
    expect(request.body).toContain('p1')
  })
})

describe('redaction', () => {
  it('shows only the public prefix of a key', () => {
    const key = `gp_abc123def456_${'f'.repeat(64)}`
    expect(redactKey(key)).toBe('gp_abc123def456_••••••••')
    expect(redactKey(key)).not.toContain('ffff')
    expect(redactKey('garbage')).toBe('••••••••')
  })

  it('never puts a secret in a copy-ready example', () => {
    const request = buildRequest({
      endpoint: endpoint('me'),
      pathValues: {},
      queryValues: {},
      headerValues: {},
      body: '',
    })
    const { curl, javascript, python } = buildExamples(request)
    expect(curl).toContain('$GAMEPULSE_KEY')
    expect(javascript).toContain('process.env.GAMEPULSE_KEY')
    expect(python).toContain('os.environ["GAMEPULSE_KEY"]')
    for (const text of [curl, javascript, python]) expect(text).not.toMatch(/gp_[0-9a-f]{12}_/)
  })
})

describe('examples', () => {
  const request = buildRequest({
    endpoint: endpoint('submit-score'),
    pathValues: {},
    queryValues: {},
    headerValues: {},
    body: '{"value": 5}',
  })

  it('produces a runnable-looking curl command with the body quoted safely', () => {
    const { curl } = buildExamples({ ...request, body: `{"name": "O'Brien"}` })
    expect(curl).toContain("curl -X POST 'http://localhost:8000/api/v1/game/scores'")
    expect(curl).toContain(`-d '{"name": "O'\\''Brien"}'`)
  })

  it('includes the method, url and body in every language', () => {
    const { curl, javascript, python } = buildExamples(request)
    for (const text of [curl, javascript, python]) {
      expect(text).toContain('POST')
      expect(text).toContain('/api/v1/game/scores')
      expect(text).toContain('"value": 5')
    }
  })
})

describe('jsonProblem', () => {
  it('accepts valid and empty bodies and reports invalid JSON', () => {
    expect(jsonProblem('')).toBeNull()
    expect(jsonProblem('{"a": 1}')).toBeNull()
    expect(jsonProblem('{"a": ')).not.toBeNull()
  })
})

describe('captureVariables', () => {
  const ok = (json: unknown, status = 201) => ({
    status,
    statusText: '',
    durationMs: 1,
    sizeBytes: 1,
    headers: {},
    bodyText: '',
    json,
  })

  it('remembers the new session id for the following requests', () => {
    const next = captureVariables(endpoint('start-session'), ok({ id: 'sess-1' }), {
      session_id: '',
      player_external_id: 'p',
    })
    expect(next.session_id).toBe('sess-1')
  })

  it('ignores failed responses', () => {
    const current = { session_id: 'old' }
    expect(captureVariables(endpoint('start-session'), ok({ id: 'x' }, 409), current)).toBe(current)
  })
})
