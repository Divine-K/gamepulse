import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'
import { describeCondition } from '../../lib/conditions'
import { formatDuration, formatPercent, timeAgo } from '../../lib/format'
import { Segmented } from './Segmented'
import { StatCard, percentChange } from './StatCard'
import { Switch } from './Switch'
import { Users } from 'lucide-react'

describe('percentChange', () => {
  it('computes a fraction and refuses to invent a percentage from zero', () => {
    expect(percentChange(150, 100)).toBeCloseTo(0.5)
    expect(percentChange(50, 100)).toBeCloseTo(-0.5)
    expect(percentChange(5, 0)).toBeNull()
  })
})

describe('StatCard', () => {
  it('shows direction in text for screen readers and keeps the hint', () => {
    render(
      <StatCard
        icon={Users}
        label="Sessions"
        value="12"
        change={0.25}
        comparedTo="vs previous 7 days"
        hint="40 all time"
      />,
    )
    expect(screen.getByText('Up')).toHaveClass('sr-only')
    expect(screen.getByText('25%')).toBeInTheDocument()
    expect(screen.getByText('vs previous 7 days')).toBeInTheDocument()
    expect(screen.getByText('40 all time')).toBeInTheDocument()
  })

  it('shows no trend when there is no baseline', () => {
    render(<StatCard icon={Users} label="Sessions" value="12" change={null} hint="first week" />)
    expect(screen.queryByText(/%/)).not.toBeInTheDocument()
    expect(screen.getByText('first week')).toBeInTheDocument()
  })
})

describe('Segmented', () => {
  function Harness({ onChange }: { onChange: (v: string) => void }) {
    const [value, setValue] = useState('a')
    return (
      <Segmented
        label="Range"
        value={value}
        options={[
          { value: 'a', label: 'A' },
          { value: 'b', label: 'B' },
          { value: 'c', label: 'C' },
        ]}
        onChange={(v) => {
          setValue(v)
          onChange(v)
        }}
      />
    )
  }

  it('is a radio group that arrow keys move through', async () => {
    const onChange = vi.fn()
    render(<Harness onChange={onChange} />)
    const group = screen.getByRole('radiogroup', { name: 'Range' })
    expect(group).toBeInTheDocument()
    screen.getByRole('radio', { name: 'A' }).focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(onChange).toHaveBeenLastCalledWith('b')
    expect(screen.getByRole('radio', { name: 'B' })).toHaveAttribute('aria-checked', 'true')
    await userEvent.keyboard('{ArrowLeft}{ArrowLeft}')
    expect(onChange).toHaveBeenLastCalledWith('c') // wraps around
  })
})

describe('Switch', () => {
  it('has an accessible name and toggles', async () => {
    const onChange = vi.fn()
    render(<Switch checked={false} label="Enable thing" onChange={onChange} />)
    const toggle = screen.getByRole('switch', { name: 'Enable thing' })
    expect(toggle).toHaveAttribute('aria-checked', 'false')
    await userEvent.click(toggle)
    expect(onChange).toHaveBeenCalledWith(true)
  })
})

describe('formatting helpers', () => {
  it('formats durations, percentages and relative times', () => {
    expect(formatDuration(null)).toBe('–')
    expect(formatDuration(45)).toBe('45s')
    expect(formatDuration(125)).toBe('2m 5s')
    expect(formatDuration(3700)).toBe('1h 1m')
    expect(formatPercent(0.1234, 1)).toBe('12.3%')
    expect(formatPercent(null)).toBe('–')
    const now = Date.UTC(2026, 10, 17, 12, 0, 0)
    expect(timeAgo('2026-11-17T11:59:58Z', now)).toBe('just now')
    expect(timeAgo('2026-11-17T11:30:00Z', now)).toBe('30m ago')
    expect(timeAgo('2026-11-15T12:00:00Z', now)).toBe('2d ago')
    expect(timeAgo(null, now)).toBe('never')
  })

  it('describes achievement conditions in plain English', () => {
    expect(describeCondition('sessions_completed', 1)).toBe('Complete 1 session')
    expect(describeCondition('sessions_completed', 10)).toBe('Complete 10 sessions')
    expect(describeCondition('leaderboard_rank', 1)).toBe('Reach #1 on the leaderboard')
    expect(describeCondition('leaderboard_rank', 5)).toBe('Reach the top 5 on the leaderboard')
    expect(describeCondition('total_play_seconds', 3600)).toBe('Play for 1h 0m in total')
  })
})
