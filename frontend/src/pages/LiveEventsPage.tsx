import { Pause, Play, Radio, Trash2 } from 'lucide-react'
import { AnimatePresence, motion } from 'motion/react'
import { useState } from 'react'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { LiveDot } from '../components/ui/LiveDot'
import { PageHeader } from '../components/ui/PageHeader'
import { useGames } from '../context/GameContext'
import { useStream } from '../context/StreamContext'
import { describeEvent } from '../lib/events'
import { formatTime } from '../lib/format'
import type { GameEvent } from '../types/api'

export function LiveEventsPage() {
  const { game } = useGames()
  const { status, events, clear } = useStream()
  const [paused, setPaused] = useState(false)
  const [frozen, setFrozen] = useState<GameEvent[]>([])

  // While paused, show a snapshot; events keep arriving in the background.
  const visible = paused ? frozen : events

  const togglePause = () => {
    if (!paused) setFrozen(events)
    setPaused((p) => !p)
  }

  return (
    <>
      <PageHeader
        title="Live Events"
        description="Everything your players do, the moment it happens."
        actions={
          <>
            <Button
              size="sm"
              onClick={togglePause}
              icon={
                paused ? (
                  <Play aria-hidden className="size-4" />
                ) : (
                  <Pause aria-hidden className="size-4" />
                )
              }
              disabled={!game}
            >
              {paused ? 'Resume' : 'Pause'}
            </Button>
            <Button
              size="sm"
              icon={<Trash2 aria-hidden className="size-4" />}
              onClick={clear}
              disabled={events.length === 0}
            >
              Clear
            </Button>
          </>
        }
      />

      <Card>
        <div className="flex items-center gap-2 border-b border-line px-5 py-3 text-sm">
          <LiveDot active={status === 'live' && !paused} />
          <span className="text-muted">
            {!game
              ? 'Create a game to see live events.'
              : paused
                ? `Paused (${events.length - frozen.length} new)`
                : status === 'live'
                  ? 'Connected. Waiting for activity.'
                  : status === 'reconnecting'
                    ? 'Reconnecting…'
                    : status === 'failed'
                      ? 'Disconnected. Reload the page to retry.'
                      : 'Connecting…'}
          </span>
        </div>

        {visible.length === 0 ? (
          <EmptyState
            icon={Radio}
            title="No events yet"
            description="Events appear here as your game sends players, sessions and scores to the API. Until the simulator ships, send requests with curl or the API docs."
          />
        ) : (
          <ul aria-label="Event feed" className="divide-y divide-line">
            <AnimatePresence initial={false}>
              {visible.slice(0, 100).map((event) => {
                const view = describeEvent(event)
                return (
                  <motion.li
                    key={event.id}
                    initial={{ opacity: 0, y: -8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.2 }}
                    className="flex items-center gap-3 px-5 py-3"
                  >
                    <Badge tone={view.tone} className="w-44 shrink-0 justify-center">
                      {view.title}
                    </Badge>
                    <span className="min-w-0 flex-1 truncate text-sm text-fg">{view.detail}</span>
                    {event.is_simulated && <Badge tone="warning">Simulated</Badge>}
                    <time dateTime={event.ts} className="shrink-0 font-mono text-xs text-subtle">
                      {formatTime(event.ts)}
                    </time>
                  </motion.li>
                )
              })}
            </AnimatePresence>
          </ul>
        )}
      </Card>
    </>
  )
}
