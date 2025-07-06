import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import datetime
from http import HTTPStatus # For status codes
import uuid # For tests that involve UUID generation

# Assuming your FastAPI app instance is in gitwrite_api.main
from gitwrite_api.main import app
from pathlib import Path

from gitwrite_api.models import (
    User, UserRole, SaveFileRequest, RepositoryCreateRequest, EPUBExportRequest,
    CherryPickRequest, BranchReviewCommit, BranchReviewResponse, # These are in models.py
    RepositoriesListResponse, RepositoryListItem # Added for new tests
)
# Models defined within routers/repository.py:
from gitwrite_api.routers.repository import (
    BranchCreateRequest, BranchSwitchRequest, BranchResponse,
    MergeBranchRequest, MergeBranchResponse,
    CompareRefsResponse,
    RevertCommitRequest, RevertCommitResponse,
    SyncFetchStatus, SyncLocalUpdateStatus, SyncPushStatus, SyncRepositoryRequest, SyncRepositoryResponse,
    TagCreateRequest, TagCreateResponse,
    IgnorePatternRequest, IgnoreListResponse, IgnoreAddResponse,
    RepositoryCreateResponse as RouterRepositoryCreateResponse # Alias if it conflicts with model's one
)

from gitwrite_api.security import get_current_active_user as actual_repo_auth_dependency

# Client for making API requests
client = TestClient(app)

# --- Mock Data ---
MOCK_REPO_PATH = "/tmp/gitwrite_repos_api"

# Define New Mock Users with Roles
MOCK_OWNER_USER = User(username="owneruser", email="owner@example.com", roles=[UserRole.OWNER], disabled=False, full_name="Owner User")
MOCK_EDITOR_USER = User(username="editoruser", email="editor@example.com", roles=[UserRole.EDITOR], disabled=False, full_name="Editor User")
MOCK_WRITER_USER = User(username="writeruser", email="writer@example.com", roles=[UserRole.WRITER], disabled=False, full_name="Writer User")
MOCK_BETA_READER_USER = User(username="betauser", email="beta@example.com", roles=[UserRole.BETA_READER], disabled=False, full_name="Beta User")
MOCK_USER_NO_ROLES = User(username="norolesuser", email="noroles@example.com", roles=[], disabled=False, full_name="No Roles User")


# --- Helper for Authentication Mocking ---
def mock_get_current_active_user():
    return MOCK_OWNER_USER

def mock_get_current_active_user_with_role(user: User):
    async def mock_user_provider():
        return user
    return mock_user_provider

def mock_unauthenticated_user():
    pass

# --- Tests for /repository/branches ---
@patch('gitwrite_api.routers.repository.list_branches')
def test_list_branches_success(mock_list_branches):
    mock_list_branches.return_value = {
        "status": "success",
        "branches": ["main", "develop"],
        "message": "Successfully retrieved local branches."
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/branches")
    assert response.status_code == 200
    data = response.json()
    assert data["branches"] == ["main", "develop"]
    assert data["status"] == "success"
    mock_list_branches.assert_called_once_with(repo_path_str=MOCK_REPO_PATH)
    app.dependency_overrides = {}

# --- RBAC Tests for /repository/repositories (Initialize) ---

@patch('gitwrite_api.routers.repository.core_initialize_repository')
def test_api_initialize_repository_rbac_owner_allowed(mock_core_init_repo):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_OWNER_USER)
    project_name = "owner-project-rbac"
    expected_repo_path = f"{MOCK_REPO_PATH}/gitwrite_user_repos/{project_name}"
    mock_core_init_repo.return_value = {
        "status": "success", "message": "Repo created by owner", "path": expected_repo_path
    }
    payload = RepositoryCreateRequest(project_name=project_name)
    response = client.post("/repository/repositories", json=payload.model_dump())
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["repository_id"] == project_name
    assert data["message"] == "Repo created by owner"
    mock_core_init_repo.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_initialize_repository')
