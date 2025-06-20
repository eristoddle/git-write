# Implementation Plan: GitWrite Platform

Project Goal: Develop a comprehensive, Git-based version control ecosystem for writers, starting with a core library, a CLI, and a REST API.

## General Project Notes
*   **Memory Bank System:** Single file `Memory_Bank.md`.
*   **Architectural Goal:** A central `gitwrite_core` library will contain all business logic. The `gitwrite_cli` and `gitwrite_api` will be thin wrappers around this core library.

---
## Phase 1-4: CLI Refactoring
Status: **Completed**
Summary: All tasks related to refactoring the CLI application and establishing the `gitwrite_core` library have been successfully completed. The project is ready for the next epic.

---

## Phase 5: REST API Development
Status: **Pending**
Architectural Notes: The API will be built using FastAPI and containerized with Docker. It will use a two-step upload process to handle large files securely and efficiently, preventing API server bottlenecks.

### Task 5.1 - Agent_API_Dev: Initial API and Docker Setup
Objective: Create the `gitwrite_api` directory, set up the basic FastAPI application, and create a `Dockerfile` for containerization.
Status: **Completed**

1.  Create the `gitwrite_api/` directory at the project root.
2.  Update the root `pyproject.toml` to include `gitwrite_api` in the `[tool.poetry.packages]` section. Add `fastapi`, `uvicorn[standard]`, and `python-jose[cryptography]` as new dependencies. Run `poetry lock` and `poetry install`.
3.  Create `gitwrite_api/main.py` with a basic FastAPI app instance and a `/` health-check endpoint.
4.  Create a `Dockerfile` at the project root that correctly copies all source directories (`gitwrite_api`, `gitwrite_core`), installs dependencies via Poetry, and runs the API using `uvicorn`.

### Task 5.2 - Agent_API_Dev: Implement Security and Authentication
Objective: Set up JWT-based authentication and basic security helpers.
Status: **Completed**

1.  Create a `gitwrite_api/security.py` module for JWT creation and decoding functions.
2.  Implement a `get_current_user` dependency to protect endpoints.
3.  Create `User` models in a `gitwrite_api/models.py` file using Pydantic.
4.  Create a `/token` endpoint in `gitwrite_api/routers/auth.py` for issuing JWTs based on a temporary in-memory user store.

### Task 5.3 - Agent_API_Dev: Implement Read-Only Repository Endpoints
Objective: Create secure endpoints for non-mutating operations to validate the API structure.
Status: **Completed** - Implemented read-only API endpoints for branches, tags, and commits. Includes core functions and API router. Unit tests added. Developed on branch `feature/api-readonly-repo-endpoints`.

1.  Create a new router file, e.g., `gitwrite_api/routers/repository.py`.
2.  Create a `GET /repositories/{repo_id}/history` endpoint. This will call `gitwrite_core.versioning.get_commit_history` and return the list of commits as JSON.
3.  Create a `GET /repositories/{repo_id}/tags` endpoint that calls `gitwrite_core.tagging.list_tags`.
4.  Protect these endpoints with the `get_current_user` dependency from Task 5.2.
5.  Add unit tests for these endpoints.

### Task 5.4 - Agent_API_Dev: Design and Implement Large File Upload Strategy
Objective: Implement the two-step upload mechanism to handle large files.
Status: **Pending**

1.  Create a new router file, e.g., `gitwrite_api/routers/uploads.py`.
2.  Implement the first step: `POST /repositories/{repo_id}/save/initiate`. This endpoint takes metadata (commit message, file paths, hashes) and returns a list of secure, one-time upload URLs and a completion token.
3.  Implement the upload handler: `PUT /upload-session/{upload_id}`. This endpoint will stream the raw request body to a temporary file on the server.
4.  Implement the final step: `POST /repositories/{repo_id}/save/complete`. This endpoint takes the `completion_token`.

### Task 5.5 - Agent_API_Dev: Implement the `save` Endpoint Logic
Objective: Connect the upload mechanism to the core `save_changes` function.
Status: **Pending**

1.  Modify the `/save/complete` endpoint from Task 5.4.
2.  After receiving the completion signal, the endpoint will gather all files from the temporary storage location associated with the token.
3.  It will then call `gitwrite_core.versioning.save_changes` with the commit message and the paths to the temporary files.
4.  Upon successful commit, it will delete the temporary files and return the new commit information.
5.  Add integration tests that simulate the full three-step `save` process.

---
## Note on Handover Protocol

For long-running projects or situations requiring context transfer (e.g., exceeding LLM context limits, changing specialized agents), the APM Handover Protocol should be initiated. This ensures smooth transitions and preserves project knowledge. Detailed procedures are outlined in the framework guide:

`prompts/01_Manager_Agent_Core_Guides/05_Handover_Protocol_Guide.md`

The current Manager Agent or you should initiate this protocol as needed.