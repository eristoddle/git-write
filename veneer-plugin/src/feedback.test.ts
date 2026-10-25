import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { parse as parseYaml } from 'yaml'
import { parseBody, readAnnotations, statusMessage, type Annotation } from './feedback'

const BODY = [
  'file_path: draft.md',
  'highlighted_text: some text',
  'start_line: 0',
  'end_line: 0',
  'comment: c',
  'author: a',
  'status: new'
].join('\n')

const commit = (id: string, body: string) => ({ id, body })
const original = (id: string, overrides = ''): ReturnType<typeof commit> => commit(id, `${BODY}\n${overrides}`)
const statusOf = (original_id: string, status: string): string =>
  BODY.replace('status: new', `status: ${status}`) + `\noriginal_annotation_id: ${original_id}\n`

describe('reading a commit body (the reader rules in docs/ANNOTATION_FORMAT.md)', () => {
  it('reads a plain annotation', () => {
    expect(parseBody(BODY)).toEqual({
      filePath: 'draft.md', text: 'some text', startLine: 0, endLine: 0, comment: 'c', author: 'a', status: 'new',
      prefix: null, suffix: null, offset: null, originalId: null
    })
  })

  it.each([
    ['unknown keys are ignored', `${BODY}\nextra_key: ignored\n`, true],
    ['an unknown status is skipped', BODY.replace('status: new', 'status: archived'), false],
    ['a missing required field is skipped', BODY.replace('status: new', ''), false],
    ['a wrong-typed line number is skipped', BODY.replace('start_line: 0', 'start_line: zero'), false],
    ['a negative line number is skipped', BODY.replace('start_line: 0', 'start_line: -1'), false],
    ['a fractional line number is skipped', BODY.replace('end_line: 0', 'end_line: 1.5'), false],
    ['a body that is a list is skipped', '- just\n- a list\n', false],
    ['a body that is a bare string is skipped', 'just a sentence', false],
    ['an empty body is skipped', '', false],
    ['invalid YAML is skipped, not fatal', 'file_path: [unclosed\n', false]
  ])('%s', (_name, body, readable) => {
    expect(parseBody(body) !== null).toBe(readable)
  })

  it.each(['prefix: [1, 2]', 'suffix: 5', 'offset: not-a-number', 'offset: -3', 'offset: true', 'offset: 1.5'])(
    'ignores a malformed anchor value (%s) but still reads the annotation',
    (bad) => {
      const body = parseBody(`${BODY}\n${bad}\n`)
      expect(body).not.toBeNull()
      expect([body?.prefix, body?.suffix, body?.offset]).toEqual([null, null, null])
    }
  )

  it('reads anchors when they are there, including empty strings (clipped at the file edge)', () => {
    const body = parseBody(`${BODY}\nprefix: ''\nsuffix: ' and after'\noffset: 12\n`)
    expect([body?.prefix, body?.suffix, body?.offset]).toEqual(['', ' and after', 12])
  })
})

describe('reading a feedback branch', () => {
  it('lists annotations oldest thread first, each at its latest status', () => {
    // Newest first, as api.history.log returns them.
    const log = [
      commit('s2', statusOf('a2', 'rejected')),
      commit('s1', statusOf('a1', 'accepted')),
      original('a2'),
      original('a1')
    ]
    const result = readAnnotations(log)

    expect(result.map((a) => [a.id, a.commitId, a.status])).toEqual([
      ['a1', 's1', 'accepted'],
      ['a2', 's2', 'rejected']
    ])
  })

  it('lets the last status win when it was changed more than once', () => {
    const log = [commit('s3', statusOf('a1', 'new')), commit('s2', statusOf('a1', 'rejected')), commit('s1', statusOf('a1', 'accepted')), original('a1')]
    expect(readAnnotations(log).map((a) => [a.id, a.commitId, a.status])).toEqual([['a1', 's3', 'new']])
  })

  it('skips the project\'s own history on the same branch, and anything malformed', () => {
    const log = [
      commit('p2', ''),
      original('a1'),
      commit('bad', 'file_path: only-this\n'),
      commit('p1', 'Chapter one, written by hand.')
    ]
    expect(readAnnotations(log).map((a) => a.id)).toEqual(['a1'])
  })

  it('returns nothing for an empty log', () => {
    expect(readAnnotations([])).toEqual([])
  })

  it('carries anchors through to the annotation', () => {
    const [one] = readAnnotations([original('a1', "prefix: 'before '\nsuffix: ' after'\noffset: 7\n")])
    expect([one?.prefix, one?.suffix, one?.offset]).toEqual(['before ', ' after', 7])
  })
})

interface Vectors {
  statusCommit: {
    annotationId: string
    created: Record<string, unknown>
    newStatus: 'accepted'
    subject: string
    body: Record<string, unknown>
    fieldOrder: string[]
  }
}
// What GitWrite's Python writes for the same change (tests/test_locate_vectors.py keeps this file true).
const { statusCommit } = JSON.parse(
  readFileSync(join(__dirname, '..', '..', 'docs', 'annotation-locate-vectors.json'), 'utf8')
) as Vectors

