# Implementation Plan: GitWrite Platform

Project Goal: Develop a comprehensive, Git-based version control ecosystem for writers, with a core library, a CLI, a feature-complete REST API, and a client-side SDK.

## General Project Notes
*   **Memory Bank System:** Single file `Memory_Bank.md`.
*   **Architectural Goal:** Achieve feature parity between the API, the CLI, and the core features defined in `writegit-project-doc.md`. The TypeScript SDK will be developed once the API is feature-complete.
*   **Project Status Re-evaluation:** This plan has been updated to reflect a detailed analysis of feature parity. The previous plan was completed, and new phases have been added to cover all remaining features from the project documentation.

---

## Phase 1-10: Foundation and Core Features
Status: **Completed**
Summary: All tasks related to the core library, CLI, initial API setup, advanced collaboration features (cherry-pick, export), SDK development, RBAC, and advanced core features (word-diff engine, annotation handling) are complete.

---

## Phase 11: Web Application Development
Status: **In Progress**
Architectural Notes: Development of the primary web interface for GitWrite. This phase will be broken down into several tasks to cover the features outlined in the `writegit-project-doc.md`.

### Task 11.1 - Agent_Web_Dev: Project Setup & Authentication
Objective: Initialize the React/TypeScript project and implement user authentication against the API.
Status: **Completed**
Summary: Created the `gitwrite-web` directory with a Vite/React/TS project. Installed dependencies, linked the local SDK, and implemented a login form, token storage, and protected routing.

### Task 11.2 - Agent_Web_Dev: UI Library Integration (Shadcn/UI & Tailwind)
Objective: Integrate Shadcn/UI and Tailwind CSS to establish a consistent, themeable design system for the web application.
Status: **Completed**

1.  Install and configure Tailwind CSS according to the official Vite guide.
2.  Initialize Shadcn/UI using the `npx shadcn-ui@latest init` command.
3.  Implement a `ThemeProvider` component for managing light/dark mode themes.
4.  Wrap the main `App` component with the `ThemeProvider`.
5.  Add a sample component (e.g., `Button`) and a theme toggle component to verify the setup is working correctly.

### Task 11.3 - Agent_Web_Dev: Project Dashboard and Repository Browser
Objective: Create the main dashboard for users to see their projects and browse the file structure of a selected repository.
Status: **Completed**
Summary: Developed frontend components for listing projects and browsing repository file trees. Integrated these into the dashboard and application routing. Current implementation uses mock data for API calls pending backend development of conceptualized endpoints.
Details:
1.  **Conceptual API Definition:**
    *   Outlined `GET /repositories` for listing projects.
    *   Outlined `GET /repository/{repo_name}/tree/{ref}?path={dir_path}` for file/folder listing.
2.  **SDK Enhancement:**
    *   Added `listRepositories()` and `listRepositoryTree()` methods to `GitWriteClient` in `gitwrite_sdk`.
    *   Defined corresponding response types (`RepositoriesListResponse`, `RepositoryTreeResponse`, etc.) in `gitwrite_sdk/src/types.ts`.
3.  **Dashboard UI (`ProjectList.tsx`):**
    *   Created a component to display a list of (mocked) projects using Shadcn/UI `Table`.
    *   Implemented navigation to individual repository views.
    *   Included loading (`Skeleton`) and error (`Alert`) states.
4.  **Repository Browser UI (`RepositoryBrowser.tsx`):**
    *   Created a component to display a (mocked) file/folder tree using Shadcn/UI `Table`.
    *   Implemented breadcrumb navigation and ability to navigate into/up directories.
    *   Integrated `RepositoryStatus.tsx` for basic repo info.
    *   Handles URL parameters for `repoName` and file path.
5.  **Status Display (`RepositoryStatus.tsx`):**
    *   Created a component to show (mocked) current branch and placeholder for dirty status.
6.  **Integration & Routing:**
    *   Modified `Dashboard.tsx` to render `ProjectList.tsx`.
    *   Updated `App.tsx` to include a route `/repository/:repoName/*` for `RepositoryBrowser.tsx`.
    *   Ensured routes are protected and use a basic `AppLayout`.
7.  **Styling:**
    *   Applied Shadcn/UI components and Tailwind CSS for consistent styling.
    *   Ensured user feedback for loading and error states.
*Action Items Outstanding:*
    *   Backend implementation of `GET /repositories` and `GET /repository/{repo_name}/tree/{ref}` API endpoints.
    *   Replacement of mock data in frontend components with live API calls via the SDK.

