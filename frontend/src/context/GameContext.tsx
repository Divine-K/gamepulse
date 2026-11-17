import { useQuery } from '@tanstack/react-query'
import { createContext, useCallback, useContext, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { gamesApi } from '../services/endpoints'
import type { Game } from '../types/api'
import { useAuth } from './AuthContext'

const KEY = 'gp-game'

interface GameValue {
  games: Game[]
  game: Game | null
  isLoading: boolean
  selectGame: (id: string) => void
}

const GameContext = createContext<GameValue | null>(null)

export function GameProvider({ children }: { children: ReactNode }) {
  const { status } = useAuth()
  const [selectedId, setSelectedId] = useState<string | null>(() => {
    try {
      return localStorage.getItem(KEY)
    } catch {
      return null
    }
  })

  const query = useQuery({
    queryKey: ['games'],
    queryFn: ({ signal }) => gamesApi.list(signal),
    enabled: status === 'authenticated',
  })

  const games = useMemo(() => query.data?.items ?? [], [query.data])
  // Fall back to the first game if the remembered one no longer exists.
  const game = games.find((g) => g.id === selectedId) ?? games[0] ?? null

  const selectGame = useCallback((id: string) => {
    setSelectedId(id)
    try {
      localStorage.setItem(KEY, id)
    } catch {
      /* ignore */
    }
  }, [])

  const value = useMemo(
    () => ({ games, game, isLoading: query.isLoading, selectGame }),
    [games, game, query.isLoading, selectGame],
  )
  return <GameContext.Provider value={value}>{children}</GameContext.Provider>
}

export function useGames(): GameValue {
  const ctx = useContext(GameContext)
  if (!ctx) throw new Error('useGames must be used inside <GameProvider>')
  return ctx
}
