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
Status: **Pending**
Architectural Notes: This phase focuses on enhancing core functionalities and exposing them through the API, ensuring a solid foundation for the frontend applications.

### Task 10.1 - Agent_Core_Dev: Core Word-by-Word Diff Engine
Objective: Refactor the existing CLI word-diff logic into a reusable core function and expose it via the API.
Status: **Completed**

1.  Analyze the `process_hunk_lines_for_word_diff` function and its dependencies in `gitwrite_cli/main.py`.
2.  Create a new function in `gitwrite_core/versioning.py`, e.g., `get_word_level_diff(patch_text: str) -> List[Dict]`.
    -   This function should take a standard diff patch string as input.
    -   It should return a structured representation of the diff, suitable for machine consumption (e.g., a list of file diffs, which contain lists of hunk diffs, which contain lists of line diffs with word-level tags).
3.  Modify the `GET /repository/compare` endpoint in `gitwrite_api/routers/repository.py` to accept an optional query parameter, `diff_mode=word`.
4.  When `diff_mode=word`, the API endpoint will call the new core function and return the structured JSON data. Otherwise, it will return the raw patch text as before.
5.  Update the `CompareRefsResponse` Pydantic model to accommodate the new structured diff format (e.g., using a `Union` type for the patch field).
6.  Add comprehensive unit tests for the new core function and the updated API endpoint.

### Task 10.2 - Agent_Core_Dev: Core Annotation Handling
Objective: Design and implement the core logic for receiving, storing, and applying annotations.
Status: **Pending**

### Task 10.3 - Agent_API_Dev: API Endpoints for Annotations
Objective: Expose the annotation handling logic via the REST API.
Status: **Pending**

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