import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { maxOf, niceAxis } from '../../lib/chartAxis'
import { formatCompact } from '../../lib/format'
import { ChartTooltip } from './ChartTooltip'
import type { SeriesDef } from './TimeSeries'

/**
 * Column chart: capped 24px width, 4px rounded tops, square at the baseline, 2px gap
 * between neighbouring bars (bar gap) and between grouped bars.
 */
export function Columns<K extends string>({
  data,
  xKey,
  series,
  xFormatter,
  valueFormatter,
  yDomainMax,
  labelFormatter,
}: {
  data: Record<string, number | string | null>[]
  xKey: string
  series: SeriesDef<K>[]
  xFormatter?: (value: string) => string
  valueFormatter?: (value: number) => string
  yDomainMax?: number
  labelFormatter?: (value: string) => string
}) {
  const axis = yDomainMax
    ? { max: yDomainMax, ticks: [0, 1, 2, 3, 4].map((i) => (i * yDomainMax) / 4) }
    : niceAxis(
        maxOf(
          data,
          series.map((s) => s.key),
        ),
      )
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart
        data={data}
        margin={{ top: 8, right: 12, bottom: 0, left: 0 }}
        barCategoryGap="20%"
        barGap={2}
      >
        <CartesianGrid vertical={false} stroke="var(--line)" strokeWidth={1} />
        <XAxis
          dataKey={xKey}
          tickFormatter={xFormatter}
          tickLine={false}
          axisLine={{ stroke: 'var(--line-strong)' }}
          tick={{ fill: 'var(--subtle)', fontSize: 12 }}
          minTickGap={12}
        />
        <YAxis
          allowDecimals={false}
          tickLine={false}
          axisLine={false}
          width={44}
          domain={[0, axis.max]}
          ticks={axis.ticks}
          tickFormatter={valueFormatter ?? formatCompact}
          tick={{ fill: 'var(--subtle)', fontSize: 12 }}
        />
        <Tooltip
          cursor={{ fill: 'var(--raised)', fillOpacity: 0.6 }}
          content={
            <ChartTooltip
              labelFormatter={labelFormatter ?? xFormatter}
              valueFormatter={valueFormatter}
            />
          }
        />
        {series.map((s) => (
          <Bar
            key={s.key}
            dataKey={s.key}
            name={s.label}
            fill={s.color}
            maxBarSize={24}
            radius={[4, 4, 0, 0]}
            animationDuration={500}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
