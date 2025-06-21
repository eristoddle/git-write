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
from gitwrite_core.exceptions import (
    RepositoryNotFoundError as CoreRepositoryNotFoundError, # Alias to avoid conflict with potential local one
    RepositoryEmptyError as CoreRepositoryEmptyError,
    BranchAlreadyExistsError as CoreBranchAlreadyExistsError,
    BranchNotFoundError as CoreBranchNotFoundError,
    GitWriteError as CoreGitWriteError
)


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
