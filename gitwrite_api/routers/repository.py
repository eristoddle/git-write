from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Any, Dict, Optional, List, Union
from pydantic import BaseModel, Field
import datetime # For commit date serialization
import pygit2 # Moved import to top

# TODO: Make this configurable or dynamically determined per user/request
PLACEHOLDER_REPO_PATH = "/tmp/gitwrite_repos_api"

# Import core functions
from gitwrite_core.repository import (
    list_branches, list_tags, list_commits, save_and_commit_file,
    list_gitignore_patterns as core_list_gitignore_patterns,
    add_pattern_to_gitignore as core_add_pattern_to_gitignore,
    initialize_repository as core_initialize_repository,
    get_file_content_at_commit as core_get_file_content_at_commit
)
from gitwrite_core.versioning import (
    get_branch_review_commits as core_get_branch_review_commits,
    cherry_pick_commit as core_cherry_pick_commit
)

# Import security dependency (assuming path based on project structure)
# Adjust the import path if your security module is located differently.
# For this example, let's assume a flat structure for simplicity or direct placement:
from ..security import get_current_active_user, require_role # Actual import
from ..models import User, UserRole, FileContentResponse # Import the canonical User model and UserRole
from ..models import SaveFileRequest, SaveFileResponse # Added for the new save endpoint

# Import core branching functions and exceptions
from gitwrite_core.branching import create_and_switch_branch, switch_to_branch
from gitwrite_core.versioning import revert_commit as core_revert_commit # Core function for revert
from gitwrite_core.repository import sync_repository as core_sync_repository # Core function for sync
from gitwrite_core.exceptions import (
    RepositoryNotFoundError as CoreRepositoryNotFoundError, # Alias to avoid conflict with potential local one
    RepositoryEmptyError as CoreRepositoryEmptyError,
    BranchAlreadyExistsError as CoreBranchAlreadyExistsError,
    BranchNotFoundError as CoreBranchNotFoundError,
    MergeConflictError as CoreMergeConflictError, # Added for merge, also used by revert and sync
    GitWriteError as CoreGitWriteError, # Also used by get_branch_review_commits
    DetachedHeadError as CoreDetachedHeadError, # Added for merge, also used by sync
    CommitNotFoundError as CoreCommitNotFoundError, # Added for compare, also used by revert, and file content
    NotEnoughHistoryError as CoreNotEnoughHistoryError, # Added for compare
    RemoteNotFoundError as CoreRemoteNotFoundError, # For sync
    FetchError as CoreFetchError, # For sync
    PushError as CorePushError, # For sync
    FileNotFoundInCommitError as CoreFileNotFoundInCommitError # For file content
)
from gitwrite_core.branching import merge_branch_into_current # Core function for merge
from gitwrite_core.versioning import get_diff as core_get_diff, get_word_level_diff as core_get_word_level_diff # Core functions for compare
# from gitwrite_core.exceptions import CommitNotFoundError as CoreCommitNotFoundError # Already imported above
# from gitwrite_core.exceptions import NotEnoughHistoryError as CoreNotEnoughHistoryError # Already imported above
from gitwrite_core.tagging import create_tag as core_create_tag # Core function for tagging
from gitwrite_core.exceptions import TagAlreadyExistsError as CoreTagAlreadyExistsError # For tagging

# For Repository Initialization
import uuid # Make sure uuid is imported here for use in export
from pathlib import Path
from ..models import RepositoryCreateRequest # Import the request model

# Models for Branch Review API
from ..models import BranchReviewResponse, BranchReviewCommit

# Models for Cherry-Pick API
from ..models import CherryPickRequest, CherryPickResponse

# Models for EPUB Export API
from ..models import EPUBExportRequest, EPUBExportResponse


# Placeholder Pydantic model for User removed, as it's now imported from ..models


router = APIRouter(
    prefix="/repository",
    tags=["repository"],
    responses={404: {"description": "Not found"}},
)

# --- Response Models ---

class BranchListResponse(BaseModel):
    status: str
    branches: List[str]
    message: str

class TagListResponse(BaseModel):
    status: str
    tags: List[str]
    message: str

class CommitDetail(BaseModel):
    sha: str
    message: str
    author_name: str
    author_email: str
    author_date: datetime.datetime # Changed from int to datetime for better type hinting/validation
    committer_name: str
    committer_email: str
    committer_date: datetime.datetime # Changed from int to datetime
    parents: List[str]

class CommitListResponse(BaseModel):
    status: str
    commits: List[CommitDetail]
    message: str

# Branching Endpoint Models
class BranchCreateRequest(BaseModel):
    branch_name: str = Field(..., min_length=1, description="Name of the branch to create.")

class BranchSwitchRequest(BaseModel):
    branch_name: str = Field(..., min_length=1, description="Name of the branch to switch to.")

class BranchResponse(BaseModel):
    status: str
    branch_name: str
    message: str
    head_commit_oid: Optional[str] = None
    previous_branch_name: Optional[str] = None # For switch operation
    is_detached: Optional[bool] = None # For switch operation

# Merge Endpoint Models
class MergeBranchRequest(BaseModel):
    source_branch: str = Field(..., min_length=1, description="Name of the branch to merge into the current branch.")

class MergeBranchResponse(BaseModel):
    status: str = Field(..., description="Outcome of the merge operation (e.g., 'merged_ok', 'fast_forwarded', 'up_to_date', 'conflict').")
    message: str = Field(..., description="Detailed message about the merge outcome.")
    current_branch: Optional[str] = Field(None, description="The current branch after the merge attempt.")
    merged_branch: Optional[str] = Field(None, description="The branch that was merged.")
    commit_oid: Optional[str] = Field(None, description="The OID of the new merge commit, if one was created.")
    conflicting_files: Optional[List[str]] = Field(None, description="List of files with conflicts, if any.")