def test_api_initialize_repository_rbac_editor_denied(mock_core_init_repo):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_EDITOR_USER)
    payload = RepositoryCreateRequest(project_name="editor-project-rbac")
    response = client.post("/repository/repositories", json=payload.model_dump())
    assert response.status_code == HTTPStatus.FORBIDDEN
    data = response.json()
    assert "User does not have the required role(s): owner" in data["detail"]
    mock_core_init_repo.assert_not_called()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_initialize_repository')
def test_api_initialize_repository_rbac_writer_denied(mock_core_init_repo):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_WRITER_USER)
    payload = RepositoryCreateRequest(project_name="writer-project-rbac")
    response = client.post("/repository/repositories", json=payload.model_dump())
    assert response.status_code == HTTPStatus.FORBIDDEN
    data = response.json()
    assert "User does not have the required role(s): owner" in data["detail"]
    mock_core_init_repo.assert_not_called()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_initialize_repository')
def test_api_initialize_repository_rbac_beta_reader_denied(mock_core_init_repo):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_BETA_READER_USER)
    payload = RepositoryCreateRequest(project_name="beta-project-rbac")
    response = client.post("/repository/repositories", json=payload.model_dump())
    assert response.status_code == HTTPStatus.FORBIDDEN
    data = response.json()
    assert "User does not have the required role(s): owner" in data["detail"]
    mock_core_init_repo.assert_not_called()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_initialize_repository')
def test_api_initialize_repository_rbac_user_no_roles_denied(mock_core_init_repo):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_USER_NO_ROLES)
    payload = RepositoryCreateRequest(project_name="no-roles-project-rbac")
    response = client.post("/repository/repositories", json=payload.model_dump())
    assert response.status_code == HTTPStatus.FORBIDDEN
    data = response.json()
    assert "User has no assigned roles" in data["detail"]
    mock_core_init_repo.assert_not_called()
    app.dependency_overrides = {}

# --- RBAC Tests for /repository/save (Save File) ---

@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_rbac_owner_allowed(mock_core_save_file):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_OWNER_USER)
    mock_core_save_file.return_value = {'status': 'success', 'message': 'Saved by owner', 'commit_id': 'commit1'}
    payload = SaveFileRequest(file_path="owner.txt", content="c", commit_message="m")
    response = client.post("/repository/save", json=payload.model_dump())
    assert response.status_code == HTTPStatus.OK
    assert response.json()["commit_id"] == "commit1"
    mock_core_save_file.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_rbac_editor_allowed(mock_core_save_file):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_EDITOR_USER)
    mock_core_save_file.return_value = {'status': 'success', 'message': 'Saved by editor', 'commit_id': 'commit2'}
    payload = SaveFileRequest(file_path="editor.txt", content="c", commit_message="m")
    response = client.post("/repository/save", json=payload.model_dump())
    assert response.status_code == HTTPStatus.OK
    assert response.json()["commit_id"] == "commit2"
    mock_core_save_file.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_rbac_writer_allowed(mock_core_save_file):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_WRITER_USER)
    mock_core_save_file.return_value = {'status': 'success', 'message': 'Saved by writer', 'commit_id': 'commit3'}
    payload = SaveFileRequest(file_path="writer.txt", content="c", commit_message="m")
    response = client.post("/repository/save", json=payload.model_dump())
    assert response.status_code == HTTPStatus.OK
    assert response.json()["commit_id"] == "commit3"
    mock_core_save_file.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_rbac_beta_reader_denied(mock_core_save_file):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_BETA_READER_USER)
    payload = SaveFileRequest(file_path="beta.txt", content="c", commit_message="m")
    response = client.post("/repository/save", json=payload.model_dump())
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "User does not have the required role(s): owner, editor, writer" in response.json()["detail"]
    mock_core_save_file.assert_not_called()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_rbac_no_roles_denied(mock_core_save_file):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_USER_NO_ROLES)
    payload = SaveFileRequest(file_path="no_roles.txt", content="c", commit_message="m")
    response = client.post("/repository/save", json=payload.model_dump())
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "User has no assigned roles" in response.json()["detail"]
    mock_core_save_file.assert_not_called()
    app.dependency_overrides = {}

