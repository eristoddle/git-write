import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { FormView, ItemsView, PluginManifest } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import {
  EXPLORATIONS_SURFACE,
  SHOW_EXPLORATIONS_COMMAND,
  START_EXPLORATION_COMMAND,
  START_SURFACE,
  SWITCH_ACTION
} from './explorations'
import * as plugin from './index'
import { NAME_RULE } from './names'
import { SAVE_SURFACE } from './save'
import { LOOSE_FILE_SENTENCE } from './words'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest
const project = { name: 'Book', kind: 'project' as const }

type Fake = ReturnType<typeof createFakeHost>

async function open(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = createFakeHost(manifest, plugin, { project, openPath: 'one.md', text: 'First draft.', ...options })
  await fake.load()
  return fake
}

/** A project with one saved version on `main`. */
async function withHistory(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = await open(options)
  await fake.api.history.init()
  await fake.api.history.save('First version')
  return fake
}

const list = (fake: Fake): ItemsView => fake.views.get(EXPLORATIONS_SURFACE) as ItemsView
const startView = (fake: Fake): FormView => fake.views.get(START_SURFACE) as FormView
const nameField = (fake: Fake) => startView(fake).fields[0]!
const notices = (fake: Fake): string[] => fake.notices.map((n) => n.message)
const current = async (fake: Fake): Promise<string | undefined> =>
  (await fake.api.history.branches()).find((b) => b.current)?.name

describe('the exploration list', () => {
  it('says there is nothing to explore until a version exists, and offers to save one', async () => {
    const fake = await open()
    expect(list(fake).items).toEqual([])
    expect(list(fake).empty).toEqual({
      text: 'No explorations yet. Save a version first, then start one.',
      action: { id: 'gitwrite:save-version', label: 'Save a Version' }
    })
    await fake.pressAction(EXPLORATIONS_SURFACE, 'gitwrite:save-version')
    expect(fake.shown).toContain(SAVE_SURFACE)
  })

  it('says why a single loose file has none', async () => {
    const fake = await open({ project: { name: 'x.md', kind: 'loose' } })
    expect(list(fake).empty).toEqual({ text: LOOSE_FILE_SENTENCE })
  })

  it('lists the explorations, marks the one the writer is on, and says what switching does', async () => {
    const fake = await withHistory()
    await fake.api.history.createBranch('darker-ending')
    await fake.refreshSurface(EXPLORATIONS_SURFACE)

    expect(list(fake).items.map((i) => [i.id, i.label, i.detail, i.kind])).toEqual([
      ['darker-ending', 'darker-ending', undefined, 'file'],
      ['main', 'main', 'You are here', 'file']
    ])
    expect(list(fake).selectedId).toBe('main')
    expect(list(fake).note).toBe(
      'Switching saves your page first, then changes the project’s files to match the exploration you pick.'
    )
    expect(list(fake).empty?.action).toEqual({ id: 'gitwrite:start-exploration', label: 'Start an Exploration' })
  })

  it('keeps the readers\' feedback branch out of the list, whatever it is called', async () => {
    const fake = await withHistory()
    await fake.api.history.createBranch('feedback')
    await fake.api.history.createBranch('ending-b')
    await fake.refreshSurface(EXPLORATIONS_SURFACE)
    expect(list(fake).items.map((i) => i.id)).toEqual(['ending-b', 'main'])

    const custom = await withHistory({ settings: { 'gitwrite:feedback-branch': 'readers' } })
    await custom.api.history.createBranch('readers')
    await custom.api.history.createBranch('feedback')
    await custom.refreshSurface(EXPLORATIONS_SURFACE)
    expect(list(custom).items.map((i) => i.id)).toEqual(['feedback', 'main'])
  })

  it('still shows the feedback branch when the project is somehow on it, so the writer can leave', async () => {
    const fake = await withHistory()
    await fake.api.history.createBranch('feedback')
    await fake.api.history.switchTo('feedback')
    await fake.refreshSurface(EXPLORATIONS_SURFACE)

    expect(list(fake).items.find((i) => i.id === 'feedback')?.detail).toBe('You are here (readers’ feedback)')
  })

  it('opens from its command and refreshes when a switch happens anywhere', async () => {
    const fake = await withHistory()
    await fake.run(SHOW_EXPLORATIONS_COMMAND)
    expect(fake.shown).toContain(EXPLORATIONS_SURFACE)

    await fake.api.history.createBranch('late')
    await fake.emit({ type: 'history:switched' })
    expect(list(fake).items.map((i) => i.id)).toEqual(['late', 'main'])
  })
})

