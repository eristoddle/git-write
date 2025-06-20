from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, Request
from typing import List, Dict, Any
from pathlib import Path
import shutil
import os
import uuid # For generating unique tokens and IDs

# Import models from the parent directory's models.py
from ..models import (
    FileMetadata,
    FileUploadInitiateRequest,
    FileUploadInitiateResponse,
    FileUploadCompleteRequest,
    FileUploadCompleteResponse,
    User  # Assuming User model is needed for auth
)

# Import security dependency (adjust path if necessary)
from ..security import get_current_user # Placeholder for actual current user dependency

# Placeholder for actual repository path logic
# TODO: Replace with dynamic path based on user/request
PLACEHOLDER_REPO_PATH_PREFIX = "/tmp/gitwrite_repos"
# Define a temporary directory for uploads
TEMP_UPLOAD_DIR = "/tmp/gitwrite_uploads"

# Ensure temporary directories exist
os.makedirs(PLACEHOLDER_REPO_PATH_PREFIX, exist_ok=True)
os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)


router = APIRouter(
    prefix="/repositories/{repo_id}/save", # Common prefix for save operations
    tags=["file_uploads"],
    responses={
        404: {"description": "Not found"},
        401: {"description": "Unauthorized"},
        400: {"description": "Bad Request"}
    },
    # dependencies=[Depends(get_current_user)] # Apply auth to all routes in this router
)

# Define this new router before or after the existing 'router' for prefixed routes
session_upload_router = APIRouter(
    tags=["file_uploads_session"], # Separate tag for clarity
    responses={
        404: {"description": "Upload session or file not found"},
        400: {"description": "Bad Request / Upload failed"},
        500: {"description": "Internal server error during file save"}
    }
)

# In-memory store for upload session metadata (for simplicity in this task)
# In a production system, use Redis or a database for this.
# Structure:
# {
#   "completion_token_xyz": {
#     "repo_id": "user_repo_1",
#     "commit_message": "My commit",
#     "files": {
#       "path/to/file1.txt": {"expected_hash": "sha256_hash_1", "upload_id": "upload_id_1", "uploaded": False, "temp_path": None},
#       "path/to/file2.txt": {"expected_hash": "sha256_hash_2", "upload_id": "upload_id_2", "uploaded": False, "temp_path": None}
#     },
#     "upload_urls_generated": True # or some other way to track state
#   }
# }
upload_sessions: Dict[str, Any] = {}

# We will add the endpoint implementations in subsequent tasks.
# This task is just to create the router file and basic setup.

@router.get("/test_upload_router") # A temporary test endpoint
async def test_router_setup(repo_id: str, current_user: User = Depends(get_current_user)):
    return {"message": f"Upload router for repo {repo_id} is active.", "user": current_user.username}


