import { isVeneerError } from '@veneer/api'
import type { HistoryCommit } from '@veneer/api'

/** Said once when the open thing is a single loose file: it has no project, so no history. */
export const LOOSE_FILE_SENTENCE =
  'Versions are kept for projects. Open a folder as a project to save versions of its pages.'

/** One line, whitespace collapsed, cut with an ellipsis at `max` characters. */
export function shorten(text: string, max = 60): string {
  const line = text.replace(/\s+/g, ' ').trim()
  return line.length <= max ? line : `${line.slice(0, max - 1).trimEnd()}…`
}

/** The first line of a version's message, which is how a writer recognises it. */
export function versionTitle(commit: Pick<HistoryCommit, 'message'>): string {
  return commit.message.trim() === '' ? '(no description)' : commit.message.trim()
}

const MINUTE = 60_000
const HOUR = 60 * MINUTE
const DAY = 24 * HOUR

/**
 * When a version was made, in the words a writer uses: "just now", "5 minutes ago", "yesterday",
 * "4 days ago", then a date. `timeZone` is for tests; leave it out to use the writer's own.
 */
export function whenText(iso: string, now: Date = new Date(), timeZone?: string): string {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return ''
  const age = now.getTime() - then.getTime()
  if (age < MINUTE) return 'just now'
  if (age < HOUR) return plural(Math.floor(age / MINUTE), 'minute') + ' ago'
  if (age < DAY) return plural(Math.floor(age / HOUR), 'hour') + ' ago'
  if (age < 2 * DAY) return 'yesterday'
  if (age < 7 * DAY) return plural(Math.floor(age / DAY), 'day') + ' ago'
  return dateText(iso, timeZone)
}

/** A date that stays true when read later ("12 Oct 2026"), for text that is saved, not shown fresh. */
export function dateText(iso: string, timeZone?: string): string {
  const then = new Date(iso)
  if (Number.isNaN(then.getTime())) return ''
  return then.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', timeZone })
}

const plural = (n: number, unit: string): string => `${n} ${unit}${n === 1 ? '' : 's'}`

/** The second line of a version's row: who saved it and when. */
export function versionDetail(commit: Pick<HistoryCommit, 'author' | 'date'>, now?: Date, timeZone?: string): string {
  const when = whenText(commit.date, now, timeZone)
  return [commit.author.name, when].filter((part) => part !== '').join(' · ')
}

/**
 * A history failure as one plain sentence for `api.notify` (git's own words stay out of it).
 * `doing` finishes "Couldn't …" when the error has nothing better to say.
 */
export function explainError(err: unknown, doing: string): string {
  if (isVeneerError(err)) {
    switch (err.code) {
      case 'history/no-project':
        return LOOSE_FILE_SENTENCE
      case 'history/not-a-repository':
        return 'This project has no version history yet. Save a version to start one.'
      case 'history/uncommitted':
        return 'Your project has changes that are not in a version yet. Use “Save a Version”, then try again.'
      case 'history/exists':
        return 'That name is already in use. Choose another.'
      default:
        return shorten(err.message, 200)
    }
  }
  return `Couldn’t ${doing}.`
}
