import { Activity } from 'lucide-react'
import type { ReactNode } from 'react'

export function AuthLayout({
  title,
  subtitle,
  children,
}: {
  title: string
  subtitle: string
  children: ReactNode
}) {
  return (
    <div className="grid min-h-dvh lg:grid-cols-2">
      <div className="relative hidden flex-col justify-between overflow-hidden border-r border-line bg-surface p-12 lg:flex">
        <div
          aria-hidden
          className="absolute -top-32 -left-32 size-96 rounded-full bg-accent/10 blur-3xl"
        />
        <div
          aria-hidden
          className="absolute right-0 -bottom-32 size-96 rounded-full bg-violet/10 blur-3xl"
        />
        <div className="relative flex items-center gap-2">
          <span className="flex size-9 items-center justify-center rounded-lg bg-accent text-accent-fg">
            <Activity aria-hidden className="size-5" strokeWidth={2.5} />
          </span>
          <span className="text-lg font-semibold tracking-tight">GamePulse</span>
        </div>
        <div className="relative space-y-4">
          <p className="max-w-md text-3xl leading-tight font-semibold tracking-tight">
            The backend behind your game.
          </p>
          <p className="max-w-md text-muted">
            Players, sessions, leaderboards, achievements and live analytics, through one API.
            Connect a game in minutes and watch it run in real time.
          </p>
        </div>
        <p className="relative text-xs text-subtle">Game backend &amp; analytics platform</p>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-sm">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 mb-8 text-sm text-muted">{subtitle}</p>
          {children}
        </div>
      </div>
    </div>
  )
}