### Task 11.4 - Agent_Web_Dev: Commit History and File Content Viewer
Objective: Allow users to view the commit history of a branch and see the contents of a file at a specific version.
Status: **Completed**
Summary: Implemented API endpoint (`GET /repository/file-content`) and core function (`get_file_content_at_commit`) to retrieve file content at a specific commit. Updated SDK with new types and methods. Developed frontend components (`CommitHistoryView`, `FileContentViewer`, `FileContentViewerPage`) and integrated them into the application, enabling users to browse commit history and view file contents at different versions.
Details:
1.  **API & Core (`gitwrite_api`, `gitwrite_core`):**
    *   Created `core_get_file_content_at_commit` in `repository.py` using `pygit2`.
    *   Added `GET /repository/file-content` endpoint in `routers/repository.py`.
    *   Defined `FileContentResponse` model in `models.py`.
    *   Wrote unit tests for both core function and API endpoint.
2.  **SDK (`gitwrite_sdk`):**
    *   Added `FileContentResponse` interface to `types.ts`.
    *   Implemented `getFileContent()` method in `apiClient.ts`.
    *   Exported new type from `index.ts` and rebuilt SDK.
3.  **Frontend (`gitwrite-web`):**
    *   `CommitHistoryView.tsx`: Displays commit list, navigates to tree view for a selected commit.
    *   `FileContentViewer.tsx`: Displays file content with syntax highlighting.
    *   `pages/FileContentViewerPage.tsx`: Handles URL params for file viewer.
    *   `App.tsx`: Added routes for history and file content views.
    *   `RepositoryBrowser.tsx`: Integrated history navigation, file viewing at current ref, and can display tree for a specific commit.
    *   `RepositoryStatus.tsx`: Updated to show commit/branch context.
*Action Items Outstanding:*
    *   The `RepositoryBrowser.tsx` component still uses mock data for its primary tree listing function. This needs to be updated when the backend API for `listRepositoryTree` (conceptualized in Task 11.3) is fully implemented.

### Task 11.5 - Agent_Web_Dev: Visual Word-by-Word Diff Viewer
Objective: Implement a rich, side-by-side comparison view for changes between commits, utilizing the word-level diff API.
Status: **Completed**
Summary: Implemented a visual word-by-word diff viewer. Updated the SDK for structured diff data. Added a "Compare to Parent" button in `CommitHistoryView`. Created `WordDiffDisplay` for rendering detailed line/word changes and `WordDiffViewerPage` for data fetching and routing. Corrected SDK type exports post-initial implementation based on user feedback.
Details:
1.  **SDK Updates (`gitwrite_sdk`):**
    *   Defined TypeScript interfaces (`StructuredDiffFile`, `WordDiffHunk`, `WordDiffLine`, `WordDiffSegment`) for structured diff data.
    *   Updated `CompareRefsResponse` and `CompareRefsParams` to support word-level diff mode.
    *   Adjusted `compareRefs` method to handle the new mode and response.
    *   Ensured all new types are correctly exported from `index.ts`.
    *   Rebuilt SDK.
2.  **Frontend - Commit History (`CommitHistoryView.tsx`):**
    *   Added "Compare to Parent" button, navigating to the diff viewer route with parent and current commit SHAs.
3.  **Frontend - Diff Viewer (`WordDiffViewerPage.tsx`, `WordDiffDisplay.tsx`):**
    *   `WordDiffViewerPage.tsx`: Fetches structured diff data using SDK's `compareRefs` with `diff_mode: 'word'`. Manages loading/error states.
    *   `WordDiffDisplay.tsx`: Renders the structured diff, highlighting file changes, line additions/deletions, and word-level additions/removals with distinct styles.
4.  **Frontend - Routing (`App.tsx`):**
    *   Added route `/repository/:repoName/compare/:ref1/:ref2` for `WordDiffViewerPage.tsx`.
*Action Items Outstanding:*
    *   Full end-to-end testing dependent on live API and preceding UI views providing a path to this feature.

### Task 11.6 - Agent_Web_Dev: Annotation Review Interface
Objective: Create a user interface for viewing and managing beta reader annotations within the context of a file.
Status: **Completed**
Summary: Implemented an annotation review interface within the `FileContentViewer`. Updated the SDK with annotation types and API client methods. Created an `AnnotationSidebar` component to list annotations relevant to the current file, display their details (author, comment, status), and provide "Accept"/"Reject" buttons. `FileContentViewer` now fetches annotations, manages their state, handles status updates via the SDK, and renders the sidebar. The feedback branch is currently hardcoded to "feedback/main".
Details:
1.  **SDK Update (`gitwrite_sdk`):**
    *   Added `AnnotationStatus` enum, `Annotation` interface, and related request/response types (`AnnotationListResponse`, `UpdateAnnotationStatusRequest`, `UpdateAnnotationStatusResponse`) to `types.ts`.
    *   Implemented `listAnnotations` and `updateAnnotationStatus` methods in `apiClient.ts`.
    *   Exported new types and rebuilt the SDK.
