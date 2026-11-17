/**
 * Round y-axis ticks: four equal steps from 0, where the step is 1, 2 or 5 times a power of 10
 * (for example a max of 1,950 gives 0 / 500 / 1,000 / 1,500 / 2,000 instead of 0 / 650 / 1.3K / 1.95K).
 */
export function niceAxis(maxValue: number): { max: number; ticks: number[] } {
  if (maxValue <= 0) return { max: 4, ticks: [0, 1, 2, 3, 4] }
  const target = maxValue / 4
  const magnitude = 10 ** Math.floor(Math.log10(target))
  const normalized = target / magnitude
  // Whole-number steps only: these axes show counts and scores.
  const nice = [1, 2, 2.5, 5, 10].find((candidate) => normalized <= candidate) ?? 10
  const step = Math.max(1, nice * magnitude)
  return { max: step * 4, ticks: [0, 1, 2, 3, 4].map((i) => i * step) }
}

/** Largest numeric value across the given keys of the rows (nulls ignored). */
export function maxOf(rows: Record<string, unknown>[], keys: string[]): number {
  let max = 0
  for (const row of rows) {
    for (const key of keys) {
      const value = row[key]
      if (typeof value === 'number' && value > max) max = value
    }
  }
  return max
}
