import { Table2, BarChart3 } from 'lucide-react'
import { useId, useState } from 'react'
import type { ReactNode } from 'react'
import { Button } from '../ui/Button'
import { Card, CardBody } from '../ui/Card'
import { Skeleton } from '../ui/Skeleton'

export interface LegendItem {
  label: string
  color: string
}

export interface TableView {
  columns: string[]
  rows: (string | number)[][]
}

/**
 * Frame for a chart: title, legend (always shown for 2+ series), loading and empty states,
 * and a "table view" toggle so every value is available without relying on colour or hover.
 */
export function ChartCard({
  title,
  description,
  legend,
  table,
  loading,
  emptyMessage,
  height = 260,
  children,
}: {
  title: string
  description?: string
  legend?: LegendItem[]
  table: TableView
  loading?: boolean
  /** When set, shown instead of the chart (e.g. "No data in this period"). */
  emptyMessage?: string
  height?: number
  children: ReactNode
}) {
  const [showTable, setShowTable] = useState(false)
  const id = useId()
  return (
    <Card>
      <CardBody>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <h2 className="text-sm font-semibold text-fg">{title}</h2>
            {description && <p className="mt-1 text-sm text-muted">{description}</p>}
          </div>
          <Button
            size="sm"
            variant="ghost"
            aria-pressed={showTable}
            aria-controls={id}
            onClick={() => setShowTable((v) => !v)}
            icon={
              showTable ? (
                <BarChart3 aria-hidden className="size-4" />
              ) : (
                <Table2 aria-hidden className="size-4" />
              )
            }
          >
            {showTable ? 'Chart' : 'Table'}
          </Button>
        </div>

        {legend && legend.length > 1 && !showTable && (
          <ul
            className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted"
            aria-label="Legend"
          >
            {legend.map((item) => (
              <li key={item.label} className="flex items-center gap-2">
                <span
                  aria-hidden
                  className="h-0.5 w-4 rounded-full"
                  style={{ background: item.color }}
                />
                {item.label}
              </li>
            ))}
          </ul>
        )}

        <div id={id} className="mt-4">
          {loading ? (
            <Skeleton className="w-full" />
          ) : showTable ? (
            <div className="max-h-72 overflow-auto rounded-md border border-line">
              <table className="w-full text-sm">
                <caption className="sr-only">{title}</caption>
                <thead className="sticky top-0 bg-raised text-left text-xs text-muted">
                  <tr>
                    {table.columns.map((c) => (
                      <th key={c} scope="col" className="px-3 py-2 font-medium">
                        {c}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {table.rows.map((row, i) => (
                    <tr key={i}>
                      {row.map((cell, j) => (
                        <td key={j} className="px-3 py-1.5 tabular-nums">
                          {cell}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : emptyMessage ? (
            <div className="flex items-center justify-center text-sm text-muted" style={{ height }}>
              {emptyMessage}
            </div>
          ) : (
            <div
              style={{ height }}
              role="img"
              aria-label={`${title}. Use the Table button for exact values.`}
            >
              {children}
            </div>
          )}
        </div>
      </CardBody>
    </Card>
  )
}
