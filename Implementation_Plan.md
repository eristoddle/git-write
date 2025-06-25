# Implementation Plan: GitWrite Platform

Project Goal: Develop a comprehensive, Git-based version control ecosystem for writers, with a core library, a CLI, a feature-complete REST API, and a client-side SDK.

## General Project Notes
*   **Memory Bank System:** Single file `Memory_Bank.md`.
*   **Architectural Goal:** Achieve feature parity between the API, the CLI, and the core features defined in `writegit-project-doc.md`. The TypeScript SDK will be developed once the API is feature-complete.
*   **Project Status Re-evaluation:** This plan has been updated to reflect a detailed analysis of feature parity. The previous plan was completed, and new phases have been added to cover all remaining features from the project documentation.

---

## Phase 1-9: Foundation and Initial Features
Status: **Completed**
Summary: All tasks related to the core library, CLI, initial API setup, advanced collaboration features (cherry-pick, export), SDK development, and initial RBAC are complete as per the previous plan.

---

## Phase 10: Advanced Core & API Features
Status: **In Progress**
Architectural Notes: This phase focuses on enhancing core functionalities and exposing them through the API, ensuring a solid foundation for the frontend applications.

### Task 10.1 - Agent_Core_Dev: Core Word-by-Word Diff Engine
Objective: Refactor the existing CLI word-diff logic into a reusable core function and expose it via the API.
Status: **Completed**

### Task 10.2 - Agent_Core_Dev: Core Annotation Handling
Objective: Design and implement the core logic for receiving, storing, and applying annotations.
Status: **Completed**

1.  **Define Data Model:** In `gitwrite_api/models.py`, define a Pydantic model for an `Annotation`. It should include fields like `file_path`, `highlighted_text`, `start_line`, `end_line`, `comment`, `author`, and `status` (`new`, `accepted`, `rejected`).
2.  **Create New Core Module:** Create a new file `gitwrite_core/annotations.py`.
3.  **Implement Annotation Committing:** In `annotations.py`, create a function `create_annotation_commit(repo_path, feedback_branch, annotation_data)`.
    -   This function will take annotation data, format it (e.g., as YAML or JSON), and create a new commit on the specified `feedback_branch`.
    -   The commit message should be standardized, e.g., `Annotation: a.txt (Lines 10-12)`. The body of the commit will contain the structured annotation data.
4.  **Implement Annotation Listing:** In `annotations.py`, create a function `list_annotations(repo_path, feedback_branch)`.
    -   This function will walk the history of the `feedback_branch`, parse the structured data from each annotation commit, and return a list of `Annotation` objects.
5.  **Implement Annotation Status Update:** In `annotations.py`, create a function `update_annotation_status(repo_path, annotation_commit_id, new_status)`.
    -   This function will create a new commit that amends the original annotation commit's message or adds a note to signify the status change (e.g., "Status: accepted"). This preserves the audit trail.
6.  **Unit Tests:** Create a new test file `tests/test_core_annotations.py` and write comprehensive tests for all new functions.

### Task 10.3 - Agent_API_Dev: API Endpoints for Annotations
Objective: Expose the annotation handling logic via the REST API.
Status: **Pending**

1.  **Create Endpoint:** In `gitwrite_api/routers/repository.py` (or a new `annotations.py` router), create `POST /repository/annotations`.
    -   This endpoint will accept annotation data in its request body.
    -   It will call the `create_annotation_commit` core function.
    -   It requires a `feedback_branch` parameter.
2.  **List Endpoint:** Create `GET /repository/annotations`.
    -   This endpoint will take a `feedback_branch` as a query parameter.
    -   It will call the `list_annotations` core function and return a list of annotation objects.
3.  **Update Endpoint:** Create `PUT /repository/annotations/{annotation_commit_id}`.
    -   This endpoint will accept a `new_status` in its body.
    -   It will call the `update_annotation_status` core function.
4.  **Unit Tests:** Create a new test file `tests/test_api_annotations.py` to test all new API endpoints, including success cases, error handling, and authentication/authorization checks.

---

## Phase 11: Web Application Development
Status: **Pending**
Architectural Notes: Development of the primary web interface for GitWrite.

### Task 11.1 - Agent_Web_Dev: Project Setup & Authentication
Objective: Initialize the React/TypeScript project and implement user authentication against the API.
Status: **Pending**

---

## Note on Handover Protocol

For long-running projects or situations requiring context transfer (e.g., exceeding LLM context limits, changing specialized agents), the APM Handover Protocol should be initiated. This ensures smooth transitions and preserves project knowledge. Detailed procedures are outlined in the framework guide:

`prompts/01_Manager_Agent_Core_Guides/05_Handover_protocol_guide.md`

The current Manager Agent or you should initiate this protocol as needed.