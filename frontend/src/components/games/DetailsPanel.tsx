import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Activity, Users, Zap } from 'lucide-react'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { formatNumber } from '../../lib/format'
import { ApiError } from '../../services/api'
import { analyticsApi, gamesApi } from '../../services/endpoints'
import type { Game } from '../../types/api'
import { Button } from '../ui/Button'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { TextAreaField, TextField } from '../ui/Field'
import { StatCard } from '../ui/StatCard'
import { useToast } from '../ui/Toast'

const schema = z.object({
  name: z.string().trim().min(1, 'Give your game a name').max(100),
  genre: z.string().trim().max(50).optional(),
  description: z.string().trim().max(2000).optional(),
})
type FormValues = z.infer<typeof schema>

export function DetailsPanel({ game }: { game: Game }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const stats = useQuery({
    queryKey: ['game-stats', game.id],
    queryFn: ({ signal }) => analyticsApi.overview(game.id, { days: 30 }, signal),
  })
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
    reset,
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: game.name, genre: game.genre ?? '', description: game.description },
  })

  const save = useMutation({
    mutationFn: (values: FormValues) =>
      gamesApi.update(game.id, {
        name: values.name,
        genre: values.genre || null,
        description: values.description ?? '',
      }),
    onSuccess: async (updated) => {
      reset({ name: updated.name, genre: updated.genre ?? '', description: updated.description })
      await queryClient.invalidateQueries({ queryKey: ['games'] })
      toast.success('Game updated')
    },
    onError: (error) =>
      toast.error(
        'Could not save changes',
        error instanceof ApiError ? error.message : 'Try again.',
      ),
  })

  const o = stats.data
  return (
    <div className="space-y-4">
      <div className="grid gap-4 sm:grid-cols-3">
        <StatCard
          icon={Users}
          label="Players"
          loading={stats.isLoading}
          value={formatNumber(o?.total_players ?? 0)}
        />
        <StatCard
          icon={Zap}
          label="Sessions"
          loading={stats.isLoading}
          value={formatNumber(o?.total_sessions ?? 0)}
        />
        <StatCard
          icon={Activity}
          label="Events"
          loading={stats.isLoading}
          value={formatNumber(o?.total_events ?? 0)}
        />
      </div>
      <Card>
        <CardHeader title="Game details" description={`Game ID: ${game.id}`} />
        <CardBody>
          <form
            onSubmit={handleSubmit((v) => save.mutate(v))}
            noValidate
            className="max-w-xl space-y-4"
          >
            <TextField label="Name" error={errors.name?.message} {...register('name')} />
            <TextField
              label="Genre (optional)"
              error={errors.genre?.message}
              {...register('genre')}
            />
            <TextAreaField
              label="Description (optional)"
              error={errors.description?.message}
              {...register('description')}
            />
            <Button type="submit" variant="primary" loading={save.isPending} disabled={!isDirty}>
              Save changes
            </Button>
          </form>
        </CardBody>
      </Card>
    </div>
  )
}
