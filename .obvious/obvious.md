# GitWrite (eristoddle/git-write)

Version control for writers, built on plain git via pygit2. A GitWrite project is an
ordinary git repository; the `gitwrite` CLI gives writer-friendly command names.

## Stack

- **Language:** Python 3.12+ (`.python-version`: 3.12), managed with [uv](https://docs.astral.sh/uv/) (`uv.lock`).
- **CLI:** Click-based (`gitwrite_cli/main.py`, entry point `gitwrite = gitwrite_cli.main:cli`).
- **Core:** pygit2, pypandoc, pyyaml, rich (`gitwrite_core/`).
- **Node sub-projects:** `veneer-plugin/` (TypeScript Veneer plugin) and `interop/` (Node harness proving pygit2 ↔ isomorphic-git repo compatibility). Node 20+ (CI uses 22).
- **External binary:** pandoc — required for `gitwrite export` (EPUB/DOCX/PDF). Not required for the rest of the CLI or tests (export tests skip when missing).

## Commands

```bash
uv sync                          # install Python deps (creates .venv)
uv run gitwrite --help           # run the CLI from source
uv run pytest --cov=gitwrite_core --cov=gitwrite_cli tests/   # tests
uv run ruff check .              # lint (line length 100)

npm ci --prefix interop && npm ci --prefix veneer-plugin
GITWRITE_REQUIRE_INTEROP=1 uv run pytest tests/   # CI parity: interop must be installed
cd veneer-plugin && npm run typecheck && npm test && npm run build
```

There is no server, database, or long-running process. "Local dev" = the CLI against
scratch git repositories. CI requires `git config --global user.name/user.email` to be set.

## Codebase map

See [codebase-map.md](codebase-map.md) for the folder-level table.

## Key conventions

- **Test rule (from CLAUDE.md):** never mock pygit2 or `gitwrite_core`. Use real temporary
  repositories and set the initial branch explicitly (`tests/helpers.init_repo(path, bare=False, branch="main")`).
- `PLAN.md` is the hot decision record; `TASKS.md` is the implementation handoff contract;
  `docs/` holds cooled decisions, AUDIT, USER_GUIDE, ANNOTATION_FORMAT.
- `.env.example` describes an old API/web stack that was deleted (decision D4/D11);
  the current codebase needs no env vars. Postgres/Redis entries there are historical.

## Local verification

1. `uv run ruff check .` — clean.
2. `uv run pytest --cov=gitwrite_core --cov=gitwrite_cli tests/` — all green (382 passed, 1 skipped at onboarding).
3. `veneer-plugin`: typecheck, vitest (300 tests), build all green.
4. End-to-end CLI flow (verified at onboarding):
   `gitwrite init "Novel"` → write `draft.md` → `gitwrite save "msg"` → `gitwrite history`
   → `gitwrite tag add milestone-1` → `gitwrite explore twist-ending` → edit + `save` →
   `gitwrite switch main` → `gitwrite compare main twist-ending` →
   `gitwrite export epub -o out.epub . draft.md`.
   Note: init creates a dir named after the project (spaces preserved). `switch`/`compare`
   expect the branch `main`; set `git config --global init.defaultBranch main` first
   (sandboxes often default to `master`).

## Sandbox snapshot

- **snapshotId:** `wj9lwp9kh8sromfr1018:default`
- **Captured:** 2026-11-19T00:43:37Z
- **State captured:** uv-installed Python 3.12 venv (`uv sync` done), `interop/` and
  `veneer-plugin/` node_modules installed, pandoc 3.1.11.1 installed, git identity
  (`Test User <test@example.com>`) and `init.defaultBranch=main` configured globally.

## Validation summary

- Lint: `uv run ruff check .` → "All checks passed!"
- Tests: 382 passed, 1 skipped (pandoc now installed so export tests run), 67% coverage.
- Plugin: typecheck OK, 300 vitest tests passed, esbuild build OK.
- Primary flow: full writer workflow above verified end-to-end, EPUB artifact produced.
- `dev_stack_healthy: true`.