const fromCreated = (created: Record<string, unknown>, id: string): Annotation => ({
  id,
  commitId: id,
  filePath: created.file_path as string,
  text: created.highlighted_text as string,
  startLine: created.start_line as number,
  endLine: created.end_line as number,
  comment: created.comment as string,
  author: created.author as string,
  status: created.status as 'new',
  prefix: (created.prefix as string | undefined) ?? null,
  suffix: (created.suffix as string | undefined) ?? null,
  offset: (created.offset as number | undefined) ?? null
})

describe('the commit that records a status change', () => {
  const annotation = fromCreated(statusCommit.created, statusCommit.annotationId)
  const message = statusMessage(annotation, statusCommit.newStatus)
  const [subject, blank, ...rest] = message.split('\n')
  const body = rest.join('\n')

  it('has the same subject and fields, in the same order, as GitWrite writes', () => {
    expect(subject).toBe(statusCommit.subject)
    expect(blank).toBe('')
    const written = parse11(body)
    expect(written).toEqual(statusCommit.body)
    expect(Object.keys(written)).toEqual(statusCommit.fieldOrder)
  })

  it('reads back as the same annotation with the new status, under its original id', () => {
    const [read] = readAnnotations([{ id: 'newcommit', body }, { id: statusCommit.annotationId, body: yamlOf(statusCommit.created) }])
    expect(read).toMatchObject({ id: statusCommit.annotationId, commitId: 'newcommit', status: 'accepted' })
    expect(read?.text).toBe(annotation.text)
    expect([read?.prefix, read?.suffix, read?.offset]).toEqual([annotation.prefix, annotation.suffix, annotation.offset])
  })

  it('points at the annotation that was named, even if only its short form shows in the subject', () => {
    expect(parse11(body).original_annotation_id).toBe(statusCommit.annotationId)
    expect(subject).toContain(statusCommit.annotationId.slice(0, 7))
  })

  it('leaves out anchors an annotation never had, as GitWrite does', () => {
    const bare = { ...annotation, prefix: null, suffix: null, offset: null }
    const keys = Object.keys(parse11(statusMessage(bare, 'rejected').split('\n\n')[1] ?? ''))
    expect(keys).toEqual(['file_path', 'highlighted_text', 'start_line', 'end_line', 'comment', 'author', 'status', 'original_annotation_id'])
  })

  it('keeps awkward text exactly: colons, quotes, newlines, emoji, and strings that look like other types', () => {
    const awkward: Annotation = {
      ...annotation,
      text: 'He said: "no" — #hashtag, [brackets], {braces} 😀',
      comment: 'null',
      author: '123',
      prefix: 'line one\nline two\n  indented ',
      suffix: ' true'
    }
    const [read] = readAnnotations([{ id: 'c', body: statusMessage(awkward, 'accepted').split('\n\n').slice(1).join('\n\n') }])
    expect(read).toMatchObject({ text: awkward.text, comment: 'null', author: '123', prefix: awkward.prefix, suffix: ' true' })
  })

  // PyYAML (YAML 1.1) reads these as booleans, numbers and dates unless they are quoted; see feedback.ts.
  it.each(['yes', 'no', 'on', 'off', 'y', 'n', 'null', '~', 'true', 'False', '1_000', '0x1F', '1:30', '2026-10-25', '12e3', '0123', '', ' lead', 'trail ', 'a: b', '#c', '- d'])(
    'quotes the text %j so it comes back as the same text',
    (tricky) => {
      const written = statusMessage({ ...annotation, comment: tricky, text: tricky === '' ? 'x' : tricky }, 'accepted')
      const body = written.split('\n\n').slice(1).join('\n\n')
      const [read] = readAnnotations([{ id: 'c', body }])
      expect(read?.comment).toBe(tricky)
      expect(typeof parse11(body).comment).toBe('string')
    }
  )

  it('does not fold a long comment across lines', () => {
    const long = { ...annotation, comment: 'word '.repeat(60).trim() }
    const written = statusMessage(long, 'accepted')
    expect(written.split('\n').filter((l) => l.startsWith('comment:'))).toHaveLength(1)
    expect(written.split('\n').find((l) => l.startsWith('comment:'))?.length).toBeGreaterThan(200)
  })
})

const parse11 = (text: string): Record<string, unknown> => parseYaml(text, { version: '1.1' }) as Record<string, unknown>

function yamlOf(value: Record<string, unknown>): string {
  // The creation commit's body as GitWrite wrote it, rebuilt from the parsed vector.
  return statusMessage({ ...fromCreated(value, 'x'), status: value.status as 'new' }, value.status as 'new')
    .split('\n\n')
    .slice(1)
    .join('\n\n')
    .replace(/\noriginal_annotation_id: .*\n?$/, '\n')
}
