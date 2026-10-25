import { readFileSync } from 'node:fs'
import { join } from 'node:path'
import { describe, expect, it } from 'vitest'
import type { FormView, HistorySyncResult, PluginManifest } from '@veneer/api'
import { veneerError } from '@veneer/api'
import { createFakeHost } from '@veneer/api/testing'
import * as plugin from './index'
import { addressProblem, CONNECT_COMMAND, CONNECT_SURFACE, FORGET_COMMAND, SYNC_COMMAND, syncSentence, TOKEN_SECRET } from './sync'
import { LOOSE_FILE_SENTENCE } from './words'

const manifest = JSON.parse(readFileSync(join(__dirname, '..', 'manifest.json'), 'utf8')) as PluginManifest
const project = { name: 'Book', kind: 'project' as const }
const ADDRESS = 'https://github.com/writer/novel.git'
const TOKEN = 'ghp_SECRET0123456789tokenvalue'

type Fake = ReturnType<typeof createFakeHost>

async function open(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = createFakeHost(manifest, plugin, { project, openPath: 'one.md', text: 'First draft.', ...options })
  await fake.load()
  return fake
}

/** A project with one saved version. */
async function withHistory(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = await open(options)
  await fake.api.history.init()
  await fake.api.history.save('First version')
  return fake
}

/** A project with a version, an origin, and a saved token. */
async function connected(options: Parameters<typeof createFakeHost>[2] = {}): Promise<Fake> {
  const fake = await withHistory(options)
  await fake.api.history.setRemote('origin', ADDRESS)
  await fake.api.secrets.set(TOKEN_SECRET, TOKEN)
  return fake
}

const form = (fake: Fake): FormView => fake.views.get(CONNECT_SURFACE) as FormView
const field = (fake: Fake, id: string) => form(fake).fields.find((f) => f.id === id)!
const notices = (fake: Fake): string[] => fake.notices.map((n) => n.message)
const result = (over: Partial<HistorySyncResult> = {}): HistorySyncResult => ({
  fetched: false, merged: 'none', pushed: false, upToDate: true, commit: null, ...over
})

/** Everything the plugin has put anywhere a person or a log could read it, as one string. */
function everythingVisible(fake: Fake): string {
  return JSON.stringify({
    views: [...fake.views.entries()],
    notices: fake.notices,
    marks: [...fake.marks.entries()],
    projectData: [...fake.projectData.entries()],
    edits: fake.edits,
    created: fake.created,
    net: fake.netRequests
  })
}

describe('addressProblem', () => {
  it.each([ADDRESS, 'https://git.example.org/me/book', 'https://gitea.local:3000/me/book.git'])('accepts %s', (a) => {
    expect(addressProblem(a)).toBeNull()
  })

  it.each([
    ['', 'Enter the address of your remote repository.'],
    ['git@github.com:writer/novel.git', 'Only https:// addresses work in Veneer. This looks like an SSH address.'],
    ['ssh://git@github.com/writer/novel.git', 'Only https:// addresses work in Veneer. This looks like an SSH address.'],
    ['http://example.com/me/book.git', 'Use an https:// address so your token is sent safely.'],
    ['https://me:secret@example.com/book.git', 'Leave your user name and token out of the address; put the token in the box below.'],
    ['https://ghp_abc@example.com/book.git', 'Leave your user name and token out of the address; put the token in the box below.'],
    ['not an address', 'That does not look like an address. It should start with https://'],
    ['ftp://example.com/x', 'That does not look like an address. It should start with https://'],
    ['file:///tmp/repo', 'That does not look like an address. It should start with https://']
  ])('explains %j', (address, sentence) => {
    expect(addressProblem(address)).toBe(sentence)
  })
})

describe('syncSentence', () => {
  it.each([
    [result(), 'Already up to date with github.com.'],
    [result({ fetched: true, merged: 'fast-forward', upToDate: false }), 'Synced with github.com: brought in their changes.'],
    [result({ fetched: true, merged: 'merge', pushed: true, upToDate: false }), 'Synced with github.com: brought in their changes and merged them with yours and sent yours.'],
    [result({ pushed: true, upToDate: false }), 'Synced with github.com: sent yours.'],
    [result({ fetched: true, pushed: true, merged: 'fast-forward', upToDate: false }), 'Synced with github.com: brought in their changes and sent yours.']
  ])('says what moved', (r, sentence) => {
    expect(syncSentence(r, 'github.com')).toBe(sentence)
  })
})

