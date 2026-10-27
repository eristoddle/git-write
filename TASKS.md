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

# ⏭ NEXT ACTIVE TASK — Queue 5: release

Branch `queue/5-release` per the standing rules. Decision D14. Queue 4 is merged (PR #4), so this is promoted from the queued drafts. Nothing here needs a running Veneer except the last piece's manual items, which go to Stephan as a checklist in the PR.

## Goal

Make the plugin installable from GitHub and account for the brief's "Done when" list.

### ▶ Run state (the agent keeps this current on every stop)
Not started.

## Design — numbered pieces (status: `[ ]` not started · `[x]` done · `[!]` blocked)

- [ ] **1.** `release.py`, copied from `~/Dropbox/python/book_forge/release.py`, with PyPI removed. (TBD at launch: confirm the agent can reach that path; a cloud session cannot, so Stephan supplies the file.)
- [ ] **2.** `.github/workflows/release.yml`.
- [ ] **3.** Install instructions in `veneer-plugin/README.md`.
- [ ] **4.** Walk through the brief's "Done when" list (Veneer's `docs/handoff/gitwrite-plugin-brief.md`) and report each item as verified by a test or needing a manual check in Veneer. Manual checks go to Stephan as a checklist in the PR (start from PR #4's checklist).

## Out of scope (do NOT do)

- Any change to `PLAN.md` decisions; new plugin features.
- Fixing the GitWrite/Veneer conflicts from queue 2 (they wait on Stephan's decision).

## Report back

What was built, which "Done when" items are test-verified vs. manual, and the PR URL.

---

## ✅ Done (collapsed — full detail in PLAN.md's session log)
- **Queue 1: cleanup and core fixes** (PR #1, merged 2026-10-25). Deleted API/SDK/web/wiki/deploy; moved to uv + Python 3.12 + ruff; fixed tag creation, branch review, `.git/` and outside-repo writes, git argument injection; rewrote mocked tests against real repos; added `tests/test_cli_e2e.py`; docs match reality. 320 passed, 1 skipped.
- **Queue 2: interop and annotation anchors** (PR #2, 2026-10-25). Annotations rewritten on pygit2 (no git CLI, HEAD/index/worktree untouched, bare repos work); D15 anchors and `locate()` in `gitwrite_core/anchors.py`; `docs/ANNOTATION_FORMAT.md` with test-generated examples; `interop/` harness (isomorphic-git 1.44.4) with both directions passing `git fsck --strict`, required in CI. 379 passed, 1 skipped. Piece 5 (investigate only) found these GitWrite/Veneer conflicts, none fixed, for Stephan to decide: (1) `.veneer/cache/` is not ignored in GitWrite-made repos and Veneer's `init` leaves existing repos alone, so both tools commit the cache; (2) a CLI merge conflict leaves `MERGE_HEAD`, and a Veneer save on top makes a single-parent commit with the merge state still on disk; (3) Veneer rejects branch/tag names with non-ASCII characters that GitWrite creates; (4) `gitwrite init` uses the machine's default branch while Veneer always uses `main`; (5) cosmetic: first commit authored "GitWrite System", saves without identity as "GitWrite User", Veneer's automatic "Veneer settings" commits; (6) `drafts/`, `notes/` and `metadata.yml` are invisible in Veneer's explorer (harmless; the two tools keep project metadata in different places).
- **Queue 3: Veneer plugin steps 1-3** (PR #3, merged 2026-10-25). `veneer-plugin/` scaffold with CI job; Save a Version (modal form, `api.history.save`, starts the history first); version list with read-only view and Restore as New Version (one undo step, history never rewritten); Compare (two versions read only, or version vs page with Accept/Reject per change). 74 plugin tests on the fake host; Python 379 passed, 1 skipped. Not yet loaded into a running Veneer: how the modal form, wide Compare panel, icons and confirm-on-row Restore look and behave is unverified. API gaps reported: no way to add `.veneer/cache/` to an existing repo's `.gitignore`; the fake host does not reject loose files with `history/no-project`; no text prompt or multi-select.
- **Queue 4: Veneer plugin steps 4–6** (PR #4, merged 2026-10-26). Explorations (list, start, switch; feedback branch hidden), Name a Version (tags with optional note, shown on the version list), merge (a conflict stops, names the files, says nothing changed), annotations as marks with Accept/Reject recorded as commits on the feedback branch (TypeScript `locate` held to the Python one by shared test vectors), sync over HTTPS with the token only in `api.secrets`. 300 plugin tests on the fake host; Python 382 passed, 1 skipped. Bugs found and pinned by tests: YAML 1.1 vs 1.2 comment round-trip, feedback list emptying on reload, stale read on reload during a read, choice field with an unoffered version. Not verified: anything in a running Veneer, and sync against a real host (manual checklist is in PR #4). API gaps: no masked input, `history.sync` is current-branch only (so feedback branch cannot travel through the plugin), plugins cannot write settings, no `MERGE_HEAD` detection, `findInText` is case-insensitive.
