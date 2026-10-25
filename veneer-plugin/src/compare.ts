import { wordDiff } from '@veneer/api'
import type { DiffSegment, HistoryCommit, PluginApi } from '@veneer/api'
import { COMPARE_SURFACE, type HistoryFeature } from './history'
import { explainError, LOOSE_FILE_SENTENCE, shorten, versionTitle, whenText } from './words'

export const COMPARE_WITH_PAGE_COMMAND = 'gitwrite:compare-with-page'
export const COMPARE_VERSIONS_COMMAND = 'gitwrite:compare-versions'

const OPEN_A_PAGE = 'Open the page you want to compare, then try again.'
const NO_VERSIONS = 'There are no versions to compare yet. Save a version first.'

/** Gives each run of neighbouring changes one id, so a replaced word is accepted or rejected as one. */
export function withChangeIds(segments: readonly { kind: DiffSegment['kind']; text: string }[]): DiffSegment[] {
  const out: DiffSegment[] = []
  let run = 0
  let inRun = false
  for (const segment of segments) {
    if (segment.kind === 'equal') {
      inRun = false
      out.push({ kind: 'equal', text: segment.text })
    } else {
      if (!inRun) run += 1
      inRun = true
      out.push({ kind: segment.kind, text: segment.text, id: `c${run}` })
    }
  }
  return out
}

/** Neighbouring `equal` segments joined, empty ones dropped. */
function tidy(segments: DiffSegment[]): DiffSegment[] {
  const out: DiffSegment[] = []
  for (const segment of segments) {
    if (segment.text === '' && segment.kind !== 'equal') continue
    const last = out.at(-1)
    if (segment.kind === 'equal' && last?.kind === 'equal') last.text += segment.text
    else if (segment.text !== '' || segment.kind !== 'equal') out.push({ ...segment })
  }
  return out
}

/** The page's text as a diff of page → version describes it: every `equal` and `delete` segment. */
const pageTextOf = (segments: readonly DiffSegment[]): string =>
  segments.filter((s) => s.kind !== 'insert').map((s) => s.text).join('')

const hasChanges = (segments: readonly DiffSegment[]): boolean => segments.some((s) => s.kind !== 'equal')

interface Comparison {
  page: string
  title: string
  when: string
  versionText: string
  segments: DiffSegment[]
}

/**
 * Compare: a version against the open page, with Accept and Reject on each change, or two versions
 * of the open page side by side (read only). In "version vs page" the diff runs page → version: an
 * insertion is text the version has that the page lacks, so Accept puts it on the page and Reject
 * keeps the page's own words. The kernel changes nothing itself; each choice is one `editor.edit`
 * (one undo step) and a new view.
 */
