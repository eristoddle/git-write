import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { parse as parseYaml, stringify } from 'yaml'
import type { ItemsView, Mark, PluginManifest, VeneerEvent } from '@veneer/api'
import { veneerError } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import { ACCEPT_ACTION, FEEDBACK_SURFACE, MARK_SET, REJECT_ACTION, SHOW_FEEDBACK_COMMAND } from './annotations'
import * as plugin from './index'
import { LOOSE_FILE_SENTENCE } from './words'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest
const project = { name: 'Book', kind: 'project' as const }

const PAGE = 'The rain had not stopped for three days, and the river was rising.\nMarta counted the sandbags twice. Then she counted them again.\nBy evening the road was gone.\n'
const PASSAGE = 'Marta counted the sandbags twice.'

type Fake = ReturnType<typeof createFakeHost>

async function open(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = createFakeHost(manifest, plugin, {
    project,
    openPath: 'one.md',
    text: PAGE,
    files: { 'two.md': 'Second page text. A line to comment on.' },
    ...options
  })
  await fake.load()
  return fake
}

interface Note {
  comment?: string
  text?: string
  file?: string
  author?: string
  status?: string
  startLine?: number
  anchor?: boolean
}

/** Writes an annotation commit on the feedback branch the way GitWrite does. Returns its commit id. */
async function annotate(fake: Fake, note: Note = {}, branch = 'feedback'): Promise<string> {
  const h = fake.api.history
  if (!(await h.isRepository())) {
    await h.init()
    await h.save('First version')
  }
  if (!(await h.branches()).some((b) => b.name === branch)) await h.createBranch(branch)
  const text = note.text ?? PASSAGE
  const source = (note.file ?? 'one.md') === 'one.md' ? PAGE : 'Second page text. A line to comment on.'
  const at = source.indexOf(text)
  const body: Record<string, unknown> = {
    file_path: note.file ?? 'one.md',
    highlighted_text: text,
    start_line: note.startLine ?? source.slice(0, Math.max(at, 0)).split('\n').length - 1,
    end_line: note.startLine ?? source.slice(0, Math.max(at, 0)).split('\n').length - 1,
    comment: note.comment ?? 'Show her fear here.',
    author: note.author ?? 'reader@example.com',
    status: note.status ?? 'new'
  }
  if (note.anchor !== false && at >= 0) {
    body.prefix = source.slice(Math.max(0, at - 32), at)
    body.suffix = source.slice(at + text.length, at + text.length + 32)
    body.offset = at
  }
  const commit = await h.commitOn(branch, `Annotation: ${body.file_path}\n\n${stringify(body, { version: '1.1', lineWidth: 0 })}`, { allowEmpty: true })
  await emit(fake, { type: 'history:saved', commit })
  return commit.id
}

/** Delivers an event whose payload fields the generic type does not list. */
const emit = (fake: Fake, event: object): Promise<void> => fake.emit(event as VeneerEvent)

const marks = (fake: Fake): Mark[] => fake.marks.get(MARK_SET) ?? []
const list = (fake: Fake): ItemsView => fake.views.get(FEEDBACK_SURFACE) as ItemsView
const notices = (fake: Fake): string[] => fake.notices.map((n) => n.message)
const quoted = (fake: Fake, m: Mark): string => (fake.text() ?? '').slice(m.from, m.to)

