import type { PluginApi } from '@veneer/api'
import { registerCompare } from './compare'
import { registerExplorations } from './explorations'
import { registerHistory } from './history'
import { registerSave } from './save'

export interface Options {
  /** The clock, so a test can pin "3 days ago". */
  now?: () => Date
}

/** Wires every feature. Exported separately from `onload` so tests can pass a fixed clock. */
export async function start(api: PluginApi, options: Options = {}): Promise<void> {
  // The list needs the save form (its empty state offers it), the form needs the list (it refreshes it).
  let beginSave: () => Promise<void> = async () => {}
  const history = registerHistory(api, { beginSave: () => beginSave(), now: options.now })
  beginSave = registerSave(api, history.refresh).begin
  registerCompare(api, history)
  const explorations = registerExplorations(api, { beginSave: () => beginSave() })
  await Promise.all([history.refresh(), explorations.refresh()])
}

/**
 * GitWrite for Veneer. Each feature attaches its handlers by the ids in manifest.json. The kernel
 * wakes the plugin on first use of a command or surface, so loading only hands over the first
 * version list.
 */
export function onload(api: PluginApi): Promise<void> {
  return start(api)
}
