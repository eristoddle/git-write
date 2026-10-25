import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { DiffSegment, DiffView, ItemsView, PluginManifest } from '@veneer/api'
import { veneerError } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import { COMPARE_VERSIONS_COMMAND, COMPARE_WITH_PAGE_COMMAND, withChangeIds } from './compare'
import { COMPARE_SURFACE, HISTORY_SURFACE, SHOW_HISTORY_COMMAND } from './history'
import { start } from './index'
import { LOOSE_FILE_SENTENCE } from './words'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest
const project = { name: 'Book', kind: 'project' as const }
const NOW = new Date('2026-10-25T12:00:00Z')
const HOUR = 3_600_000
const entry = { onload: (api: Parameters<typeof start>[0]) => start(api, { now: () => NOW }) }

type Fake = ReturnType<typeof createFakeHost>

async function open(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = createFakeHost(manifest, entry, { project, openPath: 'one.md', text: '', ...options })
  await fake.load()
  return fake
}

async function saveVersion(fake: Fake, message: string, text: string, hoursAgo: number): Promise<string> {
  await fake.api.history.init()
  fake.changeText(text)
  const commit = await fake.api.history.save(message)
  if (commit === null) throw new Error('nothing to save')
  fake.history.commits.find((c) => c.id === commit.id)!.date = new Date(NOW.getTime() - hoursAgo * HOUR).toISOString()
  return commit.id
}

const list = (fake: Fake): ItemsView => fake.views.get(HISTORY_SURFACE) as ItemsView
const diff = (fake: Fake): DiffView => fake.views.get(COMPARE_SURFACE) as DiffView
const notices = (fake: Fake): string[] => fake.notices.map((n) => n.message)
const ids = (segments: readonly DiffSegment[]): string[] => [...new Set(segments.flatMap((s) => (s.id ? [s.id] : [])))]
const kinds = (segments: readonly DiffSegment[]): string[] => segments.map((s) => `${s.kind}:${s.text}`)

/** A page 'The quick brown fox jumps over the lazy dog.' with a saved version that differs in two places. */
async function pageVsVersion(): Promise<{ fake: Fake; version: string }> {
  const fake = await open()
  const version = await saveVersion(fake, 'Livelier fox', 'The fast brown fox leaps over the lazy dog.', 5)
  fake.changeText('The quick brown fox jumps over the lazy dog.')
  await fake.run(COMPARE_WITH_PAGE_COMMAND)
  await fake.openItem(HISTORY_SURFACE, version)
  return { fake, version }
}

describe('withChangeIds', () => {
  it('gives a replaced word one id (its delete and insert) and leaves equal text unnamed', () => {
    expect(
      withChangeIds([
        { kind: 'equal', text: 'a ' },
        { kind: 'delete', text: 'b' },
        { kind: 'insert', text: 'c' },
        { kind: 'equal', text: ' d ' },
        { kind: 'insert', text: 'e' }
      ])
    ).toEqual([
      { kind: 'equal', text: 'a ' },
      { kind: 'delete', text: 'b', id: 'c1' },
      { kind: 'insert', text: 'c', id: 'c1' },
      { kind: 'equal', text: ' d ' },
      { kind: 'insert', text: 'e', id: 'c2' }
    ])
  })
})

