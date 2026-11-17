import { describe, expect, it } from 'vitest'
import { describeEvent } from './events'
import type { GameEvent } from '../types/api'

const base = { id: '1', game_id: 'g', ts: '', is_simulated: false }
const player = { id: 'p', external_id: 'x', username: 'ada' }

describe('describeEvent', () => {
  it('summarizes session end with score and result', () => {
    const event = {
      ...base,
      type: 'session.ended',
      data: { session: { id: 's', status: 'completed', result: 'win', score: 1500, player } },
    } as GameEvent
    expect(describeEvent(event)).toEqual({
      title: 'Session ended',
      detail: 'ada · score 1500 · win',
      tone: 'info',
    })
  })

  it('summarizes achievements and leaderboard moves', () => {
    const unlocked = describeEvent({
      ...base,
      type: 'achievement.unlocked',
      data: {
        player,
        achievement: { id: 'a', key: 'first_game', name: 'First Game', icon: 'play' },
      },
    })
    expect(unlocked.detail).toBe('ada · First Game')
    const board = describeEvent({
      ...base,
      type: 'leaderboard.updated',
      data: { player, rank: 2, metric: 'total_score' },
    })
    expect(board.detail).toBe('ada is now #2 on total_score')
  })
})