2.  **Frontend - `AnnotationSidebar.tsx`:**
    *   Created to display annotations, each with details and Accept/Reject buttons.
    *   Filters annotations by `currentFilePath`.
    *   Handles loading states for status updates on individual annotations.
3.  **Frontend - `FileContentViewer.tsx` Integration:**
    *   Fetches annotations for a (currently hardcoded) `feedbackBranch` in parallel with file content.
    *   Renders `AnnotationSidebar` alongside the file content.
    *   Manages annotation state, loading, errors, and handles status update logic.
4.  **Frontend - `FileContentViewerPage.tsx`:**
    *   Modified to pass a hardcoded `feedbackBranch="feedback/main"` prop to `FileContentViewer`.
*Action Items Outstanding:*
    *   Make `feedbackBranch` selection dynamic for the user.
    *   Consider visual integration of annotation markers directly into the file content viewer (e.g., line highlighting).

### Task 11.7 - Agent_Web_Dev: Selective Change Integration (Cherry-Picking)
Objective: Develop the advanced interface for reviewing commits from a branch and selectively integrating them.
Status: **Completed**
Summary: Implemented a new frontend page (`BranchReviewPage.tsx`) for reviewing commits from a specified branch that are not in the current main working branch. Users can view word-by-word diffs for each reviewable commit and trigger a cherry-pick operation. The interface provides feedback on success, conflicts (with file lists), or errors during cherry-picking. Navigation to this page is provided via a dropdown menu in the `RepositoryStatus` component, accessible from the `RepositoryBrowser`.
Details:
1.  **Frontend - `BranchReviewPage.tsx` (`gitwrite-web/src/pages/`):**
    *   Created to display commits from a selected branch (obtained via `client.reviewBranch()`) that are not in the current working branch (assumed 'main' for UI text, backend uses actual HEAD).
    *   Each commit in the list has:
        *   A "View Diff" button linking to `WordDiffViewerPage` (comparing commit to its parent: `commit.oid^` vs `commit.oid`).
        *   A "Cherry-Pick" button that calls `client.cherryPickCommit()`.
    *   Manages and displays loading states for commit fetching and individual cherry-pick operations.
    *   Provides UI feedback (Alerts) for cherry-pick success (shows new commit SHA), conflicts (lists conflicting files), or errors.
    *   Includes a "Refresh List" button to re-fetch reviewable commits.
2.  **Frontend - Navigation & Integration:**
    *   `RepositoryStatus.tsx`: Updated to include a "Review for Cherry-Pick" `DropdownMenu`. This menu lists other available branches (fetched in `RepositoryBrowser.tsx` via `client.listBranches()`). Selecting a branch navigates to the `BranchReviewPage` for that branch.
    *   `RepositoryBrowser.tsx`: Fetches all branches and passes them to `RepositoryStatus.tsx`.
    *   `App.tsx`: Added a new route `/repository/:repoName/review-branch/:branchName/*` for `BranchReviewPage.tsx`.
3.  **Diff View Context:**
    *   The existing `WordDiffViewerPage.tsx` is used to show changes for a commit by comparing it to its parent, which is appropriate for cherry-pick decisions. No modifications to the diff viewer itself were needed for this task.
*Action Items Outstanding/Limitations:*
    *   The `currentWorkingBranch` into which commits are cherry-picked is assumed to be the repository's actual current HEAD on the backend. The UI text on `BranchReviewPage` currently hardcodes "main" as the target branch for descriptive purposes. This could be made dynamic in future enhancements.
    *   The `reviewBranch` API endpoint compares against the current repository HEAD. The UI does not currently support specifying a different base branch for the review if the user intends to cherry-pick into a branch that is not the current HEAD.

### Task 11.8 - Agent_Web_Dev: Branch Management
Objective: Provide a simple UI for managing explorations (branches).
Status: **Completed**
Summary: Implemented a `BranchManagementPage.tsx` accessible via the `RepositoryStatus` component. This page allows users to list, create, switch, and merge branches. It uses existing SDK methods that call corresponding API endpoints. User feedback for operations is provided via toasts.
Details:
1.  **New Page (`BranchManagementPage.tsx`):**
    *   Created `gitwrite-web/src/pages/BranchManagementPage.tsx`.
    *   Fetches and displays a list of all branches using `client.listBranches()`.
    *   Identifies and displays the current active branch (using a heuristic: 'main', 'master', or first in list if specific data not available from API).
    *   Provides UI sections (Cards) for:
        *   **Listing Branches:** A table showing all branches, highlighting the current one, with "Switch To" buttons.
        *   **Creating Branch:** An input field and button to create a new branch (`client.createBranch()`).
        *   **Switching Branch (Card UI):** A dropdown (`Select`) to choose a branch and a button to switch (`client.switchBranch()`).
        *   **Merging Branch:** A dropdown (`Select`) to choose a source branch to merge into the current active branch (`client.mergeBranch()`).
    *   Handles loading states for asynchronous operations.
    *   Displays success or error messages using `toast` notifications.
    *   Includes navigation back to the repository browser.
