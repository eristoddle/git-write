# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Python Backend (API & Core)
```bash
# Start the API server
poetry run uvicorn gitwrite_api.main:app --reload

# Run tests
pytest

# Install dependencies
poetry install
```

### TypeScript SDK
```bash
cd gitwrite_sdk
npm install
npm run build
npm test
```

### React Web Frontend
```bash
cd gitwrite-web
npm install
npm run dev      # Development server
npm run build    # Production build
npm run lint     # ESLint
```

### CLI Development
```bash
# Run CLI from source
python -m gitwrite_cli.main --help

# Test CLI commands
python -m gitwrite_cli.main init test-project
```

## Architecture Overview

GitWrite is a multi-layer platform providing Git-based version control for writers:

### Core Components

1. **gitwrite_core/** - Core Git operations using pygit2
   - `repository.py`: Repository initialization, gitignore management, sync operations
   - `versioning.py`: Commit history, diffs, saves, reverts, cherry-picking
   - `branching.py`: Branch creation, switching, merging, branch management
   - `tagging.py`: Git tag operations for versioning
   - `annotations.py`: Annotation system for collaborative editing
   - `export.py`: Export to EPUB, PDF, DOCX using Pandoc
   - `exceptions.py`: Custom exception hierarchy

2. **gitwrite_cli/** - Click-based command line interface
   - `main.py`: Full CLI with writer-friendly commands (save, explore, switch, etc.)
   - Wraps core functionality with rich console output

3. **gitwrite_api/** - FastAPI REST API
   - `main.py`: API server with authentication
   - `models.py`: Pydantic models for API
   - `security.py`: JWT authentication, user management
   - `routers/`: API endpoints organized by functionality

4. **gitwrite_sdk/** - TypeScript SDK for web integration
   - Built with Rollup, provides typed interfaces to API

5. **gitwrite-web/** - React frontend
   - Vite-based React app with Radix UI components
   - Uses gitwrite-sdk for API communication

### Key Design Patterns

- **Git Compatibility**: All repositories are standard Git repos
- **Writer-Friendly Terminology**: "save" instead of "commit", "explore" instead of "branch"
- **Collaborative Workflows**: Branch-based editing with selective integration (cherry-picking)
- **Export Pipeline**: Pandoc integration for multiple output formats

### Development Authentication

The API includes a fake database for development with these test users:
- Owner: johndoe/secret
- Editor: editoruser/editpass  
- Writer: writeruser/writerpass
- Beta Reader: betauser/betapass

### Testing Framework

- Python: pytest with pytest-cov for coverage
- TypeScript: Jest for SDK testing
- Integration tests cover the full stack

### Dependencies

- **Core**: pygit2 (Git operations), click (CLI), fastapi (API), pyyaml (metadata)
- **Export**: pypandoc (document conversion)
- **Auth**: python-jose, passlib, bcrypt
- **Frontend**: React 19, Radix UI, Tailwind CSS, Vite
- **SDK**: TypeScript, Rollup

## Project Structure Notes

This is a monorepo with Python backend components and TypeScript frontend components. The gitwrite_sdk serves as the bridge between the Python API and JavaScript/TypeScript clients.

All writer-facing operations maintain Git compatibility while providing intuitive interfaces for non-technical users.

## Development workflow — planning vs implementation

Planning and implementation run in two layers by design.

- **Planning (the main thread).** Question/answer and exploration, landing on decisions recorded in `PLAN.md`. Reads test output, makes design calls, owns live testing. When the shape of something isn't clear yet, that exploration has a structured form: the **`living-plan`** skill's `grill` workflow interviews round-by-round until the design tree has been *visited*, so whatever stays undecided lands in Open questions or the Parking lot instead of staying invisible. Ask for it ("grill me", "what am I missing"); offer it in one line — never launch it — when the user is thinking out loud without a question.
- **Implementation (the `implementer` agent).** Once a decision is concrete enough to build, the planning thread writes the active task into `TASKS.md` and launches the `implementer` agent (Sonnet, locally or in a Claude Code cloud session). It runs in its own context window and works the queue on its own branch, ending in a PR. On return, the planning thread reviews the diff and oversees testing.

`TASKS.md` is the handoff contract. The active task is a **serial queue of numbered pieces** — stack as few or as many as you like, which serves both **pacing** (queue a little, plan ahead while the agent grinds) and **unattended** (queue a lot and walk away). The default is synchronous: one agent works the queue top-to-bottom and reports once at the end; a blocked piece is skipped (not halted on) so the run finishes everything it legitimately can, and the agent **logs run-state into `TASKS.md` on every stop** (per-piece status + a ▶ Run state note) so a killed or forgotten session is recoverable from the file on disk. Standing "how we implement here" knowledge lives in the **agent definition**, not in every task. Only fully-specified, mechanical work is delegable; design decisions, open questions, and live testing stay in the planning thread.

**Synchronous is the default on purpose — the objective is pacing, not raw throughput.** Running *parallel* agents across disjoint files is a separate, explicit **opt-in burst tactic** chosen per-task — never the default; the agent itself never self-parallelizes.

**External task mirror — the `## TODO` list in `~/Dropbox/Apps/remotely-save/Writing/10 Reference/10.06 Ideas/Software-Website-Business/📝 GitWrite.md` (Obsidian vault).** A second copy of this project's task list lives outside the repo, so items can be captured away from the machine and read back here. This only works where that path exists (Stephan's machine, not cloud sessions). **Reconcile it before starting a queue and again after finishing one** — otherwise it drifts silently and gets forgotten. An item present on one side and missing from the other is **not** a decision to delete it: absence means "not yet mirrored," never "dropped." Nothing in `PLAN.md` or `TASKS.md` exists to serve the mirror — the mirror side owns the pointer and the reconciliation, and these docs stay standalone without it.

`PLAN.md` is the **hot** decision record — keep it lean. Cooled material (old session logs, settled/superseded decisions, deferred ideas) is progressively disclosed into `docs/` with one-line pointers left behind. When `PLAN.md` grows heavy to read each session, invoke the **`living-plan`** skill — it detects what has cooled and relocates it, propose-then-confirm. Items ripen along one ladder — parking lot → open question → decision → task queue — and only a grill moves one up it, always propose-then-confirm.
