# GitWrite for Veneer

Version control for writers inside [Veneer](https://github.com/eristoddle/veneer), on plain git. A
project's history is an ordinary git repository kept by Veneer (`api.history`), so GitWrite's CLI and
any other git tool read the same history. See the repository's
[PLAN.md](../PLAN.md) for the decisions behind this and
[docs/ANNOTATION_FORMAT.md](../docs/ANNOTATION_FORMAT.md) for the feedback format used later.

## What it does so far

| Command | What it does |
|---|---|
| Save a Version | Asks what changed, then saves every change in the project as one version. Starts the project's history the first time. |
| Show Version History | Lists the project's versions, newest first. Opening one shows that version of the open page, read only. "Restore as New Version" puts it back on the page and saves it as a new version; nothing in the history is rewritten. |
| Compare Two Versions | Shows what changed between two versions of the open page. |
| Compare a Version with This Page | Shows what a version has that the page does not, with Accept and Reject on each change. Accept puts the change on the page (one undo step). |

Explorations, tags, merge, annotations and sync arrive in later releases.

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
```
