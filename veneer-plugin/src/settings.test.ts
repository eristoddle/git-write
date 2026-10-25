import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { PluginManifest } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import * as plugin from './index'
import { FEEDBACK_BRANCH_SETTING, feedbackBranch } from './settings'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest
const project = { name: 'Book', kind: 'project' as const }

async function branchFor(settings?: Record<string, string>): Promise<string> {
  const fake = createFakeHost(manifest, plugin, { project, settings })
  await fake.load()
  return feedbackBranch(fake.api)
}

describe('the feedback branch setting', () => {
  it('defaults to GitWrite\'s own branch name', async () => {
    expect(await branchFor()).toBe('feedback')
  })

  it('takes the writer\'s choice, trimmed', async () => {
    expect(await branchFor({ [FEEDBACK_BRANCH_SETTING]: '  readers  ' })).toBe('readers')
  })

  it('falls back to the default when it is cleared', async () => {
    expect(await branchFor({ [FEEDBACK_BRANCH_SETTING]: '   ' })).toBe('feedback')
  })
})
