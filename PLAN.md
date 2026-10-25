# PLAN.md

> Authoritative record of **decisions made** for GitWrite. Living document, built up across sessions. Read at the start of any planning/design conversation. **Append** decisions as they're made; don't rewrite.
>
> This is the **hot layer**, so keep it lean. Cooled material lives in `docs/` (see below). When it grows heavy (default >15000 words), invoke the **`living-plan`** skill to relocate what has cooled. That same skill's `grill` workflow is what **fills** the sections below.

## Overview

GitWrite is version control for writers on plain git: save a version, history, explorations (branches), compare with a word-level diff, milestones (tags), merge, annotations from readers, sync. The code was built quickly with early coding models in 2025 and was barely tested. See [docs/AUDIT.md](docs/AUDIT.md) for what actually works.

The direction is a **Veneer plugin** (Veneer is Stephan's desktop writing app). The plugin brief written on the Veneer side is the spec for the plugin: `~/Dropbox/node/veneer/docs/handoff/gitwrite-plugin-brief.md`. The plugin API package is `@veneer/api` (`~/Dropbox/node/veneer-api`, installed as `github:eristoddle/veneer-api#v0.40.0`). The sibling project `~/Dropbox/python/book_forge/veneer-plugin` is the layout to copy.

## Decisions

> Whole and inline while hot. `🔒 foundational` = load-bearing, never archived. `🔨` = decided but not built yet.

### D1 — Refactor in this repo, keep the core 🔒

The rewrite happens in this repo, with git history kept. The working parts of `gitwrite_core` stay: init layout, save, history, word diff, merge, revert, export via pandoc, and the annotation-as-commit format. The first version of this decision was "rewrite the API"; D11 narrows that to deleting the API outright.

### D2 — Single owner, self-hosted

Any server part is single-owner and self-hosted in v1, designed so multi-user can be added later (every request carries a token tied to an identity, and repos have an owner). Collaborator roles (editor, beta reader) wait. This only applies once a server exists (see P2).

### D3 — ~~Server-side bare repos, stateless operations~~

Superseded by [D8](#d8--local-first-veneer-drives-git-directly-) on 2026-10-24. The Veneer brief turned out to be local-first.

### D4 — Delete what Veneer replaces 🔨

Delete `gitwrite-web/`, `gitwrite_sdk/`, `wiki/`, `writegit-project-doc.md`, the duplicate deployment docs, and the nginx / docker-compose / Postgres / Redis config. They stay in git history.

### D5 — ~~v1 feature set: save, history, diff, explore/merge, revert, milestones, export~~

Superseded by [D9](#d9--plugin-v1-is-the-briefs-steps-16-) on 2026-10-24.

### D6 — Python 3.12, current deps, uv 🔨

Move to Python 3.12+, PEP 621 `pyproject.toml`, and uv (drop Poetry). Update dependencies to current versions. The old `.venv` points at another machine's pyenv and `gitwrite_cli/.venv` is a 35 MB leftover; both go.

### D7 — The Veneer plugin lives in this repo 🔒

The plugin lives in `veneer-plugin/` at the repo root, laid out like `book_forge/veneer-plugin`: `manifest.json`, `src/*.ts` with a matching `*.test.ts` each, TypeScript, esbuild (`--bundle --format=esm --platform=neutral --outfile=main.js`), Vitest on `@veneer/api/testing`'s `createFakeHost`, and `main.js` gitignored.

### D8 — Local first: Veneer drives git directly 🔒

A writer's project is a plain git repo in the project folder. The plugin is an adapter that maps GitWrite's words onto Veneer's `api.history` (isomorphic-git in Veneer's main process) and Veneer surfaces. Repos made by GitWrite's pygit2 and by Veneer's isomorphic-git must open in each other. The GitWrite server is optional and is not part of v1 (P2).

### D9 — Plugin v1 is the brief's steps 1–6 🔨

1. Save a version. 2. History, with read-only view and restore-as-new-version. 3. Compare with accept/reject per change. 4. Explorations, tags, merge. 5. Annotations as editor marks with accept/reject. 6. Sync over HTTPS with the token in `api.secrets`.

Revert, cherry-pick, rebase, SSH and LFS are out by design. Restore means saving the old text as a new version. Merge conflicts stop and name the files; the plugin never resolves them. Step 7 (server) is P2.

### D10 — Keep the CLI 🔨

The CLI stays as the local power-user tool and is the interop check in the brief's done-when ("a repo GitWrite's CLI also reads cleanly"). Fix `tag add` and `review`, and add a `gitwrite` console script so the command exists after install.

### D11 — Python v1 scope 🔨

- Fix the core bugs from the audit (tags, review, writes into `.git/`, git argument injection).
- Prove pygit2 ↔ isomorphic-git interop.
- Add annotation anchors (D15) and stop annotations from checking out the working tree.
- Document the `feedback` branch format.
- Delete `gitwrite_api/` entirely, with no stub. A new small server gets planned from scratch under P2.
- Sync targets any HTTPS git host (GitHub, Gitea); GitWrite doesn't host git.

### D12 — Done criteria for unattended work 🔒

A piece is done only when its checks pass:

- **Python:** `uv run pytest` and `uv run ruff check`. New tests use real temp repos with the initial branch set explicitly. **Never mock pygit2 or `gitwrite_core` in tests.** The old suite was green while tags and review were broken because it mocked them.
- **Plugin:** `npm run typecheck`, `npm test` (Vitest on the fake host), `npm run build`.
- **Interop:** a Node test using the real `isomorphic-git` package reads a repo the CLI made, and the CLI reads a repo isomorphic-git made. Both pass `git fsck`.

### D13 — How work lands

One branch per queue (`queue/<n>-<slug>`), one commit per piece, and a PR when the queue is done. Stephan reviews and merges; nothing goes straight to `main`. Queue order: (1) cleanup and core fixes, (2) interop and annotation anchors, (3) plugin steps 1–3, (4) plugin steps 4–6, (5) release. Each queue is promoted to the active task in `TASKS.md` after the previous PR merges.

### D14 — Releases copy book_forge 🔨

A `release.py` bumps `veneer-plugin/manifest.json`, `veneer-plugin/package.json` and `pyproject.toml` together and tags `v<version>`. A GitHub Action checks the manifest version matches the tag, runs typecheck, test and build, and attaches `manifest.json` and `main.js` to the release so writers can "Install from GitHub". No PyPI publish for now.

### D15 — Annotation anchors 🔨

New optional YAML fields on annotations: `prefix` and `suffix` (about 32 characters of surrounding text each) and `offset` (character offset of the highlighted text). Old annotations without them still parse. Locating order: prefix + text + suffix, then the text alone, then the stored line number.

## Open questions

_None open._

## Parking lot

- **P1 — Keep the CLI?** → promoted to [D10](#d10--keep-the-cli-) on 2026-10-24.
- **P2 — The GitWrite server** (auth tokens, repo mapping, concurrent saves, deployment, beta-reader feedback, export download) → [docs/parking-lot/P2.md](docs/parking-lot/P2.md)

## Session log

> Most recent sessions inline; older sessions archived → see `docs/sessions/`.

### Session 1 — 2026-10-24

- Fixed git: Dropbox had left 9 "conflicted copy" files in `.git` that broke fetch. Merged the Veneer direction note from a cloud branch.
- Ran the audit → [docs/AUDIT.md](docs/AUDIT.md). The core mostly works; the API is half-wired and had two confirmed exploits (command execution via `.git/config`, file write via annotation IDs).
- Picked living-plan over BMAD: this is a small brownfield cleanup, not a product build.
- Grill, 3 rounds: D1–D15 decided. The Veneer brief turned out to be local-first, which superseded D3 (server bare repos) and D5 (feature set) and shrank the Python side to core fixes plus interop. P1 promoted to D10; P2 (server) parked.
- Scaffolded PLAN.md, TASKS.md (queue 1 active, queues 2–5 drafted), and the implementer agent.

## Relocated (progressive disclosure)

- Decisions archive → [docs/decisions/](docs/decisions/)
- Questions detail → [docs/questions/](docs/questions/)
- Parking-lot detail → [docs/parking-lot/](docs/parking-lot/)
- Session archive → [docs/sessions/](docs/sessions/)
- Rebalance log → [docs/rebalance-log.md](docs/rebalance-log.md)