# Compare Endpoint Models
# Note: For GET /compare, parameters are via Query. This model is for response structure.
class CompareRefsResponse(BaseModel):
    ref1_oid: str = Field(..., description="Resolved OID of the first reference.")
    ref2_oid: str = Field(..., description="Resolved OID of the second reference.")
    ref1_display_name: str = Field(..., description="Display name for the first reference.")
    ref2_display_name: str = Field(..., description="Display name for the second reference.")
    patch_text: Union[str, List[Dict[str, Any]]] = Field(..., description="The diff/patch output, either as a raw string or a structured list of dictionaries for word-level diff.")

# Revert Endpoint Models
class RevertCommitRequest(BaseModel):
    commit_ish: str = Field(..., min_length=1, description="The commit reference (hash, branch, tag) to revert.")

class RevertCommitResponse(BaseModel):
    status: str = Field(..., description="Outcome of the revert operation (e.g., 'success').")
    message: str = Field(..., description="Detailed message about the revert outcome.")
    new_commit_oid: Optional[str] = Field(None, description="The OID of the new commit created by the revert, if successful.")

# Sync Endpoint Models
class SyncFetchStatus(BaseModel):
    received_objects: Optional[int] = None
    total_objects: Optional[int] = None
    message: str

class SyncLocalUpdateStatus(BaseModel):
    type: str # e.g., "none", "up_to_date", "fast_forwarded", "merged_ok", "conflicts_detected", "error", "no_remote_branch"
    message: str
    commit_oid: Optional[str] = None
    conflicting_files: Optional[List[str]] = Field(default_factory=list)

class SyncPushStatus(BaseModel):
    pushed: bool
    message: str

class SyncRepositoryRequest(BaseModel):
    remote_name: str = Field("origin", description="Name of the remote repository to sync with.")
    branch_name: Optional[str] = Field(None, description="Name of the local branch to sync. Defaults to the current branch.")
    push: bool = Field(True, description="Whether to push changes to the remote after fetching and merging/fast-forwarding.")
    allow_no_push: bool = Field(False, description="If True and push is False, considers the operation successful without pushing. If False and push is False, this flag has no effect unless core logic changes.")

class SyncRepositoryResponse(BaseModel):
    status: str = Field(..., description="Overall status of the sync operation (e.g., 'success', 'success_conflicts', 'error_in_sub_operation').")
    branch_synced: Optional[str] = Field(None, description="The local branch that was synced.")
    remote: str = Field(..., description="The remote repository name used for syncing.")
    fetch_status: SyncFetchStatus
    local_update_status: SyncLocalUpdateStatus
    push_status: SyncPushStatus

# Tagging Endpoint Models
class TagCreateRequest(BaseModel):
    tag_name: str = Field(..., min_length=1, description="Name of the tag to create.")
    message: Optional[str] = Field(None, description="If provided, creates an annotated tag with this message. Otherwise, a lightweight tag is created.")
    commit_ish: str = Field("HEAD", description="The commit-ish (e.g., commit hash, branch name, another tag) to tag. Defaults to 'HEAD'.")
    force: bool = Field(False, description="If True, overwrite an existing tag with the same name.")

class TagCreateResponse(BaseModel):
    status: str = Field(..., description="Outcome of the tag creation operation (e.g., 'created').")
    tag_name: str = Field(..., description="The name of the created tag.")
    tag_type: str = Field(..., description="Type of the tag created ('annotated' or 'lightweight').")
    target_commit_oid: str = Field(..., description="The OID of the commit that the tag points to.")
    message: Optional[str] = Field(None, description="The message of the tag, if it's an annotated tag.")

# Ignore Management Endpoint Models
class IgnorePatternRequest(BaseModel):
    pattern: str = Field(..., min_length=1, description="The .gitignore pattern to add.")

class IgnoreListResponse(BaseModel):
    status: str = Field(..., description="Outcome of the list operation.")
    patterns: List[str] = Field(..., description="List of patterns from .gitignore.")
    message: str = Field(..., description="Detailed message about the operation.")

class IgnoreAddResponse(BaseModel):
    status: str = Field(..., description="Outcome of the add pattern operation.")
    message: str = Field(..., description="Detailed message about the operation.")

class RepositoryCreateResponse(BaseModel):
    status: str = Field(..., description="Outcome of the repository creation operation (e.g., 'created').")
    message: str = Field(..., description="Detailed message about the creation outcome.")
    repository_id: str = Field(..., description="The ID or name of the created repository.")
    path: str = Field(..., description="The server path to the created repository.")


# --- Helper for error handling ---
def handle_core_response(response: Dict[str, Any], success_status: str = "success") -> Dict[str, Any]:
    """
    Processes responses from core functions and raises HTTPExceptions for errors.
    """
    if response["status"] == success_status or (success_status=="success" and response["status"] in ["no_tags", "empty_repo", "no_commits"]): # some non-error statuses
        return response
    elif response["status"] == "not_found" or response["status"] == "empty_repo" and "branch" in response.get("message","").lower(): # branch not found in empty repo
        raise HTTPException(status_code=404, detail=response.get("message", "Resource not found."))
    elif response["status"] == "error":
        raise HTTPException(status_code=500, detail=response.get("message", "An internal server error occurred."))
    elif response["status"] == "empty_repo": # General empty repo, not necessarily a 404 unless specific item not found
        # For list operations on an empty repo, returning empty list might be acceptable.
        # However, if the core function indicates 'empty_repo' as a distinct status,
        # we can choose to return it as part of a 200 OK or a specific error.
        # Here, we pass it through if it's not an explicit error.
        return response
    else: # Other non-success statuses from core
        raise HTTPException(status_code=400, detail=response.get("message", "Bad request or invalid operation."))


# --- API Endpoints ---

@router.get("/branches", response_model=BranchListResponse)
async def api_list_branches(current_user: User = Depends(get_current_active_user)):
    """
    Lists all local branches in the repository.
    Requires authentication.
    """
    # TODO: Determine repo_path dynamically based on user or other context
    repo_path = PLACEHOLDER_REPO_PATH
    result = list_branches(repo_path_str=repo_path)

    # Convert author_date and committer_date from timestamp to datetime if necessary
    # This is already handled by Pydantic model validation if core returns datetime
    # If core returns int (timestamp), Pydantic will attempt conversion or use a validator

    return handle_core_response(result)

