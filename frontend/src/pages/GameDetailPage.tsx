import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Check } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'
import { DeletePanel } from '../components/games/DeletePanel'
import { DetailsPanel } from '../components/games/DetailsPanel'
import { IntegrationPanel } from '../components/games/IntegrationPanel'
import { KeysPanel } from '../components/games/KeysPanel'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { PageHeader } from '../components/ui/PageHeader'
import { Skeleton } from '../components/ui/Skeleton'
import { TabPanel, Tabs } from '../components/ui/Tabs'
import { useGames } from '../context/GameContext'
import { useUrlState } from '../hooks/useUrlState'
import { ApiError } from '../services/api'
import { gamesApi } from '../services/endpoints'

const TABS = [
  { id: 'details', label: 'Details' },
  { id: 'keys', label: 'API keys' },
  { id: 'integration', label: 'Integration' },
  { id: 'danger', label: 'Delete' },
]

export function GameDetailPage() {
  const { gameId = '' } = useParams()
  const { game: active, selectGame } = useGames()
  const [{ tab }, update] = useUrlState({ tab: 'details' })
  const query = useQuery({
    queryKey: ['games', gameId],
    queryFn: ({ signal }) => gamesApi.get(gameId, signal),
    retry: false,
  })

  if (query.isLoading) {
    return <Skeleton className="h-48" />
  }
  if (query.isError || !query.data) {
    const notFound = query.error instanceof ApiError && query.error.status === 404
    return (
      <Card>
        <EmptyState
          title={notFound ? 'Game not found' : 'Could not load this game'}
          description={
            notFound
              ? 'It may have been deleted, or it belongs to another account.'
              : 'Check your connection and try again.'
          }
          action={
            <Link to="/games">
              <Button variant="primary">Back to games</Button>
            </Link>
          }
        />
      </Card>
    )
  }

  const game = query.data
  const isActive = active?.id === game.id
  return (
    <>
      <Link
        to="/games"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted hover:text-fg"
      >
        <ArrowLeft aria-hidden className="size-4" /> All games
      </Link>
      <PageHeader
        title={game.name}
        description={game.description || undefined}
        actions={
          isActive ? (
            <Badge tone="accent">
              <Check aria-hidden className="size-3" /> Active game
            </Badge>
          ) : (
            <Button onClick={() => selectGame(game.id)}>Make active</Button>
          )
        }
      />
      <Tabs
        tabs={TABS}
        active={tab}
        onChange={(id) => update({ tab: id })}
        label="Game sections"
        idPrefix="game"
      />
      <TabPanel id="details" active={tab} idPrefix="game">
        <DetailsPanel key={game.updated_at} game={game} />
      </TabPanel>
      <TabPanel id="keys" active={tab} idPrefix="game">
        <KeysPanel gameId={game.id} />
      </TabPanel>
      <TabPanel id="integration" active={tab} idPrefix="game">
        <IntegrationPanel />
      </TabPanel>
      <TabPanel id="danger" active={tab} idPrefix="game">
        <DeletePanel game={game} />
      </TabPanel>
    </>
  )
}
