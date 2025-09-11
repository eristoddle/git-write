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