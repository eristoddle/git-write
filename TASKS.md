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

# ⏭ NEXT ACTIVE TASK — Queue 1: cleanup and core fixes

Branch: `queue/1-cleanup`

## Goal

Cut the repo down to what the plan keeps (core + CLI), move it to Python 3.12 + uv, fix the core bugs the audit confirmed, and make the test suite honest. The result is a small, green, truthful base for queue 2.

## Why (pointer)

PLAN.md D4, D6, D10, D11, D12. Audit: `docs/AUDIT.md` sections "Suggested cleanup priorities" 2, 3, 5, 6, 7, and "Security / remote-API readiness".

### ▶ Run state (the agent keeps this current on every stop)
_Not started._

## Design — numbered pieces (status: `[ ]` not started · `[x]` done · `[!]` blocked)

- [ ] **1. Hygiene.**
  - Delete the untracked `gitwrite_cli/.venv`.
  - Untrack and delete `repomix-output.xml`, coverage files (`.coverage`, `coverage.xml`, `htmlcov/` if tracked), `gitwrite_cli/poetry.lock`, `.qoder/`, and `logs/`.
  - Untrack `.claude/settings.local.json` but keep the file locally.
  - Add all of these to `.gitignore`. Don't touch `.claude/agents/`.
- [ ] **2. Delete what Veneer replaces (D4, D11).**
  - Directories: `gitwrite-web/`, `gitwrite_sdk/`, `gitwrite_api/`, `wiki/`, `integration_tests/` (it targets the API).
  - API tests: `tests/test_api_*.py` and any other test that imports `gitwrite_api`.
  - Root files: `writegit-project-doc.md`, `nginx.conf`, `docker-compose.yml`, `Dockerfile`, `deploy.sh`, `DEPLOYMENT.md`.
  - Docs: `docs/DEPLOYMENT_GUIDE.md`, `docs/API_REFERENCE.md`.
  - Remove `gitwrite_core`'s import of `gitwrite_api.models` (audit, cleanup priority 2) and move whatever it used into core.
  - Update `.github/workflows/test.yml` to drop the SDK/Node job.
