from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, Dict, Optional, List
from pydantic import BaseModel, Field
import datetime # For commit date serialization

# TODO: Make this configurable or dynamically determined per user/request
PLACEHOLDER_REPO_PATH = "/path/to/user/repo"

# Import core functions
from gitwrite_core.repository import list_branches, list_tags, list_commits

# Import security dependency (assuming path based on project structure)
# Adjust the import path if your security module is located differently.
# For this example, let's assume a flat structure for simplicity or direct placement:
# from ..security import get_current_active_user
# from ..models import User  # If User model is needed for dependency

# Placeholder for security dependency - replace with actual import
# from gitwrite_api.security import get_current_active_user
# from gitwrite_api.models import User # Example, if User model is needed by get_current_active_user

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
