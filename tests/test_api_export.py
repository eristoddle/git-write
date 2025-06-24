import uuid
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from gitwrite_api.main import app
from gitwrite_api.models import User # Corrected import
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, FileNotFoundInCommitError, PandocError # Corrected import

# Fixture for a mock authenticated user
@pytest.fixture
def mock_authenticated_user():
    return User(username="testuser", email="test@example.com", full_name="Test User", disabled=False)

# Fixture for the TestClient
@pytest.fixture
def client():
    return TestClient(app)

# Fixture to override dependency for authenticated user
@pytest.fixture(autouse=True)
def override_get_current_active_user(mock_authenticated_user):
    # Assuming get_current_active_user is sourced from the router module where it's used.
    # This path might need adjustment if get_current_active_user is globally defined elsewhere in gitwrite_api
    from gitwrite_api.routers.repository import get_current_active_user as gau_repository
    app.dependency_overrides[gau_repository] = lambda: mock_authenticated_user

    # If other routers also use it, they might need overriding too, or a more central override.
    # For now, this targets the repository router as it's most relevant for these tests.

# Global reference for re-applying mock user after unauth test
mock_authenticated_user_global_ref = User(username="testuser", email="test@example.com", full_name="Test User", disabled=False)

@pytest.fixture(autouse=True)
def setup_global_mock_user_ref(mock_authenticated_user):
    global mock_authenticated_user_global_ref
    mock_authenticated_user_global_ref = mock_authenticated_user


def test_export_epub_success(client, mock_authenticated_user):
    # Removed mock_path for gitwrite_api.routers.repository.Path
    with patch("gitwrite_core.export.export_to_epub") as mock_export, \
         patch("gitwrite_api.routers.repository.uuid") as mock_uuid_module:

        mock_uuid_module.uuid4.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")

        # The core export_to_epub is mocked to return the string path of the successfully created epub.
        # This path is constructed based on the mocked uuid.
        expected_filename = "custom_export.epub"
        expected_job_id = "12345678-1234-5678-1234-567812345678"
        # PLACEHOLDER_REPO_PATH is "/tmp/gitwrite_repos_api"
        expected_core_output_path_str = f"/tmp/gitwrite_repos_api/exports/{expected_job_id}/{expected_filename}"
        mock_export.return_value = {"status": "success", "message": "Export successful", "output_epub_path_str": expected_core_output_path_str}


        response = client.post(
            "/repository/export/epub",
            json={
                "repo_path": "test_repo", # This is not used by the API endpoint directly, but passed to core
                "file_list": ["file1.md", "file2.md"],
                "output_filename": "custom_export.epub", # This determines the download filename
                "commit_ish": "test_commit_id" # API uses commit_ish, core uses commit_id
            }
        )
        print(response.json()) # Print the response detail for debugging
        assert response.status_code == 200
        # API now returns JSON, not a FileResponse/StreamingResponse
        # assert f"attachment; filename*=utf-8''custom_export.epub" in response.headers["content-disposition"]
        # assert response.headers["content-type"] == "application/epub+zip"

        # Check that the core function was called with the correct temporary path string
        # The router constructs job_export_dir / actual_output_filename.
        # The `actual_output_filename` is `request_data.output_filename` which is "custom_export.epub".
        # The `job_export_dir` is `export_base_dir / job_id`.
        # `export_base_dir` is `Path(PLACEHOLDER_REPO_PATH) / "exports"`.
        # `job_id` is `str(uuid.uuid4())`.
        # So, the path passed to core is complex.
        # The `output_epub_server_path` in the router is `job_export_dir / actual_output_filename`
        # `job_export_dir` is `Path(PLACEHOLDER_REPO_PATH) / "exports" / str(mock_uuid_module.uuid4())`
        # `actual_output_filename` is "custom_export.epub"

        # The API endpoint now returns a JSON response, not a FileResponse directly
        # The core function `export_to_epub` is called with `str(output_epub_server_path.resolve())`
        # The mock_export should be checked against this.
        # The `output_epub_server_path` is `job_export_dir / request_data.output_filename`
        # `job_export_dir` is `export_base_dir / job_id`
        # `job_id` is `mock_uuid_module.uuid4()` which is "12345678-1234-5678-1234-567812345678"
        # `request_data.output_filename` is "custom_export.epub"
        # `export_base_dir` is `Path(PLACEHOLDER_REPO_PATH) / "exports"`
        # `PLACEHOLDER_REPO_PATH` is "/tmp/gitwrite_repos_api"

        expected_core_output_path = Path(f"/tmp/gitwrite_repos_api/exports/12345678-1234-5678-1234-567812345678/custom_export.epub")

        mock_export.assert_called_once_with(
            repo_path_str="/tmp/gitwrite_repos_api", # PLACEHOLDER_REPO_PATH
            commit_ish_str="test_commit_id",
            file_list=["file1.md", "file2.md"],
            output_epub_path_str=str(expected_core_output_path.resolve())
        )
        # The response from API is now JSON
        assert response.json()["status"] == "success"
        assert response.json()["server_file_path"] == str(expected_core_output_path.resolve())


