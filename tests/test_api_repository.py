import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import datetime

# Assuming your FastAPI app instance is in gitwrite_api.main
from gitwrite_api.main import app
# Placeholder User model used in the router's dependency
from gitwrite_api.routers.repository import User as PlaceholderUser

# Client for making API requests
client = TestClient(app)

# --- Mock Data ---
MOCK_USER = PlaceholderUser(username="testuser", email="test@example.com", active=True)
MOCK_REPO_PATH = "/path/to/user/repo" # Should match the placeholder in the router

# --- Helper for Authentication Mocking ---
def mock_get_current_active_user():
    return MOCK_USER

def mock_unauthenticated_user():
    # This function will be used to override the dependency and simulate unauthenticated access.
    # However, FastAPI's TestClient usually handles this by not providing auth headers.
    # For dependency override, we'd typically raise HTTPException(status_code=401),
    # but the router's get_current_active_user itself is a placeholder.
    # Let's assume for now the test will check for 401 if the dependency is not met.
    # The actual `get_current_active_user` in a real app would raise 401 if token is invalid/missing.
    # For these tests, we'll explicitly override to raise 401 if needed, or just not override for some tests.
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
    app.dependency_overrides = {} # Clear overrides

def test_list_branches_unauthorized():
    # To truly test unauthorized, the actual dependency would raise HTTPException(401)
    # For now, we assume if the dependency is not overridden by a mock user, it might fail or use a default.
    # A better way is to have get_current_active_user raise 401 if no token.
    # Let's simulate the router's dependency raising 401 for this test.

    async def raise_401():
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Find the actual dependency function used in the router for get_current_active_user
    # This is tricky as it's imported directly. For robust testing, the dependency should be injectable.
    # For now, we'll assume the default behavior of a missing/invalid token would lead to 401
    # This test might need adjustment based on the actual auth implementation.
    # If the placeholder always returns a user, this test won't reflect true unauth.
    # We'll skip truly testing this for now until auth is real.
    # Instead, let's test how the app behaves if the core function returns an error.
    app.dependency_overrides = {} # Ensure no user override
    # This test is more of a placeholder for a real auth system test.
    # response = client.get("/repository/branches")
    # assert response.status_code == 401 # This depends on actual auth

