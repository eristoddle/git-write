import { describe, expect, it } from 'vitest'
import { NAME_RULE, nameProblem } from './names'

describe('nameProblem', () => {
  it.each(['darker-ending', 'draft_2', 'v1.0', 'endings/darker', 'A', '2nd-try'])('accepts %s', (name) => {
    expect(nameProblem(name)).toBeNull()
  })

  it('asks for a name when it is empty', () => {
    expect(nameProblem('')).toBe('Give it a name.')
  })

  it.each(['has space', 'épilogue', '-leading-dash', '.hidden', 'a..b', 'ends.lock', 'bad~name', 'a//b', '/lead', 'trail/', 'HEAD', 'col:on'])(
    'explains the rule for %s',
    (name) => {
      expect(nameProblem(name)).toBe(NAME_RULE)
    }
  )

  it('refuses very long names', () => {
    expect(nameProblem('a'.repeat(201))).toBe('That name is too long.')
    expect(nameProblem('a'.repeat(200))).toBeNull()
  })

  it('keeps reserved names for what they are for', () => {
    expect(nameProblem('feedback', ['feedback'])).toBe('That name is kept for readers’ feedback. Choose another.')
    expect(nameProblem('feedback-2', ['feedback'])).toBeNull()
  })
})
