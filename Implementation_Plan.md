# Implementation Plan: Core Logic Refactoring

Project Goal: Refactor the GitWrite CLI to separate core business logic from the presentation layer (Click commands) into a reusable `gitwrite_core` library. This will improve maintainability, testability, and enable future reuse by the planned REST API.

## General Project Notes
*   **Memory Bank System:** Single file `Memory_Bank.md`.
*   **Architectural Goal:** The `gitwrite_cli/main.py` script will become a "thin wrapper." Its functions will handle command-line input/output and call the appropriate functions in `gitwrite_core` to perform the actual work.
*   **Core Library Design:** Functions within `gitwrite_core` will not use `click.echo` or print to the console. They will return data (dictionaries, lists, custom objects) on success and raise specific custom exceptions on failure.

---

## Phase 1: Foundation and Initial Refactoring

### Task 1.1 - Agent_CLI_Dev: Project Structure and Core Files Setup
Objective: Create the new `gitwrite_core` directory and foundational files, including a module for custom exceptions.
Status: **Pending**

1.  Create the `gitwrite_core/` directory at the project root.
2.  Add an `__init__.py` file inside `gitwrite_core/`.
3.  Create a new file: `gitwrite_core/exceptions.py`.
    - Define a base exception: `class GitWriteError(Exception): pass`.
    - Define specific exceptions that will be needed, inheriting from the base:
        - `class RepositoryNotFoundError(GitWriteError): pass`
        - `class DirtyWorkingDirectoryError(GitWriteError): pass`
        - `class CommitNotFoundError(GitWriteError): pass`
        - `class BranchNotFoundError(GitWriteError): pass`
        - `class MergeConflictError(GitWriteError): pass`
4.  Create empty placeholder files for the upcoming logic modules:
    - `gitwrite_core/repository.py`
    - `gitwrite_core/versioning.py`
    - `gitwrite_core/branching.py`
    - `gitwrite_core/tagging.py`

### Task 1.2 - Agent_CLI_Dev: Refactor `init` and `ignore` commands
Objective: Move the logic for the `init` and `ignore` commands into the new core library and update the CLI and tests.
Status: **Completed**

1.  **`init` command:**
    - Create a function `initialize_repository(path)` in `gitwrite_core/repository.py`.
    - Move all `pygit2` and file system logic from the `init` Click command into this new function.
    - The function should return a status dictionary (e.g., `{'status': 'success', 'path': '...'}`).
    - Update the `init` command in `gitwrite_cli/main.py` to call `initialize_repository` and print results based on the return value.
    - Refactor tests in `tests/test_main.py` to unit test `initialize_repository` directly and have a smaller integration test for the CLI wrapper.
2.  **`ignore` command:**
    - Create functions `add_ignore_pattern(pattern)` and `list_ignore_patterns()` in `gitwrite_core/repository.py`.
    - Move the file I/O logic for `.gitignore` into these functions. `list_ignore_patterns` should return a list of strings. `add_ignore_pattern` can return a boolean indicating success.
    - Update the `ignore add` and `ignore list` commands in `gitwrite_cli/main.py` to use these new core functions.
    - Refactor tests for `ignore`.

---

## Phase 2: Refactoring Standard Read/Write Commands

### Task 2.1 - Agent_CLI_Dev: Refactor `tag` Command
Objective: Move the logic for the `tag` command into the core library.
Status: **Completed**

1.  Create functions `create_tag(...)` and `list_tags()` in `gitwrite_core/tagging.py`.
2.  Move all `pygit2` logic for creating lightweight and annotated tags, and for listing them, into these functions.
3.  `list_tags` should return a list of data objects (e.g., list of dictionaries), not a formatted table.
4.  Update the `tag add` and `tag list` commands in `main.py` to be thin wrappers. The `tag list` command will be responsible for formatting the data from `list_tags()` into a `rich.Table`.
5.  Refactor tests for `tag`.

### Task 2.2 - Agent_CLI_Dev: Refactor `history` and `compare` Commands
Objective: Move the logic for read-only history and comparison commands.
Status: **Completed**

1.  **`history` command:**
    - Create a function `get_history(count)` in `gitwrite_core/versioning.py`.
    - This function should walk the commit history and return a list of data objects, each representing a commit.
    - The `history` command in `main.py` will take this list and format it with `rich.Table`.
2.  **`compare` command:**
    - Create a function `compare_refs(ref1, ref2)` in `gitwrite_core/versioning.py`.
    - This function will perform the diff and return a structured representation of the diff data (e.g., a list of patch objects).
    - The `compare` command in `main.py` will be responsible for the word-level analysis and `rich` presentation.
3.  Refactor tests for both commands.

---

## Phase 3: Refactoring Complex State-Based Commands

### Task 3.1 - Agent_CLI_Dev: Refactor `explore`, `switch`, `merge`, and `revert`
Objective: Move the logic for commands that modify repository state and handle conflicts.
Status: **Partially Completed**
Note: `explore`, `switch`, and `merge` commands have been refactored. The `revert` command is pending.

1.  Create appropriate functions in `gitwrite_core/branching.py` for `explore`, `switch`, and `merge`.
2.  Create appropriate functions in `gitwrite_core/versioning.py` for `revert`.
3.  These functions will contain all `pygit2` logic for branch creation, checkout, merging, and reverting.
4.  For `merge` and `revert`, if conflicts occur, the core function should raise a `MergeConflictError` that contains information about the conflicted files.
5.  Update the Click commands in `main.py` to call these functions and handle the custom exceptions gracefully.
6.  Refactor tests to cover the core logic and the CLI's exception handling.

### Task 3.2 - Agent_CLI_Dev: Refactor `save` and `sync` Commands
Objective: Refactor the final, most complex commands that interact with repository state.
Status: **Pending**

1.  Move the logic for `save` (including selective staging and finalizing merge/revert operations) into a core function in `gitwrite_core/versioning.py`.
2.  Move the logic for `sync` (fetch, pull/merge, push) into a core function in `gitwrite_core/repository.py`.
3.  Update the Click commands in `main.py` to be thin wrappers.
4.  Update the comprehensive test suite for `save` and `sync` to target the new core functions.

---

## Phase 4: Finalization

### Task 4.1 - Agent_CLI_Dev: Final Code Review and Cleanup
Objective: Review the entire refactored codebase for consistency and clarity.
Status: **Pending**

1.  Ensure all logic has been moved out of `gitwrite_cli/main.py`.
2.  Verify that all core functions have docstrings and type hints.
3.  Clean up any unused imports or variables.

---
## Note on Handover Protocol

For long-running projects or situations requiring context transfer (e.g., exceeding LLM context limits, changing specialized agents), the APM Handover Protocol should be initiated. This ensures smooth transitions and preserves project knowledge. Detailed procedures are outlined in the framework guide:

`prompts/01_Manager_Agent_Core_Guides/05_Handover_Protocol_Guide.md`

The current Manager Agent or you should initiate this protocol as needed.