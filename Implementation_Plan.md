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
Status: **Completed**

Key Implemented Components:
1.  **Pydantic Models**: Defined `FileMetadata`, `FileUploadInitiateRequest`, `FileUploadInitiateResponse`, `FileUploadCompleteRequest`, and `FileUploadCompleteResponse` in `gitwrite_api/models.py` for handling request and response data for the upload process.
2.  **Upload Router Setup**: Created `gitwrite_api/routers/uploads.py` containing two `APIRouter` instances:
    *   `router`: For main save operations, prefixed with `/repositories/{repo_id}/save`.
    *   `session_upload_router`: For handling individual file uploads, without a repository-specific prefix.
3.  **Initiation Endpoint**: Implemented `POST /repositories/{repo_id}/save/initiate` on `router`. This endpoint:
    *   Accepts a commit message and a list of files (path and hash).
    *   Generates unique upload IDs and a completion token.
    *   Stores session metadata (repo ID, user ID, commit message, file details) in an in-memory dictionary `upload_sessions`.
    *   Returns upload URLs (relative paths like `/upload-session/{upload_id}`) and the completion token.
4.  **File Upload Handler Endpoint**: Implemented `PUT /upload-session/{upload_id}` on `session_upload_router`. This endpoint:
    *   Accepts a file via `UploadFile`.
    *   Finds the corresponding session using `upload_id`.
    *   Saves the uploaded file to a temporary location (`TEMP_UPLOAD_DIR`).
    *   Updates the session to mark the file as uploaded and records its temporary path.
5.  **Completion Endpoint**: Implemented `POST /repositories/{repo_id}/save/complete` on `router`. This endpoint:
    *   Accepts a `completion_token`.
    *   Validates the token, user ownership, repository ID, and ensures all declared files have been uploaded.
    *   Currently simulates a commit (actual Git operations deferred to Task 5.5).
    *   Clears the session from `upload_sessions`.
    *   Returns a simulated commit ID.
6.  **Main App Integration**: Updated `gitwrite_api/main.py` to include both `uploads.router` and `uploads.session_upload_router` in the FastAPI application.
7.  **Unit Tests**: Created `tests/test_api_uploads.py` with comprehensive unit tests for the initiate, upload, and complete endpoints, covering success and various error scenarios using `TestClient` and authentication mocking.

### Task 5.5 - Agent_API_Dev: Implement the `save` Endpoint Logic
Objective: Connect the upload mechanism to the core `save_changes` function.
Status: **Completed**

Implemented the `POST /repository/save` endpoint and the core function `save_and_commit_file` in `gitwrite_core/repository.py`. This allows saving file content with a commit message. Added Pydantic models `SaveFileRequest` and `SaveFileResponse`. Included comprehensive unit tests for both API and core logic.

---
## Note on Handover Protocol

For long-running projects or situations requiring context transfer (e.g., exceeding LLM context limits, changing specialized agents), the APM Handover Protocol should be initiated. This ensures smooth transitions and preserves project knowledge. Detailed procedures are outlined in the framework guide:

`prompts/01_Manager_Agent_Core_Guides/05_Handover_Protocol_Guide.md`

The current Manager Agent or you should initiate this protocol as needed.