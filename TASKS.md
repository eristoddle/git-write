# TASKS — GitWrite

> The unit of implementation work. Written by the planning thread once a decision in `PLAN.md` is concrete enough to build, executed by the `implementer` agent (Sonnet, often in a Claude Code cloud session).
>
> **The active task is a serial QUEUE of numbered pieces.** Work it top-to-bottom. A blocked piece does **not** halt the queue: mark it `[!]` with a reason, skip it, and continue with any piece that doesn't depend on it (`depends on #N`). Halt only when nothing remaining can proceed. **Always log run-state on stop** (flip each status box, update ▶ Run state), so a killed session is recoverable from this file.
>
> **Contract:** every section is filled before launch. The agent is cold on the planning conversation but warm on the project. Decisions are referenced by ID (`D12`) in `PLAN.md`; the audit findings are in `docs/AUDIT.md` with file:line.
>
> **Standing rules for every queue (D12, D13):**
> - Work on a branch named `queue/<n>-<slug>` off `main`. Commit after each piece (one commit per piece, message `queue <n>.<piece>: <summary>`). When the queue is done, push and open a PR to `main`. Never push to `main`.
> - Python checks: `uv run pytest` and `uv run ruff check .` must pass before a piece is marked `[x]`.
> - **Never mock pygit2 or `gitwrite_core` in tests.** Use real temp repos and set the initial branch explicitly (don't rely on the machine's `init.defaultBranch`).
>
> Completed queues collapse to a one-block summary under **✅ Done**; detail goes in PLAN.md's session log.

---

# ⏭ NEXT ACTIVE TASK — Queue 2: interop and annotation anchors

Branch `queue/2-interop` per the standing rules (this session uses `ccr-fab01977-3fk6x6`). Decisions D8, D11, D12, D15.

## Goal

Make annotations safe (no working-tree changes, no git CLI), add D15 anchors, document the on-disk format as the spec the plugin implements, and prove pygit2 and isomorphic-git read each other's repos.

## Why (pointer)

PLAN.md D8, D11, D12, D15. Audit: `docs/AUDIT.md` "Suggested cleanup priorities" 4.

### ▶ Run state (the agent keeps this current on every stop)
**Queue 2 complete (2026-10-25).** All 5 pieces done, none blocked; one commit per piece (`queue 2.1` … `queue 2.4`; piece 5 changed nothing, so it has no commit). Worked on the cloud session's designated branch `ccr-fab01977-3fk6x6` (restarted from `main` after the queue 1 PR merged).
Checks at finish: `uv run pytest` = 379 passed, 1 skipped (the real-pandoc PDF test; no LaTeX engine here), same with `init.defaultBranch` = main / unset / trunk / master; interop tests ran with `GITWRITE_REQUIRE_INTEROP=1`; `uv run ruff check .` clean.
Piece 5 findings (the conflicts list) are in the PR description. PR not opened yet: waiting for the user's go-ahead.

## Design — numbered pieces (status: `[ ]` not started · `[x]` done · `[!]` blocked)

- [x] **1.** Rewrite `gitwrite_core/annotations.py` to build feedback commits with pygit2 directly on the `refs/heads/feedback` ref. No `git checkout`, no git CLI, and the working tree and HEAD are never touched (audit, cleanup priority 4). Status changes stay as new commits pointing at the original.
- [x] **2.** Add D15 anchors: when creating an annotation from file content, compute `prefix`, `suffix` (about 32 characters each, clipped at file edges) and `offset`. The reader accepts annotations with or without them. Add a `locate(annotation, text)` helper with the fallback chain prefix+text+suffix → text → line, and test all three tiers plus moved and duplicated passages.
- [x] **3.** Write `docs/ANNOTATION_FORMAT.md` as the spec the plugin implements: branch name (default `feedback`, configurable), commit shape (empty tree change, YAML body), every YAML field including the D15 ones, how a status change references the original, and an example. Generate the example from a test so it can't drift.
- [x] **4.** Build an interop harness in `interop/`: a small Node package with `isomorphic-git` pinned to a current version. Test A: a pytest test drives the CLI to init, save, explore, tag, and annotate, then runs a Node script that reads the log, branches, tags and feedback commits with isomorphic-git and asserts on them. Test B: a Node script inits, commits, branches and tags with isomorphic-git, then core reads the history and branches. Both run `git fsck --strict`. Skip with a clear message if `node` is missing locally; CI installs Node and must run them.
- [x] **5.** Investigate only: compare what `gitwrite init` writes (metadata files, `.gitignore`) with what a Veneer project folder contains (`~/Dropbox/node/veneer`, the project-type / project-data docs in `~/Dropbox/node/veneer-api/docs`). Report conflicts in the PR description and change nothing.