@router.get("/tags", response_model=TagListResponse)
async def api_list_tags(current_user: User = Depends(get_current_active_user)):
    """
    Lists all tags in the repository.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    result = list_tags(repo_path_str=repo_path)
    return handle_core_response(result)

@router.get("/commits", response_model=CommitListResponse)
async def api_list_commits(
    branch_name: Optional[str] = Query(None, description="Name of the branch to list commits from. Defaults to current HEAD."),
    max_count: Optional[int] = Query(None, description="Maximum number of commits to return.", gt=0),
    current_user: User = Depends(get_current_active_user)
):
    """
    Lists commits for a given branch, or the current branch if branch_name is not provided.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    result = list_commits(
        repo_path_str=repo_path,
        branch_name=branch_name,
        max_count=max_count
    )

    # Ensure timestamps are converted to datetime objects for Pydantic validation
    # Pydantic V2 automatically converts valid ISO strings and timestamps (int/float) to datetime
    # If list_commits returns integer timestamps, Pydantic should handle it.
    # If manual conversion is needed:
    # for commit in result.get("commits", []):
    #     if isinstance(commit.get("author_date"), int):
    #         commit["author_date"] = datetime.datetime.fromtimestamp(commit["author_date"], tz=datetime.timezone.utc)
    #     if isinstance(commit.get("committer_date"), int):
    #         commit["committer_date"] = datetime.datetime.fromtimestamp(commit["committer_date"], tz=datetime.timezone.utc)

    return handle_core_response(result)


