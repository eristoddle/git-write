import { isVeneerError } from '@veneer/api'
import type { DiffView, HistoryCommit, ItemsView, PluginApi } from '@veneer/api'
import { dateText, explainError, LOOSE_FILE_SENTENCE, shorten, versionDetail, versionTitle, whenText } from './words'

export const SHOW_HISTORY_COMMAND = 'gitwrite:show-history'
export const HISTORY_SURFACE = 'gitwrite:history'
export const COMPARE_SURFACE = 'gitwrite:compare'
export const RESTORE_ACTION = 'gitwrite:restore-version'
/** The empty list's button starts the same flow as the "Save a Version" command. */
export const SAVE_ACTION = 'gitwrite:save-version'

const NO_VERSIONS = 'No versions yet. Save a version to start keeping this project’s history.'
const OPEN_A_PAGE = 'Open a page first, then choose a version to look at.'
/** `api.history.log` lists this many unless asked for more; a full list says so rather than looking complete. */
const LOG_PAGE = 100

export interface HistoryOptions {
  /** Opens the "what changed?" form, for the empty list's button. */
  beginSave: () => Promise<void>
  /** The clock, so a test can pin "3 days ago". */
  now?: () => Date
}

/** A one-time question put to the list: "choose a version", answered by the writer opening a row. */
export interface Picking {
  /** The line above the list that says what to choose. */
  note: string
  onPick(commit: HistoryCommit): Promise<void> | void
}

export interface HistoryFeature {
  /** Re-reads the versions and hands the list to the kernel. */
  refresh(): Promise<void>
  /** The versions as last listed, newest first. */
  versions(): readonly HistoryCommit[]
  /** Shows the list with `question.note` above it; the next version opened answers it instead of being viewed. */
  ask(question: Picking): Promise<void>
  /** The text of `page` in `commit`, or null after telling the writer why not. */
  textAt(commit: HistoryCommit, page: string): Promise<string | null>
  now(): Date
}

/** The page the writer has open, or why there is none. */
function openPage(api: PluginApi): string | null {
  return api.workspace.current().document
}

/** What a version looked like on the open page, as a `show` failure the writer can understand. */
function explainShowError(err: unknown, page: string): string {
  if (isVeneerError(err) && err.code === 'history/not-found') {
    return `“${page}” did not exist in that version.`
  }
  return explainError(err, 'read that version')
}

/**
 * The version list, a read-only view of one version of the open page, and "Restore as New Version".
 * History is never rewritten: restoring puts the old text on the page and saves it as a new version.
 */
