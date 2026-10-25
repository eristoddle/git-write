import { isVeneerError } from '@veneer/api'
import type { FormView, HistorySyncResult, PluginApi } from '@veneer/api'
import { explainError, LOOSE_FILE_SENTENCE, shorten } from './words'

export const SYNC_COMMAND = 'gitwrite:sync'
export const CONNECT_COMMAND = 'gitwrite:connect-remote'
export const FORGET_COMMAND = 'gitwrite:forget-token'
export const CONNECT_SURFACE = 'gitwrite:connect'
export const USERNAME_SETTING = 'gitwrite:remote-username'

/** The name the access token is kept under in `api.secrets` (the system keychain). Never a setting. */
export const TOKEN_SECRET = 'remote-token'
const REMOTE = 'origin'

const NO_VERSIONS = 'Save a version first; then you can connect the project to a remote.'

/**
 * Why `address` cannot be used as a remote, or null. Only `https://` works (a token sent over plain http
 * travels unprotected, and Veneer cannot do SSH), and the address must not hold a user name or token:
 * those go in the token box, where they are kept out of the project.
 */
export function addressProblem(address: string): string | null {
  if (address === '') return 'Enter the address of your remote repository.'
  if (/^ssh:\/\//i.test(address) || /^[\w.-]+@[\w.-]+:/.test(address)) {
    return 'Only https:// addresses work in Veneer. This looks like an SSH address.'
  }
  let url: URL
  try {
    url = new URL(address)
  } catch {
    return 'That does not look like an address. It should start with https://'
  }
  if (url.protocol === 'http:') return 'Use an https:// address so your token is sent safely.'
  if (url.protocol !== 'https:') return 'That does not look like an address. It should start with https://'
  if (url.username !== '' || url.password !== '') {
    return 'Leave your user name and token out of the address; put the token in the box below.'
  }
  return null
}

const hostOf = (address: string): string => {
  try {
    return new URL(address).host
  } catch {
    return 'the remote'
  }
}

interface ConnectState {
  address?: string
  token?: string
  error?: { field: 'address' | 'token'; text: string }
}

/**
 * The connect form. The token box is always empty when drawn: a saved token is never shown again, only
 * mentioned. (The API has no masked field, so what is typed shows on screen while typing.)
 */
export function connectForm(options: { tokenSaved: boolean; current?: string; note?: string } & ConnectState): FormView {
  return {
    kind: 'form',
    note:
      (options.note === undefined ? '' : `${options.note} `) +
      `${options.tokenSaved ? 'An access token is already saved on this computer.' : 'No access token is saved yet.'} ` +
      'Syncing sends and brings in the exploration you are on; readers’ feedback is a separate branch and is not synced yet.',
    submitLabel: 'Connect',
    fields: [
      {
        id: 'address',
        type: 'text',
        label: 'Address',
        hint: 'The https:// address of your repository, like https://github.com/you/novel.git',
        placeholder: 'https://github.com/you/novel.git',
        value: options.address ?? options.current ?? '',
        error: options.error?.field === 'address' ? options.error.text : undefined
      },
      {
        id: 'token',
        type: 'text',
        label: 'Access token',
        hint: 'Kept in your computer’s keychain, never in the project or in Settings. Leave empty to keep the one already saved.',
        value: options.token ?? '',
        error: options.error?.field === 'token' ? options.error.text : undefined
      }
    ]
  }
}

/** A sentence for a finished sync: what came in, what went out. */
export function syncSentence(result: HistorySyncResult, host: string): string {
  if (result.upToDate && !result.fetched && !result.pushed) return `Already up to date with ${host}.`
  const parts: string[] = []
  if (result.fetched) parts.push(result.merged === 'merge' ? 'brought in their changes and merged them with yours' : 'brought in their changes')
  if (result.pushed) parts.push('sent yours')
  return parts.length === 0 ? `Already up to date with ${host}.` : `Synced with ${host}: ${parts.join(' and ')}.`
}

/**
 * Sync with a remote over HTTPS. The access token lives only in `api.secrets`: it is typed once into the
 * connect form, goes straight to the keychain, and is read back only to hand to `api.history.sync`. It is
 * never put in a view, a notice, a setting or a log, and a host message that happens to contain it is
 * cut out before it is shown.
 */
