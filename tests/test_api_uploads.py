# tests/test_api_uploads.py

import pytest
from fastapi.testclient import TestClient
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile
from typing import Dict, Any, Optional
import os
import shutil # For cleaning up test uploads

# Import the main app and routers from the application
# Adjust path if your test setup requires it (e.g. if tests are outside the main package)
from gitwrite_api.main import app # Main FastAPI application
from gitwrite_api.routers import uploads # To access upload_sessions for mocking/manipulation
from gitwrite_api.models import User # User model for mocking current_user
from gitwrite_api.security import get_current_user # To override

# Define a mock user for testing
mock_user_one = User(username="testuser1", email="testuser1@example.com", disabled=False) # FastAPI User model expects `disabled`
mock_user_two = User(username="testuser2", email="testuser2@example.com", disabled=False) # FastAPI User model expects `disabled`

# Mock dependency for get_current_user
async def override_get_current_user_one():
    return mock_user_one

async def override_get_current_user_two():
    return mock_user_two

# Apply the override to the app instance for all tests in this module
# We will switch this dynamically in tests if needed, or use specific overrides per test.
app.dependency_overrides[get_current_user] = override_get_current_user_one

client = TestClient(app)

# Define constants used in tests
TEST_REPO_ID = "test_repo"
TEST_COMMIT_MSG = "Test commit message"
TEST_FILE1_PATH = "path/to/file1.txt"
TEST_FILE1_HASH = "hash1"
TEST_FILE1_CONTENT = b"This is file1."
TEST_FILE2_PATH = "path/to/file2.txt"
TEST_FILE2_HASH = "hash2"

# Ensure TEMP_UPLOAD_DIR (from uploads router) exists for tests and is clean
# This should match the TEMP_UPLOAD_DIR in gitwrite_api/routers/uploads.py
TEST_TEMP_UPLOAD_DIR = uploads.TEMP_UPLOAD_DIR

@pytest.fixture(autouse=True)
def clear_upload_state_and_temp_files():
    """ Clears upload_sessions and temporary files before and after each test. """
    uploads.upload_sessions.clear()
    if os.path.exists(TEST_TEMP_UPLOAD_DIR):
        shutil.rmtree(TEST_TEMP_UPLOAD_DIR)
    os.makedirs(TEST_TEMP_UPLOAD_DIR, exist_ok=True)
    yield # Test runs here
    uploads.upload_sessions.clear()
    if os.path.exists(TEST_TEMP_UPLOAD_DIR):
        shutil.rmtree(TEST_TEMP_UPLOAD_DIR)
    # os.makedirs(TEST_TEMP_UPLOAD_DIR, exist_ok=True) # No need to recreate after test, next fixture call will do it.


# --- Tests for POST /repositories/{repo_id}/save/initiate ---