export function registerHistory(api: PluginApi, options: HistoryOptions): HistoryFeature {
  const now = (): Date => options.now?.() ?? new Date()
  let versions: HistoryCommit[] = []
  let question: Picking | null = null

  /** What the writer is asked to do, else a warning that the list stops at the latest versions. */
  const shownNote = (): string | undefined =>
    question?.note ?? (versions.length >= LOG_PAGE ? `Showing the latest ${LOG_PAGE} versions.` : undefined)

  async function listView(): Promise<ItemsView> {
    const empty = (text: string, withSave = false): ItemsView => ({
      kind: 'list',
      items: [],
      empty: { text, ...(withSave ? { action: { id: SAVE_ACTION, label: 'Save a Version' } } : {}) }
    })
    const { project } = api.workspace.current()
    versions = []
    if (project === null || project.kind !== 'project') return empty(LOOSE_FILE_SENTENCE)
    try {
      if (!(await api.history.isRepository())) return empty(NO_VERSIONS, true)
      versions = await api.history.log()
    } catch (err) {
      versions = []
      return empty(explainError(err, 'read the version history'))
    }
    if (versions.length === 0) return empty(NO_VERSIONS, true)
    return {
      kind: 'list',
      ...(shownNote() === undefined ? {} : { note: shownNote() }),
      items: versions.map((commit) => ({
        id: commit.id,
        label: versionTitle(commit),
        detail: versionDetail(commit, now()),
        kind: 'file' as const
      })),
      empty: { text: NO_VERSIONS, action: { id: SAVE_ACTION, label: 'Save a Version' } }
    }
  }

  async function refresh(): Promise<void> {
    api.surfaces.setView(HISTORY_SURFACE, await listView())
  }

  /** The text of the open page as it was in `commit`, or null after telling the writer why not. */
  async function pageAt(commit: HistoryCommit, page: string): Promise<string | null> {
    try {
      return await api.history.show(commit.id, page)
    } catch (err) {
      api.notify({ message: explainShowError(err, page) })
      return null
    }
  }

  async function openVersion(id: string): Promise<void> {
    const commit = versions.find((v) => v.id === id)
    if (commit === undefined) return refresh()
    if (question !== null) {
      // The question is answered once; the answer may ask the next one.
      const asked = question
      question = null
      await asked.onPick(commit)
      return refresh()
    }
    const page = openPage(api)
    if (page === null) {
      api.notify({ message: OPEN_A_PAGE })
      return
    }
    const text = await pageAt(commit, page)
    if (text === null) return
    const view: DiffView = {
      kind: 'diff',
      note: `${page} as it was in “${shorten(versionTitle(commit), 50)}”, ${whenText(commit.date, now())}. Read only.`,
      segments: [{ kind: 'equal', text }]
    }
    api.surfaces.setView(COMPARE_SURFACE, view)
    api.surfaces.show(COMPARE_SURFACE)
  }

  async function restore(id: string): Promise<void> {
    const commit = versions.find((v) => v.id === id)
    if (commit === undefined) return refresh()
    const page = openPage(api)
    const current = page === null ? null : api.editor.getText()
    if (page === null || current === null) {
      api.notify({ message: 'Open the page you want to restore, then choose a version.' })
      return
    }
    const text = await pageAt(commit, page)
    if (text === null) return
    if (text === current) {
      api.notify({ message: 'This page already matches that version.' })
      return
    }
    const title = shorten(versionTitle(commit), 50)
    try {
      // One edit, so one undo step; the page is never written behind the editor's back.
      api.editor.edit({ from: 0, to: current.length, text })
    } catch (err) {
      api.notify({ message: explainError(err, 'restore that version') })
      return
    }
    try {
      await api.history.save(`Restored “${title}” (${dateText(commit.date)}) on ${page}`)
    } catch (err) {
      api.notify({
        message: shorten(
          `The page now has that version’s text, but it was not saved as a version (undo will bring your text back). ${explainError(err, 'save it')}`,
          200
        )
      })
      return
    }
    api.notify({ message: `Restored “${title}” as a new version.` })
    await refresh()
  }

  api.commands.handle(SHOW_HISTORY_COMMAND, async () => {
    question = null // Opening the history plainly drops any "choose a version" in progress.
    await refresh()
    api.surfaces.show(HISTORY_SURFACE)
  })
  api.surfaces.onRefresh(HISTORY_SURFACE, refresh)
  api.surfaces.onOpen(HISTORY_SURFACE, openVersion)
  api.surfaces.onAction(HISTORY_SURFACE, (actionId) => {
    if (actionId === SAVE_ACTION) return options.beginSave()
    return undefined
  })
  api.surfaces.onRowAction(HISTORY_SURFACE, async (actionId, rowId) => {
    if (actionId === RESTORE_ACTION) await restore(rowId)
    return undefined
  })
  // A version made anywhere (this plugin, another plugin, Veneer itself) changes the list.
  for (const name of ['history:saved', 'history:switched'] as const) {
    api.events.on(name, refresh)
  }
  api.events.on('project:switched', () => {
    question = null // A question about one project's versions means nothing in another.
    return refresh()
  })

  async function ask(next: Picking): Promise<void> {
    question = next
    await refresh()
    api.surfaces.show(HISTORY_SURFACE)
  }

  return { refresh, versions: () => versions, ask, textAt: pageAt, now }
}