2.  **Routing and Navigation:**
    *   Added a route `/repository/:repoName/branches` in `gitwrite-web/src/App.tsx` pointing to `BranchManagementPage`.
    *   Added a "Manage Branches" button in `gitwrite-web/src/components/RepositoryStatus.tsx` to navigate to this new page. This button is visible when viewing a branch, not a specific commit.
3.  **Functionality Details:**
    *   **Branch Creation:** Takes a new branch name, calls SDK, refreshes branch list, and updates current branch display.
    *   **Branch Switching:** Allows selection from a list or direct click from table, calls SDK, updates current branch display.
    *   **Branch Merging:** Allows selection of a source branch, calls SDK, displays outcomes including conflicts (with file list if provided by API).
*Action Items Outstanding/Limitations:*
    *   The determination of the "current active branch" relies on a heuristic. A more robust solution would involve the API explicitly providing this information (e.g., in `listBranches` response or a dedicated status endpoint).
    *   Advanced conflict resolution is not part of this UI; users are informed of conflicts.

---

## Phase 12: API and UI Integration for Repository Browsing
Status: **Pending**
Agent: **Agent_API_Dev** (for API tasks), **Agent_Web_Dev** (for frontend integration)
Objective: Implement the backend APIs required for the web application's repository browser and integrate them into the frontend, replacing all mock data.

### Task 12.1 - Agent_API_Dev: Implement Repository Listing API
Objective: Create the API endpoint to list all available GitWrite repositories.
1.  In `gitwrite_api/routers/repository.py`, create a new endpoint: `GET /repositories`.
2.  The endpoint logic should scan the designated base directory (e.g., `/tmp/gitwrite_repos_api/gitwrite_user_repos`) for valid Git repositories.
3.  For each repository found, gather metadata: name, last modification time, and potentially a description from `metadata.yml`.
4.  Define a `RepositoryListItem` and `RepositoriesListResponse` model in `gitwrite_api/models.py`.
5.  Return the list of repositories.
6.  Add corresponding unit tests in `tests/test_api_repository.py`.

### Task 12.2 - Agent_API_Dev: Implement Repository Tree API
Objective: Create the API endpoint to list files and folders for a given repository path and reference.
1.  In `gitwrite_api/routers/repository.py`, create a new endpoint: `GET /repository/{repo_name}/tree/{ref:path}`. The `{ref:path}` will capture branch names with slashes.
2.  The endpoint should accept an optional `path` query parameter for subdirectories.
3.  The logic should use `pygit2` to:
    *   Open the repository specified by `repo_name`.
    *   Resolve the `ref` to a commit object.
    *   Access the tree for that commit.
    *   Navigate to the subdirectory specified by the `path` query parameter.
    *   List the entries (blobs and trees) in that directory.
4.  Define `RepositoryTreeEntry`, `RepositoryTreeBreadcrumbItem`, and `RepositoryTreeResponse` models in `gitwrite_api/models.py`.
5.  Return the list of entries and breadcrumb data.
6.  Add corresponding unit tests in `tests/test_api_repository.py`.

### Task 12.3 - Agent_Web_Dev: Integrate Frontend with New APIs
Objective: Remove all mock data from the web application and replace it with live data from the newly created API endpoints.
1.  In `gitwrite-web/src/components/ProjectList.tsx`, replace the mock data fetching with a call to `client.listRepositories()`.
2.  In `gitwrite-web/src/components/RepositoryBrowser.tsx`, replace the mock data fetching with a call to `client.listRepositoryTree(repoName, ref, path)`.
3.  Update the `RepositoryStatus.tsx` component to use live data for the current branch, if this information can be derived from the new API responses or a new dedicated status endpoint.
4.  Ensure all loading and error states in the UI correctly handle real network requests.

---

## Note on Handover Protocol

For long-running projects or situations requiring context transfer (e.g., exceeding LLM context limits, changing specialized agents), the APM Handover Protocol should be initiated. This ensures smooth transitions and preserves project knowledge. Detailed procedures are outlined in the framework guide:

`prompts/01_Manager_Agent_Core_Guides/05_Handover_Protocol_Guide.md`

The current Manager Agent or you should initiate this protocol as needed.