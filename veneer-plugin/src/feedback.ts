/**
 * Reading and writing GitWrite's reader annotations in a feedback branch's commits
 * (docs/ANNOTATION_FORMAT.md). Pure: no host calls, so every rule is testable on its own.
 */
import { parse, stringify } from 'yaml'
import type { HistoryCommit } from '@veneer/api'
import type { Passage } from './locate'

/**
 * GitWrite writes and reads these commits with PyYAML, which follows YAML 1.1. The `yaml` library defaults to
 * 1.2, and the two disagree about what a plain string is: under 1.2 a comment of `yes`, `1_000`, `1:30` or
 * `2026-10-25` is written bare, and PyYAML reads it back as a boolean, a number or a date. So this plugin
 * uses 1.1 both ways (see docs/ANNOTATION_FORMAT.md).
 */
const YAML_1_1 = { version: '1.1' } as const

export const STATUSES = ['new', 'accepted', 'rejected'] as const
export type Status = (typeof STATUSES)[number]

export interface Annotation extends Passage {
  /** The commit that created it: the annotation's identity. */
  id: string
  /** The commit that recorded its current status. */
  commitId: string
  filePath: string
  comment: string
  author: string
  status: Status
}

const isStatus = (value: unknown): value is Status => STATUSES.includes(value as Status)
const isCount = (value: unknown): value is number => typeof value === 'number' && Number.isInteger(value) && value >= 0

interface Body {
  filePath: string
  text: string
  startLine: number
  endLine: number
  comment: string
  author: string
  status: Status
  prefix: string | null
  suffix: string | null
  offset: number | null
  originalId: string | null
}

/**
 * The annotation in a commit's message body, or null if the commit is not one (the feedback branch also
 * holds the project's own history). Anything missing or of the wrong type means "not one of ours": it is
 * skipped, never an error. Anchors are optional and a malformed one is ignored.
 */
export function parseBody(body: string): Body | null {
  let data: unknown
  try {
    data = parse(body, YAML_1_1)
  } catch {
    return null
  }
  if (data === null || typeof data !== 'object' || Array.isArray(data)) return null
  const d = data as Record<string, unknown>
  if (
    typeof d.file_path !== 'string' ||
    typeof d.highlighted_text !== 'string' ||
    !isCount(d.start_line) ||
    !isCount(d.end_line) ||
    typeof d.comment !== 'string' ||
    typeof d.author !== 'string' ||
    !isStatus(d.status)
  ) {
    return null
  }
  return {
    filePath: d.file_path,
    text: d.highlighted_text,
    startLine: d.start_line,
    endLine: d.end_line,
    comment: d.comment,
    author: d.author,
    status: d.status,
    prefix: typeof d.prefix === 'string' ? d.prefix : null,
    suffix: typeof d.suffix === 'string' ? d.suffix : null,
    offset: isCount(d.offset) ? d.offset : null,
    originalId: typeof d.original_annotation_id === 'string' && d.original_annotation_id !== '' ? d.original_annotation_id : null
  }
}

/**
 * The annotations in a feedback branch's log, each at its latest status. `commits` are newest first, as
 * `api.history.log` returns them; they are read oldest first, so a status commit replaces the state of the
 * annotation it points at. Annotations come back in the order their threads first appear.
 */
export function readAnnotations(commits: readonly Pick<HistoryCommit, 'id' | 'body'>[]): Annotation[] {
  const threads = new Map<string, Annotation>()
  for (const commit of [...commits].reverse()) {
    const body = parseBody(commit.body)
    if (body === null) continue
    const id = body.originalId ?? commit.id
    threads.set(id, {
      id,
      commitId: commit.id,
      filePath: body.filePath,
      text: body.text,
      startLine: body.startLine,
      endLine: body.endLine,
      comment: body.comment,
      author: body.author,
      status: body.status,
      prefix: body.prefix,
      suffix: body.suffix,
      offset: body.offset
    })
  }
  return [...threads.values()]
}

/**
 * The commit message that records a new status: the full annotation again with only `status` changed, and
 * `original_annotation_id` pointing at the commit that created it. Field order is the format's.
 */
export function statusMessage(annotation: Annotation, status: Status): string {
  const body: Record<string, unknown> = {
    file_path: annotation.filePath,
    highlighted_text: annotation.text,
    start_line: annotation.startLine,
    end_line: annotation.endLine,
    comment: annotation.comment,
    author: annotation.author,
    status
  }
  if (annotation.prefix !== null) body.prefix = annotation.prefix
  if (annotation.suffix !== null) body.suffix = annotation.suffix
  if (annotation.offset !== null) body.offset = annotation.offset
  body.original_annotation_id = annotation.id
  const subject = `Update status: ${annotation.filePath} (Annotation ${annotation.id.slice(0, 7)}) to ${status}`
  return `${subject}\n\n${stringify(body, { ...YAML_1_1, lineWidth: 0 })}`
}