describe('Connect to a Remote', () => {
  it('needs a saved version first, and a project', async () => {
    const none = await open()
    await none.run(CONNECT_COMMAND)
    expect(notices(none)).toEqual(['Save a version first; then you can connect the project to a remote.'])

    const loose = await open({ project: { name: 'x.md', kind: 'loose' } })
    await loose.run(CONNECT_COMMAND)
    expect(notices(loose)).toEqual([LOOSE_FILE_SENTENCE])
    expect(none.shown.concat(loose.shown)).toEqual([])
  })

  it('opens a form, with the current address filled in and the token box always empty', async () => {
    const fake = await connected()
    await fake.run(CONNECT_COMMAND)

    expect(fake.shown).toContain(CONNECT_SURFACE)
    expect(field(fake, 'address').value).toBe(ADDRESS)
    expect(field(fake, 'token').value).toBe('')
    expect(form(fake).note).toContain('An access token is already saved on this computer.')
    expect(form(fake).note).toContain('readers’ feedback is a separate branch and is not synced yet')
    expect(JSON.stringify(form(fake))).not.toContain(TOKEN)
  })

  it('says no token is saved when there is none', async () => {
    const fake = await withHistory()
    await fake.run(CONNECT_COMMAND)
    expect(form(fake).note).toContain('No access token is saved yet.')
  })

  it('sets the remote and keeps the token in the keychain, telling the writer without repeating either', async () => {
    const fake = await withHistory()
    await fake.run(CONNECT_COMMAND)
    await fake.formSubmit(CONNECT_SURFACE, { address: `  ${ADDRESS}  `, token: `  ${TOKEN}  ` })

    expect(await fake.api.history.remotes()).toEqual([{ name: 'origin', url: ADDRESS }])
    expect(fake.secrets.get(TOKEN_SECRET)).toBe(TOKEN)
    expect(notices(fake)).toEqual(['Connected to github.com. Your token was saved on this computer.'])
    expect(fake.closed).toContain(CONNECT_SURFACE)
  })

  it('keeps the saved token when the token box is left empty', async () => {
    const fake = await connected()
    await fake.run(CONNECT_COMMAND)
    await fake.formSubmit(CONNECT_SURFACE, { address: 'https://gitea.example.org/me/novel.git', token: '' })

    expect(fake.secrets.get(TOKEN_SECRET)).toBe(TOKEN)
    expect((await fake.api.history.remotes())[0]?.url).toBe('https://gitea.example.org/me/novel.git')
    expect(notices(fake)).toEqual(['Connected to gitea.example.org.'])
  })

  it('refuses a bad address with a reason under the box, keeps what was typed, and changes nothing', async () => {
    const fake = await withHistory()
    await fake.run(CONNECT_COMMAND)
    await fake.formSubmit(CONNECT_SURFACE, { address: 'git@github.com:writer/novel.git', token: TOKEN })

    expect(field(fake, 'address').error).toBe('Only https:// addresses work in Veneer. This looks like an SSH address.')
    expect(field(fake, 'address').value).toBe('git@github.com:writer/novel.git')
    expect(field(fake, 'token').value).toBe(TOKEN) // theirs to fix, not to retype
    expect(await fake.api.history.remotes()).toEqual([])
    expect(fake.secrets.size).toBe(0)
    expect(fake.closed).not.toContain(CONNECT_SURFACE)
  })

  it('says what went wrong when the host refuses the address', async () => {
    const fake = await withHistory()
    fake.api.history.setRemote = async () => {
      throw veneerError('history/invalid', 'That address is not one Veneer can use.')
    }
    await fake.run(CONNECT_COMMAND)
    await fake.formSubmit(CONNECT_SURFACE, { address: ADDRESS, token: TOKEN })

    expect(field(fake, 'address').error).toBe('That address is not one Veneer can use.')
    expect(fake.secrets.size).toBe(0) // no token is kept for an address that was not accepted
  })

  it('says the token could not be saved, if the keychain refuses', async () => {
    const fake = await withHistory()
    fake.api.secrets.set = async () => {
      throw veneerError('secrets/keychain-unavailable', 'The system keychain would not take it.')
    }
    await fake.run(CONNECT_COMMAND)
    await fake.formSubmit(CONNECT_SURFACE, { address: ADDRESS, token: TOKEN })

    expect(notices(fake)).toEqual(['Connected to github.com, but the token could not be saved on this computer. The system keychain would not take it.'])
    expect(everythingVisible(fake)).not.toContain(TOKEN)
  })

  it('keeps what is typed while the form is open', async () => {
    const fake = await withHistory()
    await fake.run(CONNECT_COMMAND)
    await fake.formChange(CONNECT_SURFACE, 'address', 'https://git.example.org/a.git')
    expect(field(fake, 'address').value).toBe('https://git.example.org/a.git')
  })

  it('leaves no trace of the token in any view after a connect', async () => {
    const fake = await withHistory()
    await fake.run(CONNECT_COMMAND)
    await fake.formChange(CONNECT_SURFACE, 'token', TOKEN)
    await fake.formSubmit(CONNECT_SURFACE, { address: ADDRESS, token: TOKEN })

    expect(everythingVisible(fake)).not.toContain(TOKEN)
    expect(field(fake, 'token').value).toBe('')
  })
})

