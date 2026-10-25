import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { FormView, PluginManifest } from '@veneer/api'
import { veneerError } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import * as plugin from './index'
import { SAVE_COMMAND, SAVE_SURFACE } from './save'
import { LOOSE_FILE_SENTENCE } from './words'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest
const project = { name: 'Book', kind: 'project' as const }

type Fake = ReturnType<typeof createFakeHost>

async function open(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = createFakeHost(manifest, plugin, { project, openPath: 'one.md', text: 'It was a dark night.', ...options })
  await fake.load()
  return fake
}

const form = (fake: Fake): FormView => fake.views.get(SAVE_SURFACE) as FormView
const field = (fake: Fake) => form(fake).fields[0]!
const notices = (fake: Fake): string[] => fake.notices.map((n) => n.message)

describe('Save a Version', () => {
  it('opens a form that asks what changed', async () => {
    const fake = await open()
    await fake.run(SAVE_COMMAND)

    expect(fake.shown).toContain(SAVE_SURFACE)
    expect(form(fake).submitLabel).toBe('Save version')
    expect(field(fake)).toMatchObject({ id: 'message', type: 'longtext', label: 'What changed?', value: '' })
  })

  it('says that saving starts the history when the project has none, and not otherwise', async () => {
    const fresh = await open()
    await fresh.run(SAVE_COMMAND)
    expect(form(fresh).note).toMatch(/no version history yet/)

    const started = await open()
    await started.api.history.init()
    await started.run(SAVE_COMMAND)
    expect(form(started).note).toBeUndefined()
  })

  it('starts the history and saves the first version, telling the writer in plain words', async () => {
    const fake = await open()
    await fake.run(SAVE_COMMAND)
    await fake.formSubmit(SAVE_SURFACE, { message: '  Finished chapter one  ' })

    expect(fake.history.repository).toBe(true)
    expect(fake.history.commits.map((c) => c.message)).toEqual(['Finished chapter one'])
    expect(notices(fake)).toEqual(['Saved “Finished chapter one”.'])
    expect(fake.closed).toContain(SAVE_SURFACE)
  })

  it('saves the open page as it is now, not as it was when the form opened', async () => {
    const fake = await open()
    await fake.run(SAVE_COMMAND)
    fake.changeText('It was a dark and stormy night.')
    await fake.formSubmit(SAVE_SURFACE, { message: 'Added the storm' })

    const saved = await fake.api.history.show(fake.history.commits[0]!.id, 'one.md')
    expect(saved).toBe('It was a dark and stormy night.')
  })

  it('keeps a long, multi-line description whole: the first line is the title', async () => {
    const fake = await open()
    await fake.run(SAVE_COMMAND)
    await fake.formSubmit(SAVE_SURFACE, { message: 'Second pass\n\nTightened the opening and cut the dream.' })

    const [commit] = await fake.api.history.log()
    expect(commit).toMatchObject({ message: 'Second pass', body: 'Tightened the opening and cut the dream.' })
    expect(notices(fake)).toEqual(['Saved “Second pass Tightened the opening and cut the dream.”.'])
  })

  it('asks for words when the description is empty, and saves nothing', async () => {
    const fake = await open()
    await fake.run(SAVE_COMMAND)
    await fake.formSubmit(SAVE_SURFACE, { message: '   ' })

    expect(field(fake).error).toBe('Say what changed, in a few words.')
    expect(fake.history.commits).toEqual([])
    expect(fake.closed).not.toContain(SAVE_SURFACE)
    expect(notices(fake)).toEqual([])
  })

  it('takes the error away and keeps the typed words once the writer starts typing', async () => {
    const fake = await open()
    await fake.run(SAVE_COMMAND)
    await fake.formSubmit(SAVE_SURFACE, { message: '' })
    await fake.formChange(SAVE_SURFACE, 'message', 'Fin')

    expect(field(fake).value).toBe('Fin')
    expect(field(fake).error).toBeUndefined()
  })

  it('says so when nothing has changed since the last version', async () => {
    const fake = await open()
    await fake.run(SAVE_COMMAND)
    await fake.formSubmit(SAVE_SURFACE, { message: 'First' })
    await fake.run(SAVE_COMMAND)
    await fake.formSubmit(SAVE_SURFACE, { message: 'Again' })

    expect(fake.history.commits).toHaveLength(1)
    expect(notices(fake).at(-1)).toBe('Nothing has changed since the last version.')
  })

  it('tells the writer once, and opens no form, for a single loose file', async () => {
    const fake = await open({ project: { name: 'draft.md', kind: 'loose' } })
    await fake.run(SAVE_COMMAND)

    expect(notices(fake)).toEqual([LOOSE_FILE_SENTENCE])
    expect(fake.shown).toEqual([])
  })

  it('does the same with no folder open at all', async () => {
    const fake = await open({ project: null })
    await fake.run(SAVE_COMMAND)

    expect(notices(fake)).toEqual([LOOSE_FILE_SENTENCE])
  })

  it('keeps the form open with the writer\'s words, and says what went wrong, when saving fails', async () => {
    const fake = await open()
    fake.api.history.save = async () => {
      throw veneerError('history/failed', 'Veneer could not write to the project folder.')
    }
    await fake.run(SAVE_COMMAND)
    await fake.formSubmit(SAVE_SURFACE, { message: 'Finished chapter one' })

    expect(notices(fake)).toEqual(['Veneer could not write to the project folder.'])
    expect(field(fake).value).toBe('Finished chapter one')
    expect(fake.closed).not.toContain(SAVE_SURFACE)
  })

  it('ignores a second submit while the first is still saving', async () => {
    const fake = await open()
    let release: () => void = () => {}
    const realSave = fake.api.history.save.bind(fake.api.history)
    let calls = 0
    fake.api.history.save = async (message) => {
      calls += 1
      await new Promise<void>((resolve) => (release = resolve))
      return realSave(message)
    }
    await fake.run(SAVE_COMMAND)
    const first = fake.formSubmit(SAVE_SURFACE, { message: 'One' })
    await fake.formSubmit(SAVE_SURFACE, { message: 'One' })
    release()
    await first

    expect(calls).toBe(1)
    expect(fake.history.commits).toHaveLength(1)
  })
})
