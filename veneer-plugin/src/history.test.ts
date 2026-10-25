import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { DiffView, HistorySavedEvent, ItemsView, PluginManifest } from '@veneer/api'
import { veneerError } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import { COMPARE_SURFACE, HISTORY_SURFACE, RESTORE_ACTION, SAVE_ACTION, SHOW_HISTORY_COMMAND } from './history'
import { start } from './index'
import { SAVE_COMMAND, SAVE_SURFACE } from './save'
import { LOOSE_FILE_SENTENCE } from './words'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest
const project = { name: 'Book', kind: 'project' as const }
const NOW = new Date('2026-10-25T12:00:00Z')
const HOUR = 3_600_000
const entry = { onload: (api: Parameters<typeof start>[0]) => start(api, { now: () => NOW }) }

type Fake = ReturnType<typeof createFakeHost>

async function open(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = createFakeHost(manifest, entry, { project, openPath: 'one.md', text: 'First draft.', ...options })
  await fake.load()
  return fake
}

/** Saves the open page as `text` with `message`, then dates the version `hoursAgo` hours before NOW. */
async function saveVersion(fake: Fake, message: string, text: string, hoursAgo: number): Promise<string> {
  await fake.api.history.init()
  fake.changeText(text)
  const commit = await fake.api.history.save(message)
  if (commit === null) throw new Error('nothing to save')
  const stored = fake.history.commits.find((c) => c.id === commit.id)!
  stored.date = new Date(NOW.getTime() - hoursAgo * HOUR).toISOString()
  return commit.id
}

const list = (fake: Fake): ItemsView => fake.views.get(HISTORY_SURFACE) as ItemsView
const compare = (fake: Fake): DiffView => fake.views.get(COMPARE_SURFACE) as DiffView
const notices = (fake: Fake): string[] => fake.notices.map((n) => n.message)

describe('the version list', () => {
  it('says there are no versions yet, and offers to make the first', async () => {
    const fake = await open()
    expect(list(fake).items).toEqual([])
    expect(list(fake).empty).toEqual({
      text: 'No versions yet. Save a version to start keeping this project’s history.',
      action: { id: SAVE_ACTION, label: 'Save a Version' }
    })
    await fake.pressAction(HISTORY_SURFACE, SAVE_ACTION)
    expect(fake.shown).toContain(SAVE_SURFACE)
  })

  it('says why a single loose file has no versions', async () => {
    const fake = await open({ project: { name: 'draft.md', kind: 'loose' } })
    expect(list(fake).empty).toEqual({ text: LOOSE_FILE_SENTENCE })
  })

  it('lists versions newest first with who saved them and when, in the writer\'s words', async () => {
    const fake = await open()
    await saveVersion(fake, 'First pass', 'One.', 49)
    await saveVersion(fake, 'Second pass', 'One. Two.', 3)
    await fake.refreshSurface(HISTORY_SURFACE)

    expect(list(fake).items.map((i) => [i.label, i.detail, i.kind])).toEqual([
      ['Second pass', 'Fake Writer · 3 hours ago', 'file'],
      ['First pass', 'Fake Writer · 2 days ago', 'file']
    ])
  })

  it('says when the list is cut short at the latest 100 versions, and not before', async () => {
    const fake = await open()
    await fake.api.history.init()
    for (let i = 1; i <= 99; i++) await saveVersion(fake, `Version ${i}`, `Text ${i}`, 1)
    await fake.refreshSurface(HISTORY_SURFACE)
    expect(list(fake).items).toHaveLength(99)
    expect(list(fake).note).toBeUndefined()

    await saveVersion(fake, 'Version 100', 'Text 100', 1)
    await fake.refreshSurface(HISTORY_SURFACE)
    expect(list(fake).items).toHaveLength(100)
    expect(list(fake).note).toBe('Showing the latest 100 versions.')
  })

  it('opens from the command and from the palette, freshly read each time', async () => {
    const fake = await open()
    await saveVersion(fake, 'Chapter one', 'Text.', 1)
    await fake.run(SHOW_HISTORY_COMMAND)

    expect(fake.shown).toContain(HISTORY_SURFACE)
    expect(list(fake).items.map((i) => i.label)).toEqual(['Chapter one'])
  })

  it('refreshes by itself when a version is made, by this plugin or any other', async () => {
    const fake = await open()
    await fake.run(SAVE_COMMAND)
    await fake.formSubmit(SAVE_SURFACE, { message: 'From the form' })
    expect(list(fake).items.map((i) => i.label)).toEqual(['From the form'])

    fake.changeText('Changed elsewhere.')
    const other = await fake.api.history.save('Saved by another plugin')
    const event: HistorySavedEvent = { type: 'history:saved', commit: other! }
    await fake.emit(event)
    expect(list(fake).items.map((i) => i.label)).toEqual(['Saved by another plugin', 'From the form'])
  })

  it('explains a failure to read the history instead of showing nothing', async () => {
    const fake = await open()
    await fake.api.history.init()
    fake.api.history.log = async () => {
      throw veneerError('history/failed', 'Veneer could not read the project folder.')
    }
    await fake.refreshSurface(HISTORY_SURFACE)
    expect(list(fake).empty?.text).toBe('Veneer could not read the project folder.')
  })
})

