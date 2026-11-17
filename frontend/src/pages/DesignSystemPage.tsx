import { Plus, Radio, Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Badge } from '../components/ui/Badge'
import { Button } from '../components/ui/Button'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { TextAreaField, TextField } from '../components/ui/Field'
import { LiveDot } from '../components/ui/LiveDot'
import { ConfirmDialog, Modal } from '../components/ui/Modal'
import { PageHeader } from '../components/ui/PageHeader'
import { Skeleton } from '../components/ui/Skeleton'
import { Spinner } from '../components/ui/Spinner'
import { useToast } from '../components/ui/Toast'
import { Tooltip } from '../components/ui/Tooltip'

const COLORS = [
  ['canvas', 'bg-canvas'],
  ['surface', 'bg-surface'],
  ['raised', 'bg-raised'],
  ['overlay', 'bg-overlay'],
  ['line', 'bg-line'],
  ['accent', 'bg-accent'],
  ['violet', 'bg-violet'],
  ['success', 'bg-success'],
  ['warning', 'bg-warning'],
  ['danger', 'bg-danger'],
  ['info', 'bg-info'],
] as const

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="mb-8">
      <h2 className="mb-3 text-sm font-semibold tracking-wide text-muted uppercase">{title}</h2>
      {children}
    </section>
  )
}

export function DesignSystemPage() {
  const toast = useToast()
  const [modal, setModal] = useState(false)
  const [confirm, setConfirm] = useState(false)

  return (
    <>
      <PageHeader
        title="Design system"
        description="Tokens and components used across the dashboard. Everything here is themed through CSS variables, so it works in dark and light."
      />

      <Section title="Color tokens">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          {COLORS.map(([name, cls]) => (
            <div key={name} className="overflow-hidden rounded-lg border border-line">
              <div className={`h-14 ${cls}`} />
              <p className="bg-surface px-3 py-2 font-mono text-xs text-muted">{name}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Typography">
        <Card>
          <CardBody className="space-y-2">
            <p className="text-3xl font-semibold tracking-tight">Heading, Inter 30/600</p>
            <p className="text-base">
              Body text, Inter 16/400. Players, sessions and scores at a glance.
            </p>
            <p className="text-sm text-muted">Secondary text, 14px in the muted color.</p>
            <p className="font-mono text-sm text-accent-text">
              GET /api/v1/game/leaderboards/total_score
            </p>
          </CardBody>
        </Card>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button variant="primary" icon={<Plus aria-hidden className="size-4" />}>
            Primary
          </Button>
          <Button>Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="danger" icon={<Trash2 aria-hidden className="size-4" />}>
            Danger
          </Button>
          <Button variant="primary" loading>
            Loading
          </Button>
          <Button disabled>Disabled</Button>
          <Button variant="primary" size="sm">
            Small
          </Button>
          <Button variant="primary" size="lg">
            Large
          </Button>
        </div>
      </Section>

      <Section title="Badges and status">
        <div className="flex flex-wrap items-center gap-3">
          <Badge>Neutral</Badge>
          <Badge tone="accent">Accent</Badge>
          <Badge tone="success">Success</Badge>
          <Badge tone="warning">Warning</Badge>
          <Badge tone="danger">Danger</Badge>
          <Badge tone="info">Info</Badge>
          <span className="inline-flex items-center gap-2 text-sm">
            <LiveDot active /> Live
          </span>
          <span className="inline-flex items-center gap-2 text-sm">
            <LiveDot active={false} /> Offline
          </span>
          <Spinner label="Loading" className="size-5 text-accent" />
        </div>
      </Section>

      <Section title="Form fields">
        <Card>
          <CardBody className="grid gap-4 md:grid-cols-2">
            <TextField
              label="Default"
              placeholder="Type here"
              hint="Helper text explains the field."
            />
            <TextField label="With error" defaultValue="oops" error="This value is not allowed" />
            <TextField label="Disabled" disabled defaultValue="Read only" />
            <TextAreaField label="Text area" placeholder="Longer text" />
          </CardBody>
        </Card>
      </Section>

      <Section title="Feedback">
        <div className="flex flex-wrap gap-3">
          <Button onClick={() => toast.success('Saved', 'Your changes were saved.')}>
            Success toast
          </Button>
          <Button
            onClick={() => toast.error('Something failed', 'Check your connection and retry.')}
          >
            Error toast
          </Button>
          <Button onClick={() => toast.info('Heads up', 'New events are streaming in.')}>
            Info toast
          </Button>
          <Button onClick={() => setModal(true)}>Open modal</Button>
          <Button variant="danger" onClick={() => setConfirm(true)}>
            Confirm dialog
          </Button>
          <Tooltip label="Tooltips work on hover and keyboard focus">
            <Button>Hover or focus me</Button>
          </Tooltip>
        </div>
      </Section>

      <Section title="Loading and empty states">
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <CardHeader title="Skeleton" description="Shown while data loads." />
            <CardBody className="space-y-3">
              <Skeleton className="h-6 w-1/2" />
              <Skeleton className="h-4 w-full" />
              <Skeleton className="h-4 w-3/4" />
            </CardBody>
          </Card>
          <Card>
            <EmptyState
              icon={Radio}
              title="Nothing here yet"
              description="Empty states explain what will appear and how to get started."
            />
          </Card>
        </div>
      </Section>

      <Modal
        open={modal}
        onClose={() => setModal(false)}
        title="Example modal"
        description="Focus is trapped, Esc closes it, and clicking outside dismisses it."
        footer={
          <Button variant="primary" onClick={() => setModal(false)}>
            Got it
          </Button>
        }
      >
        <TextField label="Focusable field" placeholder="Tab cycles within the dialog" />
      </Modal>
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false)
          toast.success('Deleted', 'That was only a demo.')
        }}
        title="Delete this game?"
        description="This removes the game and revokes its API keys. This action cannot be undone."
        confirmLabel="Delete game"
        destructive
      />
    </>
  )
}