@router.post("/save", response_model=SaveFileResponse)
async def api_save_file(
    save_request: SaveFileRequest = Body(...),
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.WRITER]))
):
    """
    Saves a file to the repository and commits the change.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH

    # Ensure current_user fields are available; provide defaults if placeholder returns dict
    user_email = current_user.email if hasattr(current_user, 'email') else "defaultuser@example.com"
    user_name = current_user.username if hasattr(current_user, 'username') else "Default User"


    result = save_and_commit_file(
        repo_path_str=repo_path,
        file_path=save_request.file_path,
        content=save_request.content,
        commit_message=save_request.commit_message,
        author_name=user_name,
        author_email=user_email
    )

    if result['status'] == 'success':
        return SaveFileResponse(
            status='success',
            message=result['message'],
            commit_id=result.get('commit_id') # Use .get() for safety
        )
    else: # 'error' status
        # Determine status code: 400 for client-side errors (e.g., bad path, validation), 500 for server-side.
        # The core function's message might give clues. For now, default to 400 as per prompt.
        # More specific error types from core would allow better mapping here.
        status_code = 400
        if "Repository not found" in result.get("message", ""):
            status_code = 500 # This indicates a server configuration issue with PLACEHOLDER_REPO_PATH
        elif "Error committing file" in result.get("message", "") and "Repository not found" not in result.get("message",""):
             status_code = 500 # Internal git operation error
        elif "Error staging file" in result.get("message", ""):
            status_code = 500 # Internal git operation error

        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', "An error occurred while saving the file.")
        )

# Example of how to include this router in your main FastAPI application:
# from fastapi import FastAPI
# from . import repository # Assuming this file is repository.py in a 'routers' module
#
# app = FastAPI()
# app.include_router(repository.router)
#
# @app.get("/")
# async def main_root():
#     return {"message": "Main application root"}


# --- Branching Endpoints ---

@router.post("/branches", response_model=BranchResponse, status_code=201)
async def api_create_branch(
    request_data: BranchCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Creates a new branch from the current HEAD and switches to it.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = create_and_switch_branch(
            repo_path_str=repo_path,
            branch_name=request_data.branch_name
        )
        # Core function returns: {'status': 'success', 'branch_name': branch_name, 'head_commit_oid': str(repo.head.target)}
        return BranchResponse(
            status="created", # More specific than 'success' for a POST
            branch_name=result['branch_name'],
            message=f"Branch '{result['branch_name']}' created and switched to successfully.",
            head_commit_oid=result['head_commit_oid']
        )
    except CoreBranchAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CoreRepositoryEmptyError as e:
        # This typically means HEAD is unborn, making branch creation from HEAD problematic.
        raise HTTPException(status_code=400, detail=str(e)) # 400 Bad Request or 422 Unprocessable
    except CoreRepositoryNotFoundError:
        # This implies an issue with PLACEHOLDER_REPO_PATH, a server-side configuration problem.
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        # Catch-all for other git-related errors from the core function.
        raise HTTPException(status_code=500, detail=f"Failed to create branch: {str(e)}")
    except Exception as e:
        # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.put("/branch", response_model=BranchResponse)
async def api_switch_branch(
    request_data: BranchSwitchRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Switches to an existing local branch.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = switch_to_branch(
            repo_path_str=repo_path,
            branch_name=request_data.branch_name
        )
        # Core function returns:
        # success: {'status': 'success', 'branch_name': ..., 'previous_branch_name': ..., 'head_commit_oid': ..., 'is_detached': ...}
        # already: {'status': 'already_on_branch', 'branch_name': ..., 'head_commit_oid': ...}

        message = ""
        if result['status'] == 'success':
            message = f"Switched to branch '{result['branch_name']}' successfully."
        elif result['status'] == 'already_on_branch':
            message = f"Already on branch '{result['branch_name']}'."
        else: # Should not happen if core function adheres to spec
            message = "Branch switch operation completed with an unknown status."


        return BranchResponse(
            status=result['status'], # 'success' or 'already_on_branch'
            branch_name=result['branch_name'],
            message=message,
            head_commit_oid=result.get('head_commit_oid'),
            previous_branch_name=result.get('previous_branch_name'),
            is_detached=result.get('is_detached')
        )
    except CoreBranchNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreRepositoryEmptyError as e: # e.g. switching in empty repo to non-existent branch
        raise HTTPException(status_code=400, detail=str(e))
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e: # e.g. uncommitted changes, other checkout failures
        # Check for specific conditions if needed, e.g. uncommitted changes might be 409 or 400
        if "local changes overwrite" in str(e).lower() or "unstaged changes" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Switch failed: {str(e)}") # 409 Conflict
        raise HTTPException(status_code=400, detail=f"Failed to switch branch: {str(e)}") # 400 Bad Request for other git issues
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# --- Merge Endpoint ---

@router.post("/merges", response_model=MergeBranchResponse)
async def api_merge_branch(
    request_data: MergeBranchRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Merges a specified source branch into the current branch.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = merge_branch_into_current(
            repo_path_str=repo_path,
            branch_to_merge_name=request_data.source_branch
        )
        # Core function returns dict with 'status', 'branch_name', 'current_branch', 'commit_oid' (optional)
        # e.g. {'status': 'up_to_date', 'branch_name': 'feature', 'current_branch': 'main'}
        # e.g. {'status': 'fast_forwarded', ..., 'commit_oid': 'sha'}
        # e.g. {'status': 'merged_ok', ..., 'commit_oid': 'sha'}

        status_code = 200 # Default OK for successful merges
        response_status = result['status']
        message = ""

        if response_status == 'up_to_date':
            message = f"Current branch '{result['current_branch']}' is already up-to-date with '{result['branch_name']}'."
        elif response_status == 'fast_forwarded':
            message = f"Branch '{result['branch_name']}' was fast-forwarded into '{result['current_branch']}'."
        elif response_status == 'merged_ok':
            message = f"Branch '{result['branch_name']}' was successfully merged into '{result['current_branch']}'."
        else: # Should not happen if core adheres to spec
            message = "Merge operation completed with an unknown status."
            response_status = "unknown_core_status" # To avoid conflict with HTTP status

        return MergeBranchResponse(
            status=response_status,
            message=message,
            current_branch=result.get('current_branch'),
            merged_branch=result.get('branch_name'), # Core uses 'branch_name' for the branch that was merged
            commit_oid=result.get('commit_oid')
        )

    # Note: Order of exception handling is important.
    # Catch specific exceptions before their parents if they need different handling.

    except CoreBranchNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreRepositoryEmptyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreDetachedHeadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreRepositoryNotFoundError: # Server-side configuration issue
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    # Catch CoreGitWriteError and check its type for MergeConflictError behavior
    except CoreGitWriteError as e:
        if type(e).__name__ == 'MergeConflictError' and hasattr(e, 'conflicting_files'):
            # This is likely a CoreMergeConflictError that wasn't caught by a more specific except
            # due to potential type identity issues at runtime.
            detail_payload = {
                "status": "conflict",
                "message": str(e.message), # Use e.message which CoreMergeConflictError sets
                "conflicting_files": e.conflicting_files,
                "current_branch": getattr(e, 'current_branch_name', None),
                "merged_branch": getattr(e, 'merged_branch_name', request_data.source_branch)
            }
            cleaned_detail_payload = {k: v for k, v in detail_payload.items() if v is not None}
            raise HTTPException(status_code=409, detail=cleaned_detail_payload)
        else:
            # Handle other CoreGitWriteErrors (e.g., "Cannot merge into self", "No signature")
            raise HTTPException(status_code=400, detail=f"Merge operation failed: {str(e)}")

    except Exception as e: # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during merge: {str(e)}")


# --- Compare Endpoint ---

@router.get("/compare", response_model=CompareRefsResponse)
async def api_compare_refs(
    ref1: Optional[str] = Query(None, description="The first reference (e.g., commit hash, branch, tag). Defaults to HEAD~1."),
    ref2: Optional[str] = Query(None, description="The second reference (e.g., commit hash, branch, tag). Defaults to HEAD."),
    diff_mode: Optional[str] = Query(None, description="Set to 'word' for word-level diff."),
    current_user: User = Depends(get_current_active_user)
):
    """
    Compares two references in the repository and returns the diff.
    Requires authentication.
    If ref1 and ref2 are None, compares HEAD~1 with HEAD.
    If only ref1 is provided, compares ref1 with HEAD.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        # Call the core function. It handles default logic for None refs.
        diff_result = core_get_diff(
            repo_path_str=repo_path,
            ref1_str=ref1,
            ref2_str=ref2
        )

        # Determine the output format based on diff_mode
        diff_output: Union[str, List[Dict[str, Any]]]
        if diff_mode == 'word':
            if diff_result["patch_text"]:
                diff_output = core_get_word_level_diff(diff_result["patch_text"])
            else:
                diff_output = [] # Return empty list for no textual diff
        else:
            diff_output = diff_result["patch_text"]

        return CompareRefsResponse(
            ref1_oid=diff_result["ref1_oid"],
            ref2_oid=diff_result["ref2_oid"],
            ref1_display_name=diff_result["ref1_display_name"],
            ref2_display_name=diff_result["ref2_display_name"],
            patch_text=diff_output
        )
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreNotEnoughHistoryError as e:
        # This occurs if trying to compare HEAD~1 vs HEAD on initial commit, etc.
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e: # Raised by core_get_diff for invalid ref combinations
        raise HTTPException(status_code=400, detail=str(e))
    except CoreRepositoryNotFoundError: # Server-side configuration issue
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e: # Other general errors from core
        raise HTTPException(status_code=500, detail=f"Compare operation failed: {str(e)}")
    except Exception as e: # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during compare: {str(e)}")


# --- Revert Endpoint ---

