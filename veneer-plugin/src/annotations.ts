import { MAX_HISTORY_LOG } from '@veneer/api'
import type { ItemsView, Mark, PluginApi } from '@veneer/api'
import { readAnnotations, statusMessage, type Annotation, type Status } from './feedback'
import { locate, type Location } from './locate'
import { FEEDBACK_BRANCH_SETTING, feedbackBranch } from './settings'
import { explainError, LOOSE_FILE_SENTENCE, shorten } from './words'

export const SHOW_FEEDBACK_COMMAND = 'gitwrite:show-feedback'
export const FEEDBACK_SURFACE = 'gitwrite:feedback'
export const ACCEPT_ACTION = 'gitwrite:accept-feedback'
export const REJECT_ACTION = 'gitwrite:reject-feedback'
/** The editor mark set the comments are drawn in. */
export const MARK_SET = 'gitwrite:feedback'

/** The most marks the kernel takes in all. */
const MAX_MARKS = 3000

const MARK_KIND = { new: 'note', accepted: 'change', rejected: 'flag' } as const

export interface FeedbackFeature {
  /** Re-reads the feedback branch, then redraws the marks and the list. */
  reload(): Promise<void>
}

/**
 * Readers' comments, from the feedback branch (GitWrite's format, docs/ANNOTATION_FORMAT.md), drawn as
 * marks on the open page and listed in a panel with Accept and Reject. A status change is a new commit
 * on the feedback branch; nothing on the writer's own pages is ever touched. The marks follow the
 * writer's edits, and are placed again after each save, when a page opens, and when the history changes.
 */
