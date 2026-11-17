import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Play, Plus, Radio, Send, Square, Trash2, Trophy, Zap } from 'lucide-react'
import { useState } from 'react'
import { NoGame } from '../components/NoGame'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { TextAreaField, TextField } from '../components/ui/Field'
import { ConfirmDialog } from '../components/ui/Modal'
import { PageHeader } from '../components/ui/PageHeader'
import { SelectField } from '../components/ui/Select'
import { useToast } from '../components/ui/Toast'
import { useGames } from '../context/GameContext'
import { useStream } from '../context/StreamContext'
import { useGameData } from '../hooks/useGameData'
import { describeEvent } from '../lib/events'
import { formatNumber, formatTime } from '../lib/format'
import { ApiError } from '../services/api'
import { achievementsApi, simulatorApi } from '../services/endpoints'

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

export function SimulatorPage() {
  const { game } = useGames()
  const { events, status } = useStream()
  const queryClient = useQueryClient()
  const toast = useToast()
  const gameId = game?.id ?? ''

  const [playerId, setPlayerId] = useState('')
  const [username, setUsername] = useState('')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [score, setScore] = useState('500')
  const [achievementId, setAchievementId] = useState('')
  const [eventType, setEventType] = useState('custom_boss_defeated')
  const [payloadText, setPayloadText] = useState('{"boss": "kraken"}')
  const [payloadError, setPayloadError] = useState<string | null>(null)
  const [result, setResult] = useState('win')
  const [finalScore, setFinalScore] = useState('')
  const [confirmClear, setConfirmClear] = useState(false)
  const [demoRunning, setDemoRunning] = useState(false)

  const summary = useQuery({
    queryKey: ['game', gameId, 'sim-summary'],
    queryFn: ({ signal }) => simulatorApi.summary(gameId, signal),
    enabled: !!gameId,
  })
  const players = useQuery({
    queryKey: ['game', gameId, 'sim-players'],
    queryFn: ({ signal }) => simulatorApi.players(gameId, signal),
    enabled: !!gameId,
  })
  const achievements = useGameData(['achievements'], (id, signal) =>
    achievementsApi.list(id, signal),
  )

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['game', gameId] })
  const fail = (title: string) => (error: unknown) =>
    toast.error(title, error instanceof ApiError ? error.message : 'Try again.')

  const activePlayerId = playerId || players.data?.items[0]?.id || ''

  const createPlayer = useMutation({
    mutationFn: () => simulatorApi.createPlayer(gameId, username.trim() || undefined),
    onSuccess: async (p) => {
      setPlayerId(p.id)
      setUsername('')
      toast.success('Test player created', `${p.username} is flagged as simulated.`)
      await refresh()
    },
    onError: fail('Could not create a test player'),
  })
  const startSession = useMutation({
    mutationFn: () => simulatorApi.startSession(gameId, activePlayerId),
    onSuccess: async (s) => {
      setSessionId(s.id)
      toast.success('Session started')
      await refresh()
    },
    onError: fail('Could not start the session'),
  })
  const sendScore = useMutation({
    mutationFn: () => simulatorApi.sendScore(gameId, sessionId!, Number(score)),
    onSuccess: async () => {
      toast.success('Score sent', `Live score is now ${formatNumber(Number(score))}.`)
      await refresh()
    },
    onError: fail('Could not send the score'),
  })
  const award = useMutation({
    mutationFn: () => simulatorApi.award(gameId, activePlayerId, achievementId),
    onSuccess: async (r) => {
      if (r.awarded) toast.success('Achievement awarded', r.achievement_key)
      else toast.info('Already unlocked', 'This player already has that achievement.')
      await refresh()
    },
    onError: fail('Could not award the achievement'),
  })
  const sendEvent = useMutation({
    mutationFn: (payload: Record<string, unknown>) =>
      simulatorApi.sendEvent(gameId, {
        event_type: eventType,
        player_id: activePlayerId || undefined,
        session_id: sessionId ?? undefined,
        payload,
      }),
    onSuccess: async () => {
      toast.success('Event sent', eventType)
      await refresh()
    },
    onError: fail('Could not send the event'),
  })
  const endSession = useMutation({
    mutationFn: () =>
      simulatorApi.endSession(gameId, sessionId!, {
        result,
        score: finalScore === '' ? undefined : Number(finalScore),
      }),
    onSuccess: async (s) => {
      setSessionId(null)
      const unlocked = s.unlocked_achievements.map((a) => a.name)
      toast.success(
        'Session ended',
        unlocked.length ? `Unlocked: ${unlocked.join(', ')}` : undefined,
      )
      await refresh()
    },
    onError: fail('Could not end the session'),
  })
  const clear = useMutation({
    mutationFn: () => simulatorApi.clear(gameId),
    onSuccess: async (r) => {
      setConfirmClear(false)
      setPlayerId('')
      setSessionId(null)
      toast.success(
        'Simulated data deleted',
        `${r.deleted.players} players, ${r.deleted.sessions} sessions, ${r.deleted.events} events. Real data was not touched.`,
      )
      await refresh()
    },
    onError: fail('Could not delete simulated data'),
  })

  const submitEvent = () => {
    try {
      const parsed: unknown = JSON.parse(payloadText || '{}')
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error()
      setPayloadError(null)
      sendEvent.mutate(parsed as Record<string, unknown>)
    } catch {
      setPayloadError('Payload must be a JSON object, for example {"boss": "kraken"}')
    }
  }

  /** A scripted play-through: new player, session, three score updates, an event, a win. */
  const runDemo = async () => {
    setDemoRunning(true)
    try {
      const player = await simulatorApi.createPlayer(gameId)
      setPlayerId(player.id)
      const session = await simulatorApi.startSession(gameId, player.id)
      for (const value of [250, 700, 1200]) {
        await sleep(700)
        await simulatorApi.sendScore(gameId, session.id, value)
      }
      await sleep(500)
      await simulatorApi.sendEvent(gameId, {
        event_type: 'custom_boss_defeated',
        player_id: player.id,
        session_id: session.id,
        payload: { boss: 'kraken' },
      })
      await sleep(500)
      const ended = await simulatorApi.endSession(gameId, session.id, { result: 'win' })
      toast.success(
        'Demo finished',
        ended.unlocked_achievements.length
          ? `Unlocked: ${ended.unlocked_achievements.map((a) => a.name).join(', ')}`
          : 'Watch the feed for what happened.',
      )
    } catch (error) {
      fail('The demo stopped')(error)
    } finally {
      setDemoRunning(false)
      await refresh()
    }
  }

  if (!game)
    return (
      <>
        <PageHeader title="Simulator" />
        <NoGame what="The simulator" />
      </>
    )

  const busy = demoRunning
  const hasPlayer = activePlayerId !== ''
  const counts = summary.data
  const feed = events.slice(0, 30)

  return (
    <>
      <PageHeader
        title="Simulator"
        description="Play your game without an engine. Every action goes to the real backend and is saved to the database, but is clearly labeled as simulated."
        actions={
          <Button
            variant="primary"
            icon={<Play aria-hidden className="size-4" />}
            onClick={runDemo}
            loading={demoRunning}
            disabled={createPlayer.isPending}
          >
            Run a quick demo
          </Button>
        }
      />

      <div className="grid gap-4 xl:grid-cols-5">
        <div className="space-y-4 xl:col-span-3">
          <Card>
            <CardHeader
              title="1. Choose a player"
              description="Test players are always flagged as simulated. Real players can't be driven from here."
            />
            <CardBody className="space-y-4">
              {(players.data?.items.length ?? 0) > 0 && (
                <SelectField
                  label="Test player"
                  value={activePlayerId}
                  onChange={(e) => {
                    setPlayerId(e.target.value)
                    setSessionId(null)
                  }}
                  options={players.data!.items.map((p) => ({
                    value: p.id,
                    label: `${p.username} (${p.external_id})`,
                  }))}
                />
              )}
              <div className="flex flex-wrap items-end gap-3">
                <div className="min-w-48 flex-1">
                  <TextField
                    label="New test player name (optional)"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="Sim Ada"
                    maxLength={64}
                  />
                </div>
                <Button
                  icon={<Plus aria-hidden className="size-4" />}
                  onClick={() => createPlayer.mutate()}
                  loading={createPlayer.isPending}
                  disabled={busy}
                >
                  New test player
                </Button>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="2. Session"
              description={
                sessionId
                  ? 'A session is active. Send scores and events, then end it.'
                  : 'Start a session for the chosen player.'
              }
              action={sessionId ? <Badge tone="success">Active</Badge> : <Badge>No session</Badge>}
            />
            <CardBody className="space-y-5">
              <div className="flex flex-wrap items-end gap-3">
                <Button
                  variant="primary"
                  icon={<Play aria-hidden className="size-4" />}
                  onClick={() => startSession.mutate()}
                  loading={startSession.isPending}
                  disabled={!hasPlayer || sessionId !== null || busy}
                >
                  Start session
                </Button>
                {!hasPlayer && <p className="text-sm text-muted">Create a test player first.</p>}
              </div>

              <div className="flex flex-wrap items-end gap-3">
                <div className="w-40">
                  <TextField
                    label="Score"
                    type="number"
                    min={0}
                    value={score}
                    onChange={(e) => setScore(e.target.value)}
                  />
                </div>
                <Button
                  icon={<Send aria-hidden className="size-4" />}
                  onClick={() => sendScore.mutate()}
                  loading={sendScore.isPending}
                  disabled={!sessionId || score === '' || busy}
                >
                  Send score update
                </Button>
              </div>

              <div className="flex flex-wrap items-end gap-3">
                <SelectField
                  className="min-w-56 flex-1"
                  label="Achievement"
                  value={achievementId}
                  onChange={(e) => setAchievementId(e.target.value)}
                  options={[
                    { value: '', label: 'Choose an achievement…' },
                    ...(achievements.data ?? []).map((a) => ({ value: a.id, label: a.name })),
                  ]}
                />
                <Button
                  icon={<Trophy aria-hidden className="size-4" />}
                  onClick={() => award.mutate()}
                  loading={award.isPending}
                  disabled={!hasPlayer || !achievementId || busy}
                >
                  Award achievement
                </Button>
              </div>

              <div className="space-y-3">
                <div className="grid gap-3 sm:grid-cols-3">
                  <div className="sm:col-span-1">
                    <TextField
                      label="Event type"
                      value={eventType}
                      onChange={(e) => setEventType(e.target.value)}
                      hint="custom_… or player_level_up"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <TextAreaField
                      label="Payload (JSON)"
                      value={payloadText}
                      onChange={(e) => setPayloadText(e.target.value)}
                      error={payloadError ?? undefined}
                      rows={2}
                    />
                  </div>
                </div>
                <Button
                  icon={<Zap aria-hidden className="size-4" />}
                  onClick={submitEvent}
                  loading={sendEvent.isPending}
                  disabled={busy}
                >
                  Send custom event
                </Button>
              </div>

              <div className="flex flex-wrap items-end gap-3 border-t border-line pt-5">
                <SelectField
                  className="w-36"
                  label="Result"
                  value={result}
                  onChange={(e) => setResult(e.target.value)}
                  options={[
                    { value: 'win', label: 'Win' },
                    { value: 'loss', label: 'Loss' },
                    { value: 'draw', label: 'Draw' },
                  ]}
                />
                <div className="w-44">
                  <TextField
                    label="Final score (optional)"
                    type="number"
                    min={0}
                    value={finalScore}
                    onChange={(e) => setFinalScore(e.target.value)}
                    hint="Defaults to the live score"
                  />
                </div>
                <Button
                  variant="danger"
                  icon={<Square aria-hidden className="size-4" />}
                  onClick={() => endSession.mutate()}
                  loading={endSession.isPending}
                  disabled={!sessionId || busy}
                >
                  End session
                </Button>
              </div>
            </CardBody>
          </Card>
        </div>

        <div className="space-y-4 xl:col-span-2">
          <Card>
            <CardHeader
              title="Simulated data"
              description="Saved in the database and labeled as simulated."
            />
            <CardBody className="space-y-4">
              <dl className="grid grid-cols-3 gap-3 text-center">
                {(
                  [
                    ['Players', counts?.players],
                    ['Sessions', counts?.sessions],
                    ['Events', counts?.events],
                  ] as const
                ).map(([label, value]) => (
                  <div key={label} className="rounded-lg border border-line bg-raised px-2 py-3">
                    <dd className="text-xl font-semibold tabular-nums">
                      {value === undefined ? '–' : formatNumber(value)}
                    </dd>
                    <dt className="text-xs text-muted">{label}</dt>
                  </div>
                ))}
              </dl>
              <Button
                variant="danger"
                className="w-full"
                icon={<Trash2 aria-hidden className="size-4" />}
                onClick={() => setConfirmClear(true)}
                disabled={busy || !counts || (counts.players === 0 && counts.events === 0)}
              >
                Delete all simulated data
              </Button>
              <p className="text-xs text-muted">
                Only rows flagged as simulated are removed. Your real players, sessions and events
                are never touched.
              </p>
            </CardBody>
          </Card>

          <Card>
            <CardHeader
              title="Live feed"
              description={
                status === 'live'
                  ? 'Connected. Events arrive over WebSocket.'
                  : 'Connecting to the live stream…'
              }
            />
            {feed.length === 0 ? (
              <EmptyState
                icon={Radio}
                title="Nothing yet"
                description="Start a session or run the demo and watch events appear here."
              />
            ) : (
              <ul
                aria-label="Event feed"
                className="max-h-[28rem] divide-y divide-line overflow-auto"
              >
                {feed.map((event) => {
                  const view = describeEvent(event)
                  return (
                    <li key={event.id} className="flex items-center gap-2 px-5 py-2.5 text-sm">
                      <Badge tone={view.tone} className="shrink-0">
                        {view.title}
                      </Badge>
                      <span className="min-w-0 flex-1 truncate text-muted">{view.detail}</span>
                      {event.is_simulated && <Badge tone="warning">Simulated</Badge>}
                      <time dateTime={event.ts} className="shrink-0 font-mono text-xs text-subtle">
                        {formatTime(event.ts)}
                      </time>
                    </li>
                  )
                })}
              </ul>
            )}
          </Card>
        </div>
      </div>

      <ConfirmDialog
        open={confirmClear}
        onClose={() => setConfirmClear(false)}
        onConfirm={() => clear.mutate()}
        loading={clear.isPending}
        destructive
        title="Delete all simulated data?"
        description={`This removes ${counts?.players ?? 0} simulated players, ${counts?.sessions ?? 0} sessions and ${counts?.events ?? 0} events from this game. Real data is not affected.`}
        confirmLabel="Delete simulated data"
      />
    </>
  )
}
