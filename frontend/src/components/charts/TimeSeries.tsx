import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { maxOf, niceAxis } from '../../lib/chartAxis'
import { formatCompact, formatShortDate } from '../../lib/format'
import { ChartTooltip } from './ChartTooltip'

export interface SeriesDef<K extends string> {
  key: K
  label: string
  /** CSS variable such as var(--series-1) */
  color: string
}

type Row = { date: string } & Record<string, number | string | null>

/**
 * Daily time series. Marks follow the dataviz spec: 2px lines, ~10% area wash, hairline grid,
 * 8px end markers with a surface ring, crosshair + tooltip, one shared y-axis.
 */
export function TimeSeries<K extends string>({
  data,
  series,
  valueFormatter,
}: {
  data: Row[]
  series: SeriesDef<K>[]
  valueFormatter?: (value: number) => string
}) {
  const axis = niceAxis(
    maxOf(
      data,
      series.map((s) => s.key),
    ),
  )
  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
        <defs>
          {series.map((s) => (
            <linearGradient key={s.key} id={`wash-${s.key}`} x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor={s.color} stopOpacity={0.22} />
              <stop offset="100%" stopColor={s.color} stopOpacity={0} />
            </linearGradient>
          ))}
        </defs>
        <CartesianGrid vertical={false} stroke="var(--line)" strokeWidth={1} />
        <XAxis
          dataKey="date"
          tickFormatter={formatShortDate}
          tickLine={false}
          axisLine={{ stroke: 'var(--line-strong)' }}
          tick={{ fill: 'var(--subtle)', fontSize: 12 }}
          minTickGap={24}
        />
        <YAxis
          allowDecimals={false}
          domain={[0, axis.max]}
          ticks={axis.ticks}
          tickLine={false}
          axisLine={false}
          width={44}
          tickFormatter={formatCompact}
          tick={{ fill: 'var(--subtle)', fontSize: 12 }}
        />
        <Tooltip
          cursor={{ stroke: 'var(--line-strong)', strokeWidth: 1 }}
          content={
            <ChartTooltip labelFormatter={formatShortDate} valueFormatter={valueFormatter} />
          }
        />
        {series.map((s) => (
          <Area
            key={s.key}
            type="linear"
            dataKey={s.key}
            name={s.label}
            stroke={s.color}
            strokeWidth={2}
            strokeLinecap="round"
            strokeLinejoin="round"
            fill={`url(#wash-${s.key})`}
            dot={false}
            activeDot={{ r: 5, stroke: 'var(--surface)', strokeWidth: 2, fill: s.color }}
            isAnimationActive
            animationDuration={500}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  )
}
