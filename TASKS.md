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

# ⏭ NEXT ACTIVE TASK

_None. Queue 2 is done and waiting on its PR. Promote Queue 3 (below) when that PR merges, and fill in its TBD._

---

## ⏩ Queued (drafts: promote to active when the previous queue's PR merges, and fill in anything marked TBD)

### Queue 3: plugin steps 1–3

Branch `queue/3-plugin-core`. Decisions D7, D9, D12. Spec: Veneer's `docs/handoff/gitwrite-plugin-brief.md` steps 1–3 and `docs/handoff/README.md`. Pieces:

1. Scaffold `veneer-plugin/` by copying book_forge's setup: `manifest.json` (id `gitwrite`, `apiVersion` `^0.40.0`, `main` `main.js`), `package.json` (scripts `build` / `typecheck` / `test`; dependency `@veneer/api` from `github:eristoddle/veneer-api#v0.40.0`), `.npmrc` with `allow-git=all`, `tsconfig.json`, `.gitignore` with `main.js`, and `README.md`. Add a CI job for typecheck, test and build.
2. Save a Version.
3. History surface, read-only view of a version, and Restore (saves the old text as a new version).
4. Compare: two versions, or a version and the open page, into a `diff` view, with accept/reject via `onDiffAction` and `api.editor.edit`.

Each command and surface gets a test on `createFakeHost`. TBD at promotion: the exact command and surface IDs and names.

Inputs from queue 2: Veneer's `history.init()` is the only thing that adds `.veneer/cache/` to `.gitignore`, and it skips existing repos, so the plugin should make sure that line is present before the first save in a repo GitWrite made. Never assume the default branch is `main` (a GitWrite-made repo may be on `master`). Hide the `feedback` branch from the exploration list (switching to it would swap in a stale snapshot of the files).

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
