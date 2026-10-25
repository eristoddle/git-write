# GitWrite Audit

*Audit date 2026-10-24. Read-only review of the repo at commit 9534a8f. Nothing in the source was changed. All test runs and smoke tests ran against a throwaway venv and temp repos in the session scratchpad.*

## Summary

- **The core mostly works.** In real use against real pygit2 repos, `gitwrite_core` did init, save, history, branch, switch, merge, cherry-pick, revert, gitignore, sync (push to a bare remote), tree browse, file-at-commit, word-level diff, EPUB and DOCX export, and annotation create/list/update. Two core features are broken against the locked pygit2 1.18: **tag creation** (`tagging.py:32` uses the removed `.oid`) and **branch review** (`versioning.py:691` passes `hide=` to `walk()`). The unit tests miss both because they mock pygit2.
- **The test suite is green, but only on the right machine.** 383 passed / 1 skipped / 2 xfailed with a neutral git config. With the owner's real `~/.gitconfig` (`init.defaultBranch=main`), 17 tests fail because the tests hardcode `master`. Most API tests mock the core (about 500 `mock`/`patch` uses across `tests/test_api_*.py`), so a green run says little about whether the API works end to end.
- **The API is half-wired.** Only about 9 of the 28 routes resolve a per-repository path (`/repository/{repo_name}/...`). The other routes (tags, compare, revert, sync, review, cherry-pick, file-content, all three exports, ignore, all annotations) run against one hardcoded global directory, `/tmp/gitwrite_repos_api` (`routers/repository.py:9`, `routers/annotations.py:23`), which is never a repository. Uploads use a third root, `/tmp/gitwrite_repos/{repo_id}` (`routers/uploads.py:23`), that repo creation never writes to. Through the API these features return 500 for any repo you create.
- **It is not safe to put on a network as-is.** The JWT secret is hardcoded, the users are a hardcoded fake DB, nothing checks repo ownership, and two exploits were confirmed: (1) an authenticated writer can overwrite `.git/config` through `POST /repository/{repo}/save`, and that led to command execution via `core.fsmonitor` in a test; (2) annotation IDs reach `git show` unsanitized, so `--output=<path>` writes arbitrary files.
- **The core design does not suit a multi-user remote API.** Every operation works on a server-side working tree and checks out branches in it. Annotations also run `git checkout` on the shared repo (`annotations.py:72`), which silently moves HEAD for everyone. The endpoints are `async def` but call blocking pygit2 and subprocess code, so they stall the event loop.
- **The docs overstate the project a lot.** README, USER_GUIDE, writegit-project-doc and the 35k-line generated `wiki/` describe commands and features that don't exist (`gitwrite combine`, `gitwrite annotations ...`, `cherry-pick --modify`, `selective-merge`, `config`, `stats`, `doctor`, a mobile EPUB reader, HTML export, Postgres/Redis). There is no `gitwrite` console script, so the documented `gitwrite init` command doesn't exist after install. `docs/API_REFERENCE.md` has wrong paths for save, branches, merges, commits and annotations.
- **The CLI works for single-user local use** apart from tag add and review. The SDK's 58 tests pass, but they use mocked HTTP. The web app builds with Vite but fails `tsc -b` (3 errors) and lint (29 errors), and it calls the API's global-repo endpoints, so file viewing and diffs are broken in practice.
- **Keep vs rewrite:** keep the *knowledge*, rewrite the *API layer*. Salvage the parts of `gitwrite_core` that work: the init layout, save/commit, word-diff, merge/cherry-pick/revert, export via pandoc, and the annotation-as-commit format. Port them behind a fresh, small API designed for Veneer, with a real per-repo path resolver, real auth, ownership checks, and no working-tree mutation (bare repos plus in-memory index/tree building). Throw away `gitwrite_api/routers/*`, `security.py`, the upload flow, the web app, and most of the docs/wiki. Patching the current API would mean touching nearly every endpoint anyway.

## Test results

**Python (pytest, Python 3.10.6; deps pinned to the `poetry.lock` versions, pygit2 1.18.2 / libgit2 1.9.1):**