@router.post("/revert", response_model=RevertCommitResponse)
async def api_revert_commit(
    request_data: RevertCommitRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Reverts a specified commit.
    This creates a new commit that undoes the changes from the specified commit.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_revert_commit(
            repo_path_str=repo_path,
            commit_ish_to_revert=request_data.commit_ish
        )
        # Core function returns: {'status': 'success', 'new_commit_oid': str(new_commit_oid), 'message': '...'}
        return RevertCommitResponse(
            status=result['status'], # Should be 'success'
            message=result['message'],
            new_commit_oid=result.get('new_commit_oid')
        )
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreMergeConflictError as e:
        # This means the revert operation itself caused conflicts.
        # The core function should have aborted the revert and cleaned the working directory.
        raise HTTPException(
            status_code=409,
            detail=f"Revert failed due to conflicts: {str(e)}. The working directory should be clean."
        )
    except CoreRepositoryNotFoundError: # Server-side configuration issue
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreRepositoryEmptyError as e: # e.g. trying to revert in an empty repo
        raise HTTPException(status_code=400, detail=str(e))
    except CoreGitWriteError as e:
        # Examples: "Cannot revert initial commit", "Revert resulted in empty commit" (if that's a case)
        # These are typically client errors (bad request) or specific git conditions.
        # Default to 400, but could be 500 if it seems like an internal unhandled git problem.
        # The message from core_revert_commit is crucial.
        if "Cannot revert commit" in str(e) and "no parents" in str(e): # Specific case for initial commit
             raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=400, detail=f"Revert operation failed: {str(e)}")
    except Exception as e: # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during revert: {str(e)}")


# --- Sync Endpoint ---

@router.post("/sync", response_model=SyncRepositoryResponse)
async def api_sync_repository(
    request_data: SyncRepositoryRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Synchronizes the local repository branch with its remote counterpart.
    Fetches changes, integrates them (fast-forward or merge), and optionally pushes.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_sync_repository(
            repo_path_str=repo_path,
            remote_name=request_data.remote_name,
            branch_name_opt=request_data.branch_name,
            push=request_data.push,
            allow_no_push=request_data.allow_no_push
        )
        # The core function returns a detailed dictionary. We need to map this to SyncRepositoryResponse.
        # Ensure sub-models are correctly populated.
        return SyncRepositoryResponse(
            status=result["status"],
            branch_synced=result.get("branch_synced"),
            remote=result["remote"],
            fetch_status=SyncFetchStatus(**result["fetch_status"]),
            local_update_status=SyncLocalUpdateStatus(**result["local_update_status"]),
            push_status=SyncPushStatus(**result["push_status"])
        )
    except CoreMergeConflictError as e:
        # Sync core function can raise this if merge during sync leads to conflicts.
        # The core function's return dictionary would have 'status': 'success_conflicts'
        # and details in 'local_update_status'.
        # However, if it *raises* CoreMergeConflictError, it means the operation was halted.
        # The plan asks to return 409.
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Sync failed due to merge conflicts: {str(e.message)}",
                "conflicting_files": e.conflicting_files if hasattr(e, 'conflicting_files') else [],
                # Include branch names if available from exception, though CoreMergeConflictError might not have them directly for sync
            }
        )
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreRepositoryEmptyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreDetachedHeadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreRemoteNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreBranchNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreFetchError as e:
        # 503 Service Unavailable might be appropriate as it's an external service interaction failing.
        raise HTTPException(status_code=503, detail=f"Fetch operation failed: {str(e)}")
    except CorePushError as e:
        # Similar to FetchError, 503 or could be 400/409 if specific (e.g. non-fast-forward rejected and not handled)
        # CorePushError might contain hints.
        # If push is rejected due to non-fast-forward and core doesn't handle it by merging/rebasing first (sync should),
        # then 409 might be suitable. For general push failures (auth, connection), 503.
        if "non-fast-forward" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Push rejected (non-fast-forward): {str(e)}. Try syncing again.")
        raise HTTPException(status_code=503, detail=f"Push operation failed: {str(e)}")
    except CoreGitWriteError as e: # General git errors during sync
        raise HTTPException(status_code=400, detail=f"Sync operation failed: {str(e)}")
    except Exception as e: # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during sync: {str(e)}")


# --- Tagging Endpoint ---

