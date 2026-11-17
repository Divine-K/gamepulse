import { Check, Copy } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Button } from './Button'

/** Copies `text` to the clipboard and confirms with a brief "Copied" state. */
export function CopyButton({
  text,
  label = 'Copy',
  size = 'sm',
}: {
  text: string
  label?: string
  size?: 'sm' | 'md'
}) {
  const [copied, setCopied] = useState(false)
  const timer = useRef<number | undefined>(undefined)
  useEffect(() => () => window.clearTimeout(timer.current), [])

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      window.clearTimeout(timer.current)
      timer.current = window.setTimeout(() => setCopied(false), 1800)
    } catch {
      /* clipboard blocked: the text stays selectable in the code block */
    }
  }

  return (
    <Button
      size={size}
      onClick={copy}
      aria-label={copied ? 'Copied to clipboard' : `${label} to clipboard`}
      icon={
        copied ? (
          <Check aria-hidden className="size-4 text-success" />
        ) : (
          <Copy aria-hidden className="size-4" />
        )
      }
    >
      {copied ? 'Copied' : label}
    </Button>
  )
}
