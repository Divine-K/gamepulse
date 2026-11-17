import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

/**
 * Page state kept in the URL (search, sort, page, filters): shareable, survives a refresh and
 * works with the back button. Values equal to their default are omitted from the URL.
 */
export function useUrlState<T extends Record<string, string>>(defaults: T) {
  const [params, setParams] = useSearchParams()
  const state = Object.fromEntries(
    Object.keys(defaults).map((key) => [key, params.get(key) ?? defaults[key]]),
  ) as T

  const update = useCallback(
    (patch: Partial<T>) => {
      setParams(
        (current) => {
          const next = new URLSearchParams(current)
          for (const [key, value] of Object.entries(patch)) {
            if (value === undefined || value === defaults[key]) next.delete(key)
            else next.set(key, value)
          }
          return next
        },
        { replace: true },
      )
    },
    // defaults are constant per page
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [setParams],
  )
  return [state, update] as const
}