@router.post("/tags", response_model=TagCreateResponse, status_code=201)
async def api_create_tag(
    request_data: TagCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Creates a new tag (lightweight or annotated) in the repository.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH

    # For annotated tags, pygit2.Signature is needed.
    # We'll use the current_user's details or defaults.
    tagger_signature = None
    if request_data.message: # Annotated tags require a tagger
        user_name = current_user.username if hasattr(current_user, 'username') and current_user.username else "GitWrite API User"
        user_email = current_user.email if hasattr(current_user, 'email') and current_user.email else "api@gitwrite.com"
        try:
            tagger_signature = pygit2.Signature(user_name, user_email)
        except pygit2.GitError as e:
            # More specific catch for errors during Signature creation if name/email are invalid for libgit2
            raise HTTPException(status_code=400, detail=f"Failed to create tagger signature due to invalid user details: {str(e)}")
        except TypeError as e:
            # Catch TypeError specifically, which 'dev/string_type' often manifests as from pygit2
            if 'dev/string_type' in str(e):
                raise HTTPException(status_code=500, detail="Server configuration error: pygit2 library not available or misconfigured.")
            raise HTTPException(status_code=500, detail=f"Unexpected error creating tagger signature: {str(e)}")
        except Exception as e:
            # Fallback for other errors during signature creation
            # This could be the place for the "pygit2 library not available" if we assume pygit2 itself might be None
            # For now, this addresses other unexpected issues.
            # If pygit2 module was truly not imported, an NameError would occur earlier if not handled,
            # or ImportError if `import pygit2` was inside the function and failed.
            # Given `import pygit2` is at top, this is for other runtime errors.
            raise HTTPException(status_code=500, detail=f"Unexpected error creating tagger signature: {str(e)}")


    try:
        result = core_create_tag( # Ensure core_create_tag is imported
            repo_path_str=repo_path,
            tag_name=request_data.tag_name,
            target_commit_ish=request_data.commit_ish,
            message=request_data.message,
            force=request_data.force,
            tagger=tagger_signature # Pass the signature for annotated tags
        )
        # Core function returns:
        # {'name': tag_name, 'type': 'annotated'/'lightweight', 'target': str(target_oid), 'message': message (optional)}

        return TagCreateResponse(
            status="created",
            tag_name=result['name'],
            tag_type=result['type'],
            target_commit_oid=result['target'],
            message=result.get('message') # Will be None for lightweight tags or if no message
        )
    except CoreTagAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreRepositoryNotFoundError: # Server-side configuration issue
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        # Examples: "Cannot create tags in a bare repository.", "Failed to create ... tag..."
        # These are typically client errors (bad request / invalid op) or specific git conditions.
        # Default to 400.
        raise HTTPException(status_code=400, detail=f"Tag creation failed: {str(e)}")
    except Exception as e: # Fallback for unexpected errors
        # This could include the pygit2.Signature creation failure if not handled more specifically,
        # or other unforeseen issues.
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during tag creation: {str(e)}")


# --- Ignore Management Endpoints ---

@router.get("/ignore", response_model=IgnoreListResponse)
async def api_list_ignore_patterns(current_user: User = Depends(get_current_active_user)):
    """
    Lists all patterns in the .gitignore file of the repository.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_list_gitignore_patterns(repo_path_str=repo_path)

        if not isinstance(result, dict):
            raise ValueError(f"Core function core_list_gitignore_patterns returned non-dict: {type(result)}")
        if 'status' not in result:
            raise ValueError("Core function core_list_gitignore_patterns result missing 'status' key")

        # Core function returns:
        # {'status': 'success', 'patterns': patterns_list, 'message': '...'}
        # {'status': 'not_found', 'patterns': [], 'message': '.gitignore file not found.'}
        # {'status': 'empty', 'patterns': [], 'message': '.gitignore is empty.'}
        # {'status': 'error', 'patterns': [], 'message': 'Error reading .gitignore: ...'}

        if result['status'] == 'success':
            return IgnoreListResponse(
                status=result['status'],
                patterns=result['patterns'],
                message=result['message']
            )
        elif result['status'] == 'not_found' or result['status'] == 'empty':
            # These are not errors, but valid states returning empty patterns.
            return IgnoreListResponse(
                status=result['status'],
                patterns=[], # Ensure patterns is empty list as per core
                message=result['message']
            )
        elif result['status'] == 'error':
            # Core function encountered an error (e.g., I/O error reading file)
            error_message = result.get('message', 'An error occurred while listing ignore patterns.')
            raise HTTPException(status_code=500, detail=str(error_message)) # Return specific core message
        else:
            # Should not happen if core adheres to its spec
            raise HTTPException(status_code=500, detail="Unknown error from core ignore listing.")

    # Removed generic Exception catchers to let HTTPExceptions propagate naturally
    # and to reveal any other unexpected errors directly.
    except CoreRepositoryNotFoundError: # Should not happen with placeholder, but good practice
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    # Note: Specific business logic exceptions from core layer (if any) should be caught if they are not already
    # handled by the result['status'] checks. For now, focusing on existing structure.


@router.get("/file-content", response_model=FileContentResponse)
async def api_get_file_content(
    file_path: str = Query(..., description="Relative path of the file in the repository."),
    commit_sha: str = Query(..., description="The commit SHA to retrieve the file from."),
    current_user: User = Depends(get_current_active_user)
):
    """
    Retrieves the content of a specific file at a given commit.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_get_file_content_at_commit(
            repo_path_str=repo_path,
            file_path=file_path,
            commit_sha_str=commit_sha
        )

        if result['status'] == 'success':
            return FileContentResponse(
                file_path=result['file_path'],
                commit_sha=result['commit_sha'],
                content=result['content'],
                size=result['size'],
                mode=result['mode'],
                is_binary=result['is_binary']
            )
        elif result['status'] == 'error':
            # Determine appropriate HTTP status code based on core message
            message = result.get('message', 'Error retrieving file content.')
            if "Repository not found" in message:
                raise HTTPException(status_code=500, detail=message) # Config issue
            elif "Commit with SHA" in message and ("not found" in message or "invalid" in message):
                raise HTTPException(status_code=404, detail=message)
            elif "File" in message and "not found in commit" in message:
                raise HTTPException(status_code=404, detail=message)
            elif "is not a file" in message: # e.g. path is a directory
                raise HTTPException(status_code=400, detail=message)
            else: # General core error
                raise HTTPException(status_code=500, detail=message)
        else: # Should not happen if core adheres to spec
            raise HTTPException(status_code=500, detail="Unknown error from core file content retrieval.")

    # Specific exceptions from core layer (if used instead of dict status)
    except CoreRepositoryNotFoundError as e: # Should be caught by dict status 'Repository not found'
        raise HTTPException(status_code=500, detail=str(e))
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreFileNotFoundInCommitError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreGitWriteError as e: # Other general errors from core
        raise HTTPException(status_code=400, detail=f"File content retrieval failed: {str(e)}")
    except Exception as e: # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# --- EPUB Export Endpoint ---

@router.post("/export/epub", response_model=EPUBExportResponse)
async def api_export_to_epub(
    request_data: EPUBExportRequest,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.WRITER, UserRole.BETA_READER]))
):
    """
    Exports specified markdown files from the repository at a given commit-ish to an EPUB file.
    The EPUB file is saved on the server.
    Requires authentication.
    """
    repo_path_str = PLACEHOLDER_REPO_PATH

    export_base_dir = Path(PLACEHOLDER_REPO_PATH) / "exports"

    try:
        export_base_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create base export directory: {str(e)}")

    job_id = str(uuid.uuid4())
    job_export_dir = export_base_dir / job_id
    try:
        # export_base_dir is already created with parents=True, exist_ok=True
        # Allow job_export_dir to exist, in case of test reruns or specific scenarios.
        job_export_dir.mkdir(exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create unique export job directory: {str(e)}")

    # Use default if output_filename is None (though Pydantic model now provides a default)
    actual_output_filename = request_data.output_filename if request_data.output_filename else "export.epub"
    output_epub_server_path = job_export_dir / actual_output_filename

    # It's good practice to import closer to usage if they are specific to an endpoint and large
    # However, for core functions and exceptions, top-level in router file is also common.
    # Let's ensure specific exceptions are available.
    from gitwrite_core.export import export_to_epub
    from gitwrite_core.exceptions import PandocError, FileNotFoundInCommitError

    try:
        result = export_to_epub(
            repo_path_str=repo_path_str,
            commit_ish_str=request_data.commit_ish,
            file_list=request_data.file_list,
            output_epub_path_str=str(output_epub_server_path.resolve())
        )

        if result["status"] == "success":
            return EPUBExportResponse(
                status="success",
                message=result["message"],
                server_file_path=str(output_epub_server_path.resolve())
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "EPUB export failed due to an unknown core error."))

    except CoreRepositoryNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Repository not found or configuration error: {str(e)}")
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Commit not found: {str(e)}")
    except FileNotFoundInCommitError as e:
        raise HTTPException(status_code=404, detail=f"File not found in commit: {str(e)}")
    except PandocError as e:
        if "Pandoc not found" in str(e):
            raise HTTPException(status_code=503, detail=f"EPUB generation service unavailable: Pandoc not found. {str(e)}")
        else:
            raise HTTPException(status_code=400, detail=f"EPUB conversion failed: {str(e)}")
    except CoreGitWriteError as e:
        raise HTTPException(status_code=400, detail=f"EPUB export failed due to a GitWrite core error: {str(e)}")
    except Exception as e:
        # Consider logging this e.g. logger.error(f"Unexpected error during EPUB export: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred during EPUB export: {str(e)}")