describe('comments drawn on the page', () => {
  it('draws nothing, and says so, when there is no feedback branch', async () => {
    const fake = await open()
    expect(marks(fake)).toEqual([])
    expect(list(fake).empty?.text).toBe('No feedback on this page.')
    expect(notices(fake)).toEqual([])
  })

  it('marks each comment on the open page over its passage, by status, with who said what', async () => {
    const fake = await open()
    const first = await annotate(fake, { comment: 'Show her fear.', author: 'ann@x.org' })
    await annotate(fake, { text: 'the road was gone', comment: 'Too abrupt.', status: 'accepted', author: 'bo@x.org' })
    await annotate(fake, { text: 'rain had not stopped', comment: 'Cliché.', status: 'rejected', author: 'cy@x.org' })

    expect(marks(fake).map((m) => [quoted(fake, m), m.kind, m.label])).toEqual([
      [PASSAGE, 'note', 'ann@x.org: Show her fear.'],
      ['the road was gone', 'change', 'bo@x.org: Too abrupt.'],
      ['rain had not stopped', 'flag', 'cy@x.org: Cliché.']
    ])
    expect(marks(fake)[0]?.id).toBe(first)
  })

  it('leaves comments on other pages out of the marks, but counts them', async () => {
    const fake = await open()
    await annotate(fake)
    await annotate(fake, { file: 'two.md', text: 'A line to comment on.', comment: 'Elsewhere.' })

    expect(marks(fake)).toHaveLength(1)
    expect(list(fake).note).toBe('1 comment on this page, 1 new. 1 on other pages.')
  })

  it('lists the comments with the quoted passage, who, and the status', async () => {
    const fake = await open()
    await annotate(fake, { comment: 'Show her fear.', author: 'ann@x.org' })
    await annotate(fake, { text: 'the road was gone', comment: 'Too abrupt.', status: 'accepted', author: 'bo@x.org' })

    expect(list(fake).items.map((i) => [i.label, i.detail, i.kind])).toEqual([
      ['Show her fear.', '“Marta counted the sandbags twice.” · ann@x.org · new', 'file'],
      ['Too abrupt.', '“the road was gone” · bo@x.org · accepted', 'file']
    ])
    expect(list(fake).note).toBe('2 comments on this page, 1 new.')
  })

  it('draws marks again, in the right place, after the page is edited and saved', async () => {
    const fake = await open()
    await annotate(fake)
    fake.changeText('A brand new opening line.\n' + PAGE)
    await emit(fake, { type: 'vault:saved', path: 'one.md', content: fake.text() ?? '' })

    expect(marks(fake).map((m) => quoted(fake, m))).toEqual([PASSAGE])
    expect(marks(fake)[0]!.from).toBe(PAGE.indexOf(PASSAGE) + 'A brand new opening line.\n'.length)
  })

  it('finds a passage whose surroundings changed, and falls back to the line when it was rewritten', async () => {
    const fake = await open()
    await annotate(fake)
    fake.changeText(PAGE.replace('Then she counted them again.', 'She recounted.').replace('The rain had not stopped', 'Rain fell'))
    await emit(fake, { type: 'vault:saved', path: 'one.md', content: '' })
    expect(marks(fake).map((m) => quoted(fake, m))).toEqual([PASSAGE]) // the words alone still match

    fake.changeText(PAGE.replace(PASSAGE, 'Marta tallied every sandbag.'))
    await emit(fake, { type: 'vault:saved', path: 'one.md', content: '' })
    expect(marks(fake).map((m) => quoted(fake, m))).toEqual(['Marta tallied every sandbag. Then she counted them again.']) // her whole line
  })

  it('says so, and draws no mark, when even the line is gone', async () => {
    const fake = await open()
    await annotate(fake, { startLine: 40, text: 'a passage nobody can find' })

    expect(marks(fake)).toEqual([])
    expect(list(fake).items[0]?.detail).toContain('can’t find this passage on the page any more')
  })

  it('follows the writer to another page', async () => {
    const fake = await open()
    await annotate(fake)
    await annotate(fake, { file: 'two.md', text: 'A line to comment on.', comment: 'Elsewhere.' })
    await fake.api.workspace.open('two.md')
    await emit(fake, { type: 'document:opened', path: 'two.md' })

    expect(marks(fake).map((m) => quoted(fake, m))).toEqual(['A line to comment on.'])
    expect(list(fake).items.map((i) => i.label)).toEqual(['Elsewhere.'])
  })

  it('reads GitWrite-made comments that have no anchors', async () => {
    const fake = await open()
    await annotate(fake, { anchor: false })
    expect(marks(fake).map((m) => quoted(fake, m))).toEqual([PASSAGE])
  })

  it('skips the project\'s own commits and malformed comments on the same branch', async () => {
    const fake = await open()
    await annotate(fake)
    await fake.api.history.commitOn('feedback', 'Just a note\n\nnot yaml: [', { allowEmpty: true })
    await fake.api.history.commitOn('feedback', 'Missing fields\n\nfile_path: one.md\n', { allowEmpty: true })
    await fake.refreshSurface(FEEDBACK_SURFACE)

    expect(marks(fake)).toHaveLength(1)
    expect(notices(fake)).toEqual([])
  })

  it('never hands the kernel more marks than it takes', async () => {
    const fake = await open()
    await annotate(fake)
    const repeated = Array.from({ length: 3005 }, (_, i) => ({
      id: `c${i}`,
      body: stringify({ file_path: 'one.md', highlighted_text: PASSAGE, start_line: 1, end_line: 1, comment: `n${i}`, author: 'a', status: 'new' }),
      message: 'Annotation: one.md',
      author: { name: 'x', email: 'x' },
      date: new Date().toISOString(),
      parents: []
    }))
    fake.api.history.log = async () => repeated
    await fake.refreshSurface(FEEDBACK_SURFACE)

    expect(marks(fake)).toHaveLength(3000)
    expect(list(fake).items).toHaveLength(3005)
  })

  it('says when only the latest entries could be read', async () => {
    const fake = await open()
    await annotate(fake)
    const filler = Array.from({ length: 5000 }, (_, i) => ({
      id: `p${i}`, body: '', message: `Version ${i}`, author: { name: 'x', email: 'x' }, date: new Date().toISOString(), parents: []
    }))
    fake.api.history.log = async () => filler
    await fake.refreshSurface(FEEDBACK_SURFACE)

    expect(list(fake).empty?.text).toBe('No feedback on this page.')
    fake.api.history.log = async () => [...filler.slice(1), { ...filler[0]!, id: 'a1', body: stringify({ file_path: 'one.md', highlighted_text: PASSAGE, start_line: 1, end_line: 1, comment: 'c', author: 'a', status: 'new' }) }]
    await fake.refreshSurface(FEEDBACK_SURFACE)
    expect(list(fake).note).toContain('Only the latest 5000 entries were read.')
  })
})

