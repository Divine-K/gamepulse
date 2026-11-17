import { Search } from 'lucide-react'
import { useEffect, useState } from 'react'

/** Search box that reports changes after a short pause, so typing doesn't spam the API. */
export function SearchInput({
  value,
  onChange,
  label,
  placeholder,
  delay = 300,
}: {
  value: string
  onChange: (value: string) => void
  label: string
  placeholder?: string
  delay?: number
}) {
  const [text, setText] = useState(value)
  // Keep the box in sync when the value changes from outside (e.g. browser back). Adjusting
  // state while rendering is React's recommended alternative to an effect for this.
  const [seenValue, setSeenValue] = useState(value)
  if (value !== seenValue) {
    setSeenValue(value)
    setText(value)
  }
  useEffect(() => {
    if (text === value) return
    const timer = window.setTimeout(() => onChange(text), delay)
    return () => window.clearTimeout(timer)
  }, [text, value, onChange, delay])

  return (
    <div className="relative">
      <Search
        aria-hidden
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-subtle"
      />
      <input
        type="search"
        aria-label={label}
        placeholder={placeholder}
        value={text}
        onChange={(event) => setText(event.target.value)}
        className="h-10 w-full rounded-md border border-line bg-canvas pr-3 pl-9 text-sm text-fg placeholder:text-subtle transition-colors hover:border-line-strong focus-visible:border-accent focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none sm:w-72"
      />
    </div>
  )
}
