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
    CherryPickRequest, BranchReviewCommit, BranchReviewResponse # These are in models.py
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
