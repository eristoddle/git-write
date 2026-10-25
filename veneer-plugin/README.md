# GitWrite for Veneer

Version control for writers inside [Veneer](https://github.com/eristoddle/veneer), on plain git. A
project's history is an ordinary git repository kept by Veneer (`api.history`), so GitWrite's CLI and
any other git tool read the same history. See the repository's
[PLAN.md](../PLAN.md) for the decisions behind this and
[docs/ANNOTATION_FORMAT.md](../docs/ANNOTATION_FORMAT.md) for the feedback format used later.

## What it does

| Command | What it does |
|---|---|
| Save a Version | Asks what changed, then saves every change in the project as one version. Starts the project's history the first time. |
| Show Version History | Lists the project's versions, newest first, with any names you gave them. Opening one shows that version of the open page, read only. "Restore as New Version" puts it back on the page and saves it as a new version; nothing in the history is rewritten. |
| Name a Version | Gives a version a name like “first-draft”, with an optional note, so you can find it again. |
| Compare Two Versions | Shows what changed between two versions of the open page. |
| Compare a Version with This Page | Shows what a version has that the page does not, with Accept and Reject on each change. Accept puts the change on the page (one undo step). |
| Show Explorations | Lists your explorations (branches). Opening one switches to it; the confirmation says your page is saved first and the project's files change. "Bring Into This Exploration" merges another exploration into the one you are on. A conflict changes nothing and names the files. |
| Start an Exploration | Makes an exploration from where you are and moves the project onto it. |
| Show Feedback | Lists readers' comments on the open page. The comments also show as marks over their passages; clicking a mark opens the list on that comment. Accept and Reject record a decision on the feedback branch and never touch your pages. |
| Connect to a Remote / Sync with Remote | Sets the HTTPS address of a remote repository (GitHub, Gitea, any git host) and saves an access token; Sync brings in their changes and sends yours. |
| Forget Saved Sync Token | Removes the saved token from the keychain. |

Two settings: **Feedback branch** (default `feedback`, which is where GitWrite's CLI keeps comments) and **Sync user name** (empty means the host's default; GitHub needs none).

### The access token

It is typed once into the Connect form, goes straight to the system keychain through `api.secrets`, and is read back only to hand to `api.history.sync`. It is never put in a setting, a view, a notice or a log, the form never shows it again, and a host message that happens to contain it is cut before it is shown. Veneer's form fields have no masked type, so what you type shows on screen while typing.

### What it does not do yet

- **Readers' comments do not sync.** `api.history.sync` only syncs the branch you are on, so the feedback branch cannot travel through it. How a reader's comments get to you is not something this plugin does yet; it shows the ones that are already in the project.
- **It does not write new comments**, only reads them and records Accept/Reject.
- **Merge conflicts are never settled for you.** The merge stops, names the files, and changes nothing.
- A conflicting merge made with GitWrite's command line leaves a merge in progress that Veneer cannot see; finish or abort it there first.

## Develop

Needs Node 20 or newer. The Veneer plugin API is installed from its GitHub release tag, which needs
`allow-git=all` (already in `.npmrc`).

```bash
cd veneer-plugin
npm ci
npm run typecheck
npm test            # Vitest on @veneer/api's fake host; no Veneer app needed
npm run build       # bundles src/index.ts to main.js
```

In a development build of Veneer, use **Load plugin from folder** on this folder (it needs
`manifest.json` and the built `main.js`) and **Reload plugin** after a rebuild.

`.npmrc` also sets `legacy-peer-deps=true`: npm 10, the version Node 22 and CI ship, cannot resolve
vitest 5's optional peers, so `vite` is installed explicitly instead.

## Layout

```
manifest.json   id, apiVersion, every command, surface and row action (the manifest is authoritative)
src/index.ts    onload(api): attaches handlers by id
src/*.ts        one feature per file, each with a matching *.test.ts
                (save, history, compare, explorations, tags, annotations, sync; feedback.ts reads and
                writes GitWrite's comment commits; locate.ts finds a passage again)
```

## Staying in step with GitWrite

`src/locate.ts` and `src/feedback.ts` re-implement GitWrite's Python in TypeScript. Two files keep them
honest, and the Python tests fail if either side drifts:

- `docs/annotation-locate-vectors.json` holds what Python's `locate` returns for a set of cases; this plugin's
  tests check every one. Regenerate it only after an intentional change: `UPDATE_LOCATE_VECTORS=1 uv run pytest tests/test_locate_vectors.py`.
- `tests/test_plugin_status_commit.py` bundles `feedback.ts`, has it write status commits, and reads them back
  with Python over awkward text. The YAML is read and written as **YAML 1.1** (PyYAML's rules), not the `yaml`
  package's default 1.2: otherwise a comment of `yes` or `2026-10-25` comes back as a boolean or a date.