| Run | Passed | Failed | Skipped | xfail |
|---|---|---|---|---|
| Owner's real git config (`init.defaultBranch=main`) | 366 | 17 | 1 | 2 |
| Neutral git config (HOME with only user.name/email; matches CI on ubuntu) | 383 | 0 | 1 | 2 |

Coverage (neutral run): 62% overall. core: annotations 83%, branching 90%, export 67%, repository 53%, tagging 65%, versioning 56%. api: routers/repository 48%, annotations 59%, uploads 89%, main 34%. cli/main.py 60%.

Failure groups (owner config run):

- **Hardcoded `master` branch (17).** 15 `TestSyncRepositoryCore` tests in `tests/test_core_repository.py` try to create `refs/heads/main` (e.g. line 219), which already exists when git's default branch is `main`, so they hit `AlreadyExistsError`. `test_switch_dirty_workdir_cli` fails with "Expected branch 'master' not found" (`tests/test_cli_explore_switch.py:176`), and `test_sync_conflict_cli` fails for the same reason. These are test bugs, not product bugs. Fix them by setting the initial branch explicitly in fixtures.
- **Skipped (1).** `tests/test_core_export.py:330` skips because it uses `Oid.hex`, which pygit2 1.18 removed. That's the same API drift that breaks `tagging.py`.
- **xfail (2).** `tests/test_api_uploads.py:256` (upload complete returns 404) and `tests/test_core_repository.py:559` (bare remote setup flawed).

**Environment problems found while running:**

- The root `.venv` is broken. Its `python` symlink points to `/Users/stmiller/.pyenv/versions/3.10.12/...`, a different machine and user, so `poetry run pytest` doesn't work out of the box.
- The lock file doesn't fully protect you. pydantic is not pinned in `pyproject.toml`, and fresh resolution picks pydantic 2.14, which breaks FastAPI 0.104 at import time (`AttributeError: 'FieldInfo' object has no attribute ...` in 6 API test modules). It works only with the locked pydantic 2.11.7.
- Pandoc 3.9 is installed and EPUB and DOCX export work. PDF fails locally ("pdflatex not found"). The Dockerfile does install texlive, so PDF is plausible in Docker but was not tested.
- Importing `gitwrite_api.routers.uploads` creates `/tmp/gitwrite_repos` as a side effect (`uploads.py:32`).

**SDK (`gitwrite_sdk`):** the committed `node_modules` was incomplete (no `.bin`, no ts-jest), so the first run failed with "Preset ts-jest not found". After `npm ci`: 1 suite, **58/58 passed**, `tsc --noEmit` clean. The tests mock axios, so none of them hit the real API.

**Web (`gitwrite-web`):** after `npm ci`, `vite build` **succeeds** (one chunk over 500 kB). `tsc -b` **fails with 3 errors**: `BranchReviewCommit`, `CherryPickResponse` and `CompareRefsResponse` aren't exported from `gitwrite-sdk` (TS2459). Because `npm run build` = `tsc -b && vite build`, the official build fails. `eslint .` reports **31 problems (29 errors)**: 13 `no-unused-vars`, 13 `no-explicit-any`, 3 `react-refresh/only-export-components`.

**integration_tests/:** not run. They need a live server on :8000 and the web app on :5174, and they import `requests`, which is not a declared dependency. The TestClient smoke test below covers the same ground.

## Feature matrix

Status key: works = exercised for real in this audit; broken = fails when run for real; stub = partially wired or placeholder; missing = claimed but no code; untested = code exists but wasn't exercised.

