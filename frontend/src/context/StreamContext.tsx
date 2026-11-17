import { useQueryClient } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { tokenStore } from '../services/api'
import { GameStream } from '../services/stream'
import type { StreamStatus } from '../services/stream'
import type { GameEvent } from '../types/api'
import { useAuth } from './AuthContext'
import { useGames } from './GameContext'

const MAX_EVENTS = 200

interface StreamValue {
  status: StreamStatus | 'idle'
  events: GameEvent[]
  clear: () => void
}

const StreamContext = createContext<StreamValue | null>(null)

/** One live connection for the selected game, shared by every page. */
export function StreamProvider({ children }: { children: ReactNode }) {
  const { status: authStatus } = useAuth()
  const { game } = useGames()
  const queryClient = useQueryClient()
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('connecting')
  // Events are tagged with their game so switching games never shows another game's feed.
  const [eventState, setEventState] = useState<{ gameId?: string; list: GameEvent[] }>({
    list: [],
  })

  const gameId = game?.id
  const enabled = authStatus === 'authenticated' && !!gameId

  useEffect(() => {
    const token = tokenStore.get()
    if (!enabled || !gameId || !token) return
    let refreshTimer: number | undefined
    const stream = new GameStream({
      gameId,
      token,
      onStatus: setStreamStatus,
      onEvent: (event) => {
        setEventState((current) => ({
          gameId,
          list: [event, ...(current.gameId === gameId ? current.list : [])].slice(0, MAX_EVENTS),
        }))
        // Server data changed. REST is the source of truth, so refresh this game's queries,
        // at most once per 1.5 s so a burst of events causes a single refetch.
        if (!refreshTimer) {
          refreshTimer = window.setTimeout(() => {
            refreshTimer = undefined
            void queryClient.invalidateQueries({ queryKey: ['game', gameId] })
          }, 1500)
        }
      },
      // Events can be missed while disconnected, so refetch everything on reconnect.
      onReconnected: () => void queryClient.invalidateQueries(),
    })
    stream.start()
    return () => {
      window.clearTimeout(refreshTimer)
      stream.stop()
    }
  }, [enabled, gameId, queryClient])

  const events = useMemo(
    () => (eventState.gameId === gameId ? eventState.list : []),
    [eventState, gameId],
  )
  const clear = useCallback(() => setEventState({ gameId, list: [] }), [gameId])
  const status: StreamValue['status'] = enabled ? streamStatus : 'idle'
  const value = useMemo(() => ({ status, events, clear }), [status, events, clear])
  return <StreamContext.Provider value={value}>{children}</StreamContext.Provider>
}

export function useStream(): StreamValue {
  const ctx = useContext(StreamContext)
  if (!ctx) throw new Error('useStream must be used inside <StreamProvider>')
  return ctx
}