describe('Start an Exploration', () => {
  it('tells the writer what it does and where it starts from', async () => {
    const fake = await withHistory()
    await fake.run(START_EXPLORATION_COMMAND)

    expect(fake.shown).toContain(START_SURFACE)
    expect(startView(fake).note).toBe(
      'An exploration is a copy of your project to try an idea in. It starts from “main”. Starting it saves your page, then changes the project’s files to the new exploration; you can switch back any time.'
    )
    expect(startView(fake).submitLabel).toBe('Start exploration')
  })

  it('needs a saved version to start from, and says so', async () => {
    const fake = await open()
    await fake.run(START_EXPLORATION_COMMAND)
    expect(notices(fake)).toEqual(['Save a version first; an exploration starts from a saved version.'])
    expect(fake.shown).toEqual([])
  })

  it('says why for a single loose file', async () => {
    const fake = await open({ project: { name: 'x.md', kind: 'loose' } })
    await fake.run(START_EXPLORATION_COMMAND)
    expect(notices(fake)).toEqual([LOOSE_FILE_SENTENCE])
  })

  it('makes the exploration and moves the project onto it', async () => {
    const fake = await withHistory()
    await fake.run(START_EXPLORATION_COMMAND)
    await fake.formSubmit(START_SURFACE, { name: '  darker-ending ' })

    expect(await current(fake)).toBe('darker-ending')
    expect(fake.closed).toContain(START_SURFACE)
    expect(notices(fake)).toEqual(['Started “darker-ending”. Your page was saved first and the project’s files now match it.'])
    expect(list(fake).items.find((i) => i.detail === 'You are here')?.id).toBe('darker-ending')
  })

  it.each(['', 'has space', 'épilogue', 'a..b'])('explains a name it cannot use (%j) and makes nothing', async (name) => {
    const fake = await withHistory()
    await fake.run(START_EXPLORATION_COMMAND)
    await fake.formSubmit(START_SURFACE, { name })

    expect(nameField(fake).error).toBe(name === '' ? 'Give it a name.' : NAME_RULE)
    expect((await fake.api.history.branches()).map((b) => b.name)).toEqual(['main'])
    expect(fake.closed).not.toContain(START_SURFACE)
  })

  it('keeps the name for readers\' comments for them', async () => {
    const fake = await withHistory()
    await fake.run(START_EXPLORATION_COMMAND)
    await fake.formSubmit(START_SURFACE, { name: 'feedback' })

    expect(nameField(fake).error).toBe('That name is kept for readers’ feedback. Choose another.')
  })

  it('says when the name is taken, and keeps what was typed', async () => {
    const fake = await withHistory()
    await fake.api.history.createBranch('taken')
    await fake.run(START_EXPLORATION_COMMAND)
    await fake.formSubmit(START_SURFACE, { name: 'taken' })

    expect(nameField(fake)).toMatchObject({ value: 'taken', error: 'That name is already in use. Choose another.' })
    expect(await current(fake)).toBe('main')
  })

  it('makes the exploration but stays put, and says why, when unsaved changes block the switch', async () => {
    const fake = await withHistory()
    await fake.run(START_EXPLORATION_COMMAND)
    fake.changeText('Unsaved words.')
    await fake.formSubmit(START_SURFACE, { name: 'ending-b' })

    expect(await current(fake)).toBe('main')
    expect((await fake.api.history.branches()).map((b) => b.name)).toContain('ending-b')
    expect(notices(fake)).toHaveLength(1)
    expect(notices(fake)[0]).toMatch(/^“ending-b” was made, but you are not on it yet\. Your project has changes/)
    expect(notices(fake)[0]!.length).toBeLessThanOrEqual(200)
    expect(fake.closed).toContain(START_SURFACE)
  })

  it('clears the error once the writer types again, and ignores a second submit while starting', async () => {
    const fake = await withHistory()
    await fake.run(START_EXPLORATION_COMMAND)
    await fake.formSubmit(START_SURFACE, { name: 'bad name' })
    await fake.formChange(START_SURFACE, 'name', 'bad-name')
    expect(nameField(fake).value).toBe('bad-name')
    expect(nameField(fake).error).toBeUndefined()

    let release: () => void = () => {}
    const realSwitch = fake.api.history.switchTo.bind(fake.api.history)
    let switches = 0
    fake.api.history.switchTo = async (name) => {
      switches += 1
      await new Promise<void>((resolve) => (release = resolve))
      return realSwitch(name)
    }
    const first = fake.formSubmit(START_SURFACE, { name: 'good-name' })
    await fake.formSubmit(START_SURFACE, { name: 'good-name' })
    release()
    await first
    expect(switches).toBe(1)
  })
})

