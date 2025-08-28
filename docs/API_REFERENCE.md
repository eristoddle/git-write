# GitWrite API Documentation

*RESTful API for Git-based Writing Version Control*

## Table of Contents
1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Repository Management](#repository-management)
4. [File Operations](#file-operations)
5. [Version Control](#version-control)
6. [Collaboration Features](#collaboration-features)
7. [Export Functions](#export-functions)
8. [Error Handling](#error-handling)
9. [SDK Usage](#sdk-usage)
10. [Examples](#examples)

## Overview

### Base URL
```
http://localhost:8000
```

### API Documentation
Interactive API documentation is available at:
```
http://localhost:8000/docs
```

### Content Types
- **Request**: `application/json` (except for login: `application/x-www-form-urlencoded`)
- **Response**: `application/json`

### Authentication
All endpoints except `/token` require Bearer token authentication.

## Authentication

### Login
Get an access token for API access.

```http
POST /token
Content-Type: application/x-www-form-urlencoded

username=johndoe&password=secret
```

**Response:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Default Users:**
- `johndoe` / `secret` (Owner)
- `editoruser` / `editpass` (Editor)
- `writeruser` / `writepass` (Writer) 
- `betauser` / `betapass` (Beta Reader)

### Using the Token
Include the token in the Authorization header:
```http
Authorization: Bearer <your_access_token>
```

## Repository Management

### List Repositories
Get all repositories accessible to the current user.

```http
GET /repositorys
Authorization: Bearer <token>
```

**Response:**
```json
{
  "repositories": [
    {
      "name": "my-novel",
      "last_modified": "2025-08-27T19:49:26-05:00",
      "description": "My first novel project"
    }
  ],
  "count": 1
}
```

### Create Repository
Initialize a new GitWrite repository.

```http
POST /repository/repositories
Authorization: Bearer <token>
Content-Type: application/json

{
  "project_name": "new-project"
}
```

**Response:**
```json
{
  "status": "created",
  "message": "Repository 'new-project' initialized successfully.",
  "repository_id": "new-project",
  "path": "/path/to/repositories/new-project"
}
```

### Browse Repository Tree
List files and folders in a repository at a specific reference.

```http
GET /repository/{repo_name}/tree/{ref}?path={directory_path}
Authorization: Bearer <token>
```

**Parameters:**
- `repo_name`: Repository name
- `ref`: Branch name, tag, or commit SHA
- `path`: Directory path (optional, defaults to root)

**Response:**
```json
{
  "repo_name": "my-novel",
  "ref": "main",
  "request_path": "chapters",
  "entries": [
    {
      "name": "chapter1.md",
      "path": "chapters/chapter1.md",
      "type": "blob",
      "size": 1024,
      "mode": "100644",
      "oid": "abc123..."
    },
    {
      "name": "drafts",
      "path": "chapters/drafts", 
      "type": "tree",
      "size": null,
      "mode": "40000",
      "oid": "def456..."
    }
  ],
  "breadcrumb": [
    {"name": "main", "path": ""},
    {"name": "chapters", "path": "chapters"}
  ]
}
```

## File Operations

### Get File Content
Retrieve file content at a specific commit.

```http
GET /repository/file-content?file_path=chapter1.md&commit_sha=abc123
Authorization: Bearer <token>
```

**Response:**
```json
{
  "file_path": "chapter1.md",
  "commit_sha": "abc123...",
  "content": "# Chapter 1\n\nIt was the best of times...",
  "size": 1024,
  "mode": "100644",
  "is_binary": false
}
```

### Save File
Save content to a file and create a commit.

```http
POST /repository/save
Authorization: Bearer <token>
Content-Type: application/json

{
  "file_path": "drafts/chapter2.md",
  "content": "# Chapter 2\n\nThe story continues...",
  "commit_message": "Added Chapter 2 draft"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "File saved and committed successfully",
  "commit_id": "xyz789..."
}
```

## Version Control

### List Branches
Get all branches in the repository.

```http
GET /repository/branches
Authorization: Bearer <token>
```

**Response:**
```json
{
  "status": "success",
  "branches": ["main", "alternate-ending", "editor-review"],
  "message": "Successfully retrieved local branches."
}
```

### Create Branch
Create a new branch from current HEAD.

```http
POST /repository/branches
Authorization: Bearer <token>
Content-Type: application/json

{
  "branch_name": "experimental-plot"
}
```

**Response:**
```json
{
  "status": "created",
  "branch_name": "experimental-plot",
  "message": "Branch 'experimental-plot' created and switched to successfully.",
  "head_commit_oid": "abc123..."
}
```

### Switch Branch
Switch to an existing branch.

```http
PUT /repository/branch
Authorization: Bearer <token>
Content-Type: application/json

{
  "branch_name": "main"
}
```

**Response:**
```json
{
  "status": "success",
  "branch_name": "main",
  "message": "Switched to branch 'main' successfully.",
  "head_commit_oid": "def456...",
  "previous_branch_name": "experimental-plot"
}
```

### Merge Branch
Merge a source branch into the current branch.

```http
POST /repository/merges
Authorization: Bearer <token>
Content-Type: application/json

{
  "source_branch": "experimental-plot"
}
```

**Response:**
```json
{
  "status": "merged_ok",
  "message": "Branch 'experimental-plot' was successfully merged into 'main'.",
  "current_branch": "main",
  "merged_branch": "experimental-plot",
  "commit_oid": "ghi789..."
}
```

### List Commits
Get commit history for a branch.

```http
GET /repository/commits?branch_name=main&max_count=10
Authorization: Bearer <token>
```

**Response:**
```json
{
  "status": "success",
  "commits": [
    {
      "sha": "abc123...",
      "message": "Added Chapter 2 draft",
      "author_name": "John Doe",
      "author_email": "john@example.com",
      "author_date": "2025-08-27T19:00:00Z",
      "committer_name": "John Doe", 
      "committer_email": "john@example.com",
      "committer_date": "2025-08-27T19:00:00Z",
      "parents": ["def456..."]
    }
  ],
  "message": "Successfully retrieved 1 commits."
}
```

### Compare References
Get diff between two commits, branches, or tags.

```http
GET /repository/compare?ref1=main&ref2=experimental-plot&diff_mode=word
Authorization: Bearer <token>
```

**Response:**
```json
{
  "ref1_oid": "abc123...",
  "ref2_oid": "def456...",
  "ref1_display_name": "main",
  "ref2_display_name": "experimental-plot", 
  "patch_text": [
    {
      "file_path": "chapter1.md",
      "change_type": "modified",
      "hunks": [
        {
          "lines": [
            {
              "type": "context",
              "content": "# Chapter 1"
            },
            {
              "type": "deletion",
              "content": "It was the best of times",
              "words": [
                {"type": "removed", "content": "best"},
                {"type": "context", "content": " of times"}
              ]
            },
            {
              "type": "addition", 
              "content": "It was the worst of times",
              "words": [
                {"type": "added", "content": "worst"},
                {"type": "context", "content": " of times"}
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### Revert Commit
Revert a specific commit.

```http
POST /repository/revert
Authorization: Bearer <token>
Content-Type: application/json

{
  "commit_ish": "abc123"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Commit abc123 reverted successfully",
  "new_commit_oid": "xyz789..."
}
```

### Sync Repository
Synchronize with remote repository (fetch, merge, push).

```http
POST /repository/sync
Authorization: Bearer <token>
Content-Type: application/json

{
  "remote_name": "origin",
  "branch_name": "main",
  "push": true,
  "allow_no_push": false
}
```

**Response:**
```json
{
  "status": "success",
  "branch_synced": "main",
  "remote": "origin",
  "fetch_status": {
    "received_objects": 5,
    "total_objects": 5,
    "message": "Fetch complete."
  },
  "local_update_status": {
    "type": "up_to_date",
    "message": "Local branch is already up-to-date with remote."
  },
  "push_status": {
    "pushed": false,
    "message": "Nothing to push. Local branch is not ahead of remote."
  }
}
```

## Collaboration Features

### Review Branch Commits
Get commits on a branch that are not in the current HEAD (for cherry-picking).

```http
GET /repository/review/experimental-plot?limit=10
Authorization: Bearer <token>
```

**Response:**
```json
{
  "status": "success",
  "branch_name": "experimental-plot",
  "commits": [
    {
      "short_hash": "abc123",
      "author_name": "Jane Editor",
      "date": "2025-08-27T19:00:00Z",
      "message_short": "Improved dialogue in Chapter 3",
      "oid": "abc123456..."
    }
  ],
  "message": "Found 1 reviewable commits on branch 'experimental-plot'."
}
```

### Cherry-Pick Commit
Apply a specific commit to the current branch.

```http
POST /repository/cherry-pick
Authorization: Bearer <token>
Content-Type: application/json

{
  "commit_id": "abc123456",
  "mainline": 1
}
```

**Response:**
```json
{
  "status": "success",
  "message": "Commit abc123456 cherry-picked successfully",
  "new_commit_oid": "def789..."
}
```

### Annotations

#### List Annotations
Get annotations for a specific branch and file.

```http
GET /annotations?feedback_branch=editor-feedback&file_path=chapter1.md
Authorization: Bearer <token>
```

**Response:**
```json
{
  "annotations": [
    {
      "id": "annotation123",
      "file_path": "chapter1.md",
      "highlighted_text": "It was the best of times",
      "start_line": 2,
      "end_line": 2,
      "comment": "Consider a more dramatic opening",
      "author": "editor@example.com",
      "status": "new",
      "commit_id": "abc123..."
    }
  ],
  "count": 1
}
```

#### Update Annotation Status
Accept or reject an annotation.

```http
PUT /annotations/{annotation_id}/status
Authorization: Bearer <token>
Content-Type: application/json

{
  "new_status": "accepted",
  "feedback_branch": "editor-feedback"
}
```

## Export Functions

### Export to EPUB
Generate an EPUB file from selected files.

```http
POST /repository/export/epub
Authorization: Bearer <token>
Content-Type: application/json

{
  "commit_ish": "main",
  "file_list": ["chapter1.md", "chapter2.md", "chapter3.md"],
  "output_filename": "my-novel.epub"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "EPUB exported successfully",
  "server_file_path": "/path/to/exports/12345/my-novel.epub"
}
```

## Error Handling

### Standard Error Format
```json
{
  "detail": "Error message description"
}
```

### HTTP Status Codes

#### Success
- `200 OK`: Request successful
- `201 Created`: Resource created successfully

#### Client Errors
- `400 Bad Request`: Invalid request parameters
- `401 Unauthorized`: Authentication required
- `403 Forbidden`: Insufficient permissions
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., merge conflicts)

#### Server Errors
- `500 Internal Server Error`: Server-side error
- `503 Service Unavailable`: Service temporarily unavailable

### Common Error Scenarios

#### Authentication Errors
```json
{
  "detail": "Could not validate credentials"
}
```

#### Repository Errors
```json
{
  "detail": "Repository not found"
}
```

#### Merge Conflicts
```json
{
  "status": "conflict",
  "message": "Merge resulted in conflicts",
  "conflicting_files": ["chapter1.md", "chapter2.md"],
  "current_branch": "main",
  "merged_branch": "experimental"
}
```

## SDK Usage

### TypeScript/JavaScript SDK

#### Installation
```bash
npm install gitwrite-sdk
```

#### Basic Usage
```typescript
import { GitWriteClient } from 'gitwrite-sdk';

const client = new GitWriteClient('http://localhost:8000');

// Login
await client.login({ username: 'johndoe', password: 'secret' });

// List repositories
const repos = await client.listRepositories();
console.log(repos.repositories);

// Browse repository
const tree = await client.listRepositoryTree('my-novel', 'main');
console.log(tree.entries);

// Get file content
const file = await client.getFileContent('chapter1.md', 'abc123');
console.log(file.content);
```

#### Error Handling
```typescript
try {
  const repos = await client.listRepositories();
} catch (error) {
  if (error.response?.status === 401) {
    console.log('Authentication required');
    // Redirect to login
  } else {
    console.error('API Error:', error.response?.data);
  }
}
```

## Examples

### Complete Workflow Example

#### 1. Authentication and Setup
```bash
# Get access token
curl -X POST "http://localhost:8000/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=johndoe&password=secret"

# Export token for convenience
export TOKEN="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
```

#### 2. Create and Browse Repository
```bash
# Create new repository
curl -X POST "http://localhost:8000/repository/repositories" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"project_name": "my-api-novel"}'

# List repositories
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/repositorys"

# Browse repository root
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/repository/my-api-novel/tree/main"
```

#### 3. Writing Workflow
```bash
# Save a new file
curl -X POST "http://localhost:8000/repository/save" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "chapter1.md",
    "content": "# Chapter 1\n\nOnce upon a time...",
    "commit_message": "Started Chapter 1"
  }'

# Create a branch for experiments
curl -X POST "http://localhost:8000/repository/branches" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"branch_name": "alternate-beginning"}'

# Make changes in the branch
curl -X POST "http://localhost:8000/repository/save" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "chapter1.md", 
    "content": "# Chapter 1\n\nIn a galaxy far, far away...",
    "commit_message": "Trying sci-fi opening"
  }'
```

#### 4. Review and Merge
```bash
# Compare branches
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8000/repository/compare?ref1=main&ref2=alternate-beginning"

# Switch back to main
curl -X PUT "http://localhost:8000/repository/branch" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"branch_name": "main"}'

# Merge the changes
curl -X POST "http://localhost:8000/repository/merges" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"source_branch": "alternate-beginning"}'
```

#### 5. Export Work
```bash
# Export to EPUB
curl -X POST "http://localhost:8000/repository/export/epub" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "commit_ish": "main",
    "file_list": ["chapter1.md"],
    "output_filename": "my-novel-v1.epub"
  }'
```

### SDK Example Application
```typescript
import { GitWriteClient, type RepositoryListItem } from 'gitwrite-sdk';

class WritingApp {
  private client: GitWriteClient;

  constructor(apiUrl: string) {
    this.client = new GitWriteClient(apiUrl);
  }

  async login(username: string, password: string) {
    try {
      await this.client.login({ username, password });
      console.log('✅ Logged in successfully');
    } catch (error) {
      console.error('❌ Login failed:', error);
      throw error;
    }
  }

  async listProjects(): Promise<RepositoryListItem[]> {
    const response = await this.client.listRepositories();
    return response.repositories;
  }

  async createProject(name: string) {
    return await this.client.initializeRepository({ project_name: name });
  }

  async saveChapter(content: string, message: string) {
    return await this.client.saveFile('drafts/chapter.md', content, message);
  }

  async exportToEpub(files: string[]) {
    return await this.client.exportToEpub({
      commit_ish: 'main',
      file_list: files,
      output_filename: 'novel.epub'
    });
  }
}

// Usage
const app = new WritingApp('http://localhost:8000');
await app.login('johndoe', 'secret');
const projects = await app.listProjects();
console.log('Projects:', projects);
```

## Rate Limiting and Performance

### Best Practices
- Cache repository listings when possible
- Use pagination for large commit histories
- Batch file operations when updating multiple files
- Implement retry logic for network failures

### Limits
- No explicit rate limiting currently implemented
- File size limit: Recommended max 10MB per file
- Commit message length: Recommended max 500 characters

---

This API documentation provides comprehensive coverage of the GitWrite REST API. For more examples and advanced usage, see the interactive documentation at `/docs` when running the API server.