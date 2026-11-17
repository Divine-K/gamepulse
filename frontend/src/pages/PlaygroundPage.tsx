import { useMutation } from '@tanstack/react-query'
import { KeyRound, Send, ShieldCheck } from 'lucide-react'
import { useMemo, useState } from 'react'
import { NoGame } from '../components/NoGame'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { CodeBlock } from '../components/ui/CodeBlock'
import { CopyButton } from '../components/ui/CopyButton'
import { TextAreaField, TextField } from '../components/ui/Field'
import { PageHeader } from '../components/ui/PageHeader'
import { Tabs, TabPanel } from '../components/ui/Tabs'
import { useToast } from '../components/ui/Toast'
import { useGames } from '../context/GameContext'
import { cn } from '../lib/cn'
import {
  ENDPOINTS,
  buildExamples,
  buildRequest,
  captureVariables,
  fillTemplate,
  jsonProblem,
  newVariables,
  redactKey,
  sendRequest,
} from '../lib/playground'
import type { PlaygroundEndpoint, PlaygroundResponse, Variables } from '../lib/playground'
import { ApiError } from '../services/api'
import { keysApi } from '../services/endpoints'

// The key lives in memory only: it survives moving between pages, never a reload or storage.
let memoryKey = ''

const METHOD_TONE = { GET: 'info', POST: 'success', PATCH: 'warning', DELETE: 'danger' } as const
function initialValues(endpoint: PlaygroundEndpoint) {
  const fromExamples = (params: { name: string; example: string }[]) =>
    Object.fromEntries(params.map((p) => [p.name, p.example]))
  return {
    path: fromExamples(endpoint.pathParams),
    query: fromExamples(endpoint.queryParams),
    headers: fromExamples(endpoint.headers),
    body: endpoint.body ?? '',
  }
}

const GROUPS = [...new Set(ENDPOINTS.map((e) => e.group))]

function statusTone(status: number) {
  if (status >= 500) return 'danger'
  if (status >= 400) return 'warning'
  if (status >= 300) return 'info'
  return 'success'
}

