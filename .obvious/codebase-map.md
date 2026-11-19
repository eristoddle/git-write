# Codebase map

| Path | What it is |
|---|---|
| `gitwrite_core/` | Core operations on pygit2: `repository.py`, `versioning.py` (save/history/revert), `branching.py`, `tagging.py`, `annotations.py`, `anchors.py`, `export.py` (EPUB/DOCX/PDF via pypandoc), `models.py`, `exceptions.py` |
| `gitwrite_cli/` | The `gitwrite` command — single Click app in `main.py` (all subcommands) |
| `tests/` | pytest suite; real temporary git repos, no mocks of pygit2/core; `helpers.py` sets up repos with explicit initial branch |
| `veneer-plugin/` | TypeScript Veneer plugin (`manifest.json` authoritative; `src/*.ts` + `*.test.ts` on the API's fake host); esbuild build |
| `interop/` | Node 22 harness (`read-repo.mjs`, `write-repo.mjs`, `lib.mjs`) proving pygit2 and isomorphic-git read each other's repos |
| `docs/` | `AUDIT.md`, `USER_GUIDE.md`, `ANNOTATION_FORMAT.md`, `VENEER_DIRECTION.md`, decisions/sessions/parking-lot notes |
| `.github/workflows/` | CI: `test.yml` (uv + ruff + pytest with interop; plugin job: typecheck/test/build) |
| `PLAN.md` / `TASKS.md` / `CLAUDE.md` | Decision record; implementation task queue; agent guidance |