@patch('gitwrite_api.routers.repository.list_branches')
def test_list_branches_core_error(mock_list_branches):
    mock_list_branches.return_value = {
        "status": "error",
        "message": "Git command failed"
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/branches")

    assert response.status_code == 500
    assert response.json()["detail"] == "Git command failed"
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.list_branches')
def test_list_branches_empty_repo(mock_list_branches):
    mock_list_branches.return_value = {
        "status": "empty_repo",
        "branches": [],
        "message": "Repository is empty and has no branches."
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/branches")

    assert response.status_code == 200 # As per handle_core_response
    data = response.json()
    assert data["branches"] == []
    assert data["status"] == "empty_repo"
    app.dependency_overrides = {}


# --- Tests for /repository/tags ---

@patch('gitwrite_api.routers.repository.list_tags')
def test_list_tags_success(mock_list_tags):
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
    assert data["status"] == "success"
    mock_list_tags.assert_called_once_with(repo_path_str=MOCK_REPO_PATH)
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.list_tags')
def test_list_tags_no_tags(mock_list_tags):
    mock_list_tags.return_value = {
        "status": "no_tags",
        "tags": [],
        "message": "No tags found in the repository."
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/tags")

    assert response.status_code == 200 # As per handle_core_response
    data = response.json()
    assert data["tags"] == []
    assert data["status"] == "no_tags"
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.list_tags')
def test_list_tags_core_error(mock_list_tags):
    mock_list_tags.return_value = {"status": "error", "message": "Failed to list tags"}
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/tags")

    assert response.status_code == 500
    assert response.json()["detail"] == "Failed to list tags"
    app.dependency_overrides = {}


# --- Tests for /repository/commits ---
MOCK_COMMIT_LIST = [
    {
        'sha': 'a1b2c3d4', 'message': 'Initial commit',
        'author_name': 'Test Author', 'author_email': 'author@example.com',
        'author_date': datetime.datetime.now(datetime.timezone.utc).timestamp(), # Store as timestamp
        'committer_name': 'Test Committer', 'committer_email': 'committer@example.com',
        'committer_date': datetime.datetime.now(datetime.timezone.utc).timestamp(),
        'parents': []
    },
    {
        'sha': 'e5f6g7h8', 'message': 'Add feature X',
        'author_name': 'Test Author', 'author_email': 'author@example.com',
        'author_date': (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).timestamp(),
        'committer_name': 'Test Committer', 'committer_email': 'committer@example.com',
        'committer_date': (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=1)).timestamp(),
        'parents': ['a1b2c3d4']
    }
]

@patch('gitwrite_api.routers.repository.list_commits')
def test_list_commits_success(mock_list_commits):
    # Prepare mock data that Pydantic can convert to datetime
    api_response_commits = [
        {**commit,
         'author_date': datetime.datetime.fromtimestamp(commit['author_date'], datetime.timezone.utc).isoformat(),
         'committer_date': datetime.datetime.fromtimestamp(commit['committer_date'], datetime.timezone.utc).isoformat()
        } for commit in MOCK_COMMIT_LIST
    ]

    mock_list_commits.return_value = {
        "status": "success",
        "commits": MOCK_COMMIT_LIST, # Core returns timestamps
        "message": "Successfully retrieved 2 commits."
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/commits")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    # Compare relevant fields, exact datetime string match can be tricky due to precision/format
    assert len(data["commits"]) == len(api_response_commits)
    assert data["commits"][0]["sha"] == api_response_commits[0]["sha"]
    assert data["commits"][0]["message"] == api_response_commits[0]["message"]
    # Pydantic model should have converted timestamp to ISO string
    assert "T" in data["commits"][0]["author_date"]

    mock_list_commits.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH, branch_name=None, max_count=None
    )
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.list_commits')
def test_list_commits_with_params(mock_list_commits):
    mock_list_commits.return_value = {
        "status": "success", "commits": [MOCK_COMMIT_LIST[0]], "message": "Successfully retrieved 1 commit."
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/commits?branch_name=develop&max_count=1")

    assert response.status_code == 200
    data = response.json()
    assert len(data["commits"]) == 1
    mock_list_commits.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH, branch_name="develop", max_count=1
    )
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.list_commits')
def test_list_commits_branch_not_found(mock_list_commits):
    mock_list_commits.return_value = {
        "status": "error", "commits": [], "message": "Branch 'nonexistent' not found."
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/commits?branch_name=nonexistent")

    # Based on handle_core_response, 'error' status from core maps to 500
    # However, if the message implies "not found", it might be better to map to 404.
    # The current handle_core_response maps general 'error' to 500.
    # And specific 'not_found' status to 404.
    # If core returns 'error' with 'not found' in message, it will be 500.
    # To get 404, core should return status='not_found'.
    # Let's assume core function returns status='not_found' for this case.
    mock_list_commits.return_value = {
        "status": "not_found", "commits": [], "message": "Branch 'nonexistent' not found."
    }
    # Re-override for this specific test condition, as previous call might have different mock value
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/commits?branch_name=nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Branch 'nonexistent' not found."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.list_commits')
def test_list_commits_no_commits(mock_list_commits):
    mock_list_commits.return_value = {
        "status": "no_commits", "commits": [], "message": "No commits found."
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    response = client.get("/repository/commits")

    assert response.status_code == 200 # As per handle_core_response
    data = response.json()
    assert data["commits"] == []
    assert data["status"] == "no_commits"
    app.dependency_overrides = {}

# A note on testing unauthorized (401):
# The current placeholder `get_current_active_user` in the router doesn't enforce real authentication.
# To properly test 401s, one would:
# 1. Implement actual token-based authentication in `get_current_active_user`.
# 2. In tests, either don't provide the `Authorization` header, or provide an invalid one.
#    client.get("/repository/branches") # No auth header
#    client.get("/repository/branches", headers={"Authorization": "Bearer invalidtoken"})
# For the purpose of these tests with a placeholder auth, we rely on overriding the dependency
# or assuming the default behavior would be a 401 if the dependency was more realistic.
# The `test_list_branches_unauthorized` is a placeholder for this concept.
# A simple way to simulate a 401 for a specific test, if the dependency is complex to mock for raising 401:
#
# from gitwrite_api.routers import repository as repo_router # import the module
# original_dep = repo_router.get_current_active_user # store original
# async def mock_raise_401():
#     from fastapi import HTTPException
#     raise HTTPException(status_code=401, detail="Simulated Unauth")
#
# def test_list_branches_explicit_401_override(mocker):
#     # This requires get_current_active_user to be easily patchable in the router module
#     mocker.patch('gitwrite_api.routers.repository.get_current_active_user', new=mock_raise_401)
#     response = client.get("/repository/branches")
#     assert response.status_code == 401
#     # cleanup: repo_router.get_current_active_user = original_dep // or use pytest features for this
#
# The current `app.dependency_overrides[app.router.dependencies[0].depends]` is a bit fragile
# as it depends on the order/structure of dependencies in the FastAPI app.
# A more robust way for dependency overriding is to use the specific function object:
# from gitwrite_api.routers.repository import get_current_active_user as actual_dependency_func
# app.dependency_overrides[actual_dependency_func] = new_mock_func
# This requires `get_current_active_user` to be accessible for import here.
# The placeholder `get_current_active_user` is defined in `gitwrite_api.routers.repository`
# so it can be imported directly for overriding.

from gitwrite_api.routers.repository import get_current_active_user as actual_repo_auth_dependency
from gitwrite_api.models import SaveFileRequest # For the /save endpoint tests
from http import HTTPStatus # For status codes, optional

# Import models and exceptions for new tests
from gitwrite_api.routers.repository import BranchCreateRequest, BranchSwitchRequest # BranchResponse is implicitly tested
from gitwrite_core.exceptions import (
    BranchAlreadyExistsError as CoreBranchAlreadyExistsError,
    RepositoryEmptyError as CoreRepositoryEmptyError,
    BranchNotFoundError as CoreBranchNotFoundError,
    MergeConflictError as CoreMergeConflictError,
    DetachedHeadError as CoreDetachedHeadError,
    GitWriteError as CoreGitWriteError,
    RepositoryNotFoundError as CoreRepositoryNotFoundError,
    CommitNotFoundError as CoreCommitNotFoundError, # For compare tests
    NotEnoughHistoryError as CoreNotEnoughHistoryError # For compare tests
)
from gitwrite_api.routers.repository import MergeBranchRequest # For merge tests
# No specific request model for GET /compare, but response model is CompareRefsResponse


@patch('gitwrite_api.routers.repository.list_branches')
def test_list_branches_unauthorized_explicit_override(mock_list_branches):
    async def mock_raise_401():
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Not authenticated via override")

    app.dependency_overrides[actual_repo_auth_dependency] = mock_raise_401
    response = client.get("/repository/branches")
    assert response.status_code == 401
    assert response.json()["detail"] == "Not authenticated via override"
    app.dependency_overrides = {} # Clear overrides


# --- Tests for /repository/save ---

@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_success(mock_core_save_file):
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

    assert response.status_code == HTTPStatus.OK # 200
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "File saved and committed successfully."
    assert data["commit_id"] == "fakecommit123"

    mock_core_save_file.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        file_path=payload.file_path,
        content=payload.content,
        commit_message=payload.commit_message,
        author_name=MOCK_USER.username,
        author_email=MOCK_USER.email
    )
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_core_function_error(mock_core_save_file):
    mock_core_save_file.return_value = {
        'status': 'error',
        'message': 'Core function failed spectacularly.',
        'commit_id': None
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = SaveFileRequest(
        file_path="another_test.txt",
        content="Some content",
        commit_message="A commit message"
    )
    response = client.post("/repository/save", json=payload.model_dump())

    # The API endpoint has logic to return 400 or 500.
    # If message contains "Repository not found", "Error committing file", or "Error staging file", it's 500.
    # Otherwise, it's 400. "Core function failed spectacularly." should result in 400.
    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    data = response.json()
    assert data["detail"] == "Core function failed spectacularly."
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.save_and_commit_file')
def test_api_save_file_core_function_internal_error(mock_core_save_file):
    # Test a case where the error message implies an internal server error
    mock_core_save_file.return_value = {
        'status': 'error',
        'message': 'Error committing file due to internal git problem.',
        'commit_id': None
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = SaveFileRequest(file_path="internal_error.txt", content="content", commit_message="msg")
    response = client.post("/repository/save", json=payload.model_dump())

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    data = response.json()
    assert data["detail"] == "Error committing file due to internal git problem."
    app.dependency_overrides = {}


def test_api_save_file_invalid_request_payload():
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    # Missing 'file_path', 'content', 'commit_message'
    invalid_payload = {
        "file_path": "test.txt"
        # 'content' and 'commit_message' are missing
    }
    response = client.post("/repository/save", json=invalid_payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422
    data = response.json()
    assert "detail" in data
    # Check if detail mentions the missing fields (FastAPI provides this)
    assert any("content" in error["loc"] for error in data["detail"])
    assert any("commit_message" in error["loc"] for error in data["detail"])
    app.dependency_overrides = {}


def test_api_save_file_not_authenticated():
    # Ensure no auth override for this test
    app.dependency_overrides = {}

    # Temporarily override the actual_repo_auth_dependency to simulate raising 401
    async def mock_raise_401_for_save():
        from fastapi import HTTPException
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Not authenticated for save")

    app.dependency_overrides[actual_repo_auth_dependency] = mock_raise_401_for_save

    payload = SaveFileRequest(
        file_path="test_file.txt",
        content="Hello world",
        commit_message="Add test_file.txt"
    )
    response = client.post("/repository/save", json=payload.model_dump())

    assert response.status_code == HTTPStatus.UNAUTHORIZED # 401
    assert response.json()["detail"] == "Not authenticated for save"
    app.dependency_overrides = {} # Clear overrides


# --- Tests for POST /repository/branches ---

@patch('gitwrite_api.routers.repository.create_and_switch_branch')
def test_api_create_branch_success(mock_core_create_branch):
    mock_core_create_branch.return_value = {
        'status': 'success', # Core returns 'success'
        'branch_name': 'new-feature-branch',
        'head_commit_oid': 'newcommitsha123'
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchCreateRequest(branch_name="new-feature-branch")
    response = client.post("/repository/branches", json=payload.model_dump())

    assert response.status_code == HTTPStatus.CREATED # 201
    data = response.json()
    assert data["status"] == "created" # API specific status
    assert data["branch_name"] == "new-feature-branch"
    assert data["message"] == "Branch 'new-feature-branch' created and switched to successfully."
    assert data["head_commit_oid"] == "newcommitsha123"
    mock_core_create_branch.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        branch_name="new-feature-branch"
    )
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.create_and_switch_branch')
def test_api_create_branch_already_exists(mock_core_create_branch):
    mock_core_create_branch.side_effect = CoreBranchAlreadyExistsError("Branch 'existing-branch' already exists.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchCreateRequest(branch_name="existing-branch")
    response = client.post("/repository/branches", json=payload.model_dump())

    assert response.status_code == HTTPStatus.CONFLICT # 409
    assert response.json()["detail"] == "Branch 'existing-branch' already exists."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.create_and_switch_branch')
def test_api_create_branch_repo_empty(mock_core_create_branch):
    mock_core_create_branch.side_effect = CoreRepositoryEmptyError("Cannot create branch: HEAD is unborn.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchCreateRequest(branch_name="some-branch")
    response = client.post("/repository/branches", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Cannot create branch: HEAD is unborn."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.create_and_switch_branch')
def test_api_create_branch_core_git_error(mock_core_create_branch):
    mock_core_create_branch.side_effect = CoreGitWriteError("A generic git error occurred.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchCreateRequest(branch_name="error-branch")
    response = client.post("/repository/branches", json=payload.model_dump())

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    assert response.json()["detail"] == "Failed to create branch: A generic git error occurred."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.create_and_switch_branch')
def test_api_create_branch_repo_not_found_error(mock_core_create_branch):
    # This core exception is mapped to 500 by the API endpoint
    mock_core_create_branch.side_effect = CoreRepositoryNotFoundError("Simulated repo not found.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchCreateRequest(branch_name="any-branch")
    response = client.post("/repository/branches", json=payload.model_dump())

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    assert response.json()["detail"] == "Repository configuration error."
    app.dependency_overrides = {}


def test_api_create_branch_unauthorized():
    app.dependency_overrides = {}
    async def mock_raise_401_for_create_branch():
        from fastapi import HTTPException
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Auth failed for create branch")

    app.dependency_overrides[actual_repo_auth_dependency] = mock_raise_401_for_create_branch
    payload = BranchCreateRequest(branch_name="unauth-branch")
    response = client.post("/repository/branches", json=payload.model_dump())

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Auth failed for create branch"
    app.dependency_overrides = {}

def test_api_create_branch_invalid_payload():
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    # branch_name is missing
    response = client.post("/repository/branches", json={})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422

    # branch_name is empty string (violates min_length=1 in Pydantic model)
    response = client.post("/repository/branches", json={"branch_name": ""})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422
    app.dependency_overrides = {}


# --- Tests for GET /repository/compare ---

@patch('gitwrite_api.routers.repository.core_get_diff') # core_get_diff is imported alias
def test_api_compare_refs_success_defaults(mock_core_get_diff):
    mock_core_get_diff.return_value = {
        "ref1_oid": "abcdef0", "ref2_oid": "1234567",
        "ref1_display_name": "HEAD~1", "ref2_display_name": "HEAD",
        "patch_text": "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/compare") # No params, uses defaults

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["ref1_oid"] == "abcdef0"
    assert data["ref2_oid"] == "1234567"
    assert data["ref1_display_name"] == "HEAD~1"
    assert data["ref2_display_name"] == "HEAD"
    assert "patch_text" in data
    mock_core_get_diff.assert_called_once_with(repo_path_str=MOCK_REPO_PATH, ref1_str=None, ref2_str=None)
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
def test_api_compare_refs_success_with_params(mock_core_get_diff):
    mock_core_get_diff.return_value = {
        "ref1_oid": "branch1sha", "ref2_oid": "tag2sha",
        "ref1_display_name": "branch1", "ref2_display_name": "v1.0",
        "patch_text": "diff text here"
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/compare?ref1=branch1&ref2=v1.0")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["ref1_display_name"] == "branch1"
    assert data["ref2_display_name"] == "v1.0"
    mock_core_get_diff.assert_called_once_with(repo_path_str=MOCK_REPO_PATH, ref1_str="branch1", ref2_str="v1.0")
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
def test_api_compare_refs_commit_not_found(mock_core_get_diff):
    mock_core_get_diff.side_effect = CoreCommitNotFoundError("Reference 'unknown-ref' not found.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/compare?ref1=unknown-ref")

    assert response.status_code == HTTPStatus.NOT_FOUND # 404
    assert response.json()["detail"] == "Reference 'unknown-ref' not found."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
def test_api_compare_refs_not_enough_history(mock_core_get_diff):
    mock_core_get_diff.side_effect = CoreNotEnoughHistoryError("Not enough history to compare (e.g., initial commit).")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/compare") # Default HEAD~1 vs HEAD on initial commit

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Not enough history to compare (e.g., initial commit)."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
def test_api_compare_refs_value_error_from_core(mock_core_get_diff):
    # core_get_diff raises ValueError for invalid ref combinations (e.g., ref2 without ref1 unless both are None)
    mock_core_get_diff.side_effect = ValueError("Invalid reference combination for diff.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/compare?ref2=some-ref") # ref1 is None, ref2 is not

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Invalid reference combination for diff."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
def test_api_compare_refs_repo_not_found_error(mock_core_get_diff):
    mock_core_get_diff.side_effect = CoreRepositoryNotFoundError("Repository path misconfigured.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/compare")

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    assert response.json()["detail"] == "Repository configuration error."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_get_diff')
def test_api_compare_refs_core_git_write_error(mock_core_get_diff):
    mock_core_get_diff.side_effect = CoreGitWriteError("Some other core diffing error.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.get("/repository/compare")

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    assert response.json()["detail"] == "Compare operation failed: Some other core diffing error."
    app.dependency_overrides = {}

def test_api_compare_refs_unauthorized():
    app.dependency_overrides = {}
    async def mock_raise_401_for_compare():
        from fastapi import HTTPException
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Auth failed for compare")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_raise_401_for_compare

    response = client.get("/repository/compare")

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Auth failed for compare"
    app.dependency_overrides = {}


# --- Tests for POST /repository/merges ---

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_fast_forward(mock_core_merge):
    mock_core_merge.return_value = {
        'status': 'fast_forwarded',
        'branch_name': 'feature-branch',
        'current_branch': 'main',
        'commit_oid': 'ffcommitsha'
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="feature-branch")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "fast_forwarded"
    assert data["message"] == "Branch 'feature-branch' was fast-forwarded into 'main'."
    assert data["merged_branch"] == "feature-branch"
    assert data["current_branch"] == "main"
    assert data["commit_oid"] == "ffcommitsha"
    mock_core_merge.assert_called_once_with(repo_path_str=MOCK_REPO_PATH, branch_to_merge_name="feature-branch")
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_merged_ok(mock_core_merge):
    mock_core_merge.return_value = {
        'status': 'merged_ok',
        'branch_name': 'develop',
        'current_branch': 'main',
        'commit_oid': 'mergecommitsha'
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="develop")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "merged_ok"
    assert data["message"] == "Branch 'develop' was successfully merged into 'main'."
    assert data["commit_oid"] == "mergecommitsha"
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_up_to_date(mock_core_merge):
    mock_core_merge.return_value = {
        'status': 'up_to_date',
        'branch_name': 'main',
        'current_branch': 'main'
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="main") # Merging main into main (example)
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "up_to_date"
    assert data["message"] == "Current branch 'main' is already up-to-date with 'main'."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_conflict(mock_core_merge):
    conflict_details = {
        "message": "Automatic merge failed due to conflicts.",
        "conflicting_files": ["file1.txt", "file2.txt"],
        # Simulating that core exception might provide these, though current impl doesn't directly
        # The API endpoint tries to access these:
        # "current_branch_name": "main",
        # "merged_branch_name": "feature-conflict"
    }
    # The CoreMergeConflictError needs these attributes if the API endpoint is to access them.
    # For testing, we can mock the exception object itself.
    mock_exception = CoreMergeConflictError(
        message=conflict_details["message"],
        conflicting_files=conflict_details["conflicting_files"]
    )
    # Manually add attributes if the constructor doesn't take them or if they are dynamic
    # setattr(mock_exception, 'current_branch_name', "main")
    # setattr(mock_exception, 'merged_branch_name', "feature-conflict")

    mock_core_merge.side_effect = mock_exception
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="feature-conflict")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.CONFLICT # 409
    data = response.json() # FastAPI puts the detail into response.json() for HTTPExceptions

    # The detail payload is constructed by the endpoint:
    # detail_payload = {
    #     "status": "conflict",
    #     "message": str(e.message),
    #     "conflicting_files": e.conflicting_files,
    #     "current_branch": getattr(e, 'current_branch_name', None),
    #     "merged_branch": getattr(e, 'merged_branch_name', request_data.source_branch)
    # }
    # detail_payload = {k: v for k, v in detail_payload.items() if v is not None}
    # raise HTTPException(status_code=409, detail=detail_payload)

    assert data["detail"]["status"] == "conflict"
    assert data["detail"]["message"] == conflict_details["message"] # Core message
    assert data["detail"]["conflicting_files"] == conflict_details["conflicting_files"]
    # Since current_branch_name and merged_branch_name are not on the mock_exception by default:
    assert "current_branch" not in data["detail"] # It was None, so removed
    assert data["detail"]["merged_branch"] == "feature-conflict" # Fell back to request_data.source_branch
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_branch_not_found(mock_core_merge):
    mock_core_merge.side_effect = CoreBranchNotFoundError("Branch 'ghost-branch' not found.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="ghost-branch")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.NOT_FOUND # 404
    assert response.json()["detail"] == "Branch 'ghost-branch' not found."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_repo_empty(mock_core_merge):
    mock_core_merge.side_effect = CoreRepositoryEmptyError("Repository is empty, cannot merge.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="any-branch")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Repository is empty, cannot merge."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_detached_head(mock_core_merge):
    mock_core_merge.side_effect = CoreDetachedHeadError("HEAD is detached, cannot merge.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="any-branch")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "HEAD is detached, cannot merge."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_git_write_error_merge_into_self(mock_core_merge):
    mock_core_merge.side_effect = CoreGitWriteError("Cannot merge a branch into itself.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="main") # Assuming current is main
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Merge operation failed: Cannot merge a branch into itself."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_git_write_error_no_signature(mock_core_merge):
    mock_core_merge.side_effect = CoreGitWriteError("User signature (user.name and user.email) not configured in Git.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="feature-needs-commit")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert "User signature" in response.json()["detail"]
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.merge_branch_into_current')
def test_api_merge_branch_repo_not_found_error(mock_core_merge):
    mock_core_merge.side_effect = CoreRepositoryNotFoundError("Configured repo path is invalid.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = MergeBranchRequest(source_branch="any-branch")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    assert response.json()["detail"] == "Repository configuration error."
    app.dependency_overrides = {}

def test_api_merge_branch_unauthorized():
    app.dependency_overrides = {}
    async def mock_raise_401_for_merge():
        from fastapi import HTTPException
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Auth failed for merge")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_raise_401_for_merge

    payload = MergeBranchRequest(source_branch="some-branch")
    response = client.post("/repository/merges", json=payload.model_dump())

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Auth failed for merge"
    app.dependency_overrides = {}

def test_api_merge_branch_invalid_payload():
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    # source_branch missing
    response = client.post("/repository/merges", json={})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422

    # source_branch empty
    response = client.post("/repository/merges", json={"source_branch": ""})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422
    app.dependency_overrides = {}

# --- Tests for PUT /repository/branch ---

@patch('gitwrite_api.routers.repository.switch_to_branch')
def test_api_switch_branch_success(mock_core_switch_branch):
    mock_core_switch_branch.return_value = {
        'status': 'success',
        'branch_name': 'target-branch',
        'previous_branch_name': 'main',
        'head_commit_oid': 'targetcommitsha',
        'is_detached': False
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchSwitchRequest(branch_name="target-branch")
    response = client.put("/repository/branch", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK # 200
    data = response.json()
    assert data["status"] == "success"
    assert data["branch_name"] == "target-branch"
    assert data["message"] == "Switched to branch 'target-branch' successfully."
    assert data["head_commit_oid"] == "targetcommitsha"
    assert data["previous_branch_name"] == "main"
    assert data["is_detached"] is False
    mock_core_switch_branch.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        branch_name="target-branch"
    )
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.switch_to_branch')
def test_api_switch_branch_already_on_branch(mock_core_switch_branch):
    mock_core_switch_branch.return_value = {
        'status': 'already_on_branch',
        'branch_name': 'current-branch',
        'head_commit_oid': 'currentcommitsha'
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchSwitchRequest(branch_name="current-branch")
    response = client.put("/repository/branch", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK # 200
    data = response.json()
    assert data["status"] == "already_on_branch"
    assert data["branch_name"] == "current-branch"
    assert data["message"] == "Already on branch 'current-branch'."
    assert data["head_commit_oid"] == "currentcommitsha"
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.switch_to_branch')
def test_api_switch_branch_not_found(mock_core_switch_branch):
    mock_core_switch_branch.side_effect = CoreBranchNotFoundError("Branch 'non-existent-branch' not found.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchSwitchRequest(branch_name="non-existent-branch")
    response = client.put("/repository/branch", json=payload.model_dump())

    assert response.status_code == HTTPStatus.NOT_FOUND # 404
    assert response.json()["detail"] == "Branch 'non-existent-branch' not found."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.switch_to_branch')
def test_api_switch_branch_repo_empty(mock_core_switch_branch):
    mock_core_switch_branch.side_effect = CoreRepositoryEmptyError("Cannot switch branch in an empty repository.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchSwitchRequest(branch_name="any-branch")
    response = client.put("/repository/branch", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Cannot switch branch in an empty repository."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.switch_to_branch')
def test_api_switch_branch_uncommitted_changes(mock_core_switch_branch):
    # This specific error message from core should result in a 409
    error_message = "Checkout failed: Your local changes overwrite files."
    mock_core_switch_branch.side_effect = CoreGitWriteError(error_message)
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchSwitchRequest(branch_name="conflicting-branch")
    response = client.put("/repository/branch", json=payload.model_dump())

    assert response.status_code == HTTPStatus.CONFLICT # 409
    assert response.json()["detail"] == f"Switch failed: {error_message}"
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.switch_to_branch')
def test_api_switch_branch_generic_git_error(mock_core_switch_branch):
    # Other CoreGitWriteErrors should result in 400
    error_message = "Some other git operation failure."
    mock_core_switch_branch.side_effect = CoreGitWriteError(error_message)
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchSwitchRequest(branch_name="error-branch")
    response = client.put("/repository/branch", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == f"Failed to switch branch: {error_message}"
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.switch_to_branch')
def test_api_switch_branch_repo_not_found_error(mock_core_switch_branch):
    mock_core_switch_branch.side_effect = CoreRepositoryNotFoundError("Simulated repo not found for switch.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = BranchSwitchRequest(branch_name="any-branch")
    response = client.put("/repository/branch", json=payload.model_dump())

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    assert response.json()["detail"] == "Repository configuration error."
    app.dependency_overrides = {}


def test_api_switch_branch_unauthorized():
    app.dependency_overrides = {}
    async def mock_raise_401_for_switch_branch():
        from fastapi import HTTPException
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Auth failed for switch branch")

    app.dependency_overrides[actual_repo_auth_dependency] = mock_raise_401_for_switch_branch
    payload = BranchSwitchRequest(branch_name="unauth-branch-switch")
    response = client.put("/repository/branch", json=payload.model_dump())

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Auth failed for switch branch"
    app.dependency_overrides = {}

def test_api_switch_branch_invalid_payload():
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    # branch_name is missing
    response = client.put("/repository/branch", json={})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422

    # branch_name is empty string
    response = client.put("/repository/branch", json={"branch_name": ""})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422
    app.dependency_overrides = {}


# --- Tests for POST /repository/revert ---

from gitwrite_api.routers.repository import RevertCommitRequest # For revert tests

@patch('gitwrite_api.routers.repository.core_revert_commit')
def test_api_revert_commit_success(mock_core_revert):
    mock_core_revert.return_value = {
        'status': 'success',
        'message': 'Commit abcdef0 reverted successfully.',
        'new_commit_oid': 'revertsha123'
    }
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = RevertCommitRequest(commit_ish="abcdef0")
    response = client.post("/repository/revert", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "success"
    assert data["message"] == "Commit abcdef0 reverted successfully."
    assert data["new_commit_oid"] == "revertsha123"
    mock_core_revert.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        commit_ish_to_revert="abcdef0"
    )
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_revert_commit')
def test_api_revert_commit_not_found(mock_core_revert):
    mock_core_revert.side_effect = CoreCommitNotFoundError("Commit 'unknownsha' not found.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = RevertCommitRequest(commit_ish="unknownsha")
    response = client.post("/repository/revert", json=payload.model_dump())

    assert response.status_code == HTTPStatus.NOT_FOUND # 404
    assert response.json()["detail"] == "Commit 'unknownsha' not found."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_revert_commit')
def test_api_revert_commit_merge_conflict(mock_core_revert):
    mock_core_revert.side_effect = CoreMergeConflictError(
        message="Revert resulted in conflicts.",
        # conflicting_files=["file.txt"] # CoreMergeConflictError doesn't always have conflicting_files for revert
    )
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = RevertCommitRequest(commit_ish="conflictsha")
    response = client.post("/repository/revert", json=payload.model_dump())

    assert response.status_code == HTTPStatus.CONFLICT # 409
    # The detail message is constructed by the endpoint
    expected_detail = "Revert failed due to conflicts: Revert resulted in conflicts.. The working directory should be clean."
    assert response.json()["detail"] == expected_detail
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_revert_commit')
def test_api_revert_commit_repo_not_found_error(mock_core_revert):
    mock_core_revert.side_effect = CoreRepositoryNotFoundError("Repo config error for revert.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = RevertCommitRequest(commit_ish="anysha")
    response = client.post("/repository/revert", json=payload.model_dump())

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    assert response.json()["detail"] == "Repository configuration error."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_revert_commit')
def test_api_revert_commit_repo_empty_error(mock_core_revert):
    mock_core_revert.side_effect = CoreRepositoryEmptyError("Cannot revert in empty repository.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = RevertCommitRequest(commit_ish="anysha")
    response = client.post("/repository/revert", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Cannot revert in empty repository."
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_revert_commit')
def test_api_revert_initial_commit_error(mock_core_revert):
    # Specific CoreGitWriteError for trying to revert initial commit
    error_message = "Cannot revert commit abcdef0 as it has no parents (initial commit)."
    mock_core_revert.side_effect = CoreGitWriteError(error_message)
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = RevertCommitRequest(commit_ish="abcdef0") # An initial commit SHA
    response = client.post("/repository/revert", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400, due to specific check in endpoint
    assert response.json()["detail"] == error_message # Endpoint returns the core error message directly here
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_revert_commit')
def test_api_revert_generic_git_write_error(mock_core_revert):
    error_message = "Some other generic revert failure."
    mock_core_revert.side_effect = CoreGitWriteError(error_message)
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = RevertCommitRequest(commit_ish="errorsha")
    response = client.post("/repository/revert", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == f"Revert operation failed: {error_message}"
    app.dependency_overrides = {}

def test_api_revert_commit_unauthorized():
    app.dependency_overrides = {}
    async def mock_raise_401_for_revert():
        from fastapi import HTTPException
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Auth failed for revert")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_raise_401_for_revert

    payload = RevertCommitRequest(commit_ish="autherrorsha")
    response = client.post("/repository/revert", json=payload.model_dump())

    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Auth failed for revert"
    app.dependency_overrides = {}

def test_api_revert_commit_invalid_payload():
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    # commit_ish missing
    response = client.post("/repository/revert", json={})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422

    # commit_ish empty
    response = client.post("/repository/revert", json={"commit_ish": ""})
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422
    app.dependency_overrides = {}


# --- Tests for POST /repository/sync ---

from gitwrite_api.routers.repository import SyncRepositoryRequest # For sync tests
from gitwrite_core.exceptions import ( # Import more exceptions for sync
    RemoteNotFoundError as CoreRemoteNotFoundError,
    FetchError as CoreFetchError,
    PushError as CorePushError
)

# Mock data for successful sync response from core
MOCK_CORE_SYNC_SUCCESS_RESULT = {
    "status": "success",
    "branch_synced": "main",
    "remote": "origin",
    "fetch_status": {"received_objects": 10, "total_objects": 10, "message": "Fetch complete."},
    "local_update_status": {"type": "fast_forwarded", "message": "Fast-forwarded.", "commit_oid": "newheadsha", "conflicting_files": []},
    "push_status": {"pushed": True, "message": "Push successful."}
}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_success_default_params(mock_core_sync):
    mock_core_sync.return_value = MOCK_CORE_SYNC_SUCCESS_RESULT
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    # Default request (empty body means Pydantic model will use default values)
    response = client.post("/repository/sync", json={})

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "success"
    assert data["branch_synced"] == "main"
    assert data["remote"] == "origin"
    assert data["fetch_status"]["message"] == "Fetch complete."
    assert data["local_update_status"]["type"] == "fast_forwarded"
    assert data["push_status"]["pushed"] is True

    mock_core_sync.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        remote_name="origin", # Default from SyncRepositoryRequest model
        branch_name_opt=None, # Default
        push=True,            # Default
        allow_no_push=False   # Default
    )
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_success_custom_params(mock_core_sync):
    custom_result = {
        **MOCK_CORE_SYNC_SUCCESS_RESULT,
        "branch_synced": "develop",
        "remote": "upstream",
        "push_status": {"pushed": False, "message": "Push explicitly disabled."}
    }
    mock_core_sync.return_value = custom_result
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

    payload = SyncRepositoryRequest(
        remote_name="upstream",
        branch_name="develop",
        push=False,
        allow_no_push=True # Important for push=False to be "successful" without pushing
    )
    response = client.post("/repository/sync", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "success" # Core function determines this overall status
    assert data["branch_synced"] == "develop"
    assert data["remote"] == "upstream"
    assert data["push_status"]["pushed"] is False
    assert data["push_status"]["message"] == "Push explicitly disabled."

    mock_core_sync.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        remote_name="upstream",
        branch_name_opt="develop",
        push=False,
        allow_no_push=True
    )
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_merge_conflict(mock_core_sync):
    # Scenario: Core sync function raises CoreMergeConflictError
    mock_core_sync.side_effect = CoreMergeConflictError(
        message="Merge resulted in conflicts during sync.",
        conflicting_files=["fileA.txt", "fileB.txt"]
    )
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = SyncRepositoryRequest() # Default params
    response = client.post("/repository/sync", json=payload.model_dump())

    assert response.status_code == HTTPStatus.CONFLICT # 409
    data = response.json()["detail"] # Detail is a dict here
    assert "Sync failed due to merge conflicts" in data["message"]
    assert data["conflicting_files"] == ["fileA.txt", "fileB.txt"]
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_core_returns_conflict_status(mock_core_sync):
    # Scenario: Core sync function *returns* a dict indicating conflicts, doesn't raise
    conflict_result_from_core = {
        "status": "success_conflicts", # Special status from core
        "branch_synced": "main",
        "remote": "origin",
        "fetch_status": {"received_objects": 5, "total_objects": 5, "message": "Fetch complete."},
        "local_update_status": {
            "type": "conflicts_detected",
            "message": "Merge resulted in conflicts. Please resolve them.",
            "conflicting_files": ["fileC.txt"]
        },
        "push_status": {"pushed": False, "message": "Push skipped due to conflicts."}
    }
    mock_core_sync.return_value = conflict_result_from_core
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    payload = SyncRepositoryRequest()
    response = client.post("/repository/sync", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK # 200, but body indicates conflict
    data = response.json()
    assert data["status"] == "success_conflicts"
    assert data["local_update_status"]["type"] == "conflicts_detected"
    assert data["local_update_status"]["conflicting_files"] == ["fileC.txt"]
    assert data["push_status"]["pushed"] is False
    app.dependency_overrides = {}


@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_repo_not_found(mock_core_sync):
    mock_core_sync.side_effect = CoreRepositoryNotFoundError("Sync failed: Repo not found.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest().model_dump())
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500
    assert response.json()["detail"] == "Repository configuration error."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_repo_empty(mock_core_sync):
    mock_core_sync.side_effect = CoreRepositoryEmptyError("Sync failed: Repo is empty.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest().model_dump())
    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Sync failed: Repo is empty."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_detached_head(mock_core_sync):
    mock_core_sync.side_effect = CoreDetachedHeadError("Sync failed: HEAD is detached.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest().model_dump())
    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Sync failed: HEAD is detached."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_remote_not_found(mock_core_sync):
    mock_core_sync.side_effect = CoreRemoteNotFoundError("Sync failed: Remote 'nonexistent' not found.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest(remote_name="nonexistent").model_dump())
    assert response.status_code == HTTPStatus.NOT_FOUND # 404
    assert response.json()["detail"] == "Sync failed: Remote 'nonexistent' not found."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_branch_not_found(mock_core_sync):
    mock_core_sync.side_effect = CoreBranchNotFoundError("Sync failed: Branch 'ghost' not found.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest(branch_name="ghost").model_dump())
    assert response.status_code == HTTPStatus.NOT_FOUND # 404
    assert response.json()["detail"] == "Sync failed: Branch 'ghost' not found."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_fetch_error(mock_core_sync):
    mock_core_sync.side_effect = CoreFetchError("Fetch operation failed due to network issue.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest().model_dump())
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE # 503
    assert response.json()["detail"] == "Fetch operation failed: Fetch operation failed due to network issue."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_push_error_generic(mock_core_sync):
    mock_core_sync.side_effect = CorePushError("Push operation failed: Remote disconnected.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest().model_dump())
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE # 503
    assert response.json()["detail"] == "Push operation failed: Push operation failed: Remote disconnected."
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_push_error_non_fast_forward(mock_core_sync):
    mock_core_sync.side_effect = CorePushError("Push rejected: non-fast-forward update.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest().model_dump())
    assert response.status_code == HTTPStatus.CONFLICT # 409
    assert "Push rejected (non-fast-forward)" in response.json()["detail"]
    app.dependency_overrides = {}

@patch('gitwrite_api.routers.repository.core_sync_repository')
def test_api_sync_repository_git_write_error(mock_core_sync):
    mock_core_sync.side_effect = CoreGitWriteError("A generic GitWrite error during sync.")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    response = client.post("/repository/sync", json=SyncRepositoryRequest().model_dump())
    assert response.status_code == HTTPStatus.BAD_REQUEST # 400
    assert response.json()["detail"] == "Sync operation failed: A generic GitWrite error during sync."
    app.dependency_overrides = {}

def test_api_sync_repository_unauthorized():
    app.dependency_overrides = {}
    async def mock_raise_401_for_sync():
        from fastapi import HTTPException
        raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Auth failed for sync")
    app.dependency_overrides[actual_repo_auth_dependency] = mock_raise_401_for_sync

    response = client.post("/repository/sync", json=SyncRepositoryRequest().model_dump())
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    assert response.json()["detail"] == "Auth failed for sync"
    app.dependency_overrides = {}

def test_api_sync_repository_invalid_payload():
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    # Example: 'push' field with invalid type
    invalid_payload = {"push": "not-a-boolean"}
    response = client.post("/repository/sync", json=invalid_payload)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422
    data = response.json()["detail"]
    assert any(item["type"] == "bool_parsing" and item["loc"] == ["body", "push"] for item in data)
    app.dependency_overrides = {}
