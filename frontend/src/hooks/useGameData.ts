import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { useGames } from '../context/GameContext'

/**
 * Query for data belonging to the active game. Every key starts with ['game', gameId], so the
 * live stream can refresh all of a game's data by invalidating that single prefix.
 */
export function useGameData<T>(
  key: readonly unknown[],
  fetcher: (gameId: string, signal: AbortSignal) => Promise<T>,
  options: { refetchInterval?: number; enabled?: boolean } = {},
) {
  const { game } = useGames()
  const gameId = game?.id
  return useQuery({
    queryKey: ['game', gameId, ...key],
    queryFn: ({ signal }) => fetcher(gameId!, signal),
    enabled: !!gameId && (options.enabled ?? true),
    refetchInterval: options.refetchInterval,
    // Keep showing the previous page/range while the next one loads (no flicker).
    placeholderData: keepPreviousData,
  })
}
