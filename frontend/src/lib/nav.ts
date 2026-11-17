import {
  BookOpen,
  Gamepad2,
  LayoutDashboard,
  LineChart,
  Medal,
  Radio,
  Settings,
  Swords,
  TerminalSquare,
  Trophy,
  Users,
} from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

export interface NavItem {
  to: string
  label: string
  icon: LucideIcon
  /** Pages that are not built yet show a "Soon" badge instead of pretending to work. */
  built: boolean
  description: string
}

export const NAV_ITEMS: NavItem[] = [
  {
    to: '/',
    label: 'Overview',
    icon: LayoutDashboard,
    built: true,
    description: 'Live status of your game.',
  },
  {
    to: '/games',
    label: 'Games',
    icon: Gamepad2,
    built: true,
    description: 'Register games and manage API keys.',
  },
  {
    to: '/players',
    label: 'Players',
    icon: Users,
    built: true,
    description: 'Search players and open their profiles.',
  },
  {
    to: '/sessions',
    label: 'Sessions',
    icon: Swords,
    built: true,
    description: 'Active and completed game sessions.',
  },
  {
    to: '/leaderboards',
    label: 'Leaderboards',
    icon: Trophy,
    built: true,
    description: 'Rankings by score, wins and achievements.',
  },
  {
    to: '/achievements',
    label: 'Achievements',
    icon: Medal,
    built: true,
    description: 'Configure achievements and track unlocks.',
  },
  {
    to: '/live',
    label: 'Live Events',
    icon: Radio,
    built: true,
    description: 'Real-time feed of what your players are doing.',
  },
  {
    to: '/analytics',
    label: 'Analytics',
    icon: LineChart,
    built: true,
    description: 'Engagement trends, retention and score distributions.',
  },
  {
    to: '/playground',
    label: 'API Playground',
    icon: TerminalSquare,
    built: false,
    description: 'Try the game API against the real backend.',
  },
  {
    to: '/docs',
    label: 'Documentation',
    icon: BookOpen,
    built: false,
    description: 'Integration guides and API reference.',
  },
  {
    to: '/settings',
    label: 'Settings',
    icon: Settings,
    built: true,
    description: 'Appearance and account.',
  },
]

export function findNavItem(pathname: string): NavItem | undefined {
  if (pathname === '/') return NAV_ITEMS[0]
  return NAV_ITEMS.find((item) => item.to !== '/' && pathname.startsWith(item.to))
}
