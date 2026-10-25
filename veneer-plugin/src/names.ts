/**
 * Names of explorations and named versions. Veneer creates a branch or tag only from letters, digits,
 * `.`, `_` and `-`, with `/` between parts; a name that fails is explained here, in the writer's words,
 * before anything is asked of the host.
 */
const PART = /^[A-Za-z0-9_][A-Za-z0-9._-]*$/

export const NAME_RULE = 'Use letters, numbers, dashes, dots or underscores, with no spaces.'

/** Why `name` cannot be used, or null if it can. `reserved` are names kept for something else. */
export function nameProblem(name: string, reserved: readonly string[] = []): string | null {
  if (name === '') return 'Give it a name.'
  if (name.length > 200) return 'That name is too long.'
  if (!name.split('/').every((part) => PART.test(part)) || name.includes('..') || name.endsWith('.lock') || name === 'HEAD') {
    return NAME_RULE
  }
  if (reserved.includes(name)) return 'That name is kept for readers’ feedback. Choose another.'
  return null
}
