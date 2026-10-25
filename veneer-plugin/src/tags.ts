import type { FormView, HistoryCommit, PluginApi } from '@veneer/api'
import { nameProblem } from './names'
import { explainError, LOOSE_FILE_SENTENCE, shorten, versionTitle, whenText } from './words'

export const NAME_COMMAND = 'gitwrite:name-version'
export const NAME_SURFACE = 'gitwrite:name'

const CHOICES = 20
const GONE = 'That version is no longer there. Choose another.'

interface FormState {
  name?: string
  version?: string
  note?: string
  error?: { field: 'name' | 'version'; text: string }
}

/** The form that names a version: what to call it, which version, and an optional note. */
export function nameForm(versions: readonly HistoryCommit[], state: FormState = {}, now: Date = new Date()): FormView {
  // A choice field must hold one of its options, so a version that is gone falls back to the newest.
  const chosen = versions.some((v) => v.id === state.version) ? (state.version as string) : (versions[0]?.id ?? '')
  return {
    kind: 'form',
    note: 'A name marks a version you will want to find again, like “first-draft” or “sent-to-editor”.',
    submitLabel: 'Name version',
    fields: [
      {
        id: 'name',
        type: 'text',
        label: 'Name',
        hint: 'Letters, numbers, dashes, dots or underscores.',
        placeholder: 'first-draft',
        value: state.name ?? '',
        error: state.error?.field === 'name' ? state.error.text : undefined
      },
      {
        id: 'version',
        type: 'choice',
        label: 'Which version',
        value: chosen,
        options: versions.map((v) => ({
          value: v.id,
          label: `${shorten(versionTitle(v), 50)} (${whenText(v.date, now)})`
        })),
        error: state.error?.field === 'version' ? state.error.text : undefined
      },
      { id: 'note', type: 'text', label: 'Note (optional)', value: state.note ?? '', placeholder: 'Sent to beta readers' }
    ]
  }
}

/**
 * "Name a Version": gives a version a name (a tag) so the writer can find it again. The choice offers
 * the latest versions, the newest first and already picked; `afterTag` runs once a name exists (the
 * version list refreshes there).
 */
export function registerTags(api: PluginApi, options: { afterTag?: () => Promise<void>; now?: () => Date } = {}): void {
  let offered: HistoryCommit[] = []
  let saving = false
  const typed: FormState = {}
  const now = (): Date => options.now?.() ?? new Date()

  api.commands.handle(NAME_COMMAND, async () => {
    const { project } = api.workspace.current()
    if (project === null || project.kind !== 'project') {
      api.notify({ message: LOOSE_FILE_SENTENCE })
      return
    }
    try {
      offered = (await api.history.isRepository()) ? await api.history.log({ limit: CHOICES }) : []
    } catch (err) {
      api.notify({ message: explainError(err, 'read the versions') })
      return
    }
    if (offered.length === 0) {
      api.notify({ message: 'There are no versions to name yet. Save a version first.' })
      return
    }
    typed.name = typed.version = typed.note = undefined // a fresh form each time
    api.surfaces.setView(NAME_SURFACE, nameForm(offered, {}, now()))
    api.surfaces.show(NAME_SURFACE)
  })

  // Keep what the writer has typed or chosen, and take an error away once they change a field.
  api.surfaces.onFormChange(NAME_SURFACE, (field, value) => {
    if (field === 'name' || field === 'version' || field === 'note') typed[field] = typeof value === 'string' ? value : ''
    api.surfaces.setView(NAME_SURFACE, nameForm(offered, { ...typed }, now()))
  })

  api.surfaces.onFormSubmit(NAME_SURFACE, async (values) => {
    if (saving) return
    const name = typeof values.name === 'string' ? values.name.trim() : ''
    const note = typeof values.note === 'string' ? values.note.trim() : ''
    const version = typeof values.version === 'string' ? values.version : ''
    const state: FormState = { name, version, note }
    const problem = nameProblem(name)
    if (problem !== null) {
      api.surfaces.setView(NAME_SURFACE, nameForm(offered, { ...state, error: { field: 'name', text: problem } }, now()))
      return
    }
    const target = offered.find((v) => v.id === version)
    if (target === undefined) {
      api.surfaces.setView(NAME_SURFACE, nameForm(offered, { ...state, error: { field: 'version', text: GONE } }, now()))
      return
    }
    saving = true
    try {
      await api.history.createTag(name, target.id, note === '' ? undefined : note)
      typed.name = typed.version = typed.note = undefined
      api.surfaces.close(NAME_SURFACE)
      api.notify({ message: `Named “${name}” for “${shorten(versionTitle(target), 80)}”.` })
      await options.afterTag?.()
    } catch (err) {
      api.surfaces.setView(
        NAME_SURFACE,
        nameForm(offered, { ...state, error: { field: 'name', text: explainError(err, 'name that version') } }, now())
      )
    } finally {
      saving = false
    }
  })
}