# --- RBAC Tests for /repository/review/{branch_name} (Branch Review) ---

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_rbac_owner_allowed(mock_core_review):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_OWNER_USER)
    mock_core_review.return_value = []
    response = client.get("/repository/review/main")
    assert response.status_code == HTTPStatus.OK
    mock_core_review.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_rbac_editor_allowed(mock_core_review):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_EDITOR_USER)
    mock_core_review.return_value = []
    response = client.get("/repository/review/main")
    assert response.status_code == HTTPStatus.OK
    mock_core_review.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_rbac_beta_reader_allowed(mock_core_review):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_BETA_READER_USER)
    mock_core_review.return_value = []
    response = client.get("/repository/review/main")
    assert response.status_code == HTTPStatus.OK
    mock_core_review.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_rbac_writer_denied(mock_core_review):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_WRITER_USER)
    response = client.get("/repository/review/main")
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "User does not have the required role(s): owner, editor, beta_reader" in response.json()["detail"]
    mock_core_review.assert_not_called()
    app.dependency_overrides = {}

# --- RBAC Tests for /repository/export/epub (EPUB Export) ---

@patch('gitwrite_core.export.export_to_epub') # Target the original core function
def test_api_export_epub_rbac_owner_allowed(mock_core_export_func):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_OWNER_USER)
    mock_core_export_func.return_value = {"status": "success", "message": "Exported by owner", "server_file_path": "/path/owner.epub"}
    payload = EPUBExportRequest(file_list=["file.md"], output_filename="owner.epub")
    response = client.post("/repository/export/epub", json=payload.model_dump())
    assert response.status_code == HTTPStatus.OK
    mock_core_export_func.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_core.export.export_to_epub') # Target the original core function
def test_api_export_epub_rbac_editor_allowed(mock_core_export_func):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_EDITOR_USER)
    mock_core_export_func.return_value = {"status": "success", "message": "Exported by editor", "server_file_path": "/path/editor.epub"}
    payload = EPUBExportRequest(file_list=["file.md"], output_filename="editor.epub")
    response = client.post("/repository/export/epub", json=payload.model_dump())
    assert response.status_code == HTTPStatus.OK
    mock_core_export_func.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_core.export.export_to_epub') # Target the original core function
def test_api_export_epub_rbac_writer_allowed(mock_core_export_func):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_WRITER_USER)
    mock_core_export_func.return_value = {"status": "success", "message": "Exported by writer", "server_file_path": "/path/writer.epub"}
    payload = EPUBExportRequest(file_list=["file.md"], output_filename="writer.epub")
    response = client.post("/repository/export/epub", json=payload.model_dump())
    assert response.status_code == HTTPStatus.OK
    mock_core_export_func.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_core.export.export_to_epub') # Target the original core function
def test_api_export_epub_rbac_beta_reader_allowed(mock_core_export_func):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_BETA_READER_USER)
    mock_core_export_func.return_value = {"status": "success", "message": "Exported by beta", "server_file_path": "/path/beta.epub"}
    payload = EPUBExportRequest(file_list=["file.md"], output_filename="beta.epub")
    response = client.post("/repository/export/epub", json=payload.model_dump())
    assert response.status_code == HTTPStatus.OK
    mock_core_export_func.assert_called_once()
    app.dependency_overrides = {}

@patch('gitwrite_core.export.export_to_epub') # Target the original core function
def test_api_export_epub_rbac_no_roles_denied(mock_core_export_func):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user_with_role(MOCK_USER_NO_ROLES)
    payload = EPUBExportRequest(file_list=["file.md"], output_filename="no_roles.epub")
    response = client.post("/repository/export/epub", json=payload.model_dump())
    assert response.status_code == HTTPStatus.FORBIDDEN
    assert "User has no assigned roles" in response.json()["detail"]
    mock_core_export_func.assert_not_called()
    app.dependency_overrides = {}

# --- Original tests below, ensure they use appropriate mocks ---
# (Keeping a few examples of original tests to show they should now pass with MOCK_OWNER_USER
# or be adjusted if OWNER is not sufficient for their specific logic on an RBAC endpoint)

