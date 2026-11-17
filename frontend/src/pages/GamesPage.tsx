import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Check, Gamepad2, Plus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { z } from 'zod'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { TextAreaField, TextField } from '../components/ui/Field'
import { Modal } from '../components/ui/Modal'
import { PageHeader } from '../components/ui/PageHeader'
import { Skeleton } from '../components/ui/Skeleton'
import { useToast } from '../components/ui/Toast'
import { useGames } from '../context/GameContext'
import { ApiError } from '../services/api'
import { gamesApi } from '../services/endpoints'

const schema = z.object({
  name: z.string().trim().min(1, 'Give your game a name').max(100),
  genre: z.string().trim().max(50).optional(),
  description: z.string().trim().max(2000).optional(),
})
type FormValues = z.infer<typeof schema>

export function GamesPage() {
  const { games, game: selected, selectGame, isLoading } = useGames()
  const [open, setOpen] = useState(false)
  const queryClient = useQueryClient()
  const toast = useToast()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema) })

  const create = useMutation({
    mutationFn: (values: FormValues) =>
      gamesApi.create({
        name: values.name,
        description: values.description ?? '',
        genre: values.genre || null,
      }),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ['games'] })
      selectGame(created.id)
      toast.success('Game registered', `${created.name} is now your active game.`)
      setOpen(false)
      reset()
    },
    onError: (error) =>
      toast.error(
        'Could not create the game',
        error instanceof ApiError ? error.message : 'Try again.',
      ),
  })

  const closeModal = () => {
    setOpen(false)
    reset()
  }

  return (
    <>
      <PageHeader
        title="Games"
        description="Each game has its own players, sessions, scores and achievements, fully isolated from your other games."
        actions={
          <Button
            variant="primary"
            icon={<Plus aria-hidden className="size-4" />}
            onClick={() => setOpen(true)}
          >
            New game
          </Button>
        }
      />

      {isLoading ? (
        <div aria-busy="true" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
      ) : games.length === 0 ? (
        <Card>
          <EmptyState
            icon={Gamepad2}
            title="Register your first game"
            description="A game is the container for everything GamePulse tracks. After creating one you can generate an API key and connect it."
            action={
              <Button
                variant="primary"
                icon={<Plus aria-hidden className="size-4" />}
                onClick={() => setOpen(true)}
              >
                New game
              </Button>
            }
          />
        </Card>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {games.map((g) => (
            <li key={g.id}>
              <Card className="h-full transition-colors hover:border-line-strong">
                <CardBody className="flex h-full flex-col gap-3">
                  <div className="flex items-start justify-between gap-2">
                    <h2 className="font-semibold text-fg">
                      <Link
                        to={`/games/${g.id}`}
                        className="hover:underline focus-visible:underline"
                      >
                        {g.name}
                      </Link>
                    </h2>
                    {g.id === selected?.id && (
                      <Badge tone="accent">
                        <Check aria-hidden className="size-3" /> Active
                      </Badge>
                    )}
                  </div>
                  <p className="line-clamp-2 flex-1 text-sm text-muted">
                    {g.description || 'No description yet.'}
                  </p>
                  <div className="flex items-center justify-between">
                    {g.genre ? <Badge>{g.genre}</Badge> : <span />}
                    {g.id !== selected?.id && (
                      <Button size="sm" onClick={() => selectGame(g.id)}>
                        Make active
                      </Button>
                    )}
                  </div>
                </CardBody>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <Modal
        open={open}
        onClose={closeModal}
        title="Register a game"
        description="You can edit these details later."
        footer={
          <>
            <Button onClick={closeModal}>Cancel</Button>
            <Button variant="primary" type="submit" form="create-game" loading={create.isPending}>
              Create game
            </Button>
          </>
        }
      >
        <form
          id="create-game"
          onSubmit={handleSubmit((values) => create.mutate(values))}
          noValidate
          className="space-y-4"
        >
          <TextField
            label="Name"
            placeholder="Space Runner"
            error={errors.name?.message}
            {...register('name')}
          />
          <TextField
            label="Genre (optional)"
            placeholder="arcade"
            error={errors.genre?.message}
            {...register('genre')}
          />
          <TextAreaField
            label="Description (optional)"
            placeholder="What is your game about?"
            error={errors.description?.message}
            {...register('description')}
          />
        </form>
      </Modal>
    </>
  )
}
