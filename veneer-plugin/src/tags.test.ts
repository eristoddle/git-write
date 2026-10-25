import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { FormView, ItemsView, PluginManifest } from '@veneer/api'
import { veneerError } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import { HISTORY_SURFACE } from './history'
import { start } from './index'
import { NAME_RULE } from './names'
import { NAME_COMMAND, NAME_SURFACE } from './tags'
import { LOOSE_FILE_SENTENCE } from './words'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest
const project = { name: 'Book', kind: 'project' as const }
const NOW = new Date('2026-10-25T12:00:00Z')
const HOUR = 3_600_000
const entry = { onload: (api: Parameters<typeof start>[0]) => start(api, { now: () => NOW }) }

type Fake = ReturnType<typeof createFakeHost>

async function open(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = createFakeHost(manifest, entry, { project, openPath: 'one.md', text: 'First.', ...options })
  await fake.load()
  return fake
}

async function saveVersion(fake: Fake, message: string, text: string, hoursAgo: number): Promise<string> {
  await fake.api.history.init()
  fake.changeText(text)
  const commit = await fake.api.history.save(message)
  fake.history.commits.find((c) => c.id === commit!.id)!.date = new Date(NOW.getTime() - hoursAgo * HOUR).toISOString()
  return commit!.id
}

const form = (fake: Fake): FormView => fake.views.get(NAME_SURFACE) as FormView
const field = (fake: Fake, id: string) => form(fake).fields.find((f) => f.id === id)!
const notices = (fake: Fake): string[] => fake.notices.map((n) => n.message)
const list = (fake: Fake): ItemsView => fake.views.get(HISTORY_SURFACE) as ItemsView

