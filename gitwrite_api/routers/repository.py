from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import datetime # For commit date serialization

# TODO: Make this configurable or dynamically determined per user/request
PLACEHOLDER_REPO_PATH = "/path/to/user/repo"

# Import core functions
from gitwrite_core.repository import list_branches, list_tags, list_commits, save_and_commit_file

# Import security dependency (assuming path based on project structure)
# Adjust the import path if your security module is located differently.
# For this example, let's assume a flat structure for simplicity or direct placement:
# from ..security import get_current_active_user
# from ..models import User  # If User model is needed for dependency

# Placeholder for security dependency - replace with actual import
# from gitwrite_api.security import get_current_active_user
# from gitwrite_api.models import User # Example, if User model is needed by get_current_active_user
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
    GitWriteError as CoreGitWriteError,
    DetachedHeadError as CoreDetachedHeadError, # Added for merge, also used by sync
    CommitNotFoundError as CoreCommitNotFoundError, # Added for compare, also used by revert
    NotEnoughHistoryError as CoreNotEnoughHistoryError, # Added for compare
    RemoteNotFoundError as CoreRemoteNotFoundError, # For sync
    FetchError as CoreFetchError, # For sync
    PushError as CorePushError # For sync
)
from gitwrite_core.branching import merge_branch_into_current # Core function for merge
from gitwrite_core.versioning import get_diff as core_get_diff # Core function for compare
# from gitwrite_core.exceptions import CommitNotFoundError as CoreCommitNotFoundError # Already imported above
# from gitwrite_core.exceptions import NotEnoughHistoryError as CoreNotEnoughHistoryError # Already imported above
from gitwrite_core.tagging import create_tag as core_create_tag # Core function for tagging
from gitwrite_core.exceptions import TagAlreadyExistsError as CoreTagAlreadyExistsError # For tagging


# For now, let's define a placeholder dependency to make the code runnable without the actual security module
async def get_current_active_user(): # Placeholder
    # In a real app, this would verify a token and return a user model
    return {"username": "testuser", "email": "test@example.com", "active": True}

class User(BaseModel): # Placeholder Pydantic model for User
    username: str
    email: Optional[str] = None
    active: Optional[bool] = None


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
    patch_text: str = Field(..., description="The diff/patch output as a string.")

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
    current_user: User = Depends(get_current_active_user)
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
        # Core function returns:
        # {
        #     "ref1_oid": str,
        #     "ref2_oid": str,
        #     "ref1_display_name": str,
        #     "ref2_display_name": str,
        #     "patch_text": str
        # }
        return CompareRefsResponse(
            ref1_oid=diff_result["ref1_oid"],
            ref2_oid=diff_result["ref2_oid"],
            ref1_display_name=diff_result["ref1_display_name"],
            ref2_display_name=diff_result["ref2_display_name"],
            patch_text=diff_result["patch_text"]
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
        # Need to import pygit2 for Signature
        try:
            # Attempt to import pygit2. If it's not available in this environment,
            # this would be a server-side issue. For now, assume it's available.
            import pygit2
            tagger_signature = pygit2.Signature(user_name, user_email)
        except ImportError:
            # This should ideally not happen in a deployed environment.
            # If pygit2 is missing, core functions would fail much earlier.
            # However, defensive coding suggests handling it.
            raise HTTPException(status_code=500, detail="Server configuration error: pygit2 library not available.")


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
