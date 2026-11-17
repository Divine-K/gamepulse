import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiError, api, setUnauthorizedHandler, tokenStore } from './api'

function jsonResponse(body: unknown, status = 200) {
  return Promise.resolve(new Response(JSON.stringify(body), { status }))
}

describe('api client', () => {
  const fetchMock = vi.fn()

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock)
  })
  afterEach(() => {
    fetchMock.mockReset()
    vi.unstubAllGlobals()
    setUnauthorizedHandler(null)
  })

  it('sends the bearer token and JSON body', async () => {
    tokenStore.set('abc')
    fetchMock.mockReturnValue(jsonResponse({ ok: true }))
    await api('/x', { method: 'POST', body: { a: 1 } })
    const [, init] = fetchMock.mock.calls[0]!
    expect(init.headers.Authorization).toBe('Bearer abc')
    expect(init.headers['Content-Type']).toBe('application/json')
    expect(init.body).toBe('{"a":1}')
  })

  it('omits the token when auth is false', async () => {
    tokenStore.set('abc')
    fetchMock.mockReturnValue(jsonResponse({}))
    await api('/login', { method: 'POST', body: {}, auth: false })
    expect(fetchMock.mock.calls[0]![1].headers.Authorization).toBeUndefined()
  })

  it('turns the error envelope into an ApiError', async () => {
    fetchMock.mockReturnValue(
      jsonResponse(
        {
          error: {
            code: 'validation_error',
            message: 'Request validation failed.',
            details: [{ field: 'body.name', message: 'Field required' }],
            request_id: 'rid-1',
          },
        },
        422,
      ),
    )
    const error = (await api('/x').catch((e: unknown) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect([error.status, error.code, error.requestId]).toEqual([422, 'validation_error', 'rid-1'])
    expect(error.fieldMessage('name')).toBe('Field required')
  })

  it('reports an unreachable server clearly', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    const error = (await api('/x').catch((e: unknown) => e)) as ApiError
    expect(error.code).toBe('network_error')
    expect(error.message).toMatch(/cannot reach/i)
  })

  it('returns undefined for 204 responses', async () => {
    fetchMock.mockReturnValue(Promise.resolve(new Response(null, { status: 204 })))
    await expect(api('/x', { method: 'DELETE' })).resolves.toBeUndefined()
  })

  it('signs the user out on 401 for authenticated requests only', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    fetchMock.mockImplementation(() =>
      jsonResponse({ error: { code: 'invalid_token', message: 'x', details: [] } }, 401),
    )

    await api('/login', { auth: false }).catch(() => {})
    expect(handler).not.toHaveBeenCalled() // wrong password on the login form is not an expiry

    tokenStore.set('expired')
    await api('/me').catch(() => {})
    expect(handler).toHaveBeenCalledTimes(1)
  })
})