describe('where the comments come from', () => {
  it('uses the branch the writer chose in Settings, and re-reads when it changes', async () => {
    const fake = await open({ settings: { 'gitwrite:feedback-branch': 'readers' } })
    await annotate(fake, { comment: 'On the readers branch.' }, 'readers')
    await annotate(fake, { comment: 'On the default branch.' }, 'feedback')
    expect(list(fake).items.map((i) => i.label)).toEqual(['On the readers branch.'])

    fake.setSetting('gitwrite:feedback-branch', 'feedback')
    await Promise.resolve()
    await fake.refreshSurface(FEEDBACK_SURFACE)
    expect(list(fake).items.map((i) => i.label)).toEqual(['On the default branch.'])
  })

  it('says why for a single loose file, and asks for a page when none is open', async () => {
    const loose = await open({ project: { name: 'x.md', kind: 'loose' } })
    expect(list(loose).empty?.text).toBe(LOOSE_FILE_SENTENCE)

    const none = await open({ openPath: undefined, text: null })
    await annotate(none)
    expect(list(none).empty?.text).toBe('Open a page to see the feedback on it.')
    expect(marks(none)).toEqual([])
  })

  it('explains a failure to read the history instead of showing nothing', async () => {
    const fake = await open()
    await annotate(fake)
    fake.api.history.log = async () => {
      throw veneerError('history/failed', 'Veneer could not read the project folder.')
    }
    await fake.refreshSurface(FEEDBACK_SURFACE)
    expect(list(fake).empty?.text).toBe('Veneer could not read the project folder.')
    expect(marks(fake)).toEqual([])
  })

  it('opens from its command', async () => {
    const fake = await open()
    await annotate(fake)
    await fake.run(SHOW_FEEDBACK_COMMAND)
    expect(fake.shown).toContain(FEEDBACK_SURFACE)
  })
})

describe('opening a comment', () => {
  it('clicking a mark shows the list with that comment in focus', async () => {
    const fake = await open()
    const id = await annotate(fake)
    await fake.markClick(MARK_SET, id)
    expect(fake.shown).toContain(FEEDBACK_SURFACE)
    expect(fake.shownFocus).toContain(id)
  })

  it('opening a row takes the writer to the passage, selected', async () => {
    const fake = await open()
    const id = await annotate(fake)
    await fake.openItem(FEEDBACK_SURFACE, id)

    const at = PAGE.indexOf(PASSAGE)
    expect(fake.selections).toEqual([{ path: 'one.md', from: at, to: at + PASSAGE.length }])
  })

  it('says so when the passage cannot be found', async () => {
    const fake = await open()
    const id = await annotate(fake, { startLine: 40, text: 'a passage nobody can find' })
    await fake.openItem(FEEDBACK_SURFACE, id)

    expect(notices(fake)).toEqual(['That passage can’t be found on this page any more.'])
    expect(fake.selections).toEqual([])
  })
})

