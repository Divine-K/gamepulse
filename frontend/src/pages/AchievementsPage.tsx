import { zodResolver } from '@hookform/resolvers/zod'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Medal, Pencil, Plus } from 'lucide-react'
import { useState } from 'react'
import { Controller, useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'
import { AchievementIcon, ACHIEVEMENT_ICON_NAMES } from '../components/AchievementIcon'
import { NoGame } from '../components/NoGame'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { TextAreaField, TextField } from '../components/ui/Field'
import { Modal } from '../components/ui/Modal'
import { PageHeader } from '../components/ui/PageHeader'
import { ProgressBar } from '../components/ui/ProgressBar'
import { SelectField } from '../components/ui/Select'
import { Skeleton } from '../components/ui/Skeleton'
import { Switch } from '../components/ui/Switch'
import { useToast } from '../components/ui/Toast'
import { useGames } from '../context/GameContext'
import { useGameData } from '../hooks/useGameData'
import { CONDITION_OPTIONS, describeCondition } from '../lib/conditions'
import { formatNumber, formatPercent, timeAgo } from '../lib/format'
import { ApiError } from '../services/api'
import { achievementsApi } from '../services/endpoints'
import type { Achievement, ConditionType } from '../types/api'

const createSchema = z.object({
  key: z.string().regex(/^[a-z0-9_]{1,64}$/, 'Use lowercase letters, digits and underscores'),
  name: z.string().trim().min(1, 'Give it a name').max(100),
  description: z.string().trim().max(500).optional(),
  condition_type: z.enum([
    'sessions_completed',
    'score_reached',
    'total_play_seconds',
    'wins',
    'leaderboard_rank',
  ]),
  threshold: z.coerce
    .number()
    .int('Whole numbers only')
    .min(1, 'Must be at least 1')
    .max(2_000_000_000),
  icon: z.string(),
})
type CreateValues = z.input<typeof createSchema>

const editSchema = z.object({
  name: z.string().trim().min(1, 'Give it a name').max(100),
  description: z.string().trim().max(500).optional(),
  threshold: z.coerce
    .number()
    .int('Whole numbers only')
    .min(1, 'Must be at least 1')
    .max(2_000_000_000),
})
type EditValues = z.input<typeof editSchema>

export function AchievementsPage() {
  const { game } = useGames()
  const queryClient = useQueryClient()
  const toast = useToast()
  const [creating, setCreating] = useState(false)
  const [editing, setEditing] = useState<Achievement | null>(null)

  const list = useGameData(['achievements'], (id, signal) => achievementsApi.list(id, signal))
  const unlocks = useGameData(['unlocks', 'recent'], (id, signal) =>
    achievementsApi.unlocks(id, { limit: 8 }, signal),
  )

  const refresh = () => queryClient.invalidateQueries({ queryKey: ['game', game?.id] })
  const fail = (title: string) => (error: unknown) =>
    toast.error(title, error instanceof ApiError ? error.message : 'Try again.')

  const toggle = useMutation({
    mutationFn: ({ a, enabled }: { a: Achievement; enabled: boolean }) =>
      achievementsApi.update(game!.id, a.id, { is_enabled: enabled }),
    onSuccess: async (a) => {
      toast.success(
        a.is_enabled ? 'Achievement enabled' : 'Achievement disabled',
        a.is_enabled
          ? 'It can be awarded again.'
          : 'It will not be awarded until re-enabled. Existing unlocks are kept.',
      )
      await refresh()
    },
    onError: fail('Could not update the achievement'),
  })

  const createForm = useForm<CreateValues>({
    resolver: zodResolver(createSchema),
    defaultValues: { condition_type: 'sessions_completed', icon: 'trophy' },
  })
  const watchedCondition = useWatch({ control: createForm.control, name: 'condition_type' })
  const create = useMutation({
    mutationFn: (v: CreateValues) => {
      const parsed = createSchema.parse(v)
      return achievementsApi.create(game!.id, { ...parsed, description: parsed.description ?? '' })
    },
    onSuccess: async (a) => {
      toast.success('Achievement created', `${a.name} is live for new session results.`)
      setCreating(false)
      createForm.reset()
      await refresh()
    },
    onError: (error) => {
      if (error instanceof ApiError && error.code === 'achievement_key_taken')
        createForm.setError('key', { message: 'This key is already used' })
      else fail('Could not create the achievement')(error)
    },
  })

  const editForm = useForm<EditValues>({ resolver: zodResolver(editSchema) })
  const openEdit = (a: Achievement) => {
    editForm.reset({ name: a.name, description: a.description, threshold: a.threshold })
    setEditing(a)
  }
  const edit = useMutation({
    mutationFn: (v: EditValues) => {
      const parsed = editSchema.parse(v)
      return achievementsApi.update(game!.id, editing!.id, {
        name: parsed.name,
        description: parsed.description ?? '',
        threshold: parsed.threshold,
      })
    },
    onSuccess: async () => {
      toast.success(
        'Achievement updated',
        'New thresholds apply from each player’s next session end.',
      )
      setEditing(null)
      await refresh()
    },
    onError: fail('Could not save changes'),
  })

  if (!game)
    return (
      <>
        <PageHeader title="Achievements" />
        <NoGame what="Achievements" />
      </>
    )

  const unit = (type: ConditionType) => CONDITION_OPTIONS.find((o) => o.value === type)?.unit ?? ''

  return (
    <>
      <PageHeader
        title="Achievements"
        description="Awarded automatically when a session ends. Changes to a threshold apply from each player’s next session."
        actions={
          <Button
            variant="primary"
            icon={<Plus aria-hidden className="size-4" />}
            onClick={() => setCreating(true)}
          >
            New achievement
          </Button>
        }
      />

      {list.isLoading ? (
        <div aria-busy="true" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => (
            <Skeleton key={i} className="h-44" />
          ))}
        </div>
      ) : (list.data?.length ?? 0) === 0 ? (
        <Card>
          <EmptyState
            icon={Medal}
            title="No achievements yet"
            action={
              <Button variant="primary" onClick={() => setCreating(true)}>
                Create one
              </Button>
            }
          />
        </Card>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {list.data!.map((a) => (
            <li key={a.id}>
              <Card className={a.is_enabled ? undefined : 'opacity-70'}>
                <CardBody className="space-y-3">
                  <div className="flex items-start gap-3">
                    <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-accent-soft text-accent-text">
                      <AchievementIcon name={a.icon} className="size-5" />
                    </span>
                    <div className="min-w-0 flex-1">
                      <h2 className="truncate font-semibold">{a.name}</h2>
                      <p className="text-sm text-muted">
                        {describeCondition(a.condition_type, a.threshold)}
                      </p>
                    </div>
                    <Switch
                      checked={a.is_enabled}
                      label={`${a.is_enabled ? 'Disable' : 'Enable'} ${a.name}`}
                      onChange={(enabled) => toggle.mutate({ a, enabled })}
                      disabled={toggle.isPending}
                    />
                  </div>
                  {a.description && <p className="text-sm text-muted">{a.description}</p>}
                  <div>
                    <div className="mb-1.5 flex items-center justify-between text-xs">
                      <span className="text-muted">Unlocked by</span>
                      <span className="font-medium tabular-nums">
                        {formatNumber(a.unlock_count)} players · {formatPercent(a.unlock_rate)}
                      </span>
                    </div>
                    <ProgressBar
                      value={a.unlock_rate}
                      label={`${formatPercent(a.unlock_rate)} of players have unlocked ${a.name}`}
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Badge>
                      {a.threshold.toLocaleString()}{' '}
                      {a.threshold === 1
                        ? unit(a.condition_type).replace(/s$/, '')
                        : unit(a.condition_type)}
                    </Badge>
                    <Button
                      size="sm"
                      icon={<Pencil aria-hidden className="size-3.5" />}
                      onClick={() => openEdit(a)}
                      aria-label={`Edit ${a.name}`}
                    >
                      Edit
                    </Button>
                  </div>
                </CardBody>
              </Card>
            </li>
          ))}
        </ul>
      )}

      <Card className="mt-6">
        <CardHeader title="Recent unlocks" />
        <CardBody>
          {unlocks.isLoading ? (
            <Skeleton className="h-20" />
          ) : (unlocks.data?.items.length ?? 0) === 0 ? (
            <p className="py-4 text-center text-sm text-muted">Nothing unlocked yet.</p>
          ) : (
            <ul className="divide-y divide-line">
              {unlocks.data!.items.map((u) => (
                <li key={u.id} className="flex items-center gap-3 py-2.5 text-sm">
                  <AchievementIcon name={u.achievement.icon} className="size-4 text-accent-text" />
                  <span className="font-medium">{u.player.username}</span>
                  <span className="flex-1 text-muted">unlocked {u.achievement.name}</span>
                  <span className="text-xs text-subtle">{timeAgo(u.unlocked_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>

      <Modal
        open={creating}
        onClose={() => {
          setCreating(false)
          createForm.reset()
        }}
        title="New achievement"
        description="Choose what a player must do to earn it."
        footer={
          <>
            <Button
              onClick={() => {
                setCreating(false)
                createForm.reset()
              }}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              form="create-achievement"
              loading={create.isPending}
            >
              Create
            </Button>
          </>
        }
      >
        <form
          id="create-achievement"
          onSubmit={createForm.handleSubmit((v) => create.mutate(v))}
          noValidate
          className="space-y-4"
        >
          <TextField
            label="Name"
            placeholder="Big spender"
            error={createForm.formState.errors.name?.message}
            {...createForm.register('name')}
          />
          <TextField
            label="Key"
            placeholder="big_spender"
            hint="A stable id your game can reference. Cannot be changed later."
            error={createForm.formState.errors.key?.message}
            {...createForm.register('key')}
          />
          <TextAreaField
            label="Description (optional)"
            error={createForm.formState.errors.description?.message}
            {...createForm.register('description')}
          />
          <Controller
            control={createForm.control}
            name="condition_type"
            render={({ field }) => (
              <SelectField
                label="Condition"
                value={field.value}
                onChange={field.onChange}
                options={CONDITION_OPTIONS.map((o) => ({ value: o.value, label: o.label }))}
              />
            )}
          />
          <TextField
            label="Threshold"
            type="number"
            min={1}
            hint={`In ${unit(watchedCondition)}`}
            error={createForm.formState.errors.threshold?.message}
            {...createForm.register('threshold')}
          />
          <Controller
            control={createForm.control}
            name="icon"
            render={({ field }) => (
              <SelectField
                label="Icon"
                value={field.value}
                onChange={field.onChange}
                options={ACHIEVEMENT_ICON_NAMES.map((n) => ({ value: n, label: n }))}
              />
            )}
          />
        </form>
      </Modal>

      <Modal
        open={editing !== null}
        onClose={() => setEditing(null)}
        title={`Edit ${editing?.name ?? ''}`}
        description={
          editing
            ? `${describeCondition(editing.condition_type, editing.threshold)}. The condition type is fixed after creation.`
            : undefined
        }
        footer={
          <>
            <Button onClick={() => setEditing(null)}>Cancel</Button>
            <Button
              variant="primary"
              type="submit"
              form="edit-achievement"
              loading={edit.isPending}
            >
              Save
            </Button>
          </>
        }
      >
        <form
          id="edit-achievement"
          onSubmit={editForm.handleSubmit((v) => edit.mutate(v))}
          noValidate
          className="space-y-4"
        >
          <TextField
            label="Name"
            error={editForm.formState.errors.name?.message}
            {...editForm.register('name')}
          />
          <TextAreaField
            label="Description"
            error={editForm.formState.errors.description?.message}
            {...editForm.register('description')}
          />
          <TextField
            label="Threshold"
            type="number"
            min={1}
            hint={editing ? `In ${unit(editing.condition_type)}` : undefined}
            error={editForm.formState.errors.threshold?.message}
            {...editForm.register('threshold')}
          />
        </form>
      </Modal>
    </>
  )
}