- [ ] **3. Toolchain (D6).** _(depends on #2)_
  - Rewrite `pyproject.toml` as PEP 621 for uv, `requires-python = ">=3.12"`.
  - Runtime deps at current versions: `pygit2`, `click`, `rich`, `pyyaml`, `pypandoc`, plus anything else core or CLI actually imports. Find out with grep; don't guess.
  - Drop FastAPI, uvicorn, python-jose, passlib, bcrypt, pydantic and other API-only deps unless core still imports them.
  - Dev deps: `pytest`, `pytest-cov`, `ruff`.
  - Add `[project.scripts] gitwrite = "gitwrite_cli.main:cli"` (check the actual Click group name in `gitwrite_cli/main.py`).
  - Remove `poetry.lock` and `poetry.toml`, generate `uv.lock`.
  - Update CI to `astral-sh/setup-uv`, Python 3.12, `uv sync`, `uv run pytest`, `uv run ruff check .`, keeping the pandoc install step.
  - Fix any pygit2 API breakage the version bump surfaces.
- [ ] **4. Honest tests.** _(depends on #3)_
  - Every test fixture that creates a repo sets the initial branch explicitly. The suite must pass both with `git config --global init.defaultBranch main` and with it unset.
  - Find tests that mock pygit2 or `gitwrite_core` (`grep -n "mock\|patch" tests/`). Rewrite each one against real temp repos, or delete it if it only tests the mock. If any test is xfailed only because of a mock, fix or delete it.
  - Export tests skip cleanly when pandoc isn't installed.
- [ ] **5. Core bug fixes, each with an unmocked regression test.** _(depends on #4)_
  - (a) `gitwrite_core/tagging.py` around line 32: `.oid` → `.id`, so tag creation works on current pygit2.
  - (b) `gitwrite_core/versioning.py` around line 691: `walk(..., hide=)` is not a pygit2 argument. Use `walker.hide(oid)`, so branch review works.
  - (c) `save_and_commit_file` (`gitwrite_core/repository.py`; the audit cites the API at `repository.py:781-815` calling it) rejects any path that resolves into `.git/` or outside the repo root. Test with `.git/config`, `../x`, an absolute path and a symlinked parent.
  - (d) Every `_run_git_command`-style subprocess call: pass `--` before paths, and validate that anything used as a commit ID is a hex OID (`^[0-9a-f]{4,40}$`) before it reaches git. Test that an annotation ID of `--output=/tmp/x` is rejected and writes nothing.
  - (e) Run `git grep -n "subprocess\|_run_git" gitwrite_core` and list every remaining git CLI call in the report. Don't convert them to pygit2 here (annotations are queue 2).
- [ ] **6. CLI works end to end (D10).** _(depends on #5)_
  - Add `tests/test_cli_e2e.py` using Click's `CliRunner` on a real temp repo: init → save → history → explore (create branch) → switch → save → merge → tag add → review → export epub (skip if no pandoc).
  - Each step asserts on repo state (refs, commit count, files), not just the exit code.
  - `uv run gitwrite --help` works.
- [ ] **7. Ruff clean.** _(depends on #3)_
  - Add a `[tool.ruff]` config (line length 100, target py312, default rules plus `I` for imports) and fix what it reports.
  - Any per-line `noqa` needs a short reason comment.
  - No unrelated refactors.
- [ ] **8. Docs match reality.** _(depends on #2, #6)_
  - In `CLAUDE.md`, replace everything **above** `## Development workflow — planning vs implementation` with a short accurate description: what's in the repo now (core, CLI, tests, and soon `veneer-plugin/`), the uv commands, the no-mock test rule, and a pointer to PLAN.md. Keep the workflow section and everything below it unchanged.
  - Rewrite `README.md` to the current scope: what GitWrite is, CLI install via uv, the real command list from `gitwrite --help`, and "Veneer plugin coming" with a link to PLAN.md.
  - Prune `docs/USER_GUIDE.md` and `docs/LOCAL_TESTING_GUIDE.md` to commands that exist. Delete either one if little survives.
  - In `docs/VENEER_DIRECTION.md`, append a dated line saying the open decision was settled, local first, see PLAN.md D8.
  - Leave `docs/AUDIT.md` unchanged.

## Files

- Edit: `pyproject.toml`, `.gitignore`, `.github/workflows/test.yml`, `gitwrite_core/{tagging,versioning,repository}.py` plus whichever core files hold the git subprocess calls, `gitwrite_cli/main.py` (only if the fixes need it), `tests/**`, `CLAUDE.md`, `README.md`, `docs/USER_GUIDE.md`, `docs/LOCAL_TESTING_GUIDE.md`, `docs/VENEER_DIRECTION.md`.
- New: `uv.lock`, `tests/test_cli_e2e.py`, regression tests in `tests/`.
- Delete: as listed in pieces 1–2.

## Tests (add; keep the suite green)

- Regression tests for 5(a)–(d), unmocked.
- `tests/test_cli_e2e.py` (piece 6).
- The full suite passes with `init.defaultBranch` set to `main` and unset, and `ruff check` is clean.

## Out of scope (do NOT do)

- Annotations rewrite, anchors, interop tests (queue 2).
- Anything in `veneer-plugin/` (queue 3).
- Building any server or API (PLAN.md P2).
- Changing core behavior beyond the listed bug fixes. Converting git CLI calls to pygit2 (beyond what 5(d) needs) waits.
- Editing `PLAN.md` decisions.

## Report back

- What was deleted, and the final dependency list with versions.
- Test counts before and after, plus which mocked tests were rewritten vs deleted and why.
- The list from 5(e).
- Every `[!]` blocked piece and why.
- Anything in the audit that turned out wrong.
- The PR URL.

---

## ⏩ Queued (drafts: promote to active when the previous queue's PR merges, and fill in anything marked TBD)

### Queue 2: interop and annotation anchors

Branch `queue/2-interop`. Decisions D8, D11, D12, D15. Pieces:

1. Rewrite `gitwrite_core/annotations.py` to build feedback commits with pygit2 directly on the `refs/heads/feedback` ref. No `git checkout`, no git CLI, and the working tree and HEAD are never touched (audit, cleanup priority 4). Status changes stay as new commits pointing at the original.
2. Add D15 anchors: when creating an annotation from file content, compute `prefix`, `suffix` (about 32 characters each, clipped at file edges) and `offset`. The reader accepts annotations with or without them. Add a `locate(annotation, text)` helper with the fallback chain prefix+text+suffix → text → line, and test all three tiers plus moved and duplicated passages.
3. Write `docs/ANNOTATION_FORMAT.md` as the spec the plugin implements: branch name (default `feedback`, configurable), commit shape (empty tree change, YAML body), every YAML field including the D15 ones, how a status change references the original, and an example. Generate the example from a test so it can't drift.
4. Build an interop harness in `interop/`: a small Node package with `isomorphic-git` pinned to a current version. Test A: a pytest test drives the CLI to init, save, explore, tag, and annotate, then runs a Node script that reads the log, branches, tags and feedback commits with isomorphic-git and asserts on them. Test B: a Node script inits, commits, branches and tags with isomorphic-git, then core reads the history and branches. Both run `git fsck --strict`. Skip with a clear message if `node` is missing locally; CI installs Node and must run them.
5. Investigate only: compare what `gitwrite init` writes (metadata files, `.gitignore`) with what a Veneer project folder contains (`~/Dropbox/node/veneer`, the project-type / project-data docs in `~/Dropbox/node/veneer-api/docs`). Report conflicts in the PR description and change nothing.

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
_<nothing yet>_