describe('Compare a Version with This Page', () => {
  it('says why it cannot start: a loose file, no page open, no versions yet', async () => {
    const loose = await open({ project: { name: 'x.md', kind: 'loose' } })
    await loose.run(COMPARE_WITH_PAGE_COMMAND)
    expect(notices(loose)).toEqual([LOOSE_FILE_SENTENCE])

    const noPage = await open({ openPath: undefined, text: null })
    await noPage.run(COMPARE_WITH_PAGE_COMMAND)
    expect(notices(noPage)).toEqual(['Open the page you want to compare, then try again.'])

    const noVersions = await open({ text: 'Words.' })
    await noVersions.run(COMPARE_WITH_PAGE_COMMAND)
    expect(notices(noVersions)).toEqual(['There are no versions to compare yet. Save a version first.'])
    expect(noVersions.shown).toEqual([])
  })

  it('asks which version, on the version list', async () => {
    const fake = await open({ text: 'Words.' })
    await saveVersion(fake, 'First', 'Words.', 1)
    await fake.run(COMPARE_WITH_PAGE_COMMAND)

    expect(fake.shown).toContain(HISTORY_SURFACE)
    expect(list(fake).note).toBe('Choose a version to compare with this page.')
  })

  it('draws page → version with a numbered change for each difference, and Accept/Reject on each', async () => {
    const { fake } = await pageVsVersion()

    expect(kinds(diff(fake).segments)).toEqual([
      'equal:The ',
      'delete:quick',
      'insert:fast',
      'equal: brown fox ',
      'delete:jumps',
      'insert:leaps',
      'equal: over the lazy dog.'
    ])
    expect(ids(diff(fake).segments)).toEqual(['c1', 'c2'])
    expect(diff(fake).note).toBe(
      'one.md compared with “Livelier fox”, 5 hours ago. Accept puts a change on the page; Reject keeps the page as it is.'
    )
    expect(fake.shown).toContain(COMPARE_SURFACE)
    expect(list(fake).note).toBeUndefined() // the question was answered
  })

  it('Accept puts that one change on the page in one undo step, and leaves the other to decide', async () => {
    const { fake } = await pageVsVersion()
    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c1')

    expect(fake.text()).toBe('The fast brown fox jumps over the lazy dog.')
    expect(fake.edits).toHaveLength(1)
    expect(fake.edits[0]!.changes).toEqual([{ from: 4, to: 9, text: 'fast' }])
    expect(kinds(diff(fake).segments)).toEqual([
      'equal:The fast brown fox ',
      'delete:jumps',
      'insert:leaps',
      'equal: over the lazy dog.'
    ])
    expect(ids(diff(fake).segments)).toEqual(['c2'])
  })

  it('Accept works from any position: the second change first, then the first', async () => {
    const { fake } = await pageVsVersion()
    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c2')
    expect(fake.text()).toBe('The quick brown fox leaps over the lazy dog.')
    expect(fake.edits[0]!.changes).toEqual([{ from: 20, to: 25, text: 'leaps' }])

    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c1')
    expect(fake.text()).toBe('The fast brown fox leaps over the lazy dog.')
    expect(fake.edits).toHaveLength(2) // one undo step each
    expect(ids(diff(fake).segments)).toEqual([])
    expect(diff(fake).note).toBe('one.md matches “Livelier fox”, 5 hours ago.')
  })

  it('Reject keeps the page\'s own words, edits nothing, and takes the change off the list', async () => {
    const { fake } = await pageVsVersion()
    await fake.diffAction(COMPARE_SURFACE, 'reject', 'c1')

    expect(fake.text()).toBe('The quick brown fox jumps over the lazy dog.')
    expect(fake.edits).toEqual([])
    expect(kinds(diff(fake).segments)).toEqual([
      'equal:The quick brown fox ',
      'delete:jumps',
      'insert:leaps',
      'equal: over the lazy dog.'
    ])
    expect(ids(diff(fake).segments)).toEqual(['c2'])
  })

  it('handles a sentence only the version has, and one only the page has', async () => {
    const fake = await open()
    const version = await saveVersion(fake, 'Has an ending', 'Start.\nAn ending only the version has.', 2)
    fake.changeText('Start.\nA line only the page has.')
    await fake.run(COMPARE_WITH_PAGE_COMMAND)
    await fake.openItem(HISTORY_SURFACE, version)
    for (const id of ids(diff(fake).segments)) await fake.diffAction(COMPARE_SURFACE, 'accept', id)

    expect(fake.text()).toBe('Start.\nAn ending only the version has.')
  })

  it('says the page matches when it matches, with nothing to accept', async () => {
    const fake = await open()
    const version = await saveVersion(fake, 'Same', 'Same words.', 1)
    await fake.run(COMPARE_WITH_PAGE_COMMAND)
    await fake.openItem(HISTORY_SURFACE, version)

    expect(diff(fake).note).toBe('one.md matches “Same”, 1 hour ago.')
    expect(ids(diff(fake).segments)).toEqual([])
  })

  it('redraws instead of acting on stale positions when the page changed after the comparison was drawn', async () => {
    const { fake } = await pageVsVersion()
    fake.changeText('Inserted by hand. The quick brown fox jumps over the lazy dog.')
    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c1')

    expect(fake.edits).toEqual([])
    expect(notices(fake)).toEqual(['The page changed, so the comparison was redrawn. Choose again.'])
    expect(kinds(diff(fake).segments).join('|')).toContain('Inserted by hand.')
    // The redrawn comparison works.
    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c1')
    expect(fake.edits).toHaveLength(1)
  })

  it('will not touch a different page than the one being compared', async () => {
    const { fake } = await pageVsVersion()
    fake.api.workspace.current = () => ({ project, document: 'two.md' })
    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c1')

    expect(fake.edits).toEqual([])
    expect(notices(fake)).toEqual(['This comparison is for “one.md”. Open that page to accept or reject its changes.'])
  })

  it('keeps the change on the list and says why when the page cannot be edited', async () => {
    const { fake } = await pageVsVersion()
    fake.api.editor.edit = () => {
      throw veneerError('vault/read-only', 'This page is read only.')
    }
    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c1')

    expect(notices(fake)).toEqual(['This page is read only.'])
    expect(ids(diff(fake).segments)).toEqual(['c1', 'c2'])
  })

  it('ignores an unknown change id', async () => {
    const { fake } = await pageVsVersion()
    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c99')

    expect(fake.edits).toEqual([])
    expect(ids(diff(fake).segments)).toEqual(['c1', 'c2'])
  })

  it('answers the question once: the next row opened is simply looked at', async () => {
    const { fake, version } = await pageVsVersion()
    await fake.openItem(HISTORY_SURFACE, version)

    expect(diff(fake).note).toMatch(/Read only\.$/)
    expect(ids(diff(fake).segments)).toEqual([])
  })

  it('drops the question when the history is opened plainly, or another project is opened', async () => {
    const fake = await open({ text: 'Words.' })
    await saveVersion(fake, 'First', 'Words.', 1)
    await fake.run(COMPARE_WITH_PAGE_COMMAND)
    await fake.run(SHOW_HISTORY_COMMAND)
    expect(list(fake).note).toBeUndefined()

    await fake.run(COMPARE_WITH_PAGE_COMMAND)
    await fake.switchProject({ name: 'Other', kind: 'project' })
    expect(list(fake).note).toBeUndefined()
  })

  it('says so when the open page did not exist in the chosen version', async () => {
    const fake = await open({ text: 'Words.' })
    const version = await saveVersion(fake, 'First', 'Words.', 1)
    delete (fake.history.commits.find((c) => c.id === version) as unknown as { files: Record<string, string> }).files['one.md']
    await fake.run(COMPARE_WITH_PAGE_COMMAND)
    await fake.openItem(HISTORY_SURFACE, version)

    expect(notices(fake)).toEqual(['“one.md” did not exist in that version.'])
  })
})