# --- Branch Review Endpoint ---

@router.get("/review/{branch_name}", response_model=BranchReviewResponse)
async def api_review_branch_commits(
    branch_name: str,
    limit: Optional[int] = Query(None, description="Maximum number of commits to return.", gt=0),
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.BETA_READER]))
):
    """
    Retrieves commits present on the specified branch that are not on the current HEAD.
    This is useful for reviewing changes before a potential merge or cherry-pick.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        commits_list_core = core_get_branch_review_commits(
            repo_path_str=repo_path,
            branch_name_to_review=branch_name,
            limit=limit
        )

        # Convert core dicts to BranchReviewCommit Pydantic models
        # The core function already returns list of dicts with keys:
        # "short_hash", "author_name", "date", "message_short", "oid"
        review_commits = [BranchReviewCommit(**commit_data) for commit_data in commits_list_core]

        return BranchReviewResponse(
            status="success",
            branch_name=branch_name,
            commits=review_commits,
            message=f"Found {len(review_commits)} reviewable commits on branch '{branch_name}'."
                     if review_commits else f"No unique reviewable commits found on branch '{branch_name}' compared to HEAD."
        )
    except CoreBranchNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreRepositoryNotFoundError: # Indicates server-side configuration issue
        raise HTTPException(status_code=500, detail="Repository configuration error or not found.")
    except CoreGitWriteError as e: # Catch-all for other git-related errors from core
        # This could be "HEAD is unborn" or other general issues.
        # A 400 Bad Request might be more appropriate if it's a precondition failure.
        if "HEAD is unborn" in str(e):
            raise HTTPException(status_code=400, detail=f"Cannot review branch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to review branch commits: {str(e)}")
    except Exception as e: # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# --- Cherry-Pick Endpoint ---

@router.post("/cherry-pick", response_model=CherryPickResponse)
async def api_cherry_pick_commit(
    request_data: CherryPickRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Applies a specific commit from any part of the history to the current branch.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_cherry_pick_commit(
            repo_path_str=repo_path,
            commit_oid_to_pick=request_data.commit_id,
            mainline=request_data.mainline
        )
        # Core function returns:
        # {'status': 'success', 'new_commit_oid': str(new_commit_oid_val), 'message': '...'}
        return CherryPickResponse(
            status=result['status'], # Should be 'success'
            message=result['message'],
            new_commit_oid=result.get('new_commit_oid')
        )
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreMergeConflictError as e:
        # CoreMergeConflictError has 'message' and 'conflicting_files' attributes
        return CherryPickResponse(
            status="conflict",
            message=str(e.message), # Use the specific message from the exception
            new_commit_oid=None,
            conflicting_files=e.conflicting_files if hasattr(e, 'conflicting_files') else []
        )
        # If we want to raise HTTPException 409 instead of returning 200 with status="conflict"
        # raise HTTPException(
        #     status_code=409,
        #     detail={
        #         "message": str(e.message),
        #         "conflicting_files": e.conflicting_files if hasattr(e, 'conflicting_files') else []
        #     }
        # )
    except CoreRepositoryNotFoundError: # Server-side configuration issue
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        # This can cover various scenarios:
        # - "Cannot cherry-pick in a bare repository."
        # - "Cannot cherry-pick onto an unborn HEAD."
        # - "Commit ... is a merge commit. Please specify the 'mainline' parameter..."
        # - "Invalid mainline number..."
        # - "Mainline option specified, but commit ... is not a merge commit."
        # - Other general Git errors during cherry-pick.
        # Most of these are client errors (400 or 422).
        error_detail = str(e)
        if "unborn HEAD" in error_detail or \
           "merge commit" in error_detail or \
           "mainline" in error_detail or \
           "bare repository" in error_detail:
            raise HTTPException(status_code=400, detail=error_detail)
        # For other CoreGitWriteErrors that are less clearly client-fault, 500 might be safer.
        # However, the prompt leans towards 400/422 for GitWriteErrors in this context.
        # Let's assume other GitWriteErrors are also bad requests unless specified.
        raise HTTPException(status_code=400, detail=f"Cherry-pick operation failed: {error_detail}")
    except Exception as e: # Fallback for unexpected errors
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during cherry-pick: {str(e)}")


# --- Repository Initialization Endpoint ---

@router.post("/repositories", response_model=RepositoryCreateResponse, status_code=201)
async def api_initialize_repository(
    request_data: RepositoryCreateRequest,
    current_user: User = Depends(require_role([UserRole.OWNER]))
):
    """
    Initializes a new GitWrite repository.
    If `project_name` is provided, it's used as the directory name.
    Otherwise, a unique ID is generated for the directory name.
    Requires authentication.
    """
    repo_base_path = Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos" # Define a sub-directory for user repos
    project_name_to_use: str

    if request_data.project_name:
        # Validate project_name against allowed characters (already done by Pydantic pattern, but good for defense)
        # Basic check here, Pydantic handles stricter validation
        if not request_data.project_name.isalnum() and '_' not in request_data.project_name and '-' not in request_data.project_name:
             raise HTTPException(status_code=400, detail="Invalid project_name. Only alphanumeric, hyphens, and underscores are allowed.")
        project_name_to_use = request_data.project_name
        repo_path_to_initialize_at = repo_base_path # Core function will append project_name if provided
    else:
        project_name_to_use = str(uuid.uuid4())
        # If no project name, core function expects the full path to be the target directory
        repo_path_to_initialize_at = repo_base_path / project_name_to_use
        # In this case, project_name argument to core_initialize_repository should be None
        # because the target directory name (UUID) is already part of repo_path_to_initialize_at
        # core_initialize_repository(path_str=str(repo_path_to_initialize_at), project_name=None)

    try:
        # Ensure the base directory for user repositories exists
        repo_base_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create base repository directory: {e}")

    # Call the core function
    # If request_data.project_name was provided, core_initialize_repository will create path_str / project_name
    # If not, we constructed the full path (repo_base_path / uuid_str) and pass project_name=None
    core_project_name_arg = request_data.project_name if request_data.project_name else None
    core_path_str_arg = str(repo_base_path) if request_data.project_name else str(repo_path_to_initialize_at)

    result = core_initialize_repository(
        path_str=core_path_str_arg,
        project_name=core_project_name_arg
    )

    if result['status'] == 'success':
        # 'path' from core is the absolute path to the initialized repo
        created_repo_path = result.get('path', str(repo_base_path / project_name_to_use)) # Fallback, but core should provide it
        return RepositoryCreateResponse(
            status="created",
            message=result.get('message', f"Repository '{project_name_to_use}' initialized successfully."),
            repository_id=project_name_to_use, # This is the dir name (project_name or UUID)
            path=created_repo_path
        )
    elif "already exists" in result.get("message", "").lower() and \
         "not empty" in result.get("message", "").lower() and \
         "not a git repository" in result.get("message", "").lower():
        # This condition specifically targets the case where the directory exists and is not a valid init target
        raise HTTPException(status_code=409, detail=result.get('message', "Repository directory conflict."))
    elif result['status'] == 'error':
        # Check for other specific error messages that might warrant a 400 vs 500
        if "a file named" in result.get("message", "").lower() and "already exists" in result.get("message", "").lower():
            raise HTTPException(status_code=409, detail=result.get('message')) # File conflict
        # Default to 500 for other core errors during initialization
        raise HTTPException(status_code=500, detail=result.get('message', "Failed to initialize repository due to a core error."))
    else:
        # Should not be reached if core function adheres to 'success' or 'error' statuses
        raise HTTPException(status_code=500, detail=f"Unexpected response from repository initialization: {result.get('message', 'Unknown error')}")

@router.post("/ignore", response_model=IgnoreAddResponse)
async def api_add_ignore_pattern(
    request_data: IgnorePatternRequest,
    current_user: User = Depends(get_current_active_user)
):
    """
    Adds a new pattern to the .gitignore file in the repository.
    Requires authentication.
    """
    repo_path = PLACEHOLDER_REPO_PATH
    pattern = request_data.pattern.strip() # Ensure leading/trailing whitespace is removed

    if not pattern: # Double check, though Pydantic model has min_length=1
        raise HTTPException(status_code=400, detail="Pattern cannot be empty.")

    try:
        result = core_add_pattern_to_gitignore(
            repo_path_str=repo_path,
            pattern=pattern
        )

        if not isinstance(result, dict):
            raise ValueError(f"Core function core_add_pattern_to_gitignore returned non-dict: {type(result)}")
        if 'status' not in result:
            raise ValueError("Core function core_add_pattern_to_gitignore result missing 'status' key")

        # Core function returns:
        # {'status': 'success', 'message': 'Pattern added.'}
        # {'status': 'exists', 'message': 'Pattern already exists.'}
        # {'status': 'error', 'message': 'Error writing to .gitignore: ...'}
        # {'status': 'error', 'message': 'Pattern cannot be empty.'} (handled above, but core might also return)

        if result['status'] == 'success':
            return IgnoreAddResponse(
                status=result['status'],
                message=result['message']
            )
        elif result['status'] == 'exists':
            error_message = result.get('message', 'Pattern already exists in .gitignore.')
            raise HTTPException(status_code=409, detail=str(error_message))
        elif result['status'] == 'error':
            # Distinguish between client error (empty pattern) and server error (I/O)
            error_message_core = result.get('message', '') # Use .get for safety
            if "Pattern cannot be empty" in error_message_core: # Specific check for empty pattern error from core
                raise HTTPException(status_code=400, detail=str(error_message_core))
            # Other errors are likely server-side I/O issues or unexpected problems
            raise HTTPException(status_code=500, detail=str(error_message_core)) # Return specific core message for other errors
        else:
            # Should not happen
            raise HTTPException(status_code=500, detail="Unknown error from core ignore add operation.")

    # Removed generic Exception catchers to let HTTPExceptions propagate naturally
    # and to reveal any other unexpected errors directly.
    except CoreRepositoryNotFoundError: # Should not happen with placeholder
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    # Note: Specific business logic exceptions from core layer (if any) should be caught if they are not already
    # handled by the result['status'] checks. For now, focusing on existing structure.