describe('switching explorations', () => {
  it('asks the kernel to confirm when a row is opened, and does nothing yet', async () => {
    const fake = await withHistory()
    await fake.api.history.createBranch('ending-b')
    await fake.refreshSurface(EXPLORATIONS_SURFACE)
    await fake.openItem(EXPLORATIONS_SURFACE, 'ending-b')

    expect(fake.begunRowActions).toEqual([{ surfaceId: EXPLORATIONS_SURFACE, actionId: SWITCH_ACTION, rowId: 'ending-b' }])
    expect(await current(fake)).toBe('main')
  })

  it('switches when confirmed, saying the page was saved first', async () => {
    const fake = await withHistory()
    await fake.api.history.createBranch('ending-b')
    await fake.refreshSurface(EXPLORATIONS_SURFACE)
    await fake.rowAction(EXPLORATIONS_SURFACE, SWITCH_ACTION, 'ending-b')

    expect(await current(fake)).toBe('ending-b')
    expect(notices(fake)).toEqual(['Switched to “ending-b”. Your page was saved first and the project’s files now match it.'])
    expect(list(fake).selectedId).toBe('ending-b')
  })

  it('shows the other exploration\'s text on the page after switching', async () => {
    const fake = await withHistory()
    await fake.api.history.createBranch('ending-b')
    await fake.api.history.switchTo('ending-b')
    fake.changeText('The darker ending.')
    await fake.api.history.save('Darker ending')
    await fake.refreshSurface(EXPLORATIONS_SURFACE)
    await fake.rowAction(EXPLORATIONS_SURFACE, SWITCH_ACTION, 'main')

    expect(fake.text()).toBe('First draft.')
  })

  it('says so when the writer is already there', async () => {
    const fake = await withHistory()
    await fake.refreshSurface(EXPLORATIONS_SURFACE)
    await fake.openItem(EXPLORATIONS_SURFACE, 'main')
    expect(notices(fake)).toEqual(['You are already on “main”.'])
    expect(fake.begunRowActions).toEqual([])

    await fake.rowAction(EXPLORATIONS_SURFACE, SWITCH_ACTION, 'main')
    expect(notices(fake)).toEqual(['You are already on “main”.', 'You are already on “main”.'])
  })

  it('stays put and says what to do when there are changes not in a version', async () => {
    const fake = await withHistory()
    await fake.api.history.createBranch('ending-b')
    await fake.refreshSurface(EXPLORATIONS_SURFACE)
    fake.changeText('Unsaved words.')
    await fake.rowAction(EXPLORATIONS_SURFACE, SWITCH_ACTION, 'ending-b')

    expect(await current(fake)).toBe('main')
    expect(notices(fake)).toEqual(['Your project has changes that are not in a version yet. Use “Save a Version”, then try again.'])
  })

  it('reloads the list instead of failing when the row is gone', async () => {
    const fake = await withHistory()
    await fake.refreshSurface(EXPLORATIONS_SURFACE)
    await fake.rowAction(EXPLORATIONS_SURFACE, SWITCH_ACTION, 'vanished')
    expect(notices(fake)).toEqual([])
    expect(list(fake).items.map((i) => i.id)).toEqual(['main'])
  })
})
