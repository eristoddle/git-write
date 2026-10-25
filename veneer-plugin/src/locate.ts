/**
 * Finding an annotated passage again after the page has changed (D15, docs/ANNOTATION_FORMAT.md).
 *
 * This is GitWrite's Python `locate` in TypeScript, kept identical by docs/annotation-locate-vectors.json,
 * which both sides test against. It does its own exact matching instead of `findInText`, which is
 * case-insensitive and skips overlapping matches: either would find different passages than GitWrite does.
 *
 * Positions returned are UTF-16 offsets into `text`, which is what the editor's marks use. The stored
 * `offset` is in Unicode code points (as the format says), so distances are measured in code points.
 */

/** What `locate` needs of an annotation. */
export interface Passage {
  text: string
  startLine: number
  endLine: number
  prefix: string | null
  suffix: string | null
  /** Where the highlight started, in code points. */
  offset: number | null
}

export interface Location {
  /** UTF-16 offsets: the passage is `text.slice(start, end)`. */
  start: number
  end: number
  method: 'context' | 'text' | 'line'
}

function occurrences(text: string, needle: string): number[] {
  const found: number[] = []
  let index = text.indexOf(needle)
  while (index !== -1) {
    found.push(index)
    index = text.indexOf(needle, index + 1) // overlapping matches count
  }
  return found
}

/** How many Unicode code points come before UTF-16 offset `index`. */
export function codePointsBefore(text: string, index: number): number {
  let count = 0
  for (let i = 0; i < index; i++) {
    const unit = text.charCodeAt(i)
    const isHighSurrogate = unit >= 0xd800 && unit <= 0xdbff
    if (isHighSurrogate && i + 1 < index) i += 1 // the pair is one code point
    count += 1
  }
  return count
}

/** The UTF-16 offset of the `count`-th code point, for turning a stored code-point offset into a position. */
export function utf16Offset(text: string, count: number): number {
  let index = 0
  for (let seen = 0; seen < count && index < text.length; seen++) {
    const unit = text.charCodeAt(index)
    index += unit >= 0xd800 && unit <= 0xdbff && index + 1 < text.length ? 2 : 1
  }
  return index
}

const lineOf = (text: string, index: number): number => {
  let lines = 0
  for (let i = text.indexOf('\n'); i !== -1 && i < index; i = text.indexOf('\n', i + 1)) lines += 1
  return lines
}

/** Among duplicate matches: nearest the stored offset, else nearest the stored line; ties go to the earlier. */
function closest(candidates: number[], text: string, passage: Passage, shift: number): number {
  if (candidates.length === 1) return candidates[0] as number
  const key =
    passage.offset !== null
      ? (c: number): number => Math.abs(codePointsBefore(text, c + shift) - (passage.offset as number))
      : (c: number): number => Math.abs(lineOf(text, c + shift) - passage.startLine)
  return candidates.reduce((best, c) => (key(c) < key(best) ? c : best), candidates[0] as number)
}

/**
 * Finds `passage` in `text`: first by its context (prefix + text + suffix), then by the text alone, then
 * by its stored lines. Returns null only when even the lines are gone.
 */
export function locate(passage: Passage, text: string): Location | null {
  if (passage.text !== '') {
    if (passage.prefix !== null || passage.suffix !== null) {
      const prefix = passage.prefix ?? ''
      const suffix = passage.suffix ?? ''
      const hits = occurrences(text, prefix + passage.text + suffix)
      if (hits.length > 0) {
        const start = closest(hits, text, passage, prefix.length) + prefix.length
        return { start, end: start + passage.text.length, method: 'context' }
      }
    }
    const hits = occurrences(text, passage.text)
    if (hits.length > 0) {
      const start = closest(hits, text, passage, 0)
      return { start, end: start + passage.text.length, method: 'text' }
    }
  }

  const starts = [0]
  for (let i = text.indexOf('\n'); i !== -1; i = text.indexOf('\n', i + 1)) starts.push(i + 1)
  if (passage.startLine >= starts.length) return null
  const last = Math.max(passage.startLine, Math.min(passage.endLine, starts.length - 1))
  const start = starts[passage.startLine] as number
  let end = last + 1 < starts.length ? (starts[last + 1] as number) - 1 : text.length
  if (end > start && text[end - 1] === '\r') end -= 1
  return { start, end: Math.max(start, end), method: 'line' }
}