| Feature | Claimed where | Status | Evidence |
|---|---|---|---|
| Init project (drafts/, notes/, metadata.yml, .gitignore, initial commit) | README, USER_GUIDE, CLAUDE.md | works | core + CLI `init novel` smoke; API `POST /repository/repositories` with name returns 201 |
| Init via API without project_name | API_REFERENCE | broken | returns 500 "No such file or directory"; `routers/repository.py:936-946` passes a non-existent uuid dir to core |
| Save / commit | all docs | works | core `save_changes`, `save_and_commit_file`; CLI `save`; API `POST /repository/{repo}/save` 200 |
| History / list commits | all docs | works | CLI `history`; API `GET /repository/{repo}/commits` 200 |
| Status | README, USER_GUIDE | works | CLI `status` |
| Explore (create + switch branch) | all docs | works | CLI `explore alt`; API `POST /repository/{repo}/branches` 201 |
| Switch branch / list branches | all docs | works | CLI `switch`; API `PUT /repository/{repo}/branch` 200 |
| Merge | all docs | works | fast-forward via CLI and API; conflict path covered only by tests |
| `gitwrite combine` | USER_GUIDE:202,433 | missing | command is `merge` |
| Compare / word-level diff | README, FR-007 | works (core/CLI); broken (API) | CLI `compare alt master`; core `get_word_level_diff`; API `/repository/compare` uses global path, returns 500 |
| Review branch | README, USER_GUIDE | broken | `walk() takes no keyword arguments` at `versioning.py:691`; CLI prints the error and exits 0; API route also global |
| Cherry-pick | README, API_REFERENCE | works (core); broken (API) | core smoke OK; API `routers/repository.py:890` uses global path |
| Cherry-pick `--modify`, selective-merge, split-commit, modify-change, beta-branch | README:115, writegit-project-doc | missing | no such options or commands in `gitwrite_cli/main.py` |
| Revert | API_REFERENCE, CLI | works (core/CLI); broken (API) | CLI `revert HEAD` OK on a clean tree; API global path `routers/repository.py:464` |
| Tag create | README, wiki | broken | `AttributeError: '_pygit2.Commit' object has no attribute 'oid'` at `tagging.py:32` (core, CLI `tag add`, API) |
| Tag list | wiki, SDK | works (core/CLI); broken (API) | returns empty; API global path |
| Ignore add/list | CLI | works (core/CLI); broken (API) | API global path `routers/repository.py:593` |
| Sync (fetch/merge/push) | README, USER_GUIDE | works (core); untested (CLI with remote); broken (API) | core pushed a new branch to a bare remote; API global path |
| Export EPUB | all docs | works (core/CLI); broken (API) | `book.epub` produced; API `/repository/export/epub` global path, returns 500 |
| Export DOCX | USER_GUIDE says "planned" | works (core/CLI); broken (API) | `book.docx` produced |
| Export PDF | USER_GUIDE says "planned" | untested | pdflatex not installed locally; Dockerfile installs texlive |
| Export HTML | README:268, USER_GUIDE:314 | missing | no code |
| Annotations create/list/update status | README, API_REFERENCE, wiki | works (core); broken (API) | core smoke OK, but it moves HEAD to the feedback branch; API uses global path |
| CLI `gitwrite annotations list/accept/reject` | USER_GUIDE:277-281, wiki | missing | no annotations group in CLI |
| Multi-file upload (initiate/upload/complete) | wiki/backend-api/file-uploads | stub | separate repo root `uploads.py:23`; hash check commented out `uploads.py:223`; in-memory sessions `uploads.py:56`; test xfail |
| Repo tree browse | API_REFERENCE | works | `GET /repository/{repo}/tree/HEAD` 200; `path=../..` returns 500 not 4xx |
| File content at commit | API_REFERENCE | works (core); broken (API) | API global path `routers/repository.py:655` |
| List repositories | API_REFERENCE | works | `GET /repositorys` (sic, typo is the real path) |
| JWT login | all docs | works | `/token` for all 4 users |
| Dev credential writeruser/writerpass | CLAUDE.md | broken (doc) | real password is `writepass` (`security.py:72`) |
| Role-based permissions | README, USER_GUIDE | stub | only some routes check roles; beta reader can create/switch/merge branches (`routers/repository.py:295,325,366`); no per-repo ownership |
| `/users/me` | SDK `apiClient.ts:608` | missing | endpoint commented out in `main.py:95-102` |
| `gitwrite` console command | README, USER_GUIDE | missing | no `[tool.poetry.scripts]` in `pyproject.toml`; only `python -m gitwrite_cli.main` works |
| Config via env (secret, CORS, repo path) | DEPLOYMENT*.md, .env.example, docker-compose | missing | `security.py:11` TODO; CORS hardcoded `main.py:12-16`; repo roots hardcoded |
| Postgres / Redis | .env.production, DEPLOYMENT docs | missing | no DB code anywhere |
| Health check | DEPLOYMENT docs | works | `/health` 200 |
| Web UI | README, USER_GUIDE | broken | `tsc -b` fails; calls global-repo endpoints; redirects to `tree/main` while repos default to the git config branch |
| Mobile EPUB reader | README:50 | missing | no code |
| TypeScript SDK | README | works (mocked) | 58/58 tests with mocked axios; paths match the API routes |