def test_export_epub_success_default_filename(client, mock_authenticated_user):
    # Removed mock_path_module for gitwrite_api.routers.repository.Path
    with patch("gitwrite_core.export.export_to_epub") as mock_export, \
         patch("gitwrite_api.routers.repository.uuid") as mock_uuid_module:

        mock_uuid_module.uuid4.return_value = uuid.UUID("abcdef12-abcd-ef12-abcd-ef12abcdef12")

        # Pydantic model now defaults output_filename to "export.epub"
        # API will use this default.
        default_filename = "export.epub"
        expected_job_id = "abcdef12-abcd-ef12-abcd-ef12abcdef12"
        # Construct path and resolve it to get the canonical path for assertion
        expected_core_output_path = Path(f"/tmp/gitwrite_repos_api/exports/{expected_job_id}/{default_filename}")
        expected_core_output_path_str = str(expected_core_output_path.resolve())

        # The mock should return what the core function would return. The API only uses status/message from this return.
        mock_export.return_value = {"status": "success", "message": "Export successful"}

        response = client.post(
            "/repository/export/epub",
            json={
                "repo_path": "test_repo", # Not directly used by API, passed to core
                "file_list": ["file1.md"],
                # output_filename is omitted, should use Pydantic default "export.epub"
                "commit_ish": "test_commit_id"
            }
        )
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        # The API returns a resolved path string. Compare against the resolved expected path.
        assert response.json()["server_file_path"] == str(Path(f"/tmp/gitwrite_repos_api/exports/{expected_job_id}/{default_filename}").resolve())
        assert response.json()["message"] == "Export successful" # Check message from core

        # The core function is called with the resolved path string.
        mock_export.assert_called_once_with(
            repo_path_str="/tmp/gitwrite_repos_api",
            commit_ish_str="test_commit_id",
            file_list=["file1.md"],
            output_epub_path_str=str(Path(f"/tmp/gitwrite_repos_api/exports/{expected_job_id}/{default_filename}").resolve())
        )


def test_export_epub_repository_not_found(client, mock_authenticated_user):
    with patch("gitwrite_core.export.export_to_epub", side_effect=RepositoryNotFoundError("Repo not found")) as mock_export, \
         patch("gitwrite_api.routers.repository.uuid"): # Path mock not needed if core function raises early

        response = client.post(
            "/repository/export/epub",
            json={
                "repo_path": "non_existent_repo",
                "file_list": ["file1.md"],
                "output_filename": "export.epub",
                "commit_ish": "test_commit_id"
            }
        )
        assert response.status_code == 500
        assert response.json() == {"detail": "Repository not found or configuration error: Repo not found"}
        mock_export.assert_called_once()

def test_export_epub_commit_not_found(client, mock_authenticated_user):
    with patch("gitwrite_core.export.export_to_epub", side_effect=CommitNotFoundError("Commit not found")) as mock_export, \
         patch("gitwrite_api.routers.repository.uuid"):

        response = client.post(
            "/repository/export/epub",
            json={
                "repo_path": "test_repo",
                "file_list": ["file1.md"],
                "output_filename": "export.epub",
                "commit_ish": "invalid_commit"
            }
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "Commit not found: Commit not found"}
        mock_export.assert_called_once()

def test_export_epub_file_not_found_in_commit(client, mock_authenticated_user):
    with patch("gitwrite_core.export.export_to_epub", side_effect=FileNotFoundInCommitError("File not found")) as mock_export, \
         patch("gitwrite_api.routers.repository.uuid"):

        response = client.post(
            "/repository/export/epub",
            json={
                "repo_path": "test_repo",
                "file_list": ["non_existent_file.md"],
                "output_filename": "export.epub",
                "commit_ish": "test_commit_id"
            }
        )
        assert response.status_code == 404
        assert response.json() == {"detail": "File not found in commit: File not found"}
        mock_export.assert_called_once()

