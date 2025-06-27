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
Status: **Pending**
1.  **History View:** Implement a UI to display the output from `GET /repository/history`. Each entry should be selectable.
2.  **File Viewer:** Create a component to display the content of a selected file. It should be able to fetch file content from a specific commit hash.

### Task 11.5 - Agent_Web_Dev: Visual Word-by-Word Diff Viewer
Objective: Implement a rich, side-by-side comparison view for changes between commits, utilizing the word-level diff API.
Status: **Pending**
1.  **API Integration:** Connect to the `GET /repository/compare?diff_mode=word` endpoint.
2.  **Diff Component:** Build a React component that takes the structured JSON diff data and renders it in a side-by-side or inline view, highlighting added and removed words.
3.  **Integration:** Allow users to trigger a comparison between any two commits from the history view.

### Task 11.6 - Agent_Web_Dev: Annotation Review Interface
Objective: Create a user interface for viewing and managing beta reader annotations within the context of a file.
Status: **Pending**
1.  **API Integration:** Fetch annotations for a given file and feedback branch using `GET /repository/annotations`.
2.  **Annotation Display:** Overlay or list annotations alongside the file content in the file viewer.
3.  **Status Update:** Implement UI elements (e.g., buttons) to accept or reject an annotation, calling the `PUT /repository/annotations/{annotation_commit_id}` endpoint.

### Task 11.7 - Agent_Web_Dev: Selective Change Integration (Cherry-Picking)
Objective: Develop the advanced interface for reviewing commits from a branch and selectively integrating them.
Status: **Pending**
1.  **Commit Review UI:** Create an interface to browse commits on a given branch (e.g., an editor's feedback branch).
2.  **Cherry-Pick Action:** Implement a button to trigger the `POST /repository/cherry-pick` API endpoint for a selected commit.
3.  **Granular Diff View:** For each commit, show the word-by-word diff to allow the author to see the precise changes before deciding to integrate them.

### Task 11.8 - Agent_Web_Dev: Branch Management
Objective: Provide a simple UI for managing explorations (branches).
Status: **Pending**
1.  **Branch List:** Display a list of available branches.
2.  **Create/Switch:** Implement forms/buttons to create and switch between branches.
3.  **Merge UI:** Create a simple interface to merge one branch into another, including a way to handle conflicts (e.g., by guiding the user to the CLI for complex cases).

---

## Note on Handover Protocol

For long-running projects or situations requiring context transfer (e.g., exceeding LLM context limits, changing specialized agents), the APM Handover Protocol should be initiated. This ensures smooth transitions and preserves project knowledge. Detailed procedures are outlined in the framework guide:

`prompts/01_Manager_Agent_Core_Guides/05_Handover_Protocol_Guide.md`

The current Manager Agent or you should initiate this protocol as needed.