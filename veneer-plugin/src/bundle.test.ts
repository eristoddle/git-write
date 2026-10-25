import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import { build } from 'esbuild'

/**
 * Veneer loads the plugin as one ES module in a sandbox with no Node. A dependency's Node-flavoured build
 * (a `require('process')`, a `node:` import) would make it fail on load, and nothing else would notice,
 * so this builds it the way `npm run build` does and looks inside.
 */
describe('the bundled plugin', () => {
  it('is one self-contained ES module that exports onload and reaches for nothing from Node', async () => {
    const result = await build({
      entryPoints: [join(__dirname, 'index.ts')],
      bundle: true,
      format: 'esm',
      platform: 'neutral',
      write: false,
      logLevel: 'silent'
    })
    const code = result.outputFiles[0]!.text

    expect(code).toMatch(/export\s*\{[^}]*\bonload\b/)
    expect(code).not.toMatch(/^\s*import\s.*from\s/m) // nothing left to resolve at the writer's end
    expect(code).not.toMatch(/\brequire\s*\(|__require|\bprocess\.(env|versions|cwd)|from\s*["']node:/)
    expect(code).not.toMatch(/\b__dirname\b|\b__filename\b/)
    // yaml's binary-tag code mentions Buffer, but only after checking that it exists (atob is the fallback).
    expect(code).not.toMatch(/(?<!typeof )\bBuffer\.(from|alloc|concat)\b/)
  })
})