def test_export_epub_pandoc_not_found_error(client, mock_authenticated_user):
    with patch("gitwrite_core.export.export_to_epub", side_effect=PandocError("Pandoc not found. Please ensure pandoc is installed and in your PATH.")) as mock_export, \
         patch("gitwrite_api.routers.repository.uuid"):

        response = client.post(
            "/repository/export/epub",
            json={
                "repo_path": "test_repo",
                "file_list": ["file1.md"],
                "output_filename": "export.epub",
                "commit_ish": "test_commit_id"
            }
        )
        assert response.status_code == 503
        assert response.json() == {"detail": "EPUB generation service unavailable: Pandoc not found. Pandoc not found. Please ensure pandoc is installed and in your PATH."}
        mock_export.assert_called_once()

def test_export_epub_pandoc_conversion_error(client, mock_authenticated_user):
    with patch("gitwrite_core.export.export_to_epub", side_effect=PandocError("Conversion failed")) as mock_export, \
         patch("gitwrite_api.routers.repository.uuid"):
        response = client.post(
            "/repository/export/epub",
            json={
                "repo_path": "test_repo",
                "file_list": ["file1.md"],
                "output_filename": "export.epub",
                "commit_ish": "test_commit_id"
            }
        )
        assert response.status_code == 400
        assert response.json() == {"detail": "EPUB conversion failed: Conversion failed"}
        mock_export.assert_called_once()


def test_export_epub_invalid_payload_missing_file_list(client, mock_authenticated_user):
    response = client.post(
        "/repository/export/epub",
        json={
            "repo_path": "test_repo",
            # "file_list": ["file1.md"], # Missing
            "output_filename": "export.epub", # Now optional with default
            "commit_ish": "test_commit_id"
        }
    )
    assert response.status_code == 422
    assert "file_list" in response.text
    assert "Field required" in response.text


def test_export_epub_invalid_payload_empty_file_list(client, mock_authenticated_user):
    response = client.post(
        "/repository/export/epub",
        json={
            "repo_path": "test_repo",
            "file_list": [], # Empty list
            "output_filename": "export.epub",
            "commit_ish": "test_commit_id"
        }
    )
    assert response.status_code == 422
    assert "file_list" in response.text
    assert "List should have at least 1 item after validation" in response.text


def test_export_epub_invalid_payload_invalid_output_filename(client, mock_authenticated_user):
    response = client.post(
        "/repository/export/epub",
        json={
            "repo_path": "test_repo",
            "file_list": ["file1.md"],
            "output_filename": "export.txt", # Invalid extension
            "commit_ish": "test_commit_id"
        }
    )
    assert response.status_code == 422
    assert "output_filename" in response.text
    assert "String should match pattern" in response.text


def test_export_epub_unauthenticated(client):
    from gitwrite_api.routers.repository import get_current_active_user as gau_repository
    from fastapi import HTTPException

    # Override get_current_active_user to raise 401
    app.dependency_overrides[gau_repository] = lambda: (_ for _ in ()).throw(HTTPException(status_code=401, detail="Not authenticated"))

    response = client.post(
        "/repository/export/epub",
        json={
            "repo_path": "test_repo",
            "file_list": ["file1.md"],
            "output_filename": "export.epub",
            "commit_ish": "test_commit_id"
        }
    )
    assert response.status_code == 401
    assert response.json() == {"detail": "Not authenticated"}

    # Restore overrides for other tests
    global mock_authenticated_user_global_ref # Ensure we are using the global reference
    app.dependency_overrides[gau_repository] = lambda: mock_authenticated_user_global_ref

# Helper to ensure /tmp/gitwrite_repos_api/exports exists for tests if it doesn't
# This is where the API endpoint tries to create export job directories.
@pytest.fixture(scope="session", autouse=True)
def ensure_tmp_exports_directory():
    # PLACEHOLDER_REPO_PATH is "/tmp/gitwrite_repos_api"
    # export_base_dir is Path(PLACEHOLDER_REPO_PATH) / "exports"
    tmp_exports_path = Path("/tmp/gitwrite_repos_api/exports")
    if not tmp_exports_path.exists():
        tmp_exports_path.mkdir(parents=True, exist_ok=True)
