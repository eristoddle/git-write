import type { FormView, HistoryBranch, ItemsView, PluginApi } from '@veneer/api'
import { nameProblem } from './names'
import { feedbackBranch } from './settings'
import { explainError, LOOSE_FILE_SENTENCE, shorten } from './words'

export const SHOW_EXPLORATIONS_COMMAND = 'gitwrite:show-explorations'
export const START_EXPLORATION_COMMAND = 'gitwrite:start-exploration'
export const EXPLORATIONS_SURFACE = 'gitwrite:explorations'
export const START_SURFACE = 'gitwrite:start'
export const SWITCH_ACTION = 'gitwrite:switch-exploration'

const NO_VERSIONS = 'No explorations yet. Save a version first, then start one.'
const SWITCHING_NOTE =
  'Switching saves your page first, then changes the project’s files to match the exploration you pick.'
const START_ACTION = START_EXPLORATION_COMMAND
const SAVE_ACTION = 'gitwrite:save-version'

export interface ExplorationsOptions {
  /** Opens the "what changed?" form, for the empty list's button. */
  beginSave: () => Promise<void>
}

export interface ExplorationsFeature {
  refresh(): Promise<void>
  /** Opens the "name your exploration" form (or says why not). */
  begin(): Promise<void>
}

/** The form that asks for an exploration's name. */
export function startForm(options: { current?: string; name?: string; error?: string } = {}): FormView {
  const from = options.current === undefined ? 'where you are now' : `“${options.current}”`
  return {
    kind: 'form',
    note: `An exploration is a copy of your project to try an idea in. It starts from ${from}. Starting it saves your page, then changes the project’s files to the new exploration; you can switch back any time.`,
    submitLabel: 'Start exploration',
    fields: [
      {
        id: 'name',
        type: 'text',
        label: 'Name',
        hint: 'Letters, numbers, dashes, dots or underscores, like “darker-ending”.',
        placeholder: 'darker-ending',
        value: options.name ?? '',
        error: options.error
      }
    ]
  }
}

/**
 * Explorations are branches, in the writer's words. The list hides the readers' feedback branch
 * (switching to it would swap in a stale snapshot of the files) unless the project is somehow on it.
 */