@router.post("/initiate", response_model=FileUploadInitiateResponse)
async def initiate_file_upload(
    repo_id: str,
    initiate_request: FileUploadInitiateRequest,
    request: Request, # To construct absolute URLs
    current_user: User = Depends(get_current_user) # Apply auth here
):
    """
    Initiates a file upload sequence for a repository save operation.

    - **repo_id**: The identifier of the repository.
    - **initiate_request**: Contains the commit message and list of files to upload.
    - Returns a list of upload URLs and a completion token.
    """
    completion_token = f"compl_{uuid.uuid4().hex}"
    session_files_metadata = {}
    upload_urls = {}

    if not initiate_request.files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided for upload."
        )

    for file_meta in initiate_request.files:
        upload_id = f"upl_{uuid.uuid4().hex}"
        # Construct the upload URL relative to the /upload-session/ endpoint
        # The full URL will depend on how the main app is configured and where it's hosted.
        # Using request.url_for to build path, assuming an endpoint named 'handle_file_upload' exists for PUT /upload-session/{upload_id}
        # We will define an endpoint with name "handle_file_upload" in the next step.
        # For now, we construct it manually, but url_for is preferred once the named endpoint exists.

        # Manual construction (simpler for now as 'handle_file_upload' isn't defined yet in this subtask)
        # The /upload-session/{upload_id} endpoint is not part of the current router's prefix.
        # It will be a separate endpoint, likely at the root of the API or a different router.
        # For now, let's assume it will be /api/v1/upload-session/{upload_id} or similar.
        # To keep it simple for this step, we'll return a relative path that the client can use.
        # A better approach is to use request.url_for with the name of the PUT endpoint route.

        # For the purpose of this task, we create a path that would be typically handled by a different router or a global one.
        # Let's assume there will be a top-level router for "/upload-session/{upload_id}"
        upload_url = f"/upload-session/{upload_id}" # This is a relative URL. Client needs to prepend base URL.
        # Alternatively, to make it absolute:
        # upload_url = str(request.url_for('handle_file_upload_endpoint_name', upload_id=upload_id))
        # This requires the target endpoint to be defined with a name.

        upload_urls[file_meta.file_path] = upload_url
        session_files_metadata[file_meta.file_path] = {
            "expected_hash": file_meta.file_hash,
            "upload_id": upload_id,
            "uploaded": False,
            "temp_path": None, # Will be set when the file is uploaded
        }

    upload_sessions[completion_token] = {
        "repo_id": repo_id,
        "user_id": current_user.username, # Associate with user
        "commit_message": initiate_request.commit_message,
        "files": session_files_metadata,
        "upload_urls_generated": True
    }

    return FileUploadInitiateResponse(
        upload_urls=upload_urls,
        completion_token=completion_token
    )


@session_upload_router.put("/upload-session/{upload_id}")
async def handle_file_upload(
    upload_id: str,
    uploaded_file: UploadFile = File(...)
    # No direct user dependency here, auth is via the obscurity of upload_id
    # and its association with an authenticated session creation.
):
    """
    Handles the actual file upload for a given upload_id.
    - **upload_id**: The unique ID for this specific file upload, obtained from the initiate step.
    - **uploaded_file**: The file being uploaded.
    Streams the file to a temporary location.
    """
    found_file_session = None
    target_file_path_in_session = None

    # Find the upload_id in the existing sessions
    for token, session_data in upload_sessions.items():
        for file_path, file_details in session_data.get("files", {}).items():
            if file_details.get("upload_id") == upload_id:
                if file_details.get("uploaded"):
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"File for upload_id {upload_id} has already been uploaded."
                    )
                found_file_session = session_data["files"][file_path]
                target_file_path_in_session = file_path
                break
        if found_file_session:
            break

    if not found_file_session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invalid or expired upload_id: {upload_id}. Session not found."
        )

    # Ensure TEMP_UPLOAD_DIR exists (it should from module load, but double check)
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)

    # Create a unique temporary file name based on upload_id to prevent collisions
    # Use only the filename part of uploaded_file.filename to avoid creating unwanted subdirectories
    # Path is imported at the module level now
    file_basename = Path(uploaded_file.filename).name
    temp_file_name = f"{upload_id}_{file_basename}"
    temp_file_path_obj = Path(TEMP_UPLOAD_DIR) / temp_file_name # Use Path object for operations

    try:
        with open(temp_file_path_obj, "wb") as buffer:
            shutil.copyfileobj(uploaded_file.file, buffer)

        # Resolve the path and get its size after successful save
        saved_temp_file_abs_path = temp_file_path_obj.resolve()
        uploaded_size = saved_temp_file_abs_path.stat().st_size

    except Exception as e:
        # Clean up partial file if error occurs
        if temp_file_path_obj.exists(): # Use Path object here
            os.remove(temp_file_path_obj)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Could not save uploaded file: {str(e)}"
        )
    finally:
        uploaded_file.file.close()

    # Update session metadata
    found_file_session["uploaded"] = True
    found_file_session["temp_path"] = str(saved_temp_file_abs_path) # Store as absolute string path
    found_file_session["uploaded_size"] = uploaded_size
    # Optional: Verify hash here if needed.
    # actual_hash = hashlib.sha256()
    # with open(temp_file_path, "rb") as f:
    #     for chunk in iter(lambda: f.read(4096), b""):
    #         actual_hash.update(chunk)
    # if actual_hash.hexdigest() != found_file_session["expected_hash"]:
    #     os.remove(temp_file_path) # Clean up
    #     found_file_session["uploaded"] = False # Reset status
    #     found_file_session["temp_path"] = None
    #     raise HTTPException(status_code=400, detail="File integrity check failed: Hash mismatch.")

    return {
        "message": f"File '{uploaded_file.filename}' for upload_id '{upload_id}' uploaded successfully.",
        "temporary_path": temp_file_path
    }


