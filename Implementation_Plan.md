# Implementation Plan: GitWrite Platform

Project Goal: Develop a comprehensive, Git-based version control ecosystem for writers, with a core library, a CLI, a feature-complete REST API, and a client-side SDK.

## General Project Notes
*   **Memory Bank System:** Single file `Memory_Bank.md`.
*   **Architectural Goal:** Achieve feature parity between the API, the CLI, and the core features defined in `writegit-project-doc.md`. The TypeScript SDK will be developed once the API is feature-complete.
*   **Project Status Re-evaluation:** This plan has been updated to reflect a detailed analysis of feature parity. Phase 6 was found to be incomplete, and new phases have been added to cover all required features from the project documentation.

---

## Phase 1-5: Core, CLI, and Initial API Setup
Status: **Completed**
Summary: All tasks related to the core library, CLI, and initial API setup are complete.

---

## Phase 6: Achieve Full API Feature Parity
Status: **In Progress**
Architectural Notes: This phase will address the remaining gaps to ensure the REST API can perform all core actions available in the CLI and defined in the project documentation.

### Task 6.1 - Agent_API_Dev: Repository Initialization Endpoint
Objective: Implement an API endpoint to initialize a new GitWrite repository.
Status: **Pending**

1.  Create a new endpoint, e.g., `POST /repositories`, that takes a `project_name` and other initial metadata.
2.  This endpoint will call the existing `gitwrite_core.repository.initialize_repository` function.
3.  The endpoint should handle cases where the repository already exists, the path is invalid, etc., returning appropriate HTTP status codes (e.g., 201 Created, 409 Conflict).
4.  Add comprehensive unit tests in `tests/test_api_repository.py` for the new initialization endpoint.

---

## Phase 7: Advanced Collaboration & Content Features
Status: **Pending**
Architectural Notes: This phase implements high-priority features from `writegit-project-doc.md` that are currently missing from all components (core, CLI, and API).

### Task 7.1 - Agent_Core_Dev: Selective Change Integration (Cherry-Pick)
Objective: Implement the core logic for selectively applying commits from one branch to another.
Status: **Pending**

1.  In `gitwrite_core`, create a new module or extend `versioning.py` with a `cherry_pick_commit` function.
2.  This function will take a repository path, a commit OID to pick, and options for handling conflicts.
3.  The function should support clean cherry-picks and report conflicts accurately.

### Task 7.2 - Agent_CLI_Dev: Cherry-Pick CLI Commands
Objective: Expose the cherry-pick functionality through user-friendly CLI commands.
Status: **Pending**

1.  Create a `gitwrite review <branch>` command to list commits on another branch in a review-friendly format.
2.  Create a `gitwrite cherry-pick <commit_id>` command in `gitwrite_cli/main.py` that calls the core `cherry_pick_commit` function.
3.  Add unit tests for the new CLI commands.

### Task 7.3 - Agent_API_Dev: Cherry-Pick API Endpoints
Objective: Expose the cherry-pick functionality through the REST API.
Status: **Pending**

1.  Create a `GET /repository/commits/{branch_name}` endpoint for reviewing commits (enhancement of existing list commits).
2.  Create a `POST /repository/cherry-pick` endpoint that takes a `commit_id` and calls the core `cherry_pick_commit` function.
3.  Add unit tests for the new API endpoints.

### Task 7.4 - Agent_Core_Dev: Beta Reader Workflow (EPUB Export)
Objective: Implement the core logic for exporting repository content to EPUB format.
Status: **Pending**
Guidance: This will likely require integrating a library like `pypandoc`. The function should be able to take a list of markdown files from a specific commit and compile them into an EPUB.

1.  Add `pypandoc` as a dependency.
2.  In `gitwrite_core`, create an `export.py` module with a function `export_to_epub(repo_path, commit_ish, file_list, output_path)`.
3.  The function should handle errors gracefully (e.g., pandoc not installed, file not found).

### Task 7.5 - Agent_CLI_Dev & Agent_API_Dev: Export Endpoints
Objective: Expose the EPUB export functionality through the CLI and API.
Status: **Pending**

1.  Create a `gitwrite export epub` command in the CLI.
2.  Create a `POST /repository/export/epub` endpoint in the API.
3.  Add unit tests for both interfaces.

---

## Phase 8: TypeScript SDK Development
Status: **Pending**
Architectural Notes: This phase will resume and complete the SDK development, ensuring it provides a clean, typed interface for all API endpoints, including those added in Phase 6 and 7.

### Task 8.1 - Agent_SDK_Dev: Update SDK for API Parity
Objective: Add client methods for all implemented API endpoints.
Status: **Pending**

1.  Review all endpoints in `gitwrite_api/routers/`.
2.  For each missing endpoint, add a corresponding method in `gitwrite_sdk/src/apiClient.ts`.
3.  Add all necessary request and response types in `gitwrite_sdk/src/types.ts`.
4.  Ensure the new methods handle authentication and errors correctly.

### Task 8.2 - Agent_SDK_Dev: Comprehensive SDK Testing
Objective: Ensure the SDK is robust and reliable with a full test suite.
Status: **Pending**

1.  In `gitwrite_sdk/tests/apiClient.test.ts`, add test cases for all new SDK methods.
2.  Use `axios-mock-adapter` or Jest's mocking capabilities to simulate API responses.
3.  Ensure tests cover success cases, error cases (e.g., 404, 500), and invalid parameters.

---

## Phase 9: Publishing & Documentation Workflows
Status: **Pending**
Objective: Implement features supporting formal publishing workflows.

### Task 9.1 - Agent_API_Dev: Role-Based Access Control (RBAC)
Objective: Implement a more granular permission system beyond simple authentication.
Status: **Pending**

1.  Design a role system (e.g., Owner, Editor, Writer, Beta Reader).
2.  Integrate RBAC checks into API endpoints to restrict actions based on user roles.

---
## Note on Handover Protocol

For long-running projects or situations requiring context transfer (e.g., exceeding LLM context limits, changing specialized agents), the APM Handover Protocol should be initiated. This ensures smooth transitions and preserves project knowledge. Detailed procedures are outlined in the framework guide:

`prompts/01_Manager_Agent_Core_Guides/05_Handover_Protocol_Guide.md`

The current Manager Agent or you should initiate this protocol as needed.