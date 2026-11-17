import { Check, ChevronDown, LogOut, Menu as MenuIcon, Moon, Plus, Sun, User } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Button } from '../components/ui/Button'
import { LiveDot } from '../components/ui/LiveDot'
import { Menu } from '../components/ui/Menu'
import type { MenuItem } from '../components/ui/Menu'
import { Tooltip } from '../components/ui/Tooltip'
import { useAuth } from '../context/AuthContext'
import { useGames } from '../context/GameContext'
import { useStream } from '../context/StreamContext'
import { useTheme } from '../context/ThemeContext'
import { cn } from '../lib/cn'
import { Breadcrumbs } from './Breadcrumbs'

const STREAM_LABEL = {
  idle: 'Offline',
  connecting: 'Connecting',
  live: 'Live',
  reconnecting: 'Reconnecting',
  failed: 'Disconnected',
  closed: 'Offline',
} as const

export function Topbar({ onOpenMobileNav }: { onOpenMobileNav: () => void }) {
  const { user, logout } = useAuth()
  const { games, game, selectGame } = useGames()
  const { status } = useStream()
  const { theme, toggle } = useTheme()
  const navigate = useNavigate()

  const gameItems: MenuItem[] = games.map((g) => ({
    id: g.id,
    label: g.name,
    selected: g.id === game?.id,
    icon:
      g.id === game?.id ? <Check aria-hidden className="size-4" /> : <span className="size-4" />,
    onSelect: () => selectGame(g.id),
  }))

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center gap-3 border-b border-line bg-canvas/80 px-4 backdrop-blur lg:px-6">
      <Button
        variant="ghost"
        size="sm"
        className="lg:hidden"
        aria-label="Open navigation"
        onClick={onOpenMobileNav}
      >
        <MenuIcon aria-hidden className="size-5" />
      </Button>

      <div className="hidden min-w-0 flex-1 md:block">
        <Breadcrumbs />
      </div>
      <div className="flex-1 md:hidden" />

      {/* Game selector */}
      {games.length > 0 ? (
        <Menu
          label="Select game"
          items={gameItems}
          align="right"
          footer={
            <button
              type="button"
              onClick={() => navigate('/games')}
              className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-left text-sm text-muted transition-colors hover:bg-raised hover:text-fg"
            >
              <Plus aria-hidden className="size-4" /> Manage games
            </button>
          }
          trigger={(props) => (
            <Button {...props} size="sm" className="max-w-48">
              <span className="truncate">{game?.name}</span>
              <ChevronDown aria-hidden className="size-4 shrink-0 text-muted" />
            </Button>
          )}
        />
      ) : (
        <Button
          size="sm"
          variant="primary"
          icon={<Plus aria-hidden className="size-4" />}
          onClick={() => navigate('/games')}
        >
          Create a game
        </Button>
      )}

      {/* Live connection status */}
      <Tooltip label="Real-time connection to your game">
        <span
          role="status"
          className={cn(
            'hidden items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium sm:inline-flex',
            status === 'live' ? 'border-success/40 text-success' : 'border-line text-muted',
          )}
        >
          <LiveDot active={status === 'live'} />
          {STREAM_LABEL[status]}
        </span>
      </Tooltip>

      <Button
        variant="ghost"
        size="sm"
        onClick={toggle}
        aria-label={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
      >
        {theme === 'dark' ? (
          <Sun aria-hidden className="size-[18px]" />
        ) : (
          <Moon aria-hidden className="size-[18px]" />
        )}
      </Button>

      <Menu
        label="Account"
        align="right"
        items={[
          {
            id: 'name',
            label: user?.display_name ?? 'Account',
            icon: <User aria-hidden className="size-4" />,
            onSelect: () => navigate('/settings'),
          },
          {
            id: 'logout',
            label: 'Log out',
            icon: <LogOut aria-hidden className="size-4" />,
            danger: true,
            onSelect: logout,
          },
        ]}
        trigger={(props) => (
          <Button {...props} variant="ghost" size="sm" aria-label="Account menu">
            <span className="flex size-7 items-center justify-center rounded-full bg-accent-soft text-xs font-semibold text-accent-text">
              {(user?.display_name ?? '?').slice(0, 1).toUpperCase()}
            </span>
          </Button>
        )}
      />
    </header>
  )
}
