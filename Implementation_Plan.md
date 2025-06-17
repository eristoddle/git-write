# Implementation Plan

Project Goal: Develop a command-line interface (CLI) for GitWrite, a Git-based version control platform specifically designed for writers, enabling writer-friendly commands and workflows while maintaining full Git compatibility. This initial phase focuses on the MVP for the CLI.

## General Project Notes
*   **Memory Bank System:** Single file `Memory_Bank.md` has been agreed upon.
*   **Primary Agent for CLI Development (Original Plan):** Agent_CLI_Dev
*   **Agent for QA (Original Plan):** Agent_QA
*   **Git Interaction Strategy:** Prioritize using `pygit2` (libgit2 bindings) for programmatic Git operations. Fall back to direct Git command-line calls via `subprocess` only for operations not straightforwardly available or significantly more complex with `pygit2`.
*   **Current Status:** Active development. Task 3.1 completed. Ready for next tasks.

---

## Phase 1: Core CLI Foundation & Basic Operations - Agent_CLI_Dev (Completed)

### Task 1.1 - Agent_CLI_Dev: Project Setup and Initialization
Objective: Establish the Python project structure for the GitWrite CLI, install necessary dependencies, and implement the initial `gitwrite init` command.
Status: **Completed**

1.  Initialize Python project structure.
    - Create main project directory (e.g., `gitwrite_cli`).
    - Set up a virtual environment (e.g., using `venv`).
    - Create `pyproject.toml` (using Poetry).
    - Create main CLI entry point script (`gitwrite_cli/main.py`).
    - Create a `src` directory (`gitwrite_cli/src/gitwrite_cli`).
2.  Install core dependencies.
    - `click`: For building the command-line interface.
    - `rich`: For enhanced terminal output formatting.
    - `pygit2`: For programmatic Git interactions.
3.  Implement `gitwrite init "project_name"` command.
    - Define `init` command using Click.
    - Accept an optional `project_name` argument.
    - Use `pygit2.init_repository()` to initialize a Git repository.
    - Create a standard writer-friendly project structure (`drafts/`, `notes/`, `metadata.yml`, `.gitignore`).
    - Make an initial commit for this structure using `pygit2`.
    - Provide your feedback and basic error handling.

### Task 1.2 - Agent_CLI_Dev: Implement `gitwrite save`
Objective: Implement the `gitwrite save "commit message"` command to stage all changes and create a commit. Also handles finalization of merge commits after conflict resolution.
Status: **Completed**

1.  Define `save` command using Click.
    - Accept a required `message` argument.
2.  Implement Git staging logic using `pygit2` (`repo.index.add_all()`).
3.  Implement Git commit logic using `pygit2` (`repo.create_commit()`).
    - Retrieve author/committer details from Git config (with fallbacks).
    - Correctly determine parents for normal commits and merge commits (by checking `MERGE_HEAD`).
4.  Provide your feedback and handle "nothing to commit" case.
5.  Clean up merge state (`repo.state_cleanup()`) if a merge commit was created.

### Task 1.3 - Agent_CLI_Dev: Implement `gitwrite history`
Objective: Implement the `gitwrite history` command to display the project's commit history in a writer-friendly format.
Status: **Completed**

1.  Define `history` command using Click.
    - Add option `-n, --number <count>` for number of commits.
2.  Implement Git log retrieval using `pygit2` (`repo.walk()`).
3.  Format and display history using `rich.table.Table` (short hash, author, date, message).
4.  Handle repositories with no commits or other error conditions.

---

## Phase 2: Advanced CLI Operations & Git Integration - Agent_CLI_Dev (Completed)

### Task 2.1 - Agent_CLI_Dev: Implement `gitwrite explore` and `gitwrite switch`
Objective: Implement commands for creating and switching between branches (explorations).
Status: **Completed**

1.  Implement `gitwrite explore <branch_name>` command.
    - Define with Click, require `branch_name`.
    - Use `pygit2` to create a new branch from current `HEAD` and switch to it (update working directory and `HEAD` reference).
    - Provide your feedback and handle existing branch errors.
    - Handle empty/unborn HEAD repositories.