## Component notes

### gitwrite_core

- About 4.1k lines. It's the most valuable code in the repo, but it carries API drift and layering problems.
- **pygit2 API drift:** `tagging.py:32` (`.oid`, now `.id`) and `versioning.py:691` (`walk(..., hide=)`; the new API needs `walker.hide()`). The tests didn't catch either because they mock. Pin pygit2 or run a full sweep for removed attributes.
- **Layering inversion:** `gitwrite_core/annotations.py:13` imports `Annotation` and `AnnotationStatus` from `gitwrite_api.models`, so the core depends on the API package.
- **Two engines:** most code uses pygit2, but annotations shell out to the `git` CLI (`annotations.py:19-30`) and do `git checkout <feedback_branch>` in the working tree (`annotations.py:72,407`).
- **Duplicates:** `list_branches` exists in both `branching.py:82` (returns a list) and `repository.py:605` (returns a dict). `get_conflicting_files` is copied into `repository.py:329` from `versioning.py:254`.
- **Repo lookup walks upward:** functions use repository discovery, which searches parent directories ("No Git repository found at or above ..."), so a bad path can resolve to an enclosing repo.
- **Error style is mixed.** Some functions return `{'status': 'error'}` dicts and others raise custom exceptions, so every caller has to handle both.

### gitwrite_api

- 28 routes. Three different repo-path conventions coexist (per-repo under `gitwrite_user_repos/`, global placeholder, uploads root), so most features fail end to end even though their unit tests pass.
- Route naming is inconsistent: `GET /repositorys` (`routers/repository.py:620`, `@router.get("s")`), `/repository/repositories`, `/repositories/{id}/save/initiate`, `/repository/annotations`.
- `routers/repository.py:931` has a project_name check that's logically wrong (`not isalnum() and '_' not in and '-' not in`). It's harmless only because the pydantic pattern at `models.py:67` blocks traversal first.
- Login prints usernames and auth outcomes to stdout (`routers/auth.py:31-55`).
- Error responses echo absolute server paths and raw exception text.
- The `/test_upload_router` debug endpoint is still mounted (`uploads.py:79`).

### gitwrite_cli

- `gitwrite_cli/main.py` (1,680 lines, Click + Rich) is the only real source. It worked end to end for init/save/status/history/explore/switch/compare/merge/ignore/revert/export epub+docx. `tag add` and `review` are broken (core bugs). On error, `revert` prints a stray "An unexpected error occurred: 1" because it catches its own `sys.exit`. `review` exits 0 on failure.
- The "1,086 .py files / 378k lines" are **`gitwrite_cli/.venv`**: a 35 MB Python 3.10 virtualenv (pygit2 1.18, rich, click, pytest). It's left over from when the CLI was its own Poetry project. It's untracked and gitignored, but it lives in Dropbox. Alongside it are tracked leftovers: `gitwrite_cli/poetry.lock`, `gitwrite_cli/coverage.xml`, `gitwrite_cli/.coverage`, `gitwrite_cli/README.md`.

### gitwrite_sdk

- About 1.4k lines of TypeScript, and paths match the API. It calls `/users/me`, which doesn't exist. It has no wrappers for tag create, PDF or DOCX export.
- `dist/` is committed and is what the web app consumes (`"gitwrite-sdk": "file:../gitwrite_sdk"`). It doesn't export the types the web app needs.
- Build and test tools (jest, rollup, typescript, @types/jest) sit under `dependencies` instead of `devDependencies`.
- It's irrelevant to Veneer unless the plugin is written in TS and wants a typed client. Even then, it should be regenerated from a new OpenAPI spec rather than maintained by hand.

### gitwrite-web

- React 19 / Vite 7 / Tailwind 4 / Radix. It builds with Vite, but the type check and lint fail.
- `Login.tsx:15` hardcodes `http://localhost:8000`, while other components read `VITE_API_BASE_URL`.
- It depends on the broken global-repo endpoints (file content, compare, review).
- Veneer replaces it, so it's a candidate to cut entirely.