describe('looking at a version', () => {
  it('shows that version of the open page, read only, in the compare panel', async () => {
    const fake = await open()
    const first = await saveVersion(fake, 'First pass', 'It was a dark night.', 5)
    await saveVersion(fake, 'Second pass', 'It was a dark and stormy night.', 1)
    await fake.refreshSurface(HISTORY_SURFACE)
    await fake.openItem(HISTORY_SURFACE, first)

    expect(compare(fake)).toEqual({
      kind: 'diff',
      note: 'one.md as it was in “First pass”, 5 hours ago. Read only.',
      segments: [{ kind: 'equal', text: 'It was a dark night.' }]
    })
    expect(fake.shown).toContain(COMPARE_SURFACE)
    expect(fake.text()).toBe('It was a dark and stormy night.') // the page itself is untouched
    expect(fake.edits).toEqual([])
  })

  it('asks for a page to look at when none is open', async () => {
    const fake = await open({ openPath: undefined, text: null })
    const id = await saveVersion(fake, 'First', 'Text.', 1)
    await fake.refreshSurface(HISTORY_SURFACE)
    await fake.openItem(HISTORY_SURFACE, id)

    expect(notices(fake)).toEqual(['Open a page first, then choose a version to look at.'])
    expect(fake.views.has(COMPARE_SURFACE)).toBe(false)
  })

  it('says so when the open page did not exist in that version', async () => {
    const fake = await open({ files: { 'two.md': 'Other page.' } })
    const before = await saveVersion(fake, 'Before two.md', 'One.', 4)
    // The fake keeps every file in each version; make this version lack the page.
    delete (fake.history.commits.find((c) => c.id === before) as unknown as { files: Record<string, string> }).files['one.md']
    await fake.refreshSurface(HISTORY_SURFACE)
    await fake.openItem(HISTORY_SURFACE, before)

    expect(notices(fake)).toEqual(['“one.md” did not exist in that version.'])
  })

  it('reloads the list instead of failing when the row is no longer there', async () => {
    const fake = await open()
    await fake.openItem(HISTORY_SURFACE, 'ffffffffffffffffffffffffffffffffffffffff')
    expect(notices(fake)).toEqual([])
    expect(list(fake).items).toEqual([])
  })
})

