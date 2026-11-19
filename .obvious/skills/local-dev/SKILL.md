---
name: local-dev
---

# local-dev — GitWrite

Record of the LOCAL-DEV onboarding run (2026-11-19). `dev_stack_healthy: true`.

## What the stack is

No services. Pure Python 3.12 CLI (uv-managed) plus two Node sub-projects.
`pandoc` is the only system dependency, and only for `gitwrite export`.

## Setup that worked

1. `pip install uv` (or any uv install path) — sandbox had no uv.
2. `uv sync` — creates `.venv`, installs all Python deps from `uv.lock`.
3. `sudo apt-get install -y pandoc` — enables `gitwrite export` (without it, export tests skip).
4. `npm ci --prefix interop && npm ci --prefix veneer-plugin` — needed before pytest when
   `GITWRITE_REQUIRE_INTEROP=1` (CI parity).
5. Git config is required: `git config --global user.name/user.email` and
   `git config --global init.defaultBranch main` (sandbox default was `master`, which breaks
   `gitwrite switch main` in scratch projects).

## Verification (evidence)

- `uv run ruff check .` → All checks passed.
- `GITWRITE_REQUIRE_INTEROP=1 uv run pytest --cov=gitwrite_core --cov=gitwrite_cli tests/`
  → 382 passed, 1 skipped, ~6.7s.
- `veneer-plugin`: `npm run typecheck` clean; `npm test` 300 passed (14 files); `npm run build` OK.
- Primary flow in a temp dir: init → save → history → tag add → explore → save → switch main
  → compare → `export epub -o out.epub . draft.md` → EPUB artifact (4.8 KB) produced.

## Gotchas

- `gitwrite init "My Novel"` creates a directory named `My Novel` (spaces preserved) — quote it.
- `gitwrite export epub` signature: `gitwrite export epub -o OUT.epub REPO_PATH FILES...`
  (positional repo path + markdown files, relative to repo root).
- Interop tests silently skip if `interop/node_modules` is missing unless
  `GITWRITE_REQUIRE_INTEROP=1`.
- `.env.example` is a leftover from the deleted API/web stack — no env vars are needed.
