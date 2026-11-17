import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ApiError } from '../../services/api'
import { gamesApi } from '../../services/endpoints'
import type { Game } from '../../types/api'
import { Button } from '../ui/Button'
import { Card, CardBody, CardHeader } from '../ui/Card'
import { TextField } from '../ui/Field'
import { Modal } from '../ui/Modal'
import { useToast } from '../ui/Toast'

export function DeletePanel({ game }: { game: Game }) {
  const [open, setOpen] = useState(false)
  const [typed, setTyped] = useState('')
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const toast = useToast()

  const remove = useMutation({
    mutationFn: () => gamesApi.remove(game.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['games'] })
      toast.success('Game deleted', `${game.name} and its API keys are gone.`)
      navigate('/games', { replace: true })
    },
    onError: (error) =>
      toast.error(
        'Could not delete the game',
        error instanceof ApiError ? error.message : 'Try again.',
      ),
  })

  const close = () => {
    setOpen(false)
    setTyped('')
  }

  return (
    <>
      <Card className="border-danger/40">
        <CardHeader
          title="Delete this game"
          description="Revokes all of its API keys and removes it from your dashboard."
        />
        <CardBody>
          <Button
            variant="danger"
            icon={<Trash2 aria-hidden className="size-4" />}
            onClick={() => setOpen(true)}
          >
            Delete game
          </Button>
        </CardBody>
      </Card>
      <Modal
        open={open}
        onClose={close}
        title={`Delete ${game.name}?`}
        description="Games using its API keys will immediately get 401 errors. This cannot be undone."
        footer={
          <>
            <Button onClick={close}>Cancel</Button>
            <Button
              variant="danger"
              disabled={typed !== game.name}
              loading={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Delete permanently
            </Button>
          </>
        }
      >
        <TextField
          label={`Type “${game.name}” to confirm`}
          value={typed}
          onChange={(e) => setTyped(e.target.value)}
          autoComplete="off"
        />
      </Modal>
    </>
  )
}
