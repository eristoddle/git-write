import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { codePointsBefore, locate, utf16Offset, type Passage } from './locate'

interface Vector {
  name: string
  text: string
  annotation: {
    highlighted_text: string
    start_line: number
    end_line: number
    prefix: string | null
    suffix: string | null
    offset: number | null
  }
  expected: { start: number; end: number; method: string } | null
}

// GitWrite's Python `locate` wrote these answers; docs/annotation-locate-vectors.json is checked against
// the Python code by tests/test_locate_vectors.py, so passing here means the two agree.
const vectors = (
  JSON.parse(readFileSync(join(__dirname, '..', '..', 'docs', 'annotation-locate-vectors.json'), 'utf8')) as {
    locate: Vector[]
  }
).locate

const passageOf = (v: Vector): Passage => ({
  text: v.annotation.highlighted_text,
  startLine: v.annotation.start_line,
  endLine: v.annotation.end_line,
  prefix: v.annotation.prefix,
  suffix: v.annotation.suffix,
  offset: v.annotation.offset
})

describe('locate agrees with GitWrite\'s Python locate on every shared case', () => {
  it('has the cases to check', () => {
    expect(vectors.length).toBeGreaterThan(20)
    expect(new Set(vectors.map((v) => v.expected?.method ?? null))).toEqual(new Set(['context', 'text', 'line', null]))
  })

  it.each(vectors.map((v) => [v.name, v] as const))('%s', (_name, vector) => {
    const found = locate(passageOf(vector), vector.text)
    if (vector.expected === null) {
      expect(found).toBeNull()
      return
    }
    expect(found).not.toBeNull()
    // Python counts code points; the editor counts UTF-16 units. Compare in code points.
    expect({
      start: codePointsBefore(vector.text, found!.start),
      end: codePointsBefore(vector.text, found!.end),
      method: found!.method
    }).toEqual(vector.expected)
  })
})

describe('code points and UTF-16', () => {
  const text = 'a😀b😀😀c'

  it('counts a surrogate pair once', () => {
    expect(codePointsBefore(text, 0)).toBe(0)
    expect(codePointsBefore(text, 1)).toBe(1)
    expect(codePointsBefore(text, 3)).toBe(2) // after "a😀"
    expect(codePointsBefore(text, text.length)).toBe(6)
  })

  it('turns a code-point count back into a UTF-16 offset, and round-trips', () => {
    for (let count = 0; count <= 6; count++) {
      expect(codePointsBefore(text, utf16Offset(text, count))).toBe(count)
    }
    expect(utf16Offset(text, 99)).toBe(text.length)
  })

  it('gives the mark range in UTF-16 so it lines up with the editor text', () => {
    const emoji = '😀😀 target here'
    const found = locate({ text: 'target', startLine: 0, endLine: 0, prefix: null, suffix: null, offset: null }, emoji)
    expect(emoji.slice(found!.start, found!.end)).toBe('target')
    expect(found!.start).toBe(5) // two emoji are four UTF-16 units, plus the space
  })
})