## Security / remote-API readiness

Findings are concrete and ordered by severity. "Confirmed" means it was reproduced in the scratchpad.

1. **Critical, confirmed: write into `.git/` leads to command execution.** `save_and_commit_file` (`gitwrite_core/repository.py:781-815`) checks that the path is inside the repo but doesn't reject `.git/`. It writes the file and only then fails at staging. `POST /repository/book/save` with `file_path=".git/config"` and an `fsmonitor` command overwrote the config. The next `git status` ran the attacker command, which created the PWNED marker. Annotations already shell out to git, so any future per-repo annotation call would trigger it on the server. The multi-file path does block `.git` (`repository.py:1278`); the single-file path does not. Any OWNER/EDITOR/WRITER can do this.
2. **High, confirmed: git argument injection, arbitrary file write.** `update_annotation_status` passes the user-supplied `annotation_commit_id` straight into `git show -s --format=%B <id>` (`gitwrite_core/annotations.py:418`). The ID `--output=/path/x` created the file. It's reachable through `PUT /repository/annotations/{annotation_commit_id}`. Commands need `--` separators and OID validation.
3. **High: hardcoded JWT secret.** `SECRET_KEY = "your-secret-key"` (`gitwrite_api/security.py:12`). Anyone can mint tokens for `johndoe` (OWNER). docker-compose passes `GITWRITE_SECRET_KEY`, but the code never reads it.
4. **High: fake user DB with public credentials.** `FAKE_USERS_DB` (`security.py:51-84`) holds hardcoded users whose passwords are in the docs. There's no user store, registration, password change, lockout or rate limiting on `/token`.
5. **High: no per-repo authorization.** Roles are global per user (`security.py:122-141`). Any authenticated user can list and act on every repo (`GET /repositorys` returns all). Branch create, switch, merge, cherry-pick, revert, sync, tag and compare only require login, not a role (`routers/repository.py:295,325,366,462,496,547,888`). A beta reader can create and merge branches (confirmed).
6. **Medium: unauthenticated upload endpoint.** `PUT /upload-session/{upload_id}` has no auth dependency, with "auth is via the obscurity of upload_id" (`uploads.py:152-158`). The declared SHA-256 is never checked (`uploads.py:223` commented out). Sessions live in a process-global dict (`uploads.py:56`), so they're lost on restart and don't work with multiple workers.
7. **Medium: repo_name path handling.** `repo_name` goes straight into `Path(base) / repo_name` (`routers/repository.py:228,246,261,...`). A percent-encoded `..` (`/repository/%2e%2e/commits`) resolves to the parent of the user-repos dir (confirmed), and core repository discovery then walks further up. No validation or allowlist, and no `resolve()` + `is_relative_to` check on repo paths.
8. **Medium: shared mutable working tree.** Switch, merge, cherry-pick and annotations all check out branches in the one server-side working directory. Concurrent users will corrupt each other's state. The endpoints are `async def` but do blocking I/O.
9. **Low: CORS** is hardcoded to localhost origins with `allow_credentials=True` (`main.py:12-24`), and `GITWRITE_CORS_ORIGINS` is ignored. That's harmless for a native Veneer plugin, but it shows config isn't wired.
10. **Low: information leaks.** 500 responses include absolute filesystem paths and raw exception strings. Login logs usernames via `print` (`routers/auth.py:31-55`).
11. **Low: aging security dependencies.** passlib 1.7.4 is unmaintained, and bcrypt is pinned to 4.0.1 to stay compatible with it. python-jose is a weakly maintained JWT library; PyJWT is the usual replacement. Starlette 0.27 and python-multipart 0.0.9 are far behind current releases and predate several published multipart/DoS advisories.

Remote-API verdict: not deployable. Before any network exposure you need at minimum: env-based secret, a real user store or delegated auth (API tokens per Veneer install), a per-repo ACL, one validated repo resolver, `.git` and argument-injection hardening, and moving off the shared checked-out working tree.

## Hygiene and dependencies

