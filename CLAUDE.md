# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is in this repo

GitWrite is version control for writers on plain git. Decisions and direction live in `PLAN.md`; read it
before design work. The repo holds:

- `gitwrite_core/`: operations built on pygit2 (repository, versioning, branching, tagging, annotations,
  export, exceptions, models).
- `gitwrite_cli/`: the Click-based `gitwrite` command (`gitwrite_cli.main:cli`).
- `tests/`: pytest suite.
- `veneer-plugin/`: the Veneer plugin. It does not exist yet (queues 3 and 4 in `TASKS.md`).
- `docs/`: `AUDIT.md` (what works and what was broken), `USER_GUIDE.md`, `VENEER_DIRECTION.md`,
  `ANNOTATION_FORMAT.md` (queue 2). The old API, SDK, web app, wiki and deployment files were
  deleted (D4, D11) and are in git history.

## Commands

Python 3.12+, managed with uv.

```bash
uv sync                          # install
uv run pytest                    # tests
uv run ruff check .              # lint (line length 100, rules: defaults + import sorting)
uv run gitwrite --help           # run the CLI from source
```

## Test rule

**Never mock pygit2 or `gitwrite_core` in tests.** Use real temporary repositories, and set the initial
branch explicitly (`tests/helpers.init_repo(path, bare=False, branch="main")`) so the suite does not
depend on the machine's `init.defaultBranch`. The old suite mocked these and stayed green while tag
creation and branch review were broken. Export tests that need pandoc skip when it is missing.

## Development workflow — planning vs implementation

Planning and implementation run in two layers by design.

- **Planning (the main thread).** Question/answer and exploration, landing on decisions recorded in `PLAN.md`. Reads test output, makes design calls, owns live testing. When the shape of something isn't clear yet, that exploration has a structured form: the **`living-plan`** skill's `grill` workflow interviews round-by-round until the design tree has been *visited*, so whatever stays undecided lands in Open questions or the Parking lot instead of staying invisible. Ask for it ("grill me", "what am I missing"); offer it in one line — never launch it — when the user is thinking out loud without a question.
- **Implementation (the `implementer` agent).** Once a decision is concrete enough to build, the planning thread writes the active task into `TASKS.md` and launches the `implementer` agent (Sonnet, locally or in a Claude Code cloud session). It runs in its own context window and works the queue on its own branch, ending in a PR. On return, the planning thread reviews the diff and oversees testing.

`TASKS.md` is the handoff contract. The active task is a **serial queue of numbered pieces** — stack as few or as many as you like, which serves both **pacing** (queue a little, plan ahead while the agent grinds) and **unattended** (queue a lot and walk away). The default is synchronous: one agent works the queue top-to-bottom and reports once at the end; a blocked piece is skipped (not halted on) so the run finishes everything it legitimately can, and the agent **logs run-state into `TASKS.md` on every stop** (per-piece status + a ▶ Run state note) so a killed or forgotten session is recoverable from the file on disk. Standing "how we implement here" knowledge lives in the **agent definition**, not in every task. Only fully-specified, mechanical work is delegable; design decisions, open questions, and live testing stay in the planning thread.

**Synchronous is the default on purpose — the objective is pacing, not raw throughput.** Running *parallel* agents across disjoint files is a separate, explicit **opt-in burst tactic** chosen per-task — never the default; the agent itself never self-parallelizes.

**External task mirror — the `## TODO` list in `~/Dropbox/Apps/remotely-save/Writing/10 Reference/10.06 Ideas/Software-Website-Business/📝 GitWrite.md` (Obsidian vault).** A second copy of this project's task list lives outside the repo, so items can be captured away from the machine and read back here. This only works where that path exists (Stephan's machine, not cloud sessions). **Reconcile it before starting a queue and again after finishing one** — otherwise it drifts silently and gets forgotten. An item present on one side and missing from the other is **not** a decision to delete it: absence means "not yet mirrored," never "dropped." Nothing in `PLAN.md` or `TASKS.md` exists to serve the mirror — the mirror side owns the pointer and the reconciliation, and these docs stay standalone without it.

`PLAN.md` is the **hot** decision record — keep it lean. Cooled material (old session logs, settled/superseded decisions, deferred ideas) is progressively disclosed into `docs/` with one-line pointers left behind. When `PLAN.md` grows heavy to read each session, invoke the **`living-plan`** skill — it detects what has cooled and relocates it, propose-then-confirm. Items ripen along one ladder — parking lot → open question → decision → task queue — and only a grill moves one up it, always propose-then-confirm.
