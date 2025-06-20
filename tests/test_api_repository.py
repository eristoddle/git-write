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