describe('Restore as New Version', () => {
  async function twoVersions(): Promise<{ fake: Fake; first: string; second: string }> {
    const fake = await open()
    const first = await saveVersion(fake, 'First pass', 'The old opening.', 30)
    const second = await saveVersion(fake, 'Second pass', 'A completely new opening.', 2)
    await fake.refreshSurface(HISTORY_SURFACE)
    return { fake, first, second }
  }

  it('puts the old text on the page in one undo step and saves it as a new version', async () => {
    const { fake, first } = await twoVersions()
    await fake.rowAction(HISTORY_SURFACE, RESTORE_ACTION, first)

    expect(fake.text()).toBe('The old opening.')
    expect(fake.edits).toHaveLength(1)
    expect(fake.edits[0]!.changes).toEqual([{ from: 0, to: 'A completely new opening.'.length, text: 'The old opening.' }])
    const [newest] = await fake.api.history.log()
    // The date is the version's own (local time zone), so it does not change as time passes.
    expect(newest!.message).toMatch(/^Restored “First pass” \(\d{1,2} Oct 2026\) on one\.md$/)
    expect(notices(fake)).toEqual(['Restored “First pass” as a new version.'])
  })

  it('never rewrites history: the old versions are untouched and one is added on top', async () => {
    const { fake, first, second } = await twoVersions()
    const before = (await fake.api.history.log()).map((c) => c.id)
    await fake.rowAction(HISTORY_SURFACE, RESTORE_ACTION, first)

    const after = await fake.api.history.log()
    expect(after.map((c) => c.id).slice(1)).toEqual(before)
    expect(after).toHaveLength(3)
    expect(await fake.api.history.show(second, 'one.md')).toBe('A completely new opening.')
    expect(list(fake).items.map((i) => i.label)[0]).toMatch(/^Restored “First pass”/)
  })

  it('says so, and changes nothing, when the page already matches that version', async () => {
    const { fake, second } = await twoVersions()
    await fake.rowAction(HISTORY_SURFACE, RESTORE_ACTION, second)

    expect(notices(fake)).toEqual(['This page already matches that version.'])
    expect(fake.edits).toEqual([])
    expect(fake.history.commits).toHaveLength(2)
  })

  it('asks for a page when none is open', async () => {
    const { fake, first } = await twoVersions()
    fake.api.workspace.current = () => ({ project, document: null })
    await fake.rowAction(HISTORY_SURFACE, RESTORE_ACTION, first)

    expect(notices(fake)).toEqual(['Open the page you want to restore, then choose a version.'])
    expect(fake.edits).toEqual([])
  })

  it('leaves the page alone and says why when it cannot be edited', async () => {
    const { fake, first } = await twoVersions()
    fake.api.editor.edit = () => {
      throw veneerError('vault/read-only', 'This page is read only.')
    }
    await fake.rowAction(HISTORY_SURFACE, RESTORE_ACTION, first)

    expect(notices(fake)).toEqual(['This page is read only.'])
    expect(fake.history.commits).toHaveLength(2)
  })

  it('tells the writer when the text is back on the page but could not be saved as a version', async () => {
    const { fake, first } = await twoVersions()
    fake.api.history.save = async () => {
      throw veneerError('history/failed', 'Veneer could not write to the project folder.')
    }
    await fake.rowAction(HISTORY_SURFACE, RESTORE_ACTION, first)

    expect(fake.text()).toBe('The old opening.')
    expect(notices(fake)).toHaveLength(1)
    expect(notices(fake)[0]).toMatch(/not saved as a version \(undo will bring your text back\)\. Veneer could not write/)
    expect(notices(fake)[0]!.length).toBeLessThanOrEqual(200)
  })

  it('says so when the page did not exist in that version, and edits nothing', async () => {
    const { fake, first } = await twoVersions()
    delete (fake.history.commits.find((c) => c.id === first) as unknown as { files: Record<string, string> }).files['one.md']
    await fake.rowAction(HISTORY_SURFACE, RESTORE_ACTION, first)

    expect(notices(fake)).toEqual(['“one.md” did not exist in that version.'])
    expect(fake.edits).toEqual([])
  })
})