## Out of scope (do NOT do)

- The plugin itself (`veneer-plugin/`, queues 3 and 4).
- Any server or API (PLAN.md P2).
- Changing non-annotation core behavior. Piece 5 is investigate-only.

## Report back

What changed, test counts, every `[!]` piece, the piece 5 conflicts list, decisions made on details the spec left open, and the PR URL.

---

## ⏩ Queued (drafts: promote to active when the previous queue's PR merges, and fill in anything marked TBD)

### Queue 3: plugin steps 1–3

Branch `queue/3-plugin-core`. Decisions D7, D9, D12. Spec: Veneer's `docs/handoff/gitwrite-plugin-brief.md` steps 1–3 and `docs/handoff/README.md`. Pieces:

1. Scaffold `veneer-plugin/` by copying book_forge's setup: `manifest.json` (id `gitwrite`, `apiVersion` `^0.40.0`, `main` `main.js`), `package.json` (scripts `build` / `typecheck` / `test`; dependency `@veneer/api` from `github:eristoddle/veneer-api#v0.40.0`), `.npmrc` with `allow-git=all`, `tsconfig.json`, `.gitignore` with `main.js`, and `README.md`. Add a CI job for typecheck, test and build.
2. Save a Version.
3. History surface, read-only view of a version, and Restore (saves the old text as a new version).
4. Compare: two versions, or a version and the open page, into a `diff` view, with accept/reject via `onDiffAction` and `api.editor.edit`.

Each command and surface gets a test on `createFakeHost`. TBD at promotion: the exact command and surface IDs and names.

### Queue 4: plugin steps 4–6

Branch `queue/4-plugin-collab`. Pieces:

1. Explorations: list, create and switch (tell the writer that switching saves and reloads).
2. Tags.
3. Merge. On conflict, stop and name the files in plain words.
4. Annotations as marks, per `docs/ANNOTATION_FORMAT.md`: branch-name setting defaulting to `feedback`, the D15 locate chain re-implemented in TypeScript using `findInText`, marks re-set after each save, accept/reject as new commits.
5. Sync over HTTPS with the token in `api.secrets`, never in settings or logs, and `api.notify` afterward.

Each gets a test on the fake host.

### Queue 5: release

Branch `queue/5-release`. Decision D14. Pieces:

1. `release.py`, copied from `~/Dropbox/python/book_forge/release.py`, with PyPI removed.
2. `.github/workflows/release.yml`.
3. Install instructions in `veneer-plugin/README.md`.
4. Walk through the brief's "Done when" list and report each item as verified by a test or needing a manual check in Veneer. Manual checks go to Stephan as a checklist in the PR.

---

## ✅ Done (collapsed — full detail in PLAN.md's session log)
- **Queue 1: cleanup and core fixes** (PR #1, merged 2026-10-25). Deleted API/SDK/web/wiki/deploy; moved to uv + Python 3.12 + ruff; fixed tag creation, branch review, `.git/` and outside-repo writes, git argument injection; rewrote mocked tests against real repos; added `tests/test_cli_e2e.py`; docs match reality. 320 passed, 1 skipped.
