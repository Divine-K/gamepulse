import { Clock, Crown, Flame, Gem, Medal, Play, Star, Target, Trophy, Zap } from 'lucide-react'
import type { LucideIcon } from 'lucide-react'

const ICONS: Record<string, LucideIcon> = {
  trophy: Trophy,
  play: Play,
  flame: Flame,
  target: Target,
  clock: Clock,
  medal: Medal,
  crown: Crown,
  gem: Gem,
  star: Star,
  zap: Zap,
}

export const ACHIEVEMENT_ICON_NAMES = Object.keys(ICONS)

export function AchievementIcon({ name, className }: { name: string; className?: string }) {
  const Icon = ICONS[name] ?? Trophy
  return <Icon aria-hidden className={className} />
}