export function registerCompare(api: PluginApi, history: HistoryFeature): void {
  let comparison: Comparison | null = null

  /** Whether a project with at least one version is open, saying why not if it is not. */
  async function ready(): Promise<boolean> {
    const { project, document } = api.workspace.current()
    if (project === null || project.kind !== 'project') {
      api.notify({ message: LOOSE_FILE_SENTENCE })
      return false
    }
    if (document === null) {
      api.notify({ message: OPEN_A_PAGE })
      return false
    }
    await history.refresh()
    if (history.versions().length === 0) {
      api.notify({ message: NO_VERSIONS })
      return false
    }
    return true
  }

  function note(c: Comparison, segments: readonly DiffSegment[]): string {
    if (!hasChanges(segments)) return `${c.page} matches “${c.title}”, ${c.when}.`
    return `${c.page} compared with “${c.title}”, ${c.when}. Accept puts a change on the page; Reject keeps the page as it is.`
  }

  function draw(c: Comparison): void {
    api.surfaces.setView(COMPARE_SURFACE, { kind: 'diff', note: note(c, c.segments), segments: c.segments })
  }

  async function compareWithPage(commit: HistoryCommit, page: string): Promise<void> {
    const current = api.editor.getText()
    if (current === null) {
      api.notify({ message: OPEN_A_PAGE })
      return
    }
    const versionText = await history.textAt(commit, page)
    if (versionText === null) return
    comparison = {
      page,
      title: shorten(versionTitle(commit), 50),
      when: whenText(commit.date, history.now()),
      versionText,
      segments: withChangeIds(wordDiff(current, versionText))
    }
    draw(comparison)
    api.surfaces.show(COMPARE_SURFACE)
  }

  async function compareTwo(a: HistoryCommit, b: HistoryCommit, page: string): Promise<void> {
    const order = history.versions()
    // The list is newest first, so the later position is the older version.
    const [older, newer] = order.findIndex((v) => v.id === a.id) > order.findIndex((v) => v.id === b.id) ? [a, b] : [b, a]
    const [before, after] = [await history.textAt(older, page), await history.textAt(newer, page)]
    if (before === null || after === null) return
    comparison = null // Nothing here can be accepted: there is no page to put a change on.
    const label = (c: HistoryCommit): string => `“${shorten(versionTitle(c), 40)}” (${whenText(c.date, history.now())})`
    api.surfaces.setView(COMPARE_SURFACE, {
      kind: 'diff',
      note: `${page}: changes from ${label(older)} to ${label(newer)}. Read only.`,
      segments: wordDiff(before, after)
    })
    api.surfaces.show(COMPARE_SURFACE)
  }

  api.commands.handle(COMPARE_WITH_PAGE_COMMAND, async () => {
    if (!(await ready())) return
    const page = api.workspace.current().document
    if (page === null) return
    await history.ask({
      note: 'Choose a version to compare with this page.',
      onPick: (commit) => compareWithPage(commit, page)
    })
  })

  api.commands.handle(COMPARE_VERSIONS_COMMAND, async () => {
    if (!(await ready())) return
    const page = api.workspace.current().document
    if (page === null) return
    const askSecond = (first: HistoryCommit): Promise<void> =>
      history.ask({
        note: `Now choose the other version to compare with “${shorten(versionTitle(first), 40)}”.`,
        onPick: (second) => {
          if (second.id === first.id) {
            api.notify({ message: 'Choose a different version to compare with.' })
            return askSecond(first)
          }
          return compareTwo(first, second, page)
        }
      })
    await history.ask({ note: 'Choose the first of the two versions to compare.', onPick: askSecond })
  })

  api.surfaces.onDiffAction(COMPARE_SURFACE, async (action, changeId) => {
    const c = comparison
    if (c === null) return // A read-only view has no changes to decide.
    if (api.workspace.current().document !== c.page) {
      api.notify({ message: `This comparison is for “${c.page}”. Open that page to accept or reject its changes.` })
      return
    }
    const pageNow = api.editor.getText()
    if (pageNow === null) return
    if (pageNow !== pageTextOf(c.segments)) {
      // The page changed after the comparison was drawn, so its positions no longer hold: start again.
      c.segments = withChangeIds(wordDiff(pageNow, c.versionText))
      draw(c)
      api.notify({ message: 'The page changed, so the comparison was redrawn. Choose again.' })
      return
    }

    const change = c.segments.filter((s) => s.id === changeId)
    if (change.length === 0) return
    const deleted = change.filter((s) => s.kind === 'delete').map((s) => s.text).join('')
    const inserted = change.filter((s) => s.kind === 'insert').map((s) => s.text).join('')

    let resolvedAs: string // what the page holds at this place once the writer has decided
    if (action === 'accept') {
      let from = 0
      for (const segment of c.segments) {
        if (segment.id === changeId) break
        if (segment.kind !== 'insert') from += segment.text.length
      }
      try {
        api.editor.edit({ from, to: from + deleted.length, text: inserted })
      } catch (err) {
        api.notify({ message: explainError(err, 'put that change on the page') })
        return
      }
      resolvedAs = inserted
    } else {
      resolvedAs = deleted
    }

    const first = c.segments.findIndex((s) => s.id === changeId)
    c.segments = tidy([
      ...c.segments.slice(0, first),
      { kind: 'equal', text: resolvedAs },
      ...c.segments.slice(first).filter((s) => s.id !== changeId)
    ])
    draw(c)
  })
}
