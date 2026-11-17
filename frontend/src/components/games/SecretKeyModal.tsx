import { ShieldAlert } from 'lucide-react'
import { Button } from '../ui/Button'
import { CodeBlock } from '../ui/CodeBlock'
import { Modal } from '../ui/Modal'

/** Shown once after a key is created or rotated: the full secret is never retrievable again. */
export function SecretKeyModal({
  secret,
  name,
  onClose,
}: {
  secret: string | null
  name: string
  onClose: () => void
}) {
  return (
    <Modal
      open={secret !== null}
      onClose={onClose}
      title="Copy your API key"
      description={`Key "${name}" is ready.`}
      footer={
        <Button variant="primary" onClick={onClose}>
          I have saved it
        </Button>
      }
    >
      <div className="space-y-4">
        <div className="flex gap-3 rounded-md border border-warning/40 bg-warning-soft p-3 text-sm text-fg">
          <ShieldAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-warning" />
          <p>
            This is the only time the full key is shown. GamePulse stores only a hash, so it cannot
            be recovered. If you lose it, rotate the key.
          </p>
        </div>
        {secret && <CodeBlock title="API key" code={secret} />}
      </div>
    </Modal>
  )
}