describe('Name a Version', () => {
  it('offers the recent versions, newest first and already chosen', async () => {
    const fake = await open()
    await saveVersion(fake, 'First pass', 'a', 49)
    const latest = await saveVersion(fake, 'Second pass', 'b', 3)
    await fake.run(NAME_COMMAND)

    expect(fake.shown).toContain(NAME_SURFACE)
    expect(field(fake, 'version').value).toBe(latest)
    expect(field(fake, 'version').options?.map((o) => o.label)).toEqual([
      'Second pass (3 hours ago)',
      'First pass (2 days ago)'
    ])
    expect(form(fake).submitLabel).toBe('Name version')
  })

  it('offers at most the latest twenty', async () => {
    const fake = await open()
    for (let i = 1; i <= 25; i++) await saveVersion(fake, `Version ${i}`, `t${i}`, 1)
    await fake.run(NAME_COMMAND)
    expect(field(fake, 'version').options).toHaveLength(20)
    expect(field(fake, 'version').options?.[0]?.label).toMatch(/^Version 25 /)
  })

  it('names the chosen version, with the note, and tells the writer', async () => {
    const fake = await open()
    const first = await saveVersion(fake, 'First pass', 'a', 49)
    await saveVersion(fake, 'Second pass', 'b', 3)
    await fake.run(NAME_COMMAND)
    await fake.formSubmit(NAME_SURFACE, { name: ' first-draft ', version: first, note: ' Sent to beta readers ' })

    expect([...fake.history.tags.entries()]).toEqual([['first-draft', { commit: first, message: 'Sent to beta readers' }]])
    expect(notices(fake)).toEqual(['Named “first-draft” for “First pass”.'])
    expect(fake.closed).toContain(NAME_SURFACE)
  })

  it('names the latest version without a note when nothing else is chosen', async () => {
    const fake = await open()
    const latest = await saveVersion(fake, 'Only version', 'a', 1)
    await fake.run(NAME_COMMAND)
    await fake.formSubmit(NAME_SURFACE, { name: 'v1', version: latest, note: '' })

    expect(fake.history.tags.get('v1')?.commit).toBe(latest)
    expect(fake.history.tags.get('v1')?.message).toBe('')
  })

  it('shows the names on the version list', async () => {
    const fake = await open()
    const first = await saveVersion(fake, 'First pass', 'a', 49)
    await saveVersion(fake, 'Second pass', 'b', 3)
    await fake.run(NAME_COMMAND)
    await fake.formSubmit(NAME_SURFACE, { name: 'first-draft', version: first, note: '' })
    await fake.api.history.createTag('sent', first)
    await fake.refreshSurface(HISTORY_SURFACE)

    expect(list(fake).items.map((i) => i.detail)).toEqual([
      'Fake Writer · 3 hours ago',
      'Fake Writer · 2 days ago · named “first-draft”, “sent”'
    ])
  })

  it('explains a name it cannot use and names nothing', async () => {
    const fake = await open()
    const latest = await saveVersion(fake, 'First', 'a', 1)
    await fake.run(NAME_COMMAND)
    await fake.formSubmit(NAME_SURFACE, { name: 'has space', version: latest, note: '' })
    expect(field(fake, 'name').error).toBe(NAME_RULE)

    await fake.formSubmit(NAME_SURFACE, { name: '', version: latest, note: '' })
    expect(field(fake, 'name').error).toBe('Give it a name.')
    expect(fake.history.tags.size).toBe(0)
    expect(fake.closed).not.toContain(NAME_SURFACE)
  })

  it('says when the name is taken, keeping what was typed', async () => {
    const fake = await open()
    const latest = await saveVersion(fake, 'First', 'a', 1)
    await fake.api.history.createTag('taken', latest)
    await fake.run(NAME_COMMAND)
    await fake.formSubmit(NAME_SURFACE, { name: 'taken', version: latest, note: 'My note' })

    expect(field(fake, 'name')).toMatchObject({ value: 'taken', error: 'That name is already in use. Choose another.' })
    expect(field(fake, 'note').value).toBe('My note')
    expect(fake.history.tags.size).toBe(1)
  })

  it('refuses a version that is not one of those offered', async () => {
    const fake = await open()
    await saveVersion(fake, 'First', 'a', 1)
    await fake.run(NAME_COMMAND)
    await fake.formSubmit(NAME_SURFACE, { name: 'v1', version: 'f'.repeat(40), note: '' })

    expect(field(fake, 'version').error).toBe('That version is no longer there. Choose another.')
    expect(field(fake, 'version').value).not.toBe('f'.repeat(40)) // a choice always holds one of its options
    expect(fake.history.tags.size).toBe(0)
  })

  it('keeps the form and says what went wrong when the host fails', async () => {
    const fake = await open()
    const latest = await saveVersion(fake, 'First', 'a', 1)
    fake.api.history.createTag = async () => {
      throw veneerError('history/failed', 'Veneer could not write to the project folder.')
    }
    await fake.run(NAME_COMMAND)
    await fake.formSubmit(NAME_SURFACE, { name: 'v1', version: latest, note: '' })

    expect(field(fake, 'name').error).toBe('Veneer could not write to the project folder.')
    expect(fake.closed).not.toContain(NAME_SURFACE)
  })

  it('keeps choices and typing while the form is open, and starts fresh next time', async () => {
    const fake = await open()
    const first = await saveVersion(fake, 'First', 'a', 49)
    await saveVersion(fake, 'Second', 'b', 3)
    await fake.run(NAME_COMMAND)
    await fake.formChange(NAME_SURFACE, 'name', 'draft')
    await fake.formChange(NAME_SURFACE, 'version', first)
    expect(field(fake, 'name').value).toBe('draft')
    expect(field(fake, 'version').value).toBe(first)

    await fake.run(NAME_COMMAND)
    expect(field(fake, 'name').value).toBe('')
  })

  it('says why it cannot start: a loose file, no history, no versions', async () => {
    const loose = await open({ project: { name: 'x.md', kind: 'loose' } })
    await loose.run(NAME_COMMAND)
    expect(notices(loose)).toEqual([LOOSE_FILE_SENTENCE])

    const none = await open()
    await none.run(NAME_COMMAND)
    expect(notices(none)).toEqual(['There are no versions to name yet. Save a version first.'])
    expect(none.shown).toEqual([])
  })
})