export function PlaygroundPage() {
  const { game } = useGames()
  const toast = useToast()
  const [endpoint, setEndpoint] = useState<PlaygroundEndpoint>(ENDPOINTS[0]!)
  const [variables, setVariables] = useState<Variables>(newVariables)
  const [apiKey, setApiKey] = useState(memoryKey)
  const [keyInput, setKeyInput] = useState('')
  const first = initialValues(ENDPOINTS[0]!)
  const [pathValues, setPathValues] = useState<Record<string, string>>(first.path)
  const [queryValues, setQueryValues] = useState<Record<string, string>>(first.query)
  const [headerValues, setHeaderValues] = useState<Record<string, string>>(first.headers)
  const [body, setBody] = useState(first.body)
  const [response, setResponse] = useState<PlaygroundResponse | null>(null)
  const [networkError, setNetworkError] = useState<string | null>(null)
  const [exampleTab, setExampleTab] = useState('curl')

  const choose = (next: PlaygroundEndpoint) => {
    setEndpoint(next)
    const initial = initialValues(next)
    setPathValues(initial.path)
    setQueryValues(initial.query)
    setHeaderValues(initial.headers)
    setBody(initial.body)
    setResponse(null)
    setNetworkError(null)
  }

  // Variables ({{session_id}} ...) are filled in when the request is built, so a session id captured
  // from one response flows into the next request without retyping.
  const resolved = useMemo(() => {
    const fill = (values: Record<string, string>) =>
      Object.fromEntries(Object.entries(values).map(([k, v]) => [k, fillTemplate(v, variables)]))
    return buildRequest({
      endpoint,
      pathValues: fill(pathValues),
      queryValues: fill(queryValues),
      headerValues: fill(headerValues),
      body: fillTemplate(body, variables),
    })
  }, [endpoint, pathValues, queryValues, headerValues, body, variables])

  const examples = useMemo(() => buildExamples(resolved), [resolved])
  const bodyProblem = jsonProblem(resolved.body ?? '')
  const missingPath = endpoint.pathParams.some(
    (p) => !fillTemplate(pathValues[p.name] ?? p.example, variables).trim(),
  )

  const createKey = useMutation({
    mutationFn: () => keysApi.create(game!.id, 'Playground'),
    onSuccess: (created) => {
      memoryKey = created.key
      setApiKey(created.key)
      toast.success(
        'Playground key created',
        'It is kept in memory only. Revoke it from the game’s API keys when you are done.',
      )
    },
    onError: (error) =>
      toast.error(
        'Could not create a key',
        error instanceof ApiError ? error.message : 'Try again.',
      ),
  })

  const send = useMutation({
    mutationFn: () => sendRequest(resolved, apiKey),
    onMutate: () => setNetworkError(null),
    onSuccess: (result) => {
      setResponse(result)
      setVariables((current) => captureVariables(endpoint, result, current))
    },
    onError: () => {
      setResponse(null)
      setNetworkError('Could not reach the server. Is the API running?')
    },
  })

  if (!game)
    return (
      <>
        <PageHeader title="API Playground" />
        <NoGame what="The playground" />
      </>
    )

  const useKey = () => {
    const key = keyInput.trim()
    if (!key) return
    memoryKey = key
    setApiKey(key)
    setKeyInput('')
  }

  const canSend = apiKey !== '' && !bodyProblem && !missingPath
  const prettyBody = response
    ? response.json !== null
      ? JSON.stringify(response.json, null, 2)
      : response.bodyText
    : ''

  return (
    <>
      <PageHeader
        title="API Playground"
        description="Try the game API with real requests against your backend. Nothing here is simulated: requests change real data for your game."
      />

      <Card className="mb-4">
        <CardBody className="flex flex-wrap items-end gap-4">
          <div className="flex items-center gap-3">
            <span className="flex size-9 items-center justify-center rounded-lg bg-accent-soft text-accent-text">
              <ShieldCheck aria-hidden className="size-5" />
            </span>
            <div>
              <p className="text-sm font-medium">API key for {game.name}</p>
              <p className="text-xs text-muted">
                {apiKey ? (
                  <>
                    Using <code className="font-mono">{redactKey(apiKey)}</code>. Kept in memory
                    only and never shown again.
                  </>
                ) : (
                  'Paste a key, or create a throwaway one. Game requests are authenticated with X-API-Key.'
                )}
              </p>
            </div>
          </div>
          <div className="flex flex-1 flex-wrap items-end gap-2">
            <div className="min-w-60 flex-1">
              <TextField
                label="Paste an API key"
                type="password"
                autoComplete="off"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="gp_…"
              />
            </div>
            <Button onClick={useKey} disabled={!keyInput.trim()}>
              Use key
            </Button>
            <Button
              icon={<KeyRound aria-hidden className="size-4" />}
              onClick={() => createKey.mutate()}
              loading={createKey.isPending}
            >
              Create a playground key
            </Button>
          </div>
        </CardBody>
      </Card>

      <div className="grid gap-4 xl:grid-cols-4">
        <Card className="xl:col-span-1">
          <nav aria-label="Endpoints" className="max-h-[40rem] space-y-4 overflow-auto p-3">
            {GROUPS.map((group) => (
              <div key={group}>
                <p className="px-2 pb-1 text-[11px] font-semibold tracking-wider text-subtle uppercase">
                  {group}
                </p>
                <ul className="space-y-0.5">
                  {ENDPOINTS.filter((e) => e.group === group).map((e) => (
                    <li key={e.id}>
                      <button
                        type="button"
                        aria-current={e.id === endpoint.id ? 'true' : undefined}
                        onClick={() => choose(e)}
                        className={cn(
                          'flex w-full items-center gap-2 rounded-md px-2 py-2 text-left text-sm transition-colors',
                          e.id === endpoint.id
                            ? 'bg-accent-soft text-fg'
                            : 'text-muted hover:bg-raised hover:text-fg',
                        )}
                      >
                        <Badge
                          tone={METHOD_TONE[e.method]}
                          className="w-14 shrink-0 justify-center px-1 text-[10px]"
                        >
                          {e.method}
                        </Badge>
                        <span className="truncate">{e.summary}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </nav>
        </Card>

        <div className="space-y-4 xl:col-span-3">
          <Card>
            <CardHeader
              title={endpoint.summary}
              description={endpoint.description}
              action={<Badge tone={METHOD_TONE[endpoint.method]}>{endpoint.method}</Badge>}
            />
            <CardBody className="space-y-4">
              <p className="overflow-x-auto rounded-md border border-line bg-canvas px-3 py-2 font-mono text-sm">
                {endpoint.path}
              </p>

              {endpoint.pathParams.map((p) => (
                <TextField
                  key={p.name}
                  label={`${p.name} (path, required)`}
                  hint={p.description}
                  value={pathValues[p.name] ?? p.example}
                  onChange={(e) => setPathValues({ ...pathValues, [p.name]: e.target.value })}
                />
              ))}
              {endpoint.queryParams.map((p) => (
                <TextField
                  key={p.name}
                  label={`${p.name} (query, optional)`}
                  hint={p.description}
                  value={queryValues[p.name] ?? ''}
                  onChange={(e) => setQueryValues({ ...queryValues, [p.name]: e.target.value })}
                />
              ))}
              {endpoint.headers.map((p) => (
                <TextField
                  key={p.name}
                  label={`${p.name} (header, optional)`}
                  hint={p.description}
                  value={headerValues[p.name] ?? ''}
                  onChange={(e) => setHeaderValues({ ...headerValues, [p.name]: e.target.value })}
                />
              ))}
              {endpoint.body !== undefined && (
                <TextAreaField
                  label="Request body (JSON)"
                  className="font-mono text-[13px]"
                  rows={Math.min(10, body.split('\n').length + 1)}
                  value={body}
                  onChange={(e) => setBody(e.target.value)}
                  error={bodyProblem ? `Invalid JSON: ${bodyProblem}` : undefined}
                  hint="{{session_id}} and {{player_external_id}} are filled in from earlier responses."
                />
              )}

              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="primary"
                  icon={<Send aria-hidden className="size-4" />}
                  onClick={() => send.mutate()}
                  loading={send.isPending}
                  disabled={!canSend}
                >
                  Send request
                </Button>
                {!apiKey && <span className="text-sm text-muted">Add an API key first.</span>}
                <span className="text-xs text-subtle">
                  Expected status {endpoint.successStatus}
                </span>
              </div>

              <dl className="grid gap-x-6 gap-y-1 text-xs text-muted sm:grid-cols-2">
                <div className="flex gap-2">
                  <dt>player_external_id</dt>
                  <dd className="font-mono text-fg">{variables.player_external_id}</dd>
                </div>
                <div className="flex gap-2">
                  <dt>session_id</dt>
                  <dd className="truncate font-mono text-fg">
                    {variables.session_id || 'none yet (start a session)'}
                  </dd>
                </div>
              </dl>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Response"
              description={response ? undefined : 'Send a request to see the real response here.'}
            />
            <CardBody className="space-y-3">
              {networkError && (
                <p
                  role="alert"
                  className="rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-sm text-danger"
                >
                  {networkError}
                </p>
              )}
              {response && (
                <>
                  <div
                    className="flex flex-wrap items-center gap-3 text-sm"
                    role="status"
                    aria-label="Response summary"
                  >
                    <Badge tone={statusTone(response.status)}>
                      {response.status} {response.statusText}
                    </Badge>
                    <span className="tabular-nums text-muted">{response.durationMs} ms</span>
                    <span className="tabular-nums text-muted">
                      {response.sizeBytes.toLocaleString()} bytes
                    </span>
                    {response.headers['x-request-id'] && (
                      <span className="font-mono text-xs text-subtle">
                        request {response.headers['x-request-id'].slice(0, 8)}
                      </span>
                    )}
                  </div>
                  <div className="overflow-hidden rounded-lg border border-line bg-canvas">
                    <div className="flex items-center justify-between border-b border-line px-4 py-2">
                      <span className="text-xs font-medium text-muted">Response body</span>
                      <CopyButton text={prettyBody} />
                    </div>
                    <pre
                      aria-label="Response body"
                      className="max-h-96 overflow-auto p-4 font-mono text-[13px] leading-relaxed text-fg"
                    >
                      <code>{prettyBody || '(empty)'}</code>
                    </pre>
                  </div>
                </>
              )}
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Request"
              description="Exactly what is sent. The API key is redacted here and replaced by a placeholder in the examples."
            />
            <CardBody className="space-y-4">
              <pre
                aria-label="Request preview"
                className="overflow-x-auto rounded-md border border-line bg-canvas p-3 font-mono text-[13px]"
              >
                <code>
                  {[
                    `${resolved.method} ${resolved.url}`,
                    `X-API-Key: ${apiKey ? redactKey(apiKey) : 'gp_••••••••'}`,
                    ...Object.entries(resolved.headers).map(([k, v]) => `${k}: ${v}`),
                    ...(resolved.body ? ['', resolved.body] : []),
                  ].join('\n')}
                </code>
              </pre>
              <Tabs
                tabs={[
                  { id: 'curl', label: 'curl' },
                  { id: 'javascript', label: 'JavaScript' },
                  { id: 'python', label: 'Python' },
                ]}
                active={exampleTab}
                onChange={setExampleTab}
                label="Code examples"
                idPrefix="example"
              />
              <TabPanel id="curl" active={exampleTab} idPrefix="example">
                <CodeBlock title="curl" code={examples.curl} />
              </TabPanel>
              <TabPanel id="javascript" active={exampleTab} idPrefix="example">
                <CodeBlock title="JavaScript (fetch)" code={examples.javascript} />
              </TabPanel>
              <TabPanel id="python" active={exampleTab} idPrefix="example">
                <CodeBlock title="Python (requests)" code={examples.python} />
              </TabPanel>
            </CardBody>
          </Card>
        </div>
      </div>
    </>
  )
}