2.  Implement `gitwrite switch [<branch_name>]` command.
    - Define with Click, `branch_name` is optional.
    - If no `branch_name`, list available local branches using `rich.table.Table`, marking the current one.
    - If `branch_name` provided, use `pygit2` to switch to the existing local branch (update working directory and `HEAD`).
    - Provide your feedback and handle non-existent branch errors.

### Task 2.2 - Agent_CLI_Dev: Implement `gitwrite merge`
Objective: Implement the `gitwrite merge <branch_name>` command to merge an exploration into the current one.
Status: **Completed**

1.  Define `merge` command using Click.
    - Accept a required `branch_name`.
2.  Implement Git merge logic using `pygit2`.
    - Perform merge analysis (`repo.merge_analysis()`).
    - Handle Fast-Forward merges (update ref, checkout).
    - Handle Up-to-Date cases.
    - Handle Normal Merges:
        - Call `repo.merge()` to update index.
        - If conflicts (`repo.index.has_conflicts`): Provide your feedback, list conflicted files, instruct manual resolution and `gitwrite save`.
        - If no conflicts: Create merge commit with two parents. Clean up merge state (`repo.state_cleanup()`).
    - Provide your feedback for each scenario.

### Task 2.3 - Agent_CLI_Dev: Implement `gitwrite compare`
Objective: Implement `gitwrite compare [ref1] [ref2]` for word-by-word comparison.
Status: **Completed**

1.  Define `compare` command using Click.
    - Accept optional `ref1` and `ref2` arguments (defaults: `HEAD` vs `HEAD~1`; `ref1` vs `HEAD`).
2.  Implement Git diff retrieval using `pygit2` (`repo.diff()`).
    - Resolve references to commit objects.
3.  Process and display diff with word-level highlighting using `difflib.SequenceMatcher` and `rich.text.Text`.
    - Highlight added/removed words within changed lines.
    - Display file headers and hunk headers.
4.  Handle cases with no differences or invalid references.

### Task 2.4 - Agent_CLI_Dev: Implement `gitwrite sync`
Objective: Implement `gitwrite sync` to push local changes to and pull remote changes from a configured remote repository.
Status: **Completed (with known minor typo)**

1.  Define `sync` command using Click.
    - Options for `--remote` (default `origin`) and `--branch` (default current).
2.  Implement Git Fetch logic using `pygit2` (`remote.fetch()`).
3.  Implement Pull logic (Merge/Rebase):
    - Perform merge analysis against remote tracking branch.
    - Handle fast-forward and normal merges (creating merge commit if needed).
    - Detect and report conflicts, instructing you to resolve and use `gitwrite save`.
4.  Implement Git Push logic using `pygit2` (`remote.push()`).
    - Relies on system credential helpers for authentication (MVP).
5.  Provide your feedback for all operations.
    - *Known Issue: Contains a minor typo `paciente=True` in an informational `click.echo` statement.*

---

## Phase 3: Core Feature Implementation

### Task 3.1 - Implement `gitwrite revert`
Objective: Implement `gitwrite revert <commit_ref>` to revert changes introduced by a specific commit, creating a new commit.
Status: **Completed**

1.  Defined `revert <commit_ref>` command using Click.
2.  Implemented Git revert logic using `pygit2` (`repo.revert()`).
    - Successfully implemented. Reverts non-merge commits and creates a new commit.
    - Handles conflicts by instructing manual resolution and using `gitwrite save` (which was enhanced to create appropriate revert commit messages when completing a conflicted revert).
    - Note: Reverting merge commits directly with `pygit2.Repository.revert()` and mainline selection showed limitations with `pygit2 v1.18.0`. The CLI currently disallows this specific operation with an error, guiding users to alternative Git strategies for such cases if needed.
3.  If revert is successful (no conflicts):
    - Created a new commit with a standard revert message.
4.  If conflicts occur during revert:
    - Provided feedback about conflicts.
    - Instructed user to resolve conflicts and run `gitwrite save`.

