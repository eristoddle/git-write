import { describe, expect, it } from 'vitest'
import { veneerError } from '@veneer/api'
import { dateText, explainError, LOOSE_FILE_SENTENCE, shorten, versionDetail, versionTitle, whenText } from './words'

const now = new Date('2026-10-25T12:00:00Z')
const ago = (ms: number): string => new Date(now.getTime() - ms).toISOString()
const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR

describe('whenText', () => {
  it.each([
    [30_000, 'just now'],
    [MIN, '1 minute ago'],
    [5 * MIN, '5 minutes ago'],
    [HOUR, '1 hour ago'],
    [23 * HOUR, '23 hours ago'],
    [DAY, 'yesterday'],
    [47 * HOUR, 'yesterday'],
    [2 * DAY, '2 days ago'],
    [6 * DAY + 23 * HOUR, '6 days ago']
  ])('%d ms ago reads %s', (age, expected) => {
    expect(whenText(ago(age), now, 'UTC')).toBe(expected)
  })

  it('gives a date once it is a week old or more', () => {
    expect(whenText('2026-10-02T09:00:00Z', now, 'UTC')).toBe('2 Oct 2026')
    expect(whenText('2025-01-15T09:00:00Z', now, 'UTC')).toBe('15 Jan 2025')
  })

  it('says nothing for a date it cannot read', () => {
    expect(whenText('not a date', now)).toBe('')
  })
})

describe('dateText', () => {
  it('is a plain date that does not change as time passes', () => {
    expect(dateText('2026-10-02T09:00:00Z', 'UTC')).toBe('2 Oct 2026')
    expect(dateText('nope')).toBe('')
  })
})

describe('versions in a list', () => {
  const commit = { message: 'Finished chapter two', author: { name: 'Mara', email: 'm@x.org' }, date: ago(3 * HOUR) }

  it('shows who and when', () => {
    expect(versionDetail(commit, now, 'UTC')).toBe('Mara · 3 hours ago')
  })

  it('drops a time it cannot read rather than printing nonsense', () => {
    expect(versionDetail({ ...commit, date: 'x' }, now)).toBe('Mara')
  })

  it('titles an empty message instead of leaving a blank row', () => {
    expect(versionTitle(commit)).toBe('Finished chapter two')
    expect(versionTitle({ message: '  ' })).toBe('(no description)')
  })
})

describe('shorten', () => {
  it('collapses whitespace and cuts long text with an ellipsis', () => {
    expect(shorten('  a\n\n b   c ')).toBe('a b c')
    expect(shorten('x'.repeat(100), 10)).toBe('xxxxxxxxx…')
    expect(shorten('short', 10)).toBe('short')
  })
})

describe('explainError', () => {
  it('says why a loose file has no versions', () => {
    expect(explainError(veneerError('history/no-project', 'A loose file is open.'), 'save')).toBe(LOOSE_FILE_SENTENCE)
  })

  it('says a project has no history yet in plain words', () => {
    const sentence = explainError(veneerError('history/not-a-repository', 'x'), 'save')
    expect(sentence).toBe('This project has no version history yet. Save a version to start one.')
  })

  it('passes on the host\'s own plain sentence for other failures, kept to one short line', () => {
    expect(explainError(veneerError('history/not-found', "That file isn't in that save point."), 'x')).toBe(
      "That file isn't in that save point."
    )
    expect(explainError(veneerError('history/failed', 'a\n' + 'b'.repeat(400)), 'x').length).toBeLessThanOrEqual(200)
  })

  it('falls back to a generic sentence for anything else, never leaking an error object', () => {
    expect(explainError(new Error('ENOENT /secret/path'), 'save that version')).toBe("Couldn't save that version.")
    expect(explainError('boom', 'save that version')).toBe("Couldn't save that version.")
  })
})
