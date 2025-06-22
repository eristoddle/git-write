import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from typing import List, Dict, Optional, Any
from http import HTTPStatus
from fastapi import HTTPException # Added import

from gitwrite_api.main import app  # Assuming your FastAPI app instance is named 'app'
from gitwrite_api.models import BranchReviewCommit, CherryPickRequest
from gitwrite_api.routers.repository import get_current_active_user as actual_repo_auth_dependency
from gitwrite_core.exceptions import (
    RepositoryNotFoundError,
    BranchNotFoundError,
    CommitNotFoundError,
    MergeConflictError,
    GitWriteError
)

# Mock user for dependency override
MOCK_USER = {"username": "testuser", "email": "test@example.com", "active": True}
MOCK_REPO_PATH = "/tmp/gitwrite_repos_api" # Align with router's PLACEHOLDER_REPO_PATH

def mock_get_current_active_user():
    return MOCK_USER

@pytest.fixture(autouse=True)
def override_auth_dependency():
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user
    yield
    app.dependency_overrides = {}

client = TestClient(app)

# --- Tests for GET /repository/review/{branch_name} ---

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_commits_success(mock_core_review):
    branch_name = "feature-branch"
    mock_commits_data = [
        {"short_hash": "123abcd", "author_name": "Test Author", "date": "2023-01-01 10:00:00 +0000", "message_short": "Feat: new thing", "oid": "123abcdef123"},
        {"short_hash": "456defg", "author_name": "Test Author", "date": "2023-01-02 11:00:00 +0000", "message_short": "Fix: old thing", "oid": "456defghi456"},
    ]
    mock_core_review.return_value = mock_commits_data

    response = client.get(f"/repository/review/{branch_name}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "success"
    assert data["branch_name"] == branch_name
    assert len(data["commits"]) == 2
    assert data["commits"][0]["short_hash"] == "123abcd"
    assert data["message"] == f"Found 2 reviewable commits on branch '{branch_name}'."
    mock_core_review.assert_called_once_with(repo_path_str=MOCK_REPO_PATH, branch_name_to_review=branch_name, limit=None)

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_commits_with_limit(mock_core_review):
    branch_name = "feature-branch"
    limit = 1
    mock_commits_data = [
        {"short_hash": "123abcd", "author_name": "Test Author", "date": "2023-01-01 10:00:00 +0000", "message_short": "Feat: new thing", "oid": "123abcdef123"},
    ]
    # Core function will be called with limit, so it should return limited data
    mock_core_review.return_value = mock_commits_data

    response = client.get(f"/repository/review/{branch_name}?limit={limit}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert len(data["commits"]) == limit
    mock_core_review.assert_called_once_with(repo_path_str=MOCK_REPO_PATH, branch_name_to_review=branch_name, limit=limit)

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_commits_no_unique_commits(mock_core_review):
    branch_name = "main"
    mock_core_review.return_value = [] # No unique commits

    response = client.get(f"/repository/review/{branch_name}")

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "success"
    assert data["branch_name"] == branch_name
    assert len(data["commits"]) == 0
    assert data["message"] == f"No unique reviewable commits found on branch '{branch_name}' compared to HEAD."

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_not_found(mock_core_review):
    branch_name = "non-existent-branch"
    mock_core_review.side_effect = BranchNotFoundError(f"Branch '{branch_name}' not found.")

    response = client.get(f"/repository/review/{branch_name}")

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert branch_name in response.json()["detail"]

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_repo_not_found(mock_core_review):
    branch_name = "any-branch"
    mock_core_review.side_effect = RepositoryNotFoundError("Repository not found.")

    response = client.get(f"/repository/review/{branch_name}")

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR # 500 for repo config issues
    assert "Repository configuration error" in response.json()["detail"]

@patch('gitwrite_api.routers.repository.core_get_branch_review_commits')
def test_api_review_branch_unborn_head(mock_core_review):
    branch_name = "any-branch"
    mock_core_review.side_effect = GitWriteError("Cannot review branches when HEAD is unborn.")

    response = client.get(f"/repository/review/{branch_name}")

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400 for unborn HEAD
    assert "HEAD is unborn" in response.json()["detail"]

# --- Tests for POST /repository/cherry-pick ---

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_success(mock_core_cherry_pick):
    commit_id_to_pick = "abcdef123456"
    new_commit_oid = "fedcba654321"
    mock_core_cherry_pick.return_value = {
        "status": "success",
        "new_commit_oid": new_commit_oid,
        "message": f"Commit '{commit_id_to_pick[:7]}' cherry-picked successfully as '{new_commit_oid[:7]}'."
    }
    payload = CherryPickRequest(commit_id=commit_id_to_pick)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "success"
    assert data["new_commit_oid"] == new_commit_oid
    assert commit_id_to_pick[:7] in data["message"]
    mock_core_cherry_pick.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        commit_oid_to_pick=commit_id_to_pick,
        mainline=None
    )

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_merge_commit_with_mainline_success(mock_core_cherry_pick):
    commit_id_to_pick = "mergecommit123"
    new_commit_oid = "newoid456"
    mainline_param = 1
    mock_core_cherry_pick.return_value = {
        "status": "success",
        "new_commit_oid": new_commit_oid,
        "message": "Cherry-picked successfully."
    }
    payload = CherryPickRequest(commit_id=commit_id_to_pick, mainline=mainline_param)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "success"
    assert data["new_commit_oid"] == new_commit_oid
    mock_core_cherry_pick.assert_called_once_with(
        repo_path_str=MOCK_REPO_PATH,
        commit_oid_to_pick=commit_id_to_pick,
        mainline=mainline_param
    )

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_conflict(mock_core_cherry_pick):
    commit_id_to_pick = "conflictcommit789"
    conflicting_files_list = ["file1.txt", "file2.txt"]
    mock_core_cherry_pick.side_effect = MergeConflictError(
        message="Cherry-pick resulted in conflicts.",
        conflicting_files=conflicting_files_list
    )
    payload = CherryPickRequest(commit_id=commit_id_to_pick)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.OK # As per current implementation, 200 with status="conflict"
    data = response.json()
    assert data["status"] == "conflict"
    assert "Cherry-pick resulted in conflicts" in data["message"]
    assert data["new_commit_oid"] is None
    assert data["conflicting_files"] == conflicting_files_list
    # If changed to raise HTTPException(409) for conflicts:
    # assert response.status_code == HTTPStatus.CONFLICT
    # data = response.json()["detail"] # Detail would contain message and files
    # assert "Cherry-pick resulted in conflicts" in data["message"]
    # assert data["conflicting_files"] == conflicting_files_list

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_commit_not_found(mock_core_cherry_pick):
    commit_id_to_pick = "nonexistentcommit"
    mock_core_cherry_pick.side_effect = CommitNotFoundError(f"Commit '{commit_id_to_pick}' not found.")
    payload = CherryPickRequest(commit_id=commit_id_to_pick)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.NOT_FOUND
    assert commit_id_to_pick in response.json()["detail"]

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_merge_commit_without_mainline(mock_core_cherry_pick):
    commit_id_to_pick = "mergecommitrequiringmainline"
    error_message = f"Commit {commit_id_to_pick} is a merge commit. Please specify the 'mainline' parameter."
    mock_core_cherry_pick.side_effect = GitWriteError(error_message)
    payload = CherryPickRequest(commit_id=commit_id_to_pick)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # 400 for this GitWriteError
    assert error_message in response.json()["detail"]

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_invalid_mainline(mock_core_cherry_pick):
    commit_id_to_pick = "mergecommit"
    mainline_param = 99 # Invalid
    error_message = f"Invalid mainline number {mainline_param} for merge commit."
    mock_core_cherry_pick.side_effect = GitWriteError(error_message)
    payload = CherryPickRequest(commit_id=commit_id_to_pick, mainline=mainline_param)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert error_message in response.json()["detail"]

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_on_unborn_head(mock_core_cherry_pick):
    commit_id_to_pick = "anycommit"
    error_message = "Cannot cherry-pick onto an unborn HEAD."
    mock_core_cherry_pick.side_effect = GitWriteError(error_message)
    payload = CherryPickRequest(commit_id=commit_id_to_pick)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST
    assert error_message in response.json()["detail"]

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_repo_not_found(mock_core_cherry_pick):
    commit_id_to_pick = "anycommit"
    mock_core_cherry_pick.side_effect = RepositoryNotFoundError("Repo config error.")
    payload = CherryPickRequest(commit_id=commit_id_to_pick)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Repository configuration error" in response.json()["detail"]

@patch('gitwrite_api.routers.repository.core_cherry_pick_commit')
def test_api_cherry_pick_generic_git_write_error(mock_core_cherry_pick):
    commit_id_to_pick = "anycommit"
    error_message = "A generic Git error occurred during cherry-pick."
    # This tests a GitWriteError that doesn't match specific patterns like "unborn HEAD" or "mainline"
    mock_core_cherry_pick.side_effect = GitWriteError(error_message)
    payload = CherryPickRequest(commit_id=commit_id_to_pick)

    response = client.post("/repository/cherry-pick", json=payload.model_dump())

    assert response.status_code == HTTPStatus.BAD_REQUEST # Default for other GitWriteErrors
    assert f"Cherry-pick operation failed: {error_message}" in response.json()["detail"]

def mock_fail_auth():
    raise HTTPException(status_code=HTTPStatus.UNAUTHORIZED, detail="Not authenticated")

def test_api_cherry_pick_unauthorized():
    # Temporarily override with a mock that fails auth
    app.dependency_overrides[actual_repo_auth_dependency] = mock_fail_auth
    payload = CherryPickRequest(commit_id="anycommit")
    response = client.post("/repository/cherry-pick", json=payload.model_dump())
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    # The global fixture `override_auth_dependency` will reset app.dependency_overrides after the test.
    # So, no need to manually restore here if the fixture is active for all tests.
    # However, to be safe and explicit, especially if this test were run standalone or fixture scope changes:
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

# mock_fail_auth is already defined above test_api_cherry_pick_unauthorized

def test_api_review_branch_unauthorized():
    # Temporarily override with a mock that fails auth
    app.dependency_overrides[actual_repo_auth_dependency] = mock_fail_auth
    response = client.get("/repository/review/anybranch")
    assert response.status_code == HTTPStatus.UNAUTHORIZED
    # Restore for other tests that rely on the global fixture override (handled by fixture teardown if this was a fixture)
    # For this direct manipulation, ensure it's reset if other tests follow in the same session without re-running fixtures.
    # However, the global fixture `override_auth_dependency` should handle resetting for subsequent tests.
    app.dependency_overrides[actual_repo_auth_dependency] = mock_get_current_active_user

# Test for invalid payload (e.g., missing commit_id for cherry-pick)
def test_api_cherry_pick_invalid_payload():
    response = client.post("/repository/cherry-pick", json={}) # Missing commit_id
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY # 422 for Pydantic validation errors
    # Check for detail about missing field
    details = response.json().get("detail", [])
    assert any("commit_id" in error.get("loc", []) and "Field required" in error.get("msg","") for error in details)

# Test for invalid mainline type (e.g., string instead of int)
def test_api_cherry_pick_invalid_mainline_type():
    payload = {"commit_id": "somecommit", "mainline": "not-an-int"}
    response = client.post("/repository/cherry-pick", json=payload)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    details = response.json().get("detail", [])
    assert any("mainline" in error.get("loc", []) and "Input should be a valid integer" in error.get("msg","") for error in details)

# Test for negative or zero mainline value (gt=0 constraint)
@pytest.mark.parametrize("invalid_mainline", [0, -1])
def test_api_cherry_pick_invalid_mainline_value(invalid_mainline):
    payload = {"commit_id": "somecommit", "mainline": invalid_mainline}
    response = client.post("/repository/cherry-pick", json=payload)
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    details = response.json().get("detail", [])
    assert any("mainline" in error.get("loc", []) and "Input should be greater than 0" in error.get("msg","") for error in details)

# Test for invalid limit type for review endpoint
def test_api_review_invalid_limit_type():
    response = client.get("/repository/review/somebranch?limit=not-an-int")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    details = response.json().get("detail", [])
    assert any("limit" in error.get("loc", []) and "Input should be a valid integer" in error.get("msg","") for error in details)

# Test for negative or zero limit value (gt=0 constraint)
@pytest.mark.parametrize("invalid_limit", [0, -1])
def test_api_review_invalid_limit_value(invalid_limit):
    response = client.get(f"/repository/review/somebranch?limit={invalid_limit}")
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    details = response.json().get("detail", [])
    assert any("limit" in error.get("loc", []) and "Input should be greater than 0" in error.get("msg","") for error in details)
