import { ChartCard } from '../components/charts/ChartCard'
import { Columns } from '../components/charts/Columns'
import { TimeSeries } from '../components/charts/TimeSeries'
import { NoGame } from '../components/NoGame'
import { AchievementIcon } from '../components/AchievementIcon'
import { Card, CardBody, CardHeader } from '../components/ui/Card'
import { PageHeader } from '../components/ui/PageHeader'
import { ProgressBar } from '../components/ui/ProgressBar'
import { Segmented } from '../components/ui/Segmented'
import { Skeleton } from '../components/ui/Skeleton'
import { useGames } from '../context/GameContext'
import { useGameData } from '../hooks/useGameData'
import { useUrlState } from '../hooks/useUrlState'
import { formatDuration, formatNumber, formatPercent, formatShortDate } from '../lib/format'
import { analyticsApi } from '../services/endpoints'

const RANGES = [
  { value: '7', label: '7 days' },
  { value: '30', label: '30 days' },
  { value: '90', label: '90 days' },
]
const SOURCES = [
  { value: 'all', label: 'All data' },
  { value: 'real', label: 'Exclude simulated' },
]

export function AnalyticsPage() {
  const { game } = useGames()
  const [{ days: daysText, source }, update] = useUrlState({ days: '30', source: 'all' })
  const days = Number(daysText)
  const include = source === 'all'
  const query = { days, include_simulated: include }

  const engagement = useGameData(['analytics', 'engagement', days, include], (id, s) =>
    analyticsApi.engagement(id, query, s),
  )
  const retention = useGameData(['analytics', 'retention', include], (id, s) =>
    analyticsApi.retention(id, { include_simulated: include }, s),
  )
  const scores = useGameData(['analytics', 'scores', include], (id, s) =>
    analyticsApi.scores(id, { include_simulated: include }, s),
  )
  const ach = useGameData(['analytics', 'achievements', days, include], (id, s) =>
    analyticsApi.achievements(id, query, s),
  )

  if (!game)
    return (
      <>
        <PageHeader title="Analytics" />
        <NoGame what="Analytics" />
      </>
    )

  const points = engagement.data?.points ?? []
  const quiet = !points.some((p) => p.events > 0)
  const empty = quiet ? 'No activity in this period yet.' : undefined
  const asRows = points as unknown as { date: string }[]
  const retentionPoints = retention.data?.points ?? []
  const retentionData = retentionPoints.map((p) => ({
    day: `Day ${p.day}`,
    rate: p.rate === null ? null : Math.round(p.rate * 1000) / 10,
  }))
  const noRetention = retentionPoints.every((p) => p.rate === null)
  const buckets = scores.data?.buckets ?? []
  const scoreData = buckets.map((b) => ({
    range: b.start === b.end ? String(b.start) : `${b.start}–${b.end}`,
    count: b.count,
  }))

  return (
    <>
      <PageHeader
        title="Analytics"
        description="Calculated from your game’s real records. Switch off simulated data to see only what your players did."
        actions={
          <>
            <Segmented
              label="Date range"
              options={RANGES}
              value={daysText}
              onChange={(v) => update({ days: v })}
            />
            <Segmented
              label="Data source"
              options={SOURCES}
              value={source}
              onChange={(v) => update({ source: v })}
            />
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Player engagement"
          description="Active and new players per day (UTC)."
          loading={engagement.isLoading}
          emptyMessage={empty}
          legend={[
            { label: 'Active players', color: 'var(--series-1)' },
            { label: 'New players', color: 'var(--series-2)' },
          ]}
          table={{
            columns: ['Date', 'Active players', 'New players'],
            rows: points.map((p) => [formatShortDate(p.date), p.active_players, p.new_players]),
          }}
        >
          <TimeSeries
            data={asRows}
            series={[
              { key: 'active_players', label: 'Active players', color: 'var(--series-1)' },
              { key: 'new_players', label: 'New players', color: 'var(--series-2)' },
            ]}
          />
        </ChartCard>

        <ChartCard
          title="Sessions"
          description="Sessions started and completed per day."
          loading={engagement.isLoading}
          emptyMessage={empty}
          legend={[
            { label: 'Started', color: 'var(--series-1)' },
            { label: 'Completed', color: 'var(--series-3)' },
          ]}
          table={{
            columns: ['Date', 'Started', 'Completed'],
            rows: points.map((p) => [
              formatShortDate(p.date),
              p.sessions_started,
              p.sessions_completed,
            ]),
          }}
        >
          <Columns
            data={points as unknown as Record<string, number | string | null>[]}
            xKey="date"
            xFormatter={formatShortDate}
            series={[
              { key: 'sessions_started', label: 'Started', color: 'var(--series-1)' },
              { key: 'sessions_completed', label: 'Completed', color: 'var(--series-3)' },
            ]}
          />
        </ChartCard>

        <ChartCard
          title="Average session length"
          description="Completed sessions, by the day they ended."
          loading={engagement.isLoading}
          emptyMessage={
            points.some((p) => p.avg_session_duration_seconds !== null)
              ? undefined
              : 'No completed sessions in this period.'
          }
          table={{
            columns: ['Date', 'Average length'],
            rows: points.map((p) => [
              formatShortDate(p.date),
              formatDuration(p.avg_session_duration_seconds),
            ]),
          }}
        >
          <TimeSeries
            data={points.map((p) => ({ date: p.date, avg: p.avg_session_duration_seconds }))}
            series={[{ key: 'avg', label: 'Avg session length', color: 'var(--series-1)' }]}
            valueFormatter={formatDuration}
          />
        </ChartCard>

        <ChartCard
          title="Events"
          description="Everything recorded per day: sessions, scores, achievements and custom events."
          loading={engagement.isLoading}
          emptyMessage={empty}
          table={{
            columns: ['Date', 'Events'],
            rows: points.map((p) => [formatShortDate(p.date), p.events]),
          }}
        >
          <Columns
            data={points as unknown as Record<string, number | string | null>[]}
            xKey="date"
            xFormatter={formatShortDate}
            series={[{ key: 'events', label: 'Events', color: 'var(--series-1)' }]}
          />
        </ChartCard>

        <ChartCard
          title="Retention"
          description="Of players who registered at least N days ago, the share active exactly N days later."
          loading={retention.isLoading}
          emptyMessage={
            noRetention
              ? 'Not enough history yet. Day-1 retention appears once players are a day old.'
              : undefined
          }
          table={{
            columns: ['Day', 'Eligible players', 'Retained', 'Rate'],
            rows: retentionPoints.map((p) => [
              `Day ${p.day}`,
              p.eligible_players,
              p.retained_players,
              formatPercent(p.rate, 1),
            ]),
          }}
        >
          <Columns
            data={retentionData}
            xKey="day"
            yDomainMax={100}
            valueFormatter={(v) => `${v}%`}
            series={[{ key: 'rate', label: 'Retention', color: 'var(--series-1)' }]}
          />
        </ChartCard>

        <ChartCard
          title="Score distribution"
          description={
            scores.data && scores.data.completed_sessions > 0
              ? `Completed sessions · median ${formatNumber(Math.round(scores.data.median ?? 0))} · 90th percentile ${formatNumber(Math.round(scores.data.p90 ?? 0))}`
              : 'How session scores are spread.'
          }
          loading={scores.isLoading}
          emptyMessage={buckets.length === 0 ? 'No completed sessions yet.' : undefined}
          table={{
            columns: ['Score range', 'Sessions'],
            rows: scoreData.map((b) => [b.range, b.count]),
          }}
        >
          <Columns
            data={scoreData}
            xKey="range"
            series={[{ key: 'count', label: 'Sessions', color: 'var(--series-1)' }]}
          />
        </ChartCard>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Achievement unlocks"
          description="Unlocks per day."
          loading={ach.isLoading}
          emptyMessage={ach.data && ach.data.total_unlocks === 0 ? 'No unlocks yet.' : undefined}
          table={{
            columns: ['Date', 'Unlocks'],
            rows: (ach.data?.unlocks_by_day ?? []).map((d) => [formatShortDate(d.date), d.count]),
          }}
        >
          <Columns
            data={
              (ach.data?.unlocks_by_day ?? []) as unknown as Record<
                string,
                number | string | null
              >[]
            }
            xKey="date"
            xFormatter={formatShortDate}
            series={[{ key: 'count', label: 'Unlocks', color: 'var(--series-3)' }]}
          />
        </ChartCard>

        <Card>
          <CardHeader
            title="Unlock rate by achievement"
            description="Share of all players who have unlocked each one."
          />
          <CardBody>
            {ach.isLoading ? (
              <Skeleton className="h-40" />
            ) : (
              <ul className="space-y-3">
                {(ach.data?.achievements ?? []).map((a) => (
                  <li key={a.key}>
                    <div className="mb-1 flex items-center justify-between gap-2 text-sm">
                      <span className="flex items-center gap-2">
                        <AchievementIcon name={a.icon} className="size-4 text-muted" />
                        {a.name}
                        {!a.is_enabled && <span className="text-xs text-subtle">(disabled)</span>}
                      </span>
                      <span className="font-medium tabular-nums">
                        {formatPercent(a.unlock_rate)} · {formatNumber(a.unlock_count)}
                      </span>
                    </div>
                    <ProgressBar
                      value={a.unlock_rate}
                      label={`${a.name}: ${formatPercent(a.unlock_rate)} of players`}
                    />
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
    </>
  )
}
