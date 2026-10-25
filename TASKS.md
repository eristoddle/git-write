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

# ⏭ NEXT ACTIVE TASK — Queue 3: plugin steps 1–3

Branch `queue/3-plugin-core` per the standing rules (this session uses `ccr-fab01977-3fk6x6`). Decisions D7, D9, D12. Spec: Veneer's `docs/handoff/gitwrite-plugin-brief.md` steps 1–3 and `docs/handoff/README.md` (both in the `veneer` / `veneer-api` repos).

## Goal

A `veneer-plugin/` that lets a writer save a version, browse and restore versions, and compare them with Accept/Reject, on `api.history`, tested on the fake host.

## Why (pointer)

PLAN.md D7, D8, D9, D12. Plugin layout per the Veneer handoff README and its example plugins (`book_forge`'s copy is on Stephan's machine, not in the cloud session).

### ▶ Run state (the agent keeps this current on every stop)
_Started 2026-10-25 on the designated branch `ccr-fab01977-3fk6x6` (restarted from `main` after the queue 2 PR merged)._

## Contribution IDs (decided at promotion, 2026-10-25; Stephan approved these names)

Plugin id `gitwrite`; contributions are `gitwrite:<lowercase-hyphen>`; titles use writer words.

| Kind | ID | Title / notes |
|---|---|---|
| command | `gitwrite:save-version` | Save a Version |
| command | `gitwrite:show-history` | Show Version History |
| command | `gitwrite:compare-versions` | Compare Two Versions |
| command | `gitwrite:compare-with-page` | Compare a Version with This Page |
| surface | `gitwrite:history` | Versions; icon `history`; side right; row action `gitwrite:restore-version` ("Restore as New Version", confirm) |
| surface | `gitwrite:compare` | Compare; icon `git-compare`; side right, wide; shows a version read-only and diffs |
| surface | `gitwrite:save` | Save a Version; icon `save`; side modal; a form asking what changed (added by the planner: the API has no other way to ask for a message) |

## Design — numbered pieces (status: `[ ]` not started · `[x]` done · `[!]` blocked)

- [ ] **1.** Scaffold `veneer-plugin/` from the Veneer handoff README and its example plugins: `manifest.json` (id `gitwrite`, `apiVersion` `^0.40.0`, `main` `main.js`, the contributions above), `package.json` (scripts `build` / `typecheck` / `test`; `@veneer/api` from `github:eristoddle/veneer-api#v0.40.0`), `.npmrc` with `allow-git=all`, `tsconfig.json`, `.gitignore` with `main.js`, `README.md`. Add a CI job for typecheck, test and build.
- [ ] **2.** Save a Version: command opens the `gitwrite:save` form; submitting calls `api.history.save` (starting history first when the project has none), tells the writer in plain words what happened (including "nothing changed" and "no history for a loose file"), and refreshes the history list.
- [ ] **3.** History surface (newest first: message, author, time), read-only view of a version of the open page, and Restore (puts the old text on the open page with `api.editor.edit`, then saves it as a new version; history is never rewritten).
- [ ] **4.** Compare: two versions, or a version and the open page, into a `diff` view; for version-vs-page, Accept/Reject per change via `onDiffAction` and `api.editor.edit` (one undo step each).

Each command and surface gets a test on `createFakeHost`; every `src/*.ts` has a matching `*.test.ts`.

Inputs from queue 2: Veneer's `history.init()` is the only thing that adds `.veneer/cache/` to `.gitignore`, and it skips existing repos, so the plugin should make sure that line is present before the first save in a repo GitWrite made. Never assume the default branch is `main` (a GitWrite-made repo may be on `master`). Hide the `feedback` branch from the exploration list (switching to it would swap in a stale snapshot of the files).

## Out of scope (do NOT do)

- Explorations, tags, merge, annotations, sync (queue 4); release (queue 5).
- Working around a missing API with a hack: write down what was missing (the Veneer handoff asks for this) in the PR.
- Any change to the Python code.

## Report back

What was built and tested per brief item, anything the API lacked, decisions made, and the PR URL.

---

## ⏩ Queued (drafts: promote to active when the previous queue's PR merges, and fill in anything marked TBD)

### Queue 4: plugin steps 4–6

Branch `queue/4-plugin-collab`. Pieces:

1. Explorations: list, create and switch (tell the writer that switching saves and reloads).
2. Tags.
3. Merge. On conflict, stop and name the files in plain words.
4. Annotations as marks, per `docs/ANNOTATION_FORMAT.md`: branch-name setting defaulting to `feedback`, the D15 locate chain re-implemented in TypeScript using `findInText`, marks re-set after each save, accept/reject as new commits.
5. Sync over HTTPS with the token in `api.secrets`, never in settings or logs, and `api.notify` afterward.

Each gets a test on the fake host.

Inputs from queue 2: the format spec is `docs/ANNOTATION_FORMAT.md`; `interop/lib.mjs` is a working JS reader of it and `interop/write-repo.mjs` shows `api.history`-style writing (same-tree commit with a YAML body). Offsets and context lengths count Unicode code points (use `Array.from`), line numbers are 0-indexed, and locate ties go to the match nearest the stored offset, then the stored line. Veneer's `createBranch` and tag creation accept only ASCII letters, digits, `.`, `_`, `-` and `/`, while GitWrite accepts any valid git name. A conflicting merge in the GitWrite CLI leaves `MERGE_HEAD` behind, which Veneer does not detect: check for it before saving.

### Queue 5: release

Branch `queue/5-release`. Decision D14. Pieces:

1. `release.py`, copied from `~/Dropbox/python/book_forge/release.py`, with PyPI removed.
2. `.github/workflows/release.yml`.
3. Install instructions in `veneer-plugin/README.md`.
4. Walk through the brief's "Done when" list and report each item as verified by a test or needing a manual check in Veneer. Manual checks go to Stephan as a checklist in the PR.

---

## ✅ Done (collapsed — full detail in PLAN.md's session log)
- **Queue 1: cleanup and core fixes** (PR #1, merged 2026-10-25). Deleted API/SDK/web/wiki/deploy; moved to uv + Python 3.12 + ruff; fixed tag creation, branch review, `.git/` and outside-repo writes, git argument injection; rewrote mocked tests against real repos; added `tests/test_cli_e2e.py`; docs match reality. 320 passed, 1 skipped.
- **Queue 2: interop and annotation anchors** (PR #2, 2026-10-25). Annotations rewritten on pygit2 (no git CLI, HEAD/index/worktree untouched, bare repos work); D15 anchors and `locate()` in `gitwrite_core/anchors.py`; `docs/ANNOTATION_FORMAT.md` with test-generated examples; `interop/` harness (isomorphic-git 1.44.4) with both directions passing `git fsck --strict`, required in CI. 379 passed, 1 skipped. Piece 5 (investigate only) found these GitWrite/Veneer conflicts, none fixed, for Stephan to decide: (1) `.veneer/cache/` is not ignored in GitWrite-made repos and Veneer's `init` leaves existing repos alone, so both tools commit the cache; (2) a CLI merge conflict leaves `MERGE_HEAD`, and a Veneer save on top makes a single-parent commit with the merge state still on disk; (3) Veneer rejects branch/tag names with non-ASCII characters that GitWrite creates; (4) `gitwrite init` uses the machine's default branch while Veneer always uses `main`; (5) cosmetic: first commit authored "GitWrite System", saves without identity as "GitWrite User", Veneer's automatic "Veneer settings" commits; (6) `drafts/`, `notes/` and `metadata.yml` are invisible in Veneer's explorer (harmless; the two tools keep project metadata in different places).