@router.post("/complete", response_model=FileUploadCompleteResponse)
async def complete_file_upload(
    repo_id: str,
    complete_request: FileUploadCompleteRequest,
    current_user: User = Depends(get_current_user) # Apply auth here
):
    """
    Finalizes a file upload sequence and triggers the save operation.
    - **repo_id**: The identifier of the repository.
    - **complete_request**: Contains the completion_token.
    - (Currently) Simulates commit and returns a placeholder commit ID.
    - (Future Task 5.5) Will call core.save_changes and perform cleanup.
    """
    completion_token = complete_request.completion_token

    if completion_token not in upload_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invalid or expired completion_token: {completion_token}"
        )

    session_data = upload_sessions[completion_token]

    # Verify this token belongs to the user and repo_id
    if session_data.get("user_id") != current_user.username:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This completion token does not belong to the current user."
        )
    if session_data.get("repo_id") != repo_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"This completion token is for a different repository (expected {session_data.get('repo_id')}, got {repo_id})."
        )

    # Verify all files in the session have been uploaded
    all_files_uploaded = True
    uploaded_file_paths = [] # Will store temp paths for Task 5.5

    for file_path, file_details in session_data.get("files", {}).items():
        temp_file_path_str = file_details.get("temp_path")

        if not file_details.get("uploaded"):
            all_files_uploaded = False
            break # File not marked as uploaded

        if not temp_file_path_str:
            all_files_uploaded = False
            break # Temp path not stored

        if not Path(temp_file_path_str).exists():
            all_files_uploaded = False
            # Consider logging this specific issue: temp_path recorded but file missing
            break # Temp file does not exist at the stored path

        uploaded_file_paths.append(temp_file_path_str) # Store for later use

    if not all_files_uploaded:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not all files for this session have been successfully uploaded."
        )

    # --- Placeholder for Task 5.5 ---
    # In Task 5.5, this section will:
    # 1. Construct the full repository path (e.g., using PLACEHOLDER_REPO_PATH_PREFIX and repo_id).
    # 2. Create a list of (target_repo_path, temp_file_path_on_server) tuples.
    #    The target_repo_path is session_data["files"][file_path]["original_path_in_repo"] (or just file_path key).
    # 3. Call core.versioning.save_changes(repo_path, session_data["commit_message"], files_to_commit_map).
    # 4. If successful, clean up temporary files from TEMP_UPLOAD_DIR.
    # 5. Clean up the entry from upload_sessions.

    # For now, simulate success:
    simulated_commit_id = f"sim_commit_{uuid.uuid4().hex}"

    # Placeholder: Clean up session data (actual file cleanup for Task 5.5)
    # For now, just pop from upload_sessions. In 5.5, this happens *after* successful core operation.
    # And actual temp files need to be os.remove()'d.
    upload_sessions.pop(completion_token, None)

    return FileUploadCompleteResponse(
        commit_id=simulated_commit_id,
        message="Files processed successfully (simulation). Actual commit in next task."
    )