describe('Accept and Reject', () => {
  const feedbackLog = async (fake: Fake) => fake.api.history.log({ branch: 'feedback' })

  it('records the decision as a new commit on the feedback branch, and updates the marks', async () => {
    const fake = await open()
    const id = await annotate(fake)
    await fake.rowAction(FEEDBACK_SURFACE, ACCEPT_ACTION, id)

    const [latest] = await feedbackLog(fake)
    expect(latest?.message).toBe(`Update status: one.md (Annotation ${id.slice(0, 7)}) to accepted`)
    expect(parseYaml(latest?.body ?? '', { version: '1.1' }).original_annotation_id).toBe(id)
    expect(latest?.body).toContain('status: accepted')
    expect(notices(fake)).toEqual(['Marked as accepted.'])
    expect(marks(fake)[0]?.kind).toBe('change')
    expect(list(fake).items[0]?.detail).toContain('accepted')
    expect(list(fake).note).toBe('1 comment on this page, 0 new.')
  })

  it('Reject works the same way, and a decision can be changed', async () => {
    const fake = await open()
    const id = await annotate(fake)
    await fake.rowAction(FEEDBACK_SURFACE, REJECT_ACTION, id)
    expect(marks(fake)[0]?.kind).toBe('flag')

    await fake.rowAction(FEEDBACK_SURFACE, ACCEPT_ACTION, id)
    expect(marks(fake)[0]?.kind).toBe('change')
    expect(list(fake).items).toHaveLength(1) // still one comment, now accepted
  })

  it('touches nothing of the writer\'s: no edit, no save, no commit on the current branch', async () => {
    const fake = await open()
    const id = await annotate(fake)
    const mainBefore = (await fake.api.history.log()).map((c) => c.id)
    await fake.rowAction(FEEDBACK_SURFACE, ACCEPT_ACTION, id)

    expect(fake.edits).toEqual([])
    expect(fake.text()).toBe(PAGE)
    expect((await fake.api.history.log()).map((c) => c.id)).toEqual(mainBefore)
    expect((await fake.api.history.branches()).find((b) => b.current)?.name).toBe('main')
  })

  it('says so, and writes nothing, when the comment already has that status', async () => {
    const fake = await open()
    const id = await annotate(fake, { status: 'accepted' })
    const before = (await feedbackLog(fake)).length
    await fake.rowAction(FEEDBACK_SURFACE, ACCEPT_ACTION, id)

    expect(notices(fake)).toEqual(['That comment is already accepted.'])
    expect((await feedbackLog(fake)).length).toBe(before)
  })

  it('says what went wrong, and changes nothing, if the host cannot record it', async () => {
    const fake = await open()
    const id = await annotate(fake)
    fake.api.history.commitOn = async () => {
      throw veneerError('history/failed', 'Veneer could not write to the project folder.')
    }
    await fake.rowAction(FEEDBACK_SURFACE, ACCEPT_ACTION, id)

    expect(notices(fake)).toEqual(['Veneer could not write to the project folder.'])
    expect(marks(fake)[0]?.kind).toBe('note')
  })

  it('still works when the writer clicks while the comments are being read again', async () => {
    const fake = await open()
    const id = await annotate(fake)
    const realLog = fake.api.history.log.bind(fake.api.history)
    let release: () => void = () => {}
    let slow = false
    fake.api.history.log = async (options) => {
      if (slow) await new Promise<void>((resolve) => (release = resolve))
      return realLog(options)
    }
    slow = true
    const reloading = fake.refreshSurface(FEEDBACK_SURFACE) // a reload is now waiting on the host
    await Promise.resolve()
    await Promise.resolve()
    slow = false
    const accepted = fake.rowAction(FEEDBACK_SURFACE, ACCEPT_ACTION, id)
    release()
    await Promise.all([reloading, accepted])

    expect(notices(fake)).toEqual(['Marked as accepted.'])
    expect(marks(fake)[0]?.kind).toBe('change')
  })

  it('reloads instead of failing when the comment is no longer there', async () => {
    const fake = await open()
    await annotate(fake)
    await fake.rowAction(FEEDBACK_SURFACE, ACCEPT_ACTION, 'f'.repeat(40))
    expect(notices(fake)).toEqual([])
  })

  it('writes to the branch the writer chose', async () => {
    const fake = await open({ settings: { 'gitwrite:feedback-branch': 'readers' } })
    const id = await annotate(fake, {}, 'readers')
    await fake.rowAction(FEEDBACK_SURFACE, REJECT_ACTION, id)

    const [latest] = await fake.api.history.log({ branch: 'readers' })
    expect(latest?.message).toContain('to rejected')
    expect((await fake.api.history.branches()).map((b) => b.name)).not.toContain('feedback')
  })
})