export function registerExplorations(api: PluginApi, options: ExplorationsOptions): ExplorationsFeature {
  let branches: HistoryBranch[] = []
  let starting = false
  let switching = false

  async function reserved(): Promise<string> {
    return feedbackBranch(api)
  }

  async function listView(): Promise<ItemsView> {
    const empty = (text: string, action: { id: string; label: string }): ItemsView => ({
      kind: 'list',
      items: [],
      empty: { text, action }
    })
    const { project } = api.workspace.current()
    branches = []
    if (project === null || project.kind !== 'project') {
      return { kind: 'list', items: [], empty: { text: LOOSE_FILE_SENTENCE } }
    }
    try {
      if (!(await api.history.isRepository())) return empty(NO_VERSIONS, { id: SAVE_ACTION, label: 'Save a Version' })
      branches = await api.history.branches()
    } catch (err) {
      branches = []
      return { kind: 'list', items: [], empty: { text: explainError(err, 'read the explorations') } }
    }
    const hidden = await reserved()
    const shown = branches.filter((b) => b.name !== hidden || b.current)
    const current = shown.find((b) => b.current)
    return {
      kind: 'list',
      note: SWITCHING_NOTE,
      items: shown.map((b) => ({
        id: b.name,
        label: b.name,
        detail: b.current ? (b.name === hidden ? 'You are here (readers’ feedback)' : 'You are here') : undefined,
        kind: 'file' as const
      })),
      ...(current === undefined ? {} : { selectedId: current.name }),
      empty: { text: NO_VERSIONS, action: { id: START_ACTION, label: 'Start an Exploration' } }
    }
  }

  async function refresh(): Promise<void> {
    api.surfaces.setView(EXPLORATIONS_SURFACE, await listView())
  }

  async function begin(): Promise<void> {
    const { project } = api.workspace.current()
    if (project === null || project.kind !== 'project') {
      api.notify({ message: LOOSE_FILE_SENTENCE })
      return
    }
    try {
      if (!(await api.history.isRepository())) {
        api.notify({ message: 'Save a version first; an exploration starts from a saved version.' })
        return
      }
      const current = (await api.history.branches()).find((b) => b.current)?.name
      api.surfaces.setView(START_SURFACE, startForm({ current }))
      api.surfaces.show(START_SURFACE)
    } catch (err) {
      api.notify({ message: explainError(err, 'start an exploration') })
    }
  }

  async function start(raw: unknown): Promise<void> {
    if (starting) return
    const name = typeof raw === 'string' ? raw.trim() : ''
    const problem = nameProblem(name, [await reserved()])
    if (problem !== null) {
      api.surfaces.setView(START_SURFACE, startForm({ name, error: problem }))
      return
    }
    starting = true
    try {
      try {
        await api.history.createBranch(name)
      } catch (err) {
        api.surfaces.setView(START_SURFACE, startForm({ name, error: explainError(err, 'start that exploration') }))
        return
      }
      try {
        await api.history.switchTo(name)
      } catch (err) {
        // The exploration exists; the writer just is not on it yet.
        api.surfaces.close(START_SURFACE)
        api.notify({
          message: shorten(`“${name}” was made, but you are not on it yet. ${explainError(err, 'switch to it')}`, 200)
        })
        await refresh()
        return
      }
      api.surfaces.close(START_SURFACE)
      api.notify({ message: `Started “${name}”. Your page was saved first and the project’s files now match it.` })
      await refresh()
    } finally {
      starting = false
    }
  }

  async function switchTo(name: string): Promise<void> {
    if (switching) return
    switching = true
    try {
      const target = branches.find((b) => b.name === name)
      if (target === undefined) return refresh()
      if (target.current) {
        api.notify({ message: `You are already on “${name}”.` })
        return
      }
      try {
        await api.history.switchTo(name)
      } catch (err) {
        api.notify({ message: explainError(err, 'switch explorations') })
        return
      }
      api.notify({ message: `Switched to “${name}”. Your page was saved first and the project’s files now match it.` })
      await refresh()
    } finally {
      switching = false
    }
  }

  api.commands.handle(SHOW_EXPLORATIONS_COMMAND, async () => {
    await refresh()
    api.surfaces.show(EXPLORATIONS_SURFACE)
  })
  api.commands.handle(START_EXPLORATION_COMMAND, begin)

  api.surfaces.onRefresh(EXPLORATIONS_SURFACE, refresh)
  // Opening a row asks to switch; the kernel draws the confirmation that says what switching does.
  api.surfaces.onOpen(EXPLORATIONS_SURFACE, (name) => {
    const target = branches.find((b) => b.name === name)
    if (target === undefined) return refresh()
    if (target.current) {
      api.notify({ message: `You are already on “${name}”.` })
      return undefined
    }
    api.surfaces.beginRowAction(EXPLORATIONS_SURFACE, SWITCH_ACTION, name)
    return undefined
  })
  api.surfaces.onAction(EXPLORATIONS_SURFACE, (actionId) => {
    if (actionId === START_ACTION) return begin()
    if (actionId === SAVE_ACTION) return options.beginSave()
    return undefined
  })
  api.surfaces.onRowAction(EXPLORATIONS_SURFACE, async (actionId, rowId) => {
    if (actionId === SWITCH_ACTION) await switchTo(rowId)
    return undefined
  })

  api.surfaces.onFormChange(START_SURFACE, (_field, value) => {
    api.surfaces.setView(START_SURFACE, startForm({ name: typeof value === 'string' ? value : '' }))
  })
  api.surfaces.onFormSubmit(START_SURFACE, (values) => start(values.name))

  for (const name of ['history:saved', 'history:switched', 'project:switched'] as const) {
    api.events.on(name, refresh)
  }

  return { refresh, begin }
}
