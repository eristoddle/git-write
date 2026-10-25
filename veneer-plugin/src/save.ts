import type { FormView, PluginApi } from '@veneer/api'
import { explainError, LOOSE_FILE_SENTENCE, shorten } from './words'

export const SAVE_COMMAND = 'gitwrite:save-version'
export const SAVE_SURFACE = 'gitwrite:save'

const FIRST_VERSION_NOTE = 'This project has no version history yet. Saving the first version starts it.'

/** The "what changed?" form: a few words the writer will recognise later. */
export function saveForm(options: { note?: string; message?: string; error?: string } = {}): FormView {
  return {
    kind: 'form',
    note: options.note,
    submitLabel: 'Save version',
    fields: [
      {
        id: 'message',
        type: 'longtext',
        label: 'What changed?',
        hint: 'A few words you will recognise later, like “Finished chapter two”.',
        placeholder: 'Finished chapter two',
        value: options.message ?? '',
        error: options.error
      }
    ]
  }
}

/**
 * "Save a Version": the command asks what changed in a form, and submitting saves every change in
 * the project as one version with `api.history.save`, which also saves the open page first. The first
 * save in a project that has no history starts it. `afterSave` runs once a version exists (the
 * history list refreshes there).
 */
export function registerSave(api: PluginApi, afterSave: () => Promise<void> = async () => {}): void {
  let note: string | undefined
  let saving = false

  api.commands.handle(SAVE_COMMAND, async () => {
    const { project } = api.workspace.current()
    if (project === null || project.kind !== 'project') {
      api.notify({ message: LOOSE_FILE_SENTENCE })
      return
    }
    note = (await api.history.isRepository()) ? undefined : FIRST_VERSION_NOTE
    api.surfaces.setView(SAVE_SURFACE, saveForm({ note }))
    api.surfaces.show(SAVE_SURFACE)
  })

  // Keep what the writer has typed, and take the error away once they start fixing it.
  api.surfaces.onFormChange(SAVE_SURFACE, (_field, value) => {
    api.surfaces.setView(SAVE_SURFACE, saveForm({ note, message: typeof value === 'string' ? value : '' }))
  })

  api.surfaces.onFormSubmit(SAVE_SURFACE, async (values) => {
    if (saving) return
    const message = typeof values.message === 'string' ? values.message.trim() : ''
    if (message === '') {
      api.surfaces.setView(SAVE_SURFACE, saveForm({ note, error: 'Say what changed, in a few words.' }))
      return
    }
    saving = true
    try {
      if (!(await api.history.isRepository())) await api.history.init()
      const commit = await api.history.save(message)
      api.surfaces.close(SAVE_SURFACE)
      api.notify({
        message: commit === null ? 'Nothing has changed since the last version.' : `Saved “${shorten(message)}”.`
      })
      if (commit !== null) await afterSave()
    } catch (err) {
      // The form stays open with the writer's words in it, so they can try again.
      api.surfaces.setView(SAVE_SURFACE, saveForm({ note, message }))
      api.notify({ message: explainError(err, 'save that version') })
    } finally {
      saving = false
    }
  })
}