def test_initiate_upload_success():
    response = client.post(
        f"/repositories/{TEST_REPO_ID}/save/initiate",
        json={
            "commit_message": TEST_COMMIT_MSG,
            "files": [{"file_path": TEST_FILE1_PATH, "file_hash": TEST_FILE1_HASH}]
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert "upload_urls" in data
    assert "completion_token" in data
    assert TEST_FILE1_PATH in data["upload_urls"]
    assert data["upload_urls"][TEST_FILE1_PATH].startswith("/upload-session/")

    # Check session state
    assert data["completion_token"] in uploads.upload_sessions
    session = uploads.upload_sessions[data["completion_token"]]
    assert session["repo_id"] == TEST_REPO_ID
    assert session["commit_message"] == TEST_COMMIT_MSG
    assert session["user_id"] == mock_user_one.username
    assert TEST_FILE1_PATH in session["files"]
    assert session["files"][TEST_FILE1_PATH]["expected_hash"] == TEST_FILE1_HASH
    assert not session["files"][TEST_FILE1_PATH]["uploaded"]

def test_initiate_upload_no_files():
    response = client.post(
        f"/repositories/{TEST_REPO_ID}/save/initiate",
        json={"commit_message": TEST_COMMIT_MSG, "files": []}
    )
    assert response.status_code == 400 # Bad Request
    assert "No files provided" in response.json()["detail"]

def test_initiate_upload_unauthenticated():
    original_overrides = app.dependency_overrides.copy()
    app.dependency_overrides.clear() # Remove user override for this test
    response = client.post(
        f"/repositories/{TEST_REPO_ID}/save/initiate",
        json={
            "commit_message": TEST_COMMIT_MSG,
            "files": [{"file_path": TEST_FILE1_PATH, "file_hash": TEST_FILE1_HASH}]
        }
    )
    assert response.status_code == 401 # Unauthorized
    app.dependency_overrides = original_overrides # Restore


# --- Tests for PUT /upload-session/{upload_id} ---

def test_handle_file_upload_success():
    # 1. Initiate upload to get an upload_id
    init_resp = client.post(
        f"/repositories/{TEST_REPO_ID}/save/initiate",
        json={
            "commit_message": TEST_COMMIT_MSG,
            "files": [{"file_path": TEST_FILE1_PATH, "file_hash": TEST_FILE1_HASH}]
        }
    )
    init_data = init_resp.json()
    upload_url = init_data["upload_urls"][TEST_FILE1_PATH] # This is like "/upload-session/upl_xxx"
    completion_token = init_data["completion_token"]

    # 2. Upload the file
    # Create a dummy file to upload
    dummy_file_name = "testfile_for_upload.tmp"
    with open(dummy_file_name, "wb") as f:
        f.write(TEST_FILE1_CONTENT)

    with open(dummy_file_name, "rb") as f_upload:
        upload_response = client.put(
            upload_url, # Use the relative URL obtained
            files={"uploaded_file": (TEST_FILE1_PATH, f_upload, "text/plain")} # FastAPI expects a tuple for files
        )

    os.remove(dummy_file_name)

    assert upload_response.status_code == 200
    upload_data = upload_response.json()
    assert "successfully" in upload_data["message"]
    assert "temporary_path" in upload_data
    temp_file_on_server = upload_data["temporary_path"]
    assert os.path.exists(temp_file_on_server)

    with open(temp_file_on_server, "rb") as f_server:
        assert f_server.read() == TEST_FILE1_CONTENT

    # Check session state
    session = uploads.upload_sessions[completion_token]
    assert session["files"][TEST_FILE1_PATH]["uploaded"]
    assert session["files"][TEST_FILE1_PATH]["temp_path"] == temp_file_on_server

def test_handle_file_upload_invalid_upload_id():
    dummy_file_name = "testfile_for_upload_invalid.tmp"
    with open(dummy_file_name, "wb") as f:
        f.write(b"content")

    with open(dummy_file_name, "rb") as f_upload:
        response = client.put(
            "/upload-session/invalid_id_does_not_exist",
            files={"uploaded_file": ("file.txt", f_upload, "text/plain")}
        )
    os.remove(dummy_file_name)
    assert response.status_code == 404 # Not Found
    assert "Invalid or expired upload_id" in response.json()["detail"]

def test_handle_file_upload_already_uploaded():
    init_resp = client.post(f"/repositories/{TEST_REPO_ID}/save/initiate", json={"commit_message": "msg", "files": [{"file_path": "f.txt", "file_hash": "h"}]})
    upload_url = init_resp.json()["upload_urls"]["f.txt"]

    dummy_file_name = "testfile_for_upload_already.tmp"
    with open(dummy_file_name, "wb") as f:
        f.write(b"c1")

    with open(dummy_file_name, "rb") as f_upload:
        client.put(upload_url, files={"uploaded_file": ("f.txt", f_upload, "text/plain")}) # First upload

    with open(dummy_file_name, "wb") as f: # Prepare for second upload attempt
        f.write(b"c2")
    with open(dummy_file_name, "rb") as f_upload:
        response_again = client.put(upload_url, files={"uploaded_file": ("f.txt", f_upload, "text/plain")}) # Second attempt

    os.remove(dummy_file_name)

    assert response_again.status_code == 400 # Bad Request
    assert "already been uploaded" in response_again.json()["detail"]


# --- Tests for POST /repositories/{repo_id}/save/complete ---

def test_complete_upload_success():
    # 1. Initiate
    init_resp = client.post(f"/repositories/{TEST_REPO_ID}/save/initiate", json={"commit_message": TEST_COMMIT_MSG, "files": [{"file_path": TEST_FILE1_PATH, "file_hash": TEST_FILE1_HASH}]})
    init_data = init_resp.json()
    upload_url = init_data["upload_urls"][TEST_FILE1_PATH]
    completion_token = init_data["completion_token"]

    # 2. Upload file
    dummy_file_name = "testfile_for_complete.tmp"
    with open(dummy_file_name, "wb") as f:
        f.write(TEST_FILE1_CONTENT)
    with open(dummy_file_name, "rb") as f_upload:
        client.put(upload_url, files={"uploaded_file": (TEST_FILE1_PATH, f_upload, "text/plain")})
    os.remove(dummy_file_name)

    # 3. Complete
    complete_response = client.post(
        f"/repositories/{TEST_REPO_ID}/save/complete",
        json={"completion_token": completion_token}
    )
    assert complete_response.status_code == 200
    complete_data = complete_response.json()
    assert "commit_id" in complete_data
    assert "sim_commit_" in complete_data["commit_id"] # As it's simulated for now
    assert completion_token not in uploads.upload_sessions # Session should be cleared

def test_complete_upload_invalid_token():
    response = client.post(f"/repositories/{TEST_REPO_ID}/save/complete", json={"completion_token": "invalid_token"})
    assert response.status_code == 404
    assert "Invalid or expired completion_token" in response.json()["detail"]

def test_complete_upload_not_all_files_uploaded():
    init_resp = client.post(f"/repositories/{TEST_REPO_ID}/save/initiate", json={"commit_message": TEST_COMMIT_MSG, "files": [{"file_path": TEST_FILE1_PATH, "file_hash": "h1"}, {"file_path": TEST_FILE2_PATH, "file_hash": "h2"}]})
    init_data = init_resp.json()
    upload_url1 = init_data["upload_urls"][TEST_FILE1_PATH]
    completion_token = init_data["completion_token"]

    dummy_file_name = "testfile_not_all.tmp"
    with open(dummy_file_name, "wb") as f:
        f.write(b"c1")
    with open(dummy_file_name, "rb") as f_upload:
        client.put(upload_url1, files={"uploaded_file": (TEST_FILE1_PATH, f_upload, "text/plain")}) # Only upload one file
    os.remove(dummy_file_name)

    response = client.post(f"/repositories/{TEST_REPO_ID}/save/complete", json={"completion_token": completion_token})
    assert response.status_code == 400
    assert "Not all files for this session have been successfully uploaded" in response.json()["detail"]

def test_complete_upload_token_for_different_user():
    original_overrides = app.dependency_overrides.copy()
    # User1 initiates
    app.dependency_overrides[get_current_user] = override_get_current_user_one
    init_resp_user1 = client.post(f"/repositories/{TEST_REPO_ID}/save/initiate", json={"commit_message": "msg1", "files": [{"file_path": "f1.txt", "file_hash": "h1"}]})
    completion_token_user1 = init_resp_user1.json()["completion_token"]
    upload_url_user1 = init_resp_user1.json()["upload_urls"]["f1.txt"]

    dummy_file_name = "testfile_diff_user.tmp"
    with open(dummy_file_name, "wb") as f:
        f.write(b"c1")
    with open(dummy_file_name, "rb") as f_upload:
        client.put(upload_url_user1, files={"uploaded_file": ("f1.txt", f_upload, "text/plain")})
    os.remove(dummy_file_name)

    # User2 tries to complete User1's session
    app.dependency_overrides[get_current_user] = override_get_current_user_two
    response_user2 = client.post(f"/repositories/{TEST_REPO_ID}/save/complete", json={"completion_token": completion_token_user1})

    app.dependency_overrides = original_overrides # Restore

    assert response_user2.status_code == 403 # Forbidden
    assert "does not belong to the current user" in response_user2.json()["detail"]

def test_complete_upload_token_for_different_repo():
    init_resp = client.post(f"/repositories/{TEST_REPO_ID}/save/initiate", json={"commit_message": "msg", "files": [{"file_path": "f.txt", "file_hash": "h"}]})
    token = init_resp.json()["completion_token"]
    url = init_resp.json()["upload_urls"]["f.txt"]

    dummy_file_name = "testfile_diff_repo.tmp"
    with open(dummy_file_name, "wb") as f:
        f.write(b"c")
    with open(dummy_file_name, "rb") as f_upload:
        client.put(url, files={"uploaded_file": ("f.txt", f_upload, "text/plain")})
    os.remove(dummy_file_name)

    response = client.post(f"/repositories/DIFFERENT_REPO/save/complete", json={"completion_token": token})
    assert response.status_code == 400 # Bad Request
    assert "token is for a different repository" in response.json()["detail"]

def test_complete_upload_unauthenticated():
    original_overrides = app.dependency_overrides.copy()
    # Need a valid token first, so let's quickly create one (this part would be authenticated)
    app.dependency_overrides[get_current_user] = override_get_current_user_one
    init_resp = client.post(f"/repositories/{TEST_REPO_ID}/save/initiate", json={"commit_message": "msg", "files": [{"file_path": "f.txt", "file_hash": "h"}]})
    token = init_resp.json()["completion_token"]
    url = init_resp.json()["upload_urls"]["f.txt"]

    dummy_file_name = "testfile_unauth.tmp"
    with open(dummy_file_name, "wb") as f:
        f.write(b"c")
    with open(dummy_file_name, "rb") as f_upload:
        client.put(url, files={"uploaded_file": ("f.txt", f_upload, "text/plain")})
    os.remove(dummy_file_name)

    app.dependency_overrides.clear() # Now make complete unauthenticated

    response = client.post(f"/repositories/{TEST_REPO_ID}/save/complete", json={"completion_token": token})
    assert response.status_code == 401 # Unauthorized
    app.dependency_overrides = original_overrides # Restore