- **Committed by mistake:** `repomix-output.xml` (1.3 MB, tracked even though `.gitignore` lists it), `.coverage`, `gitwrite_cli/.coverage`, `gitwrite_cli/coverage.xml`, `gitwrite_cli/poetry.lock` (a stale second lock), `gitwrite_sdk/dist/`, `.claude/settings.local.json`, `.vscode/settings.json` (also gitignored), `.qoder/quests/*`, `gitwrite_api/.placeholder`, `tests/check_pygit2_import.py`.
- **Untracked bloat on disk:** `gitwrite_cli/.venv` (35 MB) and the broken root `.venv` (104 MB, points to another user's pyenv).
- **Duplicate and generated docs:** `DEPLOYMENT.md` and `docs/DEPLOYMENT_GUIDE.md` overlap. `wiki/` is about 35k lines of generated prose describing features that don't exist (`config`, `stats`, `doctor`, `backup`, `collaborate`, `milestone`, ...). `writegit-project-doc.md` is a 1,000-line aspirational PRD. README's roadmap lists everything as unchecked, while other docs claim the same features are done.
- **Python:** `requires-python >=3.10`; CI, Dockerfile and venvs all use 3.10, which reaches end of life in October 2026, so move to 3.12+.
- **pyproject.toml:** it uses the deprecated `[tool.poetry.dev-dependencies]` and deprecated `[tool.poetry]` metadata (Poetry 2.3 warns). It has no `[tool.poetry.scripts]`. pydantic is not declared even though the API depends on its version. `typer` is a dev dep used by only one test file.
- **Python versions, locked vs latest:** fastapi 0.104.1 vs 0.162, starlette 0.27 vs 1.7, uvicorn 0.29 vs 0.54, httpx 0.25 vs 0.28, python-multipart 0.0.9 vs 0.0.32, bcrypt 4.0.1 vs 5.0, pydantic 2.11 vs 2.14 (and 2.14 breaks fastapi 0.104). pygit2 1.18.2 is recent, but the code was written against an older API.
- **JS:** web is mostly current-ish (React 19.1, Vite 7) but behind on react-router 6 to 7, eslint 9 to 10, and TypeScript 5.8 (7.x is out). SDK jest 30 and rollup 4 are fine. `npm ci` warns that esbuild/fsevents install scripts were blocked; the build still worked.
- **CI** (`.github/workflows/test.yml`) runs pytest with coverage for core and CLI only (no API coverage), plus SDK jest. It doesn't run web build or lint. It passes only because ubuntu's git default branch is `master`.

## Suggested cleanup priorities

1. **Decide the Veneer API shape first** (bare repos, stateless operations, token auth per Veneer install, per-repo ACL) and treat the current `gitwrite_api` as reference only. Don't harden it in place.
2. **Fix the core blockers you'll reuse:** `tagging.py:32` `.oid` to `.id`, `versioning.py:691` walk/hide, reject `.git/` in `save_and_commit_file`, add `--` and OID validation to every `_run_git_command`, remove the `gitwrite_core` to `gitwrite_api.models` import.
3. **Make the test suite honest:** set the initial branch explicitly in fixtures, pin pydantic (or upgrade FastAPI), and add unmocked integration tests that drive core and API against real temp repos (the scratchpad smoke scripts are a template). Delete or rewrite the mock-heavy API tests along with the API.
4. **Replace the annotation implementation's `git` CLI and `checkout` usage** with pygit2 commits built straight onto the feedback ref without touching the working tree.
5. **Repo hygiene pass:** untrack `repomix-output.xml`, the coverage files, `gitwrite_cli/poetry.lock`, `gitwrite_sdk/dist`, `.claude/settings.local.json`, `.qoder/`. Delete `gitwrite_cli/.venv` and recreate the root `.venv` (`poetry env remove` + `poetry install`). Modernize `pyproject.toml` to PEP 621 and move to Python 3.12+.
6. **Cut or archive the stuff Veneer replaces:** `gitwrite-web/`, `gitwrite_sdk/` (regenerate from OpenAPI later if needed), `wiki/`, `writegit-project-doc.md`, the duplicate deployment docs, nginx/docker-compose Postgres/Redis config that nothing uses.
7. **Rewrite README and API docs from what actually exists** after the new API lands. Until then, add a banner to README that the docs are aspirational.
8. **Keep the CLI only if it's useful as a local power-user tool.** It mostly works and is cheap to keep once the core bugs are fixed, but it isn't on the Veneer path.