describe('Sync with Remote', () => {
  it('says why it cannot start: a loose file, no versions', async () => {
    const loose = await open({ project: { name: 'x.md', kind: 'loose' } })
    await loose.run(SYNC_COMMAND)
    expect(notices(loose)).toEqual([LOOSE_FILE_SENTENCE])

    const none = await open()
    await none.run(SYNC_COMMAND)
    expect(notices(none)).toEqual(['Save a version first; then you can connect the project to a remote.'])
  })

  it('opens the connect form, saying why, when there is no remote yet', async () => {
    const fake = await withHistory()
    await fake.run(SYNC_COMMAND)

    expect(fake.shown).toContain(CONNECT_SURFACE)
    expect(form(fake).note).toMatch(/^This project is not connected to a remote yet\./)
    expect(fake.history.syncs).toEqual([])
  })

  it('syncs origin with the saved token and the writer\'s user name, and tells the writer what moved', async () => {
    const fake = await connected({ settings: { 'gitwrite:remote-username': 'me' } })
    fake.history.syncResult = result({ fetched: true, merged: 'fast-forward', pushed: true, upToDate: false })
    await fake.run(SYNC_COMMAND)

    expect(fake.history.syncs).toEqual([{ remote: 'origin', token: TOKEN, username: 'me' }])
    expect(notices(fake)).toEqual(['Synced with github.com: brought in their changes and sent yours.'])
  })

  it('sends no token and no user name when there are none (a public repository)', async () => {
    const fake = await withHistory()
    await fake.api.history.setRemote('origin', ADDRESS)
    await fake.run(SYNC_COMMAND)

    expect(fake.history.syncs).toEqual([{ remote: 'origin' }])
  })

  it('says it is up to date when nothing moved', async () => {
    const fake = await connected()
    fake.history.syncResult = result()
    await fake.run(SYNC_COMMAND)
    expect(notices(fake)).toEqual(['Already up to date with github.com.'])
  })

  it('never changes the writer\'s page itself', async () => {
    const fake = await connected()
    await fake.run(SYNC_COMMAND)
    expect(fake.edits).toEqual([])
    expect(fake.text()).toBe('First draft.')
  })

  it.each([
    [veneerError('history/conflict', 'Syncing conflicts in one.md; nothing changed.'), 'Couldn’t sync with github.com. Syncing conflicts in one.md; nothing changed.'],
    [veneerError('history/conflict', 'Both changed one.md and two.md.'), 'Couldn’t sync with github.com. Both changed one.md and two.md. Nothing was changed.'],
    [veneerError('history/uncommitted', 'Save a point before syncing.'), 'Your project has changes that are not in a version yet. Use “Save a Version”, then try again.'],
    [veneerError('plugin/declined', 'declined'), 'You did not allow Veneer to contact github.com, so nothing was sent.'],
    [veneerError('history/ssh-unsupported', 'Only HTTPS remotes work; this one uses SSH.'), 'Only https:// addresses work. Use “Connect to a Remote” to change it.'],
    [veneerError('history/failed', 'The host refused the token.'), 'The host refused the token.'],
    [new Error('socket hang up'), 'Couldn’t sync.']
  ])('explains a failure in plain words (%#)', async (error, sentence) => {
    const fake = await connected()
    fake.api.history.sync = async () => {
      throw error
    }
    await fake.run(SYNC_COMMAND)
    expect(notices(fake)).toEqual([sentence])
  })

  it('cuts the token out of a message the host wrote, whatever it says', async () => {
    const fake = await connected()
    fake.api.history.sync = async () => {
      throw veneerError('history/failed', `Authentication failed for https://x:${TOKEN}@github.com/writer/novel.git`)
    }
    await fake.run(SYNC_COMMAND)

    expect(notices(fake)).toHaveLength(1)
    expect(notices(fake)[0]).not.toContain(TOKEN)
    expect(notices(fake)[0]).toContain('Authentication failed')
  })

  it('refreshes the lists afterwards, since a sync can bring in versions and comments', async () => {
    const fake = await connected()
    fake.history.syncResult = result({ fetched: true, merged: 'fast-forward', upToDate: false })
    await fake.run(SYNC_COMMAND)
    expect(fake.views.get('gitwrite:history')).toBeDefined()
  })

  it('ignores a second sync while the first is running', async () => {
    const fake = await connected()
    let release: () => void = () => {}
    let calls = 0
    fake.api.history.sync = async () => {
      calls += 1
      await new Promise<void>((resolve) => (release = resolve))
      return result()
    }
    const first = fake.run(SYNC_COMMAND)
    for (let waited = 0; waited < 100 && calls === 0; waited++) await new Promise((resolve) => setTimeout(resolve, 0))
    await fake.run(SYNC_COMMAND) // pressed again while the first is still waiting on the host
    release()
    await first
    expect(calls).toBe(1)
  })

  it('never lets the token reach a view, notice, setting, file or network request of the plugin\'s own', async () => {
    const fake = await withHistory({ settings: { 'gitwrite:remote-username': 'me' } })
    await fake.run(CONNECT_COMMAND)
    await fake.formChange(CONNECT_SURFACE, 'token', TOKEN)
    await fake.formSubmit(CONNECT_SURFACE, { address: ADDRESS, token: TOKEN })
    fake.history.syncResult = result({ fetched: true, pushed: true, merged: 'merge', upToDate: false })
    await fake.run(SYNC_COMMAND)
    fake.api.history.sync = async () => {
      throw veneerError('history/failed', `bad token ${TOKEN}`)
    }
    await fake.run(SYNC_COMMAND)

    expect(everythingVisible(fake)).not.toContain(TOKEN)
    expect(JSON.stringify(await fake.api.settings.get('gitwrite:remote-username'))).not.toContain(TOKEN)
    expect(JSON.stringify([...fake.history.commits])).not.toContain(TOKEN)
    expect(JSON.stringify(await fake.api.history.remotes())).not.toContain(TOKEN)
    expect(fake.secrets.get(TOKEN_SECRET)).toBe(TOKEN) // it is kept in exactly one place
  })
})

describe('Forget Saved Sync Token', () => {
  it('removes the token from the keychain and says so', async () => {
    const fake = await connected()
    await fake.run(FORGET_COMMAND)

    expect(fake.secrets.has(TOKEN_SECRET)).toBe(false)
    expect(notices(fake)).toEqual(['Forgot the saved sync token. You will need to enter it again to sync a private repository.'])
  })

  it('says so when there was none', async () => {
    const fake = await withHistory()
    await fake.run(FORGET_COMMAND)
    expect(notices(fake)).toEqual(['No sync token is saved on this computer.'])
  })
})
