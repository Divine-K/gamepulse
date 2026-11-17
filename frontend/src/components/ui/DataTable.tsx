import { ArrowDown, ArrowUp, ChevronsUpDown } from 'lucide-react'
import type { ReactNode } from 'react'
import { cn } from '../../lib/cn'
import { Skeleton } from './Skeleton'

export interface Column<T> {
  key: string
  header: string
  cell: (row: T) => ReactNode
  /** Sort key sent to the API; omit for columns that are not sortable. */
  sortKey?: string
  align?: 'left' | 'right'
  className?: string
}

export interface SortState {
  key: string
  descending: boolean
}

interface DataTableProps<T> {
  caption: string
  columns: Column<T>[]
  rows: T[] | undefined
  rowKey: (row: T) => string
  loading?: boolean
  sort?: SortState
  onSortChange?: (sort: SortState) => void
  /** Rendered instead of the table body when there are no rows. */
  empty?: ReactNode
  skeletonRows?: number
}

/** Data table with sortable headers (aria-sort), loading skeleton and an empty slot. */
export function DataTable<T>({
  caption,
  columns,
  rows,
  rowKey,
  loading,
  sort,
  onSortChange,
  empty,
  skeletonRows = 6,
}: DataTableProps<T>) {
  const toggle = (sortKey: string) => {
    if (!onSortChange) return
    onSortChange(
      sort?.key === sortKey
        ? { key: sortKey, descending: !sort.descending }
        : { key: sortKey, descending: true },
    )
  }

  if (!loading && rows && rows.length === 0 && empty) return <>{empty}</>

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-sm" aria-busy={loading || undefined}>
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr className="border-b border-line text-left text-xs tracking-wide text-muted uppercase">
            {columns.map((column) => {
              const sorted = column.sortKey && sort?.key === column.sortKey
              return (
                <th
                  key={column.key}
                  scope="col"
                  aria-sort={sorted ? (sort.descending ? 'descending' : 'ascending') : undefined}
                  className={cn('px-5 py-3 font-medium', column.align === 'right' && 'text-right')}
                >
                  {column.sortKey && onSortChange ? (
                    <button
                      type="button"
                      onClick={() => toggle(column.sortKey!)}
                      className={cn(
                        'inline-flex items-center gap-1 uppercase transition-colors hover:text-fg',
                        sorted && 'text-fg',
                      )}
                    >
                      {column.header}
                      {sorted ? (
                        sort.descending ? (
                          <ArrowDown aria-hidden className="size-3" />
                        ) : (
                          <ArrowUp aria-hidden className="size-3" />
                        )
                      ) : (
                        <ChevronsUpDown aria-hidden className="size-3 opacity-50" />
                      )}
                    </button>
                  ) : (
                    column.header
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody className="divide-y divide-line">
          {loading || !rows
            ? Array.from({ length: skeletonRows }, (_, i) => (
                <tr key={i}>
                  {columns.map((column) => (
                    <td key={column.key} className="px-5 py-3.5">
                      <Skeleton className="h-4 w-full max-w-32" />
                    </td>
                  ))}
                </tr>
              ))
            : rows.map((row) => (
                <tr key={rowKey(row)} className="transition-colors hover:bg-raised/60">
                  {columns.map((column) => (
                    <td
                      key={column.key}
                      className={cn(
                        'px-5 py-3.5 text-fg',
                        column.align === 'right' && 'text-right tabular-nums',
                        column.className,
                      )}
                    >
                      {column.cell(row)}
                    </td>
                  ))}
                </tr>
              ))}
        </tbody>
      </table>
    </div>
  )
}
