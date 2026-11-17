import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { KeyRound, Plus, RefreshCw, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { formatDateTime, timeAgo } from '../../lib/format'
import { ApiError } from '../../services/api'
import { keysApi } from '../../services/endpoints'
import type { ApiKey } from '../../types/api'
import { Badge } from '../ui/Badge'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { DataTable } from '../ui/DataTable'
import { EmptyState } from '../ui/EmptyState'
import { TextField } from '../ui/Field'
import { ConfirmDialog, Modal } from '../ui/Modal'
import { useToast } from '../ui/Toast'
import { SecretKeyModal } from './SecretKeyModal'

export function KeysPanel({ gameId }: { gameId: string }) {
  const queryClient = useQueryClient()
  const toast = useToast()
  const [creating, setCreating] = useState(false)
  const [name, setName] = useState('')
  const [secret, setSecret] = useState<{ key: string; name: string } | null>(null)
  const [rotating, setRotating] = useState<ApiKey | null>(null)
  const [revoking, setRevoking] = useState<ApiKey | null>(null)

  const keys = useQuery({
    queryKey: ['keys', gameId],
    queryFn: ({ signal }) => keysApi.list(gameId, signal),
  })
  const refresh = () => queryClient.invalidateQueries({ queryKey: ['keys', gameId] })
  const fail = (title: string) => (error: unknown) =>
    toast.error(title, error instanceof ApiError ? error.message : 'Try again.')

  const create = useMutation({
    mutationFn: () => keysApi.create(gameId, name.trim() || 'Default'),
    onSuccess: async (created) => {
      setCreating(false)
      setName('')
      setSecret({ key: created.key, name: created.name })
      await refresh()
    },
    onError: fail('Could not create the key'),
  })
  const rotate = useMutation({
    mutationFn: (key: ApiKey) => keysApi.rotate(gameId, key.id),
    onSuccess: async (created) => {
      setRotating(null)
      setSecret({ key: created.key, name: created.name })
      await refresh()
    },
    onError: fail('Could not rotate the key'),
  })
  const revoke = useMutation({
    mutationFn: (key: ApiKey) => keysApi.revoke(gameId, key.id),
    onSuccess: async () => {
      setRevoking(null)
      toast.success('Key revoked', 'Requests using it now fail with 401.')
      await refresh()
    },
    onError: fail('Could not revoke the key'),
  })

  const rows = keys.data

  return (
    <>
      <div className="mb-4 flex items-center justify-between gap-4">
        <p className="max-w-xl text-sm text-muted">
          API keys let your game talk to GamePulse. Each key belongs to this game only. Rotate a key
          to replace it, or revoke it to cut off access immediately.
        </p>
        <Button
          variant="primary"
          icon={<Plus aria-hidden className="size-4" />}
          onClick={() => setCreating(true)}
        >
          New key
        </Button>
      </div>

      <Card>
        <DataTable
          caption="API keys"
          loading={keys.isLoading}
          rows={rows}
          rowKey={(k) => k.id}
          empty={
            <EmptyState
              icon={KeyRound}
              title="No API keys yet"
              description="Create a key, then follow the Integration tab to send your first request."
              action={
                <Button variant="primary" onClick={() => setCreating(true)}>
                  Create a key
                </Button>
              }
            />
          }
          columns={[
            {
              key: 'name',
              header: 'Name',
              cell: (k) => <span className="font-medium">{k.name}</span>,
            },
            {
              key: 'prefix',
              header: 'Key',
              cell: (k) => (
                <code className="font-mono text-xs text-muted">gp_{k.key_prefix}_••••••••</code>
              ),
            },
            { key: 'created', header: 'Created', cell: (k) => formatDateTime(k.created_at) },
            {
              key: 'used',
              header: 'Last used',
              cell: (k) => (k.last_used_at ? timeAgo(k.last_used_at) : 'Never'),
            },
            {
              key: 'status',
              header: 'Status',
              cell: (k) =>
                k.revoked_at ? (
                  <Badge tone="danger">Revoked</Badge>
                ) : (
                  <Badge tone="success">Active</Badge>
                ),
            },
            {
              key: 'actions',
              header: 'Actions',
              align: 'right',
              cell: (k) =>
                k.revoked_at ? null : (
                  <div className="flex justify-end gap-2">
                    <Button
                      size="sm"
                      icon={<RefreshCw aria-hidden className="size-3.5" />}
                      onClick={() => setRotating(k)}
                      aria-label={`Rotate key ${k.name}`}
                    >
                      Rotate
                    </Button>
                    <Button
                      size="sm"
                      variant="danger"
                      icon={<Trash2 aria-hidden className="size-3.5" />}
                      onClick={() => setRevoking(k)}
                      aria-label={`Revoke key ${k.name}`}
                    >
                      Revoke
                    </Button>
                  </div>
                ),
            },
          ]}
        />
      </Card>

      <Modal
        open={creating}
        onClose={() => setCreating(false)}
        title="Create an API key"
        description="Give it a name so you can tell keys apart (for example “Production server”)."
        footer={
          <>
            <Button onClick={() => setCreating(false)}>Cancel</Button>
            <Button variant="primary" loading={create.isPending} onClick={() => create.mutate()}>
              Create key
            </Button>
          </>
        }
      >
        <TextField
          label="Key name"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Production server"
          maxLength={100}
        />
      </Modal>

      <SecretKeyModal
        secret={secret?.key ?? null}
        name={secret?.name ?? ''}
        onClose={() => setSecret(null)}
      />

      <ConfirmDialog
        open={rotating !== null}
        onClose={() => setRotating(null)}
        onConfirm={() => rotating && rotate.mutate(rotating)}
        loading={rotate.isPending}
        title="Rotate this key?"
        description="The current key stops working immediately and you get a replacement. Update your game before rotating, or requests will fail until you do."
        confirmLabel="Rotate key"
      />
      <ConfirmDialog
        open={revoking !== null}
        onClose={() => setRevoking(null)}
        onConfirm={() => revoking && revoke.mutate(revoking)}
        loading={revoke.isPending}
        title="Revoke this key?"
        description="Any game using this key will immediately get 401 errors. This cannot be undone."
        confirmLabel="Revoke key"
        destructive
      />
    </>
  )
}