### Task 3.2 - Implement `gitwrite ignore`
Objective: Implement commands to manage `.gitignore` entries.
Status: **Completed**

1.  Defined `ignore add <pattern>` subcommand:
    *   Allows adding a specified pattern to the project's `.gitignore` file.
    *   Handles creation of `.gitignore` if it doesn't exist.
    *   Prevents duplicate entries.
    *   Provides user feedback on success or if pattern already exists.
2.  Defined `ignore list` subcommand:
    *   Displays the contents of the `.gitignore` file.
    *   Informs the user if the file is not found or is empty.
3.  Implemented logic to read, append to, and display `.gitignore` entries.
4.  Added comprehensive unit tests for both subcommands, covering various scenarios including adding new/duplicate patterns, whitespace handling, and listing different states of the `.gitignore` file. All tests are passing.

### Task 3.3 - Implement `gitwrite tag`
Objective: Implement commands for creating and listing tags.
Status: **Completed**

1.  Defined `tag add <name> [commit_ref] [-m <message>]` subcommand:
    *   Creates a new tag.
    *   If `-m/--message` is provided, an annotated tag is created using `repo.create_tag()`. The tagger is determined from the Git config or environment variables.
    *   Otherwise, a lightweight tag is created using `repo.references.create()`.
    *   The tag points to `commit_ref` (defaults to `HEAD`).
    *   Handles cases like existing tags, empty/bare repositories, and invalid commit references.
2.  Defined `tag list` subcommand:
    *   Lists all tags in the repository using `repo.listall_tags()`.
    *   Differentiates between "Annotated" and "Lightweight" tags.
    *   For annotated tags, displays the first line of the tag message.
    *   Displays the short ID of the target commit for each tag.
    *   Uses `rich.Table` for formatted output.
    *   Handles repositories with no tags.
3.  Implemented logic using `pygit2` for tag creation (both lightweight and annotated) and listing.
4.  Added comprehensive unit tests for both subcommands, covering various scenarios including different tag types, existing tags, repository states, and error conditions. All tests are passing.

---

## Phase 4: Testing, Documentation & Refinement

### Task 4.1 - Develop Unit and Integration Tests
Objective: Create a comprehensive test suite for all CLI commands to ensure reliability and correctness.
Status: **Partially Completed / Ongoing**

1.  Set up testing framework (e.g., `pytest`).
    - Comprehensive tests for `gitwrite revert` were successfully implemented and are passing. Tests for earlier commands still need to be developed.
2.  Write unit tests for core logic of all implemented commands.
3.  Write integration tests for CLI commands, covering success cases, edge cases, and error conditions.
4.  Aim for high test coverage.

### Task 4.2 - Create User Documentation
Objective: Develop user-friendly documentation for the GitWrite CLI.
Status: **Pending**

1.  Outline documentation structure (Installation, Getting Started, Command Reference, Troubleshooting).
2.  Write content for each section.
3.  Choose documentation format (e.g., Markdown, static site generator).

### Task 4.3 - Refine CLI and Address Issues
Objective: Iterate on the CLI based on testing results and documentation process to improve usability and robustness.
Status: **Pending**

1.  Fix known typo in `gitwrite sync` (`paciente=True`).
2.  Review all test failures and bug reports.
3.  Enhance error handling and your feedback across all commands.
4.  Review CLI usability (command names, arguments, options, output clarity).
5.  Perform final round of integration testing.

---
## Note on Handover Protocol

For long-running projects or situations requiring context transfer (e.g., exceeding LLM context limits, changing specialized agents), the APM Handover Protocol should be initiated. This ensures smooth transitions and preserves project knowledge. Detailed procedures are outlined in the framework guide:

`prompts/01_Manager_Agent_Core_Guides/05_Handover_Protocol_Guide.md`

The current Manager Agent or you should initiate this protocol as needed. Given the current blocker, this plan and the associated Memory Bank log serve as a handover document for the remaining tasks to the human developer.
---