@patch('gitwrite_api.routers.repository.list_tags')
def test_list_tags_success(mock_list_tags): # Example of a non-RBAC protected endpoint test
    mock_list_tags.return_value = {
        "status": "success",
        "tags": ["v1.0", "v1.1"],
        "message": "Successfully retrieved tags."
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/tags")
    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["v1.0", "v1.1"]
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_success_original_style(mock_core_save_file): # Original test, now using MOCK_OWNER_USER
    mock_core_save_file.return_value = {
        'status': 'success',
        'message': 'File saved and committed successfully.',
        'commit_id': 'fakecommit123'
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = SaveFileRequest(
        file_path="test_file.txt",
        content="Hello world",
        commit_message="Add test_file.txt"
    )
    response = client.post("/repository/save", json=payload.model_dump())
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "success"
    assert data["commit_id"] == "fakecommit123"
    mock_core_save_file.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        file_path=payload.file_path,
        content=payload.content,
        commit_message=payload.commit_message,
        author_name=MOCK_OWNER_USER.username,
        author_email=MOCK_OWNER_USER.email
    )
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_initialize_repository')
@patch('gitwrite_api.routers.repository.uuid.uuid4')
def test_api_initialize_repository_with_project_name_success_original_style(mock_uuid4, mock_core_init_repo):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    project_name = "test-project-original-style"
    expected_repo_path = f"{MOCK_REPO_PATH}/gitwrite_user_repos/{project_name}"
    mock_core_init_repo.return_value = {
        "status": "success",
        "message": f"Repository '{project_name}' initialized.",
        "path": expected_repo_path
    }
    payload = RepositoryCreateRequest(project_name=project_name)
    response = client.post("/repository/repositories", json=payload.model_dump())
    assert response.status_code == HTTPStatus.CREATED
    data = response.json()
    assert data["repository_id"] == project_name
    app.dependency_overrides = {}

# (The rest of the original tests would follow here)

# --- Tests for /repository/compare ---
@patch('gitwrite_api.routers.repository.core_get_diff')
@patch('gitwrite_api.routers.repository.core_get_word_level_diff')
def test_api_compare_refs_default_mode(mock_get_word_diff, mock_get_diff):
    mock_get_diff.return_value = {
        "ref1_oid": "abc", "ref2_oid": "def",
        "ref1_display_name": "HEAD~1", "ref2_display_name": "HEAD",
        "patch_text": "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/compare?ref1=HEAD~1&ref2=HEAD")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["patch_text"] == "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
    assert isinstance(data["patch_text"], str)
    mock_get_diff.assert_called_once_with(repo_path_str=MOCK_REPO_PATH, ref1_str="HEAD~1", ref2_str="HEAD")
    mock_get_word_diff.assert_not_called()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
@patch('gitwrite_api.routers.repository.core_get_word_level_diff')
def test_api_compare_refs_word_mode(mock_get_word_diff, mock_get_diff):
    raw_patch_text = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old content\n+new content"
    mock_get_diff.return_value = {
        "ref1_oid": "abc", "ref2_oid": "def",
        "ref1_display_name": "HEAD~1", "ref2_display_name": "HEAD",
        "patch_text": raw_patch_text
    }
    structured_diff_expected = [
        {"file_path": "file.txt", "hunks": [{"lines": [
            {"type": "deletion", "content": "old content", "words": [{"type": "removed", "content": "old content"}]},
            {"type": "addition", "content": "new content", "words": [{"type": "added", "content": "new content"}]}
        ]}]}
    ]
    mock_get_word_diff.return_value = structured_diff_expected

    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/compare?ref1=HEAD~1&ref2=HEAD&diff_mode=word")
    assert response.status_code == HTTPStatus.OK
    data = response.json()

    assert data["patch_text"] == structured_diff_expected
    assert isinstance(data["patch_text"], list)
    mock_get_diff.assert_called_once_with(repo_path_str=MOCK_REPO_PATH, ref1_str="HEAD~1", ref2_str="HEAD")
    mock_get_word_diff.assert_called_once_with(raw_patch_text)
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
@patch('gitwrite_api.routers.repository.core_get_word_level_diff')
def test_api_compare_refs_word_mode_no_diff(mock_get_word_diff, mock_get_diff):
    mock_get_diff.return_value = {
        "ref1_oid": "abc", "ref2_oid": "def",
        "ref1_display_name": "HEAD~1", "ref2_display_name": "HEAD",
        "patch_text": "" # No textual diff
    }
    # core_get_word_level_diff should return [] if patch_text is empty
    mock_get_word_diff.return_value = []

    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/compare?diff_mode=word") # Using default refs
    assert response.status_code == HTTPStatus.OK
    data = response.json()

    assert data["patch_text"] == [] # Expect empty list for structured diff of no changes
    assert isinstance(data["patch_text"], list)
    mock_get_diff.assert_called_once_with(repo_path_str=MOCK_REPO_PATH, ref1_str=None, ref2_str=None)
    # core_get_word_level_diff is NOT called if patch_text is empty
    mock_get_word_diff.assert_not_called()
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
def test_api_compare_refs_invalid_diff_mode(mock_get_diff):
    mock_get_diff.return_value = {
        "ref1_oid": "abc", "ref2_oid": "def",
        "ref1_display_name": "HEAD~1", "ref2_display_name": "HEAD",
        "patch_text": "some raw patch"
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/compare?diff_mode=invalid")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["patch_text"] == "some raw patch" # Should fall back to raw patch
    assert isinstance(data["patch_text"], str)
    mock_get_diff.assert_called_once()
    app.dependency_overrides = {}


# --- Tests for /repository/file-content ---

@patch('gitwrite_api.routers.repository.core_get_file_content_at_commit')
def test_api_get_file_content_success(mock_core_get_content):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    file_path_param = "src/main.py"
    commit_sha_param = "a1b2c3d4e5f6"
    mock_core_get_content.return_value = {
        'status': 'success',
        'file_path': file_path_param,
        'commit_sha': commit_sha_param,
        'content': 'print("Hello, World!")',
        'size': 22,
        'mode': '100644',
        'is_binary': False,
        'message': 'File content retrieved successfully.'
    }

    response = client.get(f"/repository/file-content?file_path={file_path_param}&commit_sha={commit_sha_param}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["file_path"] == file_path_param
    assert data["commit_sha"] == commit_sha_param
    assert data["content"] == 'print("Hello, World!")'
    assert data["is_binary"] is False
    mock_core_get_content.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        file_path=file_path_param,
        commit_sha_str=commit_sha_param
    )
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_get_file_content_at_commit')
def test_api_get_file_content_binary(mock_core_get_content):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    file_path_param = "image.png"
    commit_sha_param = "b2c3d4e5f6a1"
    mock_core_get_content.return_value = {
        'status': 'success',
        'file_path': file_path_param,
        'commit_sha': commit_sha_param,
        'content': '[Binary content of size 1024 bytes]',
        'size': 1024,
        'mode': '100644',
        'is_binary': True,
        'message': 'File content retrieved successfully.'
    }

    response = client.get(f"/repository/file-content?file_path={file_path_param}&commit_sha={commit_sha_param}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["file_path"] == file_path_param
    assert data["is_binary"] is True
    assert data["content"] == '[Binary content of size 1024 bytes]'
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_get_file_content_at_commit')
def test_api_get_file_content_file_not_found_in_commit(mock_core_get_content):
    from gitwrite_core.exceptions import FileNotFoundInCommitError
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    error_message = "File 'ghost.txt' not found in commit 'a1b2c3d4e5f6'."
    mock_core_get_content.side_effect = FileNotFoundInCommitError(error_message)
    response = client.get("/repository/file-content?file_path=ghost.txt&commit_sha=a1b2c3d4e5f6")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert error_message in response.json()["detail"]
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_get_file_content_at_commit')
def test_api_get_file_content_commit_not_found(mock_core_get_content):
    from gitwrite_core.exceptions import CommitNotFoundError
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    invalid_sha = "000000"
    error_message = f"Commit with SHA '{invalid_sha}' not found or invalid."
    mock_core_get_content.side_effect = CommitNotFoundError(error_message)
    response = client.get(f"/repository/file-content?file_path=any.txt&commit_sha={invalid_sha}")
    assert response.status_code == HTTPStatus.NOT_FOUND
    assert error_message in response.json()["detail"]
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_get_file_content_at_commit')
def test_api_get_file_content_repo_config_error(mock_core_get_content):
    from gitwrite_core.exceptions import RepositoryNotFoundError
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    error_message = "Repository not found at /nonexistent/path."
    mock_core_get_content.side_effect = RepositoryNotFoundError(error_message)
    response = client.get("/repository/file-content?file_path=any.txt&commit_sha=a1b2c3")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert error_message in response.json()["detail"]
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_get_file_content_at_commit')
def test_api_get_file_content_path_is_directory(mock_core_get_content):
    from gitwrite_core.exceptions import FileNotFoundInCommitError
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    error_message = "Path 'src_dir' in commit 'a1b2c3' is not a file (it's a tree)."
    mock_core_get_content.side_effect = FileNotFoundInCommitError(error_message)
    response = client.get("/repository/file-content?file_path=src_dir&commit_sha=a1b2c3")
    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert error_message in response.json()["detail"]
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_get_file_content_at_commit')
def test_api_get_file_content_generic_core_error(mock_core_get_content):
    from gitwrite_core.exceptions import GitWriteError
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    error_message = "A generic core layer error occurred."
    mock_core_get_content.side_effect = GitWriteError(error_message)
    response = client.get("/repository/file-content?file_path=some.txt&commit_sha=a1b2c3")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert error_message in response.json()["detail"]
    app.dependency_overrides = {}

# Test with actual core exceptions being raised (if core layer changes to that pattern)
# For now, sticking to dict-based error reporting from core.

# --- Tests for GET /repositorys (List Repositories) ---

from gitwrite_api.models import RepositoriesListResponse, RepositoryListItem # Ensure these are imported

@patch('gitwrite_api.routers.repository.core_get_repository_metadata')
@patch('gitwrite_api.routers.repository.os.listdir')
@patch('gitwrite_api.routers.repository.Path.is_dir')
def test_api_list_repositories_success(mock_is_dir, mock_listdir, mock_get_metadata):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    mock_listdir.return_value = ["repo1", "repo2", "not_a_repo_file.txt"]

    # Simulate Path.is_dir behavior for items from listdir
    # repo1 and repo2 are dirs, not_a_repo_file.txt is not
    class MockHelper:
        def is_dir_side_effect(self, self_arg, path):
            if path.name in ["repo1", "repo2"]:
                return True
            return False

    mock_helper = MockHelper()
    mock_is_dir.side_effect = mock_helper.is_dir_side_effect

    # Mock metadata returned by core_get_repository_metadata
    now = datetime.datetime.now(datetime.timezone.utc)
    mock_get_metadata.side_effect = [
        {"name": "repo1", "last_modified": now, "description": "First repo"},
        {"name": "repo2", "last_modified": now - datetime.timedelta(days=1), "description": None},
        # Note: core_get_repository_metadata will only be called for directories.
        # For "not_a_repo_file.txt", mock_is_dir returns False, so core_get_repository_metadata isn't called.
    ]

    expected_user_repos_base_dir = Path(MOCK_REPO_PATH) / "gitwrite_user_repos"

    response = client.get("/repositorys") # Path will be /repository + s

    assert response.status_code == HTTPStatus.OK
    data = response.json()

    assert data["count"] == 2
    assert len(data["repositories"]) == 2

    # Check repo1 details
    assert data["repositories"][0]["name"] == "repo1"
    assert data["repositories"][0]["description"] == "First repo"
    # Pydantic will convert datetime to ISO string
    assert datetime.datetime.fromisoformat(data["repositories"][0]["last_modified"]) == now

    # Check repo2 details
    assert data["repositories"][1]["name"] == "repo2"
    assert data["repositories"][1]["description"] is None
    assert datetime.datetime.fromisoformat(data["repositories"][1]["last_modified"]) == now - datetime.timedelta(days=1)

    mock_listdir.assert_called_once_with(expected_user_repos_base_dir)
    # mock_is_dir should be called for each item from listdir
    assert mock_is_dir.call_count == 3
    # core_get_repository_metadata should be called for each directory
    assert mock_get_metadata.call_count == 2
    mock_get_metadata.assert_any_call(expected_user_repos_base_dir / "repo1")
    mock_get_metadata.assert_any_call(expected_user_repos_base_dir / "repo2")

    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.os.listdir')
@patch('gitwrite_api.routers.repository.Path.is_dir') # Mock is_dir as well
def test_api_list_repositories_empty(mock_is_dir, mock_listdir):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    mock_listdir.return_value = []
    mock_is_dir.return_value = False # Default for empty or non-dirs

    response = client.get("/repositorys")
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["count"] == 0
    assert len(data["repositories"]) == 0
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.os.listdir')
def test_api_list_repositories_os_error(mock_listdir):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    mock_listdir.side_effect = OSError("Simulated permission denied")

    response = client.get("/repositorys")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Error accessing repository storage" in response.json()["detail"]
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.Path.exists')
@patch('gitwrite_api.routers.repository.Path.is_dir')
def test_api_list_repositories_base_dir_not_exist(mock_path_is_dir, mock_path_exists):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    # Simulate the base path not existing or not being a directory
    # user_repos_base_dir = Path(MOCK_REPO_PATH) / "gitwrite_user_repos"
    # We need to mock its .exists() or .is_dir() call.
    # The check is `if not user_repos_base_dir.exists() or not user_repos_base_dir.is_dir():`

    # Case 1: Base path does not exist
    mock_path_exists.return_value = False
    mock_path_is_dir.return_value = False # Doesn't matter if exists is false

    response_no_exist = client.get("/repositorys")
    assert response_no_exist.status_code == HTTPStatus.OK
    data_no_exist = response_no_exist.json()
    assert data_no_exist["count"] == 0
    assert len(data_no_exist["repositories"]) == 0

    # Case 2: Base path exists but is not a directory
    mock_path_exists.return_value = True
    mock_path_is_dir.return_value = False

    response_not_dir = client.get("/repositorys")
    assert response_not_dir.status_code == HTTPStatus.OK
    data_not_dir = response_not_dir.json()
    assert data_not_dir["count"] == 0
    assert len(data_not_dir["repositories"]) == 0

    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_repository_metadata')
@patch('gitwrite_api.routers.repository.os.listdir')
@patch('gitwrite_api.routers.repository.Path.is_dir')
def test_api_list_repositories_metadata_parse_failure(mock_is_dir, mock_listdir, mock_get_metadata):
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    mock_listdir.return_value = ["repo_bad_meta"]
    mock_is_dir.return_value = True # It's a directory

    # Simulate core_get_repository_metadata returning valid data, but then Pydantic model fails
    # No, the test should be that core_get_repository_metadata returns data, and Pydantic parsing is tested here.
    # If core_get_repository_metadata returns None, it's skipped.
    # This test aims for when core_get_repository_metadata returns a dict that RepositoryListItem can't parse.
    # This is more of an integration test of the Pydantic model itself.
    # Let's assume core_get_repository_metadata returns a valid dict for one, and an invalid for another.

    mock_listdir.return_value = ["repo_good", "repo_invalid_structure"]
    now = datetime.datetime.now(datetime.timezone.utc)

    def get_meta_side_effect(path_arg):
        if path_arg.name == "repo_good":
            return {"name": "repo_good", "last_modified": now, "description": "Good one"}
        elif path_arg.name == "repo_invalid_structure":
            # This dict is missing 'last_modified', which is required by RepositoryListItem
            return {"name": "repo_invalid_structure", "description": "Bad structure"}
        return None # Should not be called for others if is_dir handles it

    mock_get_metadata.side_effect = get_meta_side_effect
    mock_is_dir.return_value = True # All are dirs for this test

    response = client.get("/repositorys")
    assert response.status_code == HTTPStatus.OK
    data = response.json()

    # Only the "repo_good" should be in the list, as "repo_invalid_structure" would fail Pydantic validation
    # within the endpoint loop and be skipped.
    assert data["count"] == 1
    assert len(data["repositories"]) == 1
    assert data["repositories"][0]["name"] == "repo_good"

    app.dependency_overrides = {}