describe('Compare Two Versions', () => {
  async function threeVersions(): Promise<{ fake: Fake; a: string; b: string; c: string }> {
    const fake = await open()
    const a = await saveVersion(fake, 'Draft one', 'The old opening line.', 72)
    const b = await saveVersion(fake, 'Draft two', 'A new opening line.', 24)
    const c = await saveVersion(fake, 'Draft three', 'A new opening line, polished.', 1)
    return { fake, a, b, c }
  }

  it('asks for the two versions in turn, naming the first', async () => {
    const { fake, a } = await threeVersions()
    await fake.run(COMPARE_VERSIONS_COMMAND)
    expect(list(fake).note).toBe('Choose the first of the two versions to compare.')

    await fake.openItem(HISTORY_SURFACE, a)
    expect(list(fake).note).toBe('Now choose the other version to compare with “Draft one”.')
  })

  it('shows what changed from the older to the newer, read only, whichever order they are chosen in', async () => {
    const { fake, a, c } = await threeVersions()
    await fake.run(COMPARE_VERSIONS_COMMAND)
    await fake.openItem(HISTORY_SURFACE, c)
    await fake.openItem(HISTORY_SURFACE, a)

    expect(diff(fake).note).toBe(
      'one.md: changes from “Draft one” (3 days ago) to “Draft three” (1 hour ago). Read only.'
    )
    // Older text is what was deleted, newer text what was inserted.
    expect(kinds(diff(fake).segments)).toEqual([
      'delete:The old',
      'insert:A new',
      'equal: opening ',
      'delete:line.',
      'insert:line, polished.'
    ])
    expect(ids(diff(fake).segments)).toEqual([])
    expect(fake.shown).toContain(COMPARE_SURFACE)
    expect(list(fake).note).toBeUndefined()
  })

  it('has no Accept or Reject: choosing on a read-only comparison changes nothing', async () => {
    const { fake, a, b } = await threeVersions()
    await fake.run(COMPARE_VERSIONS_COMMAND)
    await fake.openItem(HISTORY_SURFACE, a)
    await fake.openItem(HISTORY_SURFACE, b)
    await fake.diffAction(COMPARE_SURFACE, 'accept', 'c1')

    expect(fake.edits).toEqual([])
    expect(fake.text()).toBe('A new opening line, polished.')
  })

  it('asks again, and says so, when the same version is chosen twice', async () => {
    const { fake, a, b } = await threeVersions()
    await fake.run(COMPARE_VERSIONS_COMMAND)
    await fake.openItem(HISTORY_SURFACE, a)
    await fake.openItem(HISTORY_SURFACE, a)

    expect(notices(fake)).toEqual(['Choose a different version to compare with.'])
    expect(list(fake).note).toBe('Now choose the other version to compare with “Draft one”.')
    await fake.openItem(HISTORY_SURFACE, b)
    expect(diff(fake).note).toMatch(/changes from “Draft one”/)
  })

  it('says why it cannot start when there is no page or no versions', async () => {
    const noPage = await open({ openPath: undefined, text: null })
    await noPage.run(COMPARE_VERSIONS_COMMAND)
    expect(notices(noPage)).toEqual(['Open the page you want to compare, then try again.'])

    const none = await open({ text: 'x' })
    await none.run(COMPARE_VERSIONS_COMMAND)
    expect(notices(none)).toEqual(['There are no versions to compare yet. Save a version first.'])
  })
})
