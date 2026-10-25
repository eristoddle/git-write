import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { PluginManifest } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import * as plugin from './index'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest

describe('manifest', () => {
  it('names the plugin and the API range it was built for', () => {
    expect(manifest.id).toBe('gitwrite')
    expect(manifest.apiVersion).toBe('^0.40.0')
    expect(manifest.main).toBe('main.js')
  })

  it('declares every contribution once, under the plugin id, with writer words as titles', () => {
    const commands = manifest.contributes?.commands ?? []
    const surfaces = manifest.contributes?.surfaces ?? []
    const ids = [
      ...commands.map((c) => c.id),
      ...surfaces.map((s) => s.id),
      ...surfaces.flatMap((s) => (s.rowActions ?? []).map((a) => a.id))
    ]
    expect(new Set(ids).size).toBe(ids.length)
    for (const id of ids) expect(id).toMatch(/^gitwrite:[a-z]+(-[a-z]+)*$/)
    expect(commands.map((c) => c.title)).toEqual([
      'Save a Version',
      'Show Version History',
      'Compare Two Versions',
      'Compare a Version with This Page',
      'Show Explorations',
      'Start an Exploration'
    ])
    // Git's own words stay out of what the writer reads.
    const titles = [...commands.map((c) => c.title), ...surfaces.map((s) => s.title)].join(' ')
    expect(titles).not.toMatch(/commit|branch|checkout|revert/i)
  })

  it('loads on the fake host, changes nothing, and lets go of everything when unloaded', async () => {
    const fake = createFakeHost(manifest, plugin)
    await fake.load()
    expect([...fake.views.keys()].sort()).toEqual(['gitwrite:explorations', 'gitwrite:history'])
    expect(fake.edits).toEqual([])
    expect(fake.notices).toEqual([])
    expect(fake.history.commits).toEqual([])
    await fake.unload()
    expect(fake.liveDisposables()).toBe(0)
  })
})
