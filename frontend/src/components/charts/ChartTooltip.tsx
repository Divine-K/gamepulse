import { formatNumber } from '../../lib/format'

interface Row {
  name?: string | number
  value?: number | string | null
  color?: string
}

interface Props {
  active?: boolean
  label?: string | number
  payload?: Row[]
  labelFormatter?: (label: string) => string
  valueFormatter?: (value: number) => string
}

/**
 * Hover tooltip: label on top, one row per series with a colour key. Text stays in text
 * tokens; only the small key carries the series colour.
 */
export function ChartTooltip({ active, label, payload, labelFormatter, valueFormatter }: Props) {
  if (!active || !payload || payload.length === 0) return null
  const format = valueFormatter ?? formatNumber
  return (
    <div className="min-w-36 rounded-lg border border-line-strong bg-overlay px-3 py-2 text-sm shadow-pop">
      <p className="mb-1.5 text-xs font-medium text-muted">
        {labelFormatter ? labelFormatter(String(label)) : String(label)}
      </p>
      <ul className="space-y-1">
        {payload.map((row) => (
          <li key={String(row.name)} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-2 text-fg">
              <span aria-hidden className="size-2 rounded-full" style={{ background: row.color }} />
              {row.name}
            </span>
            <span className="font-medium text-fg tabular-nums">
              {typeof row.value === 'number' ? format(row.value) : '–'}
            </span>
          </li>
        ))}
      </ul>
    </div>
  )
}
