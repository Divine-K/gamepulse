import { describe, expect, it } from 'vitest'
import { maxOf, niceAxis } from './chartAxis'

describe('niceAxis', () => {
  it.each([
    [1950, [0, 500, 1000, 1500, 2000]],
    [8, [0, 2, 4, 6, 8]],
    [3, [0, 1, 2, 3, 4]],
    [23, [0, 10, 20, 30, 40]],
    [100, [0, 25, 50, 75, 100]],
    [0, [0, 1, 2, 3, 4]],
  ])('picks round ticks for a maximum of %i', (max, ticks) => {
    expect(niceAxis(max).ticks).toEqual(ticks)
  })

  it('always covers the data', () => {
    for (const max of [1, 7, 13, 99, 480, 2557, 40_000, 123_456]) {
      expect(niceAxis(max).max).toBeGreaterThanOrEqual(max)
    }
  })
})

describe('maxOf', () => {
  it('finds the largest value and ignores nulls and other keys', () => {
    expect(
      maxOf(
        [
          { a: 3, b: null, c: 99 },
          { a: 7, b: 5 },
        ],
        ['a', 'b'],
      ),
    ).toBe(7)
    expect(maxOf([], ['a'])).toBe(0)
  })
})