export function registerFeedback(api: PluginApi): FeedbackFeature {
  let annotations: Annotation[] = []
  let truncated = false
  let problem: string | null = null
  /** Where each of the open page's comments was found the last time marks were placed. */
  let found = new Map<string, Location | null>()
  let running: Promise<void> | null = null
  let queued: Promise<void> | null = null

  const openPage = (): string | null => api.workspace.current().document

  /**
   * Reads the feedback branch. The new state is built aside and swapped in whole at the end, so a click
   * that arrives while a reload is running still sees the comments as they were, never an empty list.
   */
  async function read(): Promise<void> {
    let next: Annotation[] = []
    let cut = false
    let failed: string | null = null
    const { project } = api.workspace.current()
    if (project !== null && project.kind === 'project') {
      try {
        if (await api.history.isRepository()) {
          const branch = await feedbackBranch(api)
          if ((await api.history.branches()).some((b) => b.name === branch)) {
            const commits = await api.history.log({ branch, limit: MAX_HISTORY_LOG })
            cut = commits.length >= MAX_HISTORY_LOG
            next = readAnnotations(commits)
          }
        }
      } catch (err) {
        next = []
        failed = explainError(err, 'read the feedback')
      }
    }
    annotations = next
    truncated = cut
    problem = failed
  }

  const onThisPage = (): Annotation[] => {
    const page = openPage()
    return page === null ? [] : annotations.filter((a) => a.filePath === page)
  }

  /** Draws the open page's comments as marks, finding each passage in the text as it is now. */
  function place(): void {
    found = new Map()
    const marks: Mark[] = []
    const text = openPage() === null ? null : api.editor.getText()
    if (text !== null) {
      for (const a of onThisPage()) {
        const where = locate(a, text)
        found.set(a.id, where)
        if (where !== null && where.end > where.start) {
          marks.push({
            id: a.id,
            from: where.start,
            to: where.end,
            kind: MARK_KIND[a.status],
            label: shorten(`${a.author}: ${a.comment}`, 120)
          })
        }
      }
    }
    try {
      api.editor.setMarks(MARK_SET, marks.slice(0, MAX_MARKS))
    } catch {
      /* no page to mark right now */
    }
  }

  function view(): ItemsView {
    const empty = (text: string): ItemsView => ({ kind: 'list', items: [], empty: { text } })
    const { project } = api.workspace.current()
    if (project === null || project.kind !== 'project') return empty(LOOSE_FILE_SENTENCE)
    if (problem !== null) return empty(problem)
    const page = openPage()
    if (page === null) return empty('Open a page to see the feedback on it.')
    const here = onThisPage()
    const elsewhere = annotations.length - here.length
    if (here.length === 0) {
      return empty(elsewhere === 0 ? 'No feedback on this page.' : `No feedback on this page. ${elsewhere} comment${elsewhere === 1 ? '' : 's'} on other pages.`)
    }
    const fresh = here.filter((a) => a.status === 'new').length
    const parts = [`${here.length} comment${here.length === 1 ? '' : 's'} on this page, ${fresh} new.`]
    if (elsewhere > 0) parts.push(`${elsewhere} on other pages.`)
    if (truncated) parts.push(`Only the latest ${MAX_HISTORY_LOG} entries were read.`)
    return {
      kind: 'list',
      note: parts.join(' '),
      items: here.map((a) => ({
        id: a.id,
        label: shorten(a.comment, 90),
        detail: [
          `“${shorten(a.text, 50)}”`,
          a.author,
          a.status,
          ...(found.get(a.id) === null ? ['can’t find this passage on the page any more'] : [])
        ].join(' · '),
        kind: 'file' as const
      })),
      empty: { text: 'No feedback on this page.' }
    }
  }

  const draw = (): void => api.surfaces.setView(FEEDBACK_SURFACE, view())

  /**
   * Reads again and redraws. A call made while a read is running cannot share it: that read may have started
   * before the caller's change. So the caller waits for one more read, shared with any others who asked
   * in the meantime.
   */
  function reload(): Promise<void> {
    if (running === null) {
      running = read()
        .then(() => {
          place()
          draw()
        })
        .finally(() => {
          running = null
        })
      return running
    }
    queued ??= running.then(() => {
      queued = null
      return reload()
    })
    return queued
  }

  /** The page changed or was saved, not the history: place the marks again from what is already read. */
  function replace(): void {
    place()
    draw()
  }

  async function setStatus(id: string, status: Status): Promise<void> {
    const annotation = annotations.find((a) => a.id === id)
    if (annotation === undefined) return reload()
    if (annotation.status === status) {
      api.notify({ message: `That comment is already ${status}.` })
      return
    }
    try {
      const branch = await feedbackBranch(api)
      await api.history.commitOn(branch, statusMessage(annotation, status), { allowEmpty: true })
    } catch (err) {
      api.notify({ message: explainError(err, 'record that') })
      return
    }
    api.notify({ message: `Marked as ${status}.` })
    await reload()
  }

  api.commands.handle(SHOW_FEEDBACK_COMMAND, async () => {
    await reload()
    api.surfaces.show(FEEDBACK_SURFACE)
  })
  api.surfaces.onRefresh(FEEDBACK_SURFACE, reload)

  // Opening a comment takes the writer to its passage.
  api.surfaces.onOpen(FEEDBACK_SURFACE, async (id) => {
    const page = openPage()
    const where = found.get(id)
    if (page === null || where === undefined) return reload()
    if (where === null) {
      api.notify({ message: 'That passage can’t be found on this page any more.' })
      return undefined
    }
    return api.workspace.open(page, { select: { from: where.start, to: where.end } })
  })
  api.surfaces.onRowAction(FEEDBACK_SURFACE, async (actionId, rowId) => {
    if (actionId === ACCEPT_ACTION) await setStatus(rowId, 'accepted')
    if (actionId === REJECT_ACTION) await setStatus(rowId, 'rejected')
    return undefined
  })
  api.editor.onMarkClick(MARK_SET, (markId) => {
    api.surfaces.show(FEEDBACK_SURFACE, { focus: markId })
  })

  // A version or switch changes what is on the feedback branch; a save or a newly opened page only
  // changes where the passages are.
  for (const name of ['history:saved', 'history:switched', 'project:switched'] as const) api.events.on(name, reload)
  for (const name of ['vault:saved', 'document:opened'] as const) api.events.on(name, replace)
  api.settings.onChanged((id) => (id === FEEDBACK_BRANCH_SETTING ? reload() : undefined))

  return { reload }
}