export function registerSync(api: PluginApi, options: { afterSync?: () => Promise<void> } = {}): void {
  let syncing = false
  let connecting = false
  const typed: ConnectState = {}
  let current: string | undefined

  const originAddress = async (): Promise<string | undefined> =>
    (await api.history.remotes()).find((r) => r.name === REMOTE)?.url

  /** Replaces the form with an empty one so nothing the writer typed lingers in the view after it closes. */
  async function scrub(): Promise<void> {
    const tokenSaved = (await api.secrets.get(TOKEN_SECRET)) !== null
    api.surfaces.setView(CONNECT_SURFACE, connectForm({ tokenSaved, current }))
  }

  /** Never show the token, even inside a message the host wrote. */
  async function redact(text: string): Promise<string> {
    const token = await api.secrets.get(TOKEN_SECRET).catch(() => null)
    return token === null || token === '' ? text : text.split(token).join('…')
  }

  async function say(message: string): Promise<void> {
    api.notify({ message: shorten(await redact(message), 200) })
  }

  /** The reasons a sync can fail, in a sentence each; anything else is the host's own plain sentence. */
  async function explainSync(err: unknown, host: string): Promise<string> {
    if (isVeneerError(err)) {
      if (err.code === 'plugin/declined') return `You did not allow Veneer to contact ${host}, so nothing was sent.`
      if (err.code === 'history/ssh-unsupported') return 'Only https:// addresses work. Use “Connect to a Remote” to change it.'
      if (err.code === 'history/conflict') {
        const said = err.message.trim()
        return `Couldn’t sync with ${host}. ${said}${/nothing (was )?changed/i.test(said) ? '' : ' Nothing was changed.'}`
      }
    }
    return explainError(err, 'sync')
  }

  async function begin(note?: string): Promise<void> {
    const { project } = api.workspace.current()
    if (project === null || project.kind !== 'project') {
      api.notify({ message: LOOSE_FILE_SENTENCE })
      return
    }
    try {
      if (!(await api.history.isRepository())) {
        api.notify({ message: NO_VERSIONS })
        return
      }
      current = await originAddress()
      typed.address = typed.token = typed.error = undefined // a fresh form each time
      const tokenSaved = (await api.secrets.get(TOKEN_SECRET)) !== null
      api.surfaces.setView(CONNECT_SURFACE, connectForm({ tokenSaved, current, note }))
      api.surfaces.show(CONNECT_SURFACE)
    } catch (err) {
      await say(explainError(err, 'open the connection form'))
    }
  }

  async function connect(values: Record<string, unknown>): Promise<void> {
    if (connecting) return
    const address = typeof values.address === 'string' ? values.address.trim() : ''
    const token = typeof values.token === 'string' ? values.token.trim() : ''
    const tokenSaved = (await api.secrets.get(TOKEN_SECRET)) !== null
    const redraw = (error?: ConnectState['error']): void =>
      api.surfaces.setView(CONNECT_SURFACE, connectForm({ tokenSaved, current, address, token, error }))
    const problem = addressProblem(address)
    if (problem !== null) {
      redraw({ field: 'address', text: problem })
      return
    }
    connecting = true
    try {
      try {
        await api.history.setRemote(REMOTE, address)
      } catch (err) {
        redraw({ field: 'address', text: await redact(explainError(err, 'use that address')) })
        return
      }
      current = address
      let saved = false
      if (token !== '') {
        try {
          await api.secrets.set(TOKEN_SECRET, token)
          saved = true
        } catch (err) {
          await scrub()
          api.surfaces.close(CONNECT_SURFACE)
          await say(`Connected to ${hostOf(address)}, but the token could not be saved on this computer. ${explainError(err, 'save it')}`)
          return
        }
      }
      await scrub()
      api.surfaces.close(CONNECT_SURFACE)
      await say(`Connected to ${hostOf(address)}.${saved ? ' Your token was saved on this computer.' : ''}`)
    } finally {
      connecting = false
    }
  }

  async function sync(): Promise<void> {
    if (syncing) return
    const { project } = api.workspace.current()
    if (project === null || project.kind !== 'project') {
      api.notify({ message: LOOSE_FILE_SENTENCE })
      return
    }
    syncing = true
    try {
      let address: string | undefined
      try {
        if (!(await api.history.isRepository())) {
          api.notify({ message: NO_VERSIONS })
          return
        }
        address = await originAddress()
      } catch (err) {
        await say(explainError(err, 'sync'))
        return
      }
      if (address === undefined) {
        await begin('This project is not connected to a remote yet.')
        return
      }
      const host = hostOf(address)
      const token = (await api.secrets.get(TOKEN_SECRET)) ?? undefined
      const user = String(await api.settings.get(USERNAME_SETTING)).trim()
      try {
        const result = await api.history.sync({
          remote: REMOTE,
          ...(token === undefined ? {} : { token }),
          ...(user === '' ? {} : { username: user })
        })
        await say(syncSentence(result, host))
        await options.afterSync?.()
      } catch (err) {
        await say(await explainSync(err, host))
      }
    } finally {
      syncing = false
    }
  }

  async function forget(): Promise<void> {
    if ((await api.secrets.get(TOKEN_SECRET)) === null) {
      api.notify({ message: 'No sync token is saved on this computer.' })
      return
    }
    await api.secrets.delete(TOKEN_SECRET)
    api.notify({ message: 'Forgot the saved sync token. You will need to enter it again to sync a private repository.' })
  }

  api.commands.handle(SYNC_COMMAND, sync)
  api.commands.handle(CONNECT_COMMAND, () => begin())
  api.commands.handle(FORGET_COMMAND, forget)

  // Keep what the writer has typed. The error goes once they change a field.
  api.surfaces.onFormChange(CONNECT_SURFACE, async (field, value) => {
    if (field === 'address') typed.address = typeof value === 'string' ? value : ''
    if (field === 'token') typed.token = typeof value === 'string' ? value : ''
    const tokenSaved = (await api.secrets.get(TOKEN_SECRET)) !== null
    api.surfaces.setView(CONNECT_SURFACE, connectForm({ tokenSaved, current, address: typed.address, token: typed.token }))
  })
  api.surfaces.onFormSubmit(CONNECT_SURFACE, connect)
}
