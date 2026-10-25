import type { PluginApi } from '@veneer/api'

/**
 * GitWrite for Veneer. Each feature attaches its handlers here; nothing runs at load (the kernel
 * wakes the plugin on first use of a command or surface declared in manifest.json).
 */
export function onload(api: PluginApi): void {
  void api
}
