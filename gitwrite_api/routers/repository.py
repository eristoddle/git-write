from fastapi import APIRouter, Depends, HTTPException, Query, Body
from typing import Any, Dict, Optional, List, Union
from pydantic import BaseModel, Field
import datetime # For commit date serialization
import pygit2 # Moved import to top
from http import HTTPStatus # Moved to top

# TODO: Make this configurable or dynamically determined per user/request
PLACEHOLDER_REPO_PATH = "/tmp/gitwrite_repos_api"

# Import core functions
from gitwrite_core.repository import (
    list_branches, list_tags, list_commits, save_and_commit_file,
    list_gitignore_patterns as core_list_gitignore_patterns,
    add_pattern_to_gitignore as core_add_pattern_to_gitignore,
    initialize_repository as core_initialize_repository,
    get_file_content_at_commit as core_get_file_content_at_commit,
    get_repository_metadata as core_get_repository_metadata,
    list_repository_tree as core_list_repository_tree
)
from gitwrite_core.versioning import (
    get_branch_review_commits as core_get_branch_review_commits,
    cherry_pick_commit as core_cherry_pick_commit
)

# Import security dependency (assuming path based on project structure)
from ..security import get_current_active_user, require_role # Actual import
from ..models import User, UserRole, FileContentResponse # Import the canonical User model and UserRole
from ..models import SaveFileRequest, SaveFileResponse # Added for the new save endpoint

# Import core branching functions and exceptions
from gitwrite_core.branching import create_and_switch_branch, switch_to_branch
from gitwrite_core.versioning import revert_commit as core_revert_commit # Core function for revert
from gitwrite_core.repository import sync_repository as core_sync_repository # Core function for sync
from gitwrite_core.exceptions import (
    RepositoryNotFoundError as CoreRepositoryNotFoundError,
    RepositoryEmptyError as CoreRepositoryEmptyError,
    BranchAlreadyExistsError as CoreBranchAlreadyExistsError,
    BranchNotFoundError as CoreBranchNotFoundError,
    MergeConflictError as CoreMergeConflictError,
    GitWriteError as CoreGitWriteError,
    DetachedHeadError as CoreDetachedHeadError,
    CommitNotFoundError as CoreCommitNotFoundError,
    NotEnoughHistoryError as CoreNotEnoughHistoryError,
    RemoteNotFoundError as CoreRemoteNotFoundError,
    FetchError as CoreFetchError,
    PushError as CorePushError,
    FileNotFoundInCommitError as CoreFileNotFoundInCommitError
)
from gitwrite_core.branching import merge_branch_into_current
from gitwrite_core.versioning import get_diff as core_get_diff, get_word_level_diff as core_get_word_level_diff
from gitwrite_core.tagging import create_tag as core_create_tag
from gitwrite_core.exceptions import TagAlreadyExistsError as CoreTagAlreadyExistsError

# For Repository Initialization
import uuid
import os
from pathlib import Path
from ..models import RepositoryCreateRequest, RepositoriesListResponse, RepositoryListItem, RepositoryTreeResponse

# Models for Branch Review API
from ..models import BranchReviewResponse, BranchReviewCommit

# Models for Cherry-Pick API
from ..models import CherryPickRequest, CherryPickResponse

# Models for EPUB Export API
from ..models import EPUBExportRequest, EPUBExportResponse

# Models for PDF and DOCX Export APIs
from ..models import PDFExportRequest, PDFExportResponse, DOCXExportRequest, DOCXExportResponse


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
    author_date: datetime.datetime
    committer_name: str
    committer_email: str
    committer_date: datetime.datetime
    parents: List[str]

class CommitListResponse(BaseModel):
    status: str
    commits: List[CommitDetail]
    message: str

class BranchCreateRequest(BaseModel):
    branch_name: str = Field(..., min_length=1, description="Name of the branch to create.")

class BranchSwitchRequest(BaseModel):
    branch_name: str = Field(..., min_length=1, description="Name of the branch to switch to.")

class BranchResponse(BaseModel):
    status: str
    branch_name: str
    message: str
    head_commit_oid: Optional[str] = None
    previous_branch_name: Optional[str] = None
    is_detached: Optional[bool] = None

class MergeBranchRequest(BaseModel):
    source_branch: str = Field(..., min_length=1, description="Name of the branch to merge into the current branch.")

class MergeBranchResponse(BaseModel):
    status: str = Field(..., description="Outcome of the merge operation (e.g., 'merged_ok', 'fast_forwarded', 'up_to_date', 'conflict').")
    message: str = Field(..., description="Detailed message about the merge outcome.")
    current_branch: Optional[str] = Field(None, description="The current branch after the merge attempt.")
    merged_branch: Optional[str] = Field(None, description="The branch that was merged.")
    commit_oid: Optional[str] = Field(None, description="The OID of the new merge commit, if one was created.")
    conflicting_files: Optional[List[str]] = Field(None, description="List of files with conflicts, if any.")

class CompareRefsResponse(BaseModel):
    ref1_oid: str = Field(..., description="Resolved OID of the first reference.")
    ref2_oid: str = Field(..., description="Resolved OID of the second reference.")
    ref1_display_name: str = Field(..., description="Display name for the first reference.")
    ref2_display_name: str = Field(..., description="Display name for the second reference.")
    patch_text: Union[str, List[Dict[str, Any]]] = Field(..., description="The diff/patch output, either as a raw string or a structured list of dictionaries for word-level diff.")

class RevertCommitRequest(BaseModel):
    commit_ish: str = Field(..., min_length=1, description="The commit reference (hash, branch, tag) to revert.")

class RevertCommitResponse(BaseModel):
    status: str = Field(..., description="Outcome of the revert operation (e.g., 'success').")
    message: str = Field(..., description="Detailed message about the revert outcome.")
    new_commit_oid: Optional[str] = Field(None, description="The OID of the new commit created by the revert, if successful.")

class SyncFetchStatus(BaseModel):
    received_objects: Optional[int] = None
    total_objects: Optional[int] = None
    message: str

class SyncLocalUpdateStatus(BaseModel):
    type: str
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
    if response["status"] == success_status or (success_status=="success" and response["status"] in ["no_tags", "empty_repo", "no_commits"]):
        return response
    elif response["status"] == "not_found" or response["status"] == "empty_repo" and "branch" in response.get("message","").lower():
        raise HTTPException(status_code=404, detail=response.get("message", "Resource not found."))
    elif response["status"] == "error":
        raise HTTPException(status_code=500, detail=response.get("message", "An internal server error occurred."))
    elif response["status"] == "empty_repo":
        return response
    else:
        raise HTTPException(status_code=400, detail=response.get("message", "Bad request or invalid operation."))

@router.get("/{repo_name}/branches", response_model=BranchListResponse)
async def api_list_branches(
    repo_name: str,
    current_user: User = Depends(get_current_active_user)
):
    # Resolve repo_name to the actual repository path
    repo_path = str(Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos" / repo_name)
    result = list_branches(repo_path_str=repo_path)
    return handle_core_response(result)

@router.get("/tags", response_model=TagListResponse)
async def api_list_tags(current_user: User = Depends(get_current_active_user)):
    repo_path = PLACEHOLDER_REPO_PATH
    result = list_tags(repo_path_str=repo_path)
    return handle_core_response(result)

@router.get("/{repo_name}/commits", response_model=CommitListResponse)
async def api_list_commits(
    repo_name: str,
    branch_name: Optional[str] = Query(None, description="Name of the branch to list commits from. Defaults to current HEAD."),
    max_count: Optional[int] = Query(None, description="Maximum number of commits to return.", gt=0),
    current_user: User = Depends(get_current_active_user)
):
    # Resolve repo_name to the actual repository path
    repo_path = str(Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos" / repo_name)
    result = list_commits(
        repo_path_str=repo_path,
        branch_name=branch_name,
        max_count=max_count
    )
    return handle_core_response(result)

@router.post("/{repo_name}/save", response_model=SaveFileResponse)
async def api_save_file(
    repo_name: str,
    save_request: SaveFileRequest = Body(...),
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.WRITER]))
):
    # Resolve repo_name to the actual repository path
    repo_path = str(Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos" / repo_name)
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
            commit_id=result.get('commit_id')
        )
    else:
        status_code = 400
        if "Repository not found" in result.get("message", ""):
            status_code = 500
        elif "Error committing file" in result.get("message", "") and "Repository not found" not in result.get("message",""):
             status_code = 500
        elif "Error staging file" in result.get("message", ""):
            status_code = 500
        raise HTTPException(
            status_code=status_code,
            detail=result.get('message', "An error occurred while saving the file.")
        )

@router.post("/{repo_name}/branches", response_model=BranchResponse, status_code=201)
async def api_create_branch(
    repo_name: str,
    request_data: BranchCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    # Resolve repo_name to the actual repository path
    repo_path = str(Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos" / repo_name)
    try:
        result = create_and_switch_branch(
            repo_path_str=repo_path,
            branch_name=request_data.branch_name
        )
        return BranchResponse(
            status="created",
            branch_name=result['branch_name'],
            message=f"Branch '{result['branch_name']}' created and switched to successfully.",
            head_commit_oid=result['head_commit_oid']
        )
    except CoreBranchAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CoreRepositoryEmptyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        raise HTTPException(status_code=500, detail=f"Failed to create branch: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.put("/{repo_name}/branch", response_model=BranchResponse)
async def api_switch_branch(
    repo_name: str,
    request_data: BranchSwitchRequest,
    current_user: User = Depends(get_current_active_user)
):
    # Resolve repo_name to the actual repository path
    repo_path = str(Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos" / repo_name)
    try:
        result = switch_to_branch(
            repo_path_str=repo_path,
            branch_name=request_data.branch_name
        )
        message = ""
        if result['status'] == 'success':
            message = f"Switched to branch '{result['branch_name']}' successfully."
        elif result['status'] == 'already_on_branch':
            message = f"Already on branch '{result['branch_name']}'."
        else:
            message = "Branch switch operation completed with an unknown status."
        return BranchResponse(
            status=result['status'],
            branch_name=result['branch_name'],
            message=message,
            head_commit_oid=result.get('head_commit_oid'),
            previous_branch_name=result.get('previous_branch_name'),
            is_detached=result.get('is_detached')
        )
    except CoreBranchNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreRepositoryEmptyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        if "local changes overwrite" in str(e).lower() or "unstaged changes" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Switch failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to switch branch: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.post("/{repo_name}/merges", response_model=MergeBranchResponse)
async def api_merge_branch(
    repo_name: str,
    request_data: MergeBranchRequest,
    current_user: User = Depends(get_current_active_user)
):
    # Resolve repo_name to the actual repository path
    repo_path = str(Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos" / repo_name)
    try:
        result = merge_branch_into_current(
            repo_path_str=repo_path,
            branch_to_merge_name=request_data.source_branch
        )
        response_status = result['status']
        message = ""
        if response_status == 'up_to_date':
            message = f"Current branch '{result['current_branch']}' is already up-to-date with '{result['branch_name']}'."
        elif response_status == 'fast_forwarded':
            message = f"Branch '{result['branch_name']}' was fast-forwarded into '{result['current_branch']}'."
        elif response_status == 'merged_ok':
            message = f"Branch '{result['branch_name']}' was successfully merged into '{result['current_branch']}'."
        else:
            message = "Merge operation completed with an unknown status."
            response_status = "unknown_core_status"
        return MergeBranchResponse(
            status=response_status,
            message=message,
            current_branch=result.get('current_branch'),
            merged_branch=result.get('branch_name'),
            commit_oid=result.get('commit_oid')
        )
    except CoreBranchNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreRepositoryEmptyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreDetachedHeadError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        if type(e).__name__ == 'MergeConflictError' and hasattr(e, 'conflicting_files'):
            detail_payload = {
                "status": "conflict",
                "message": str(e.message),
                "conflicting_files": e.conflicting_files,
                "current_branch": getattr(e, 'current_branch_name', None),
                "merged_branch": getattr(e, 'merged_branch_name', request_data.source_branch)
            }
            cleaned_detail_payload = {k: v for k, v in detail_payload.items() if v is not None}
            raise HTTPException(status_code=409, detail=cleaned_detail_payload)
        else:
            raise HTTPException(status_code=400, detail=f"Merge operation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during merge: {str(e)}")

@router.get("/compare", response_model=CompareRefsResponse)
async def api_compare_refs(
    ref1: Optional[str] = Query(None, description="The first reference (e.g., commit hash, branch, tag). Defaults to HEAD~1."),
    ref2: Optional[str] = Query(None, description="The second reference (e.g., commit hash, branch, tag). Defaults to HEAD."),
    diff_mode: Optional[str] = Query(None, description="Set to 'word' for word-level diff."),
    current_user: User = Depends(get_current_active_user)
):
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        diff_result = core_get_diff(
            repo_path_str=repo_path,
            ref1_str=ref1,
            ref2_str=ref2
        )
        diff_output: Union[str, List[Dict[str, Any]]]
        if diff_mode == 'word':
            if diff_result["patch_text"]:
                diff_output = core_get_word_level_diff(diff_result["patch_text"])
            else:
                diff_output = []
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
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        raise HTTPException(status_code=500, detail=f"Compare operation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during compare: {str(e)}")

@router.post("/revert", response_model=RevertCommitResponse)
async def api_revert_commit(
    request_data: RevertCommitRequest,
    current_user: User = Depends(get_current_active_user)
):
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_revert_commit(
            repo_path_str=repo_path,
            commit_ish_to_revert=request_data.commit_ish
        )
        return RevertCommitResponse(
            status=result['status'],
            message=result['message'],
            new_commit_oid=result.get('new_commit_oid')
        )
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreMergeConflictError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Revert failed due to conflicts: {str(e)}. The working directory should be clean."
        )
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreRepositoryEmptyError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except CoreGitWriteError as e:
        if "Cannot revert commit" in str(e) and "no parents" in str(e):
             raise HTTPException(status_code=400, detail=str(e))
        raise HTTPException(status_code=400, detail=f"Revert operation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during revert: {str(e)}")

@router.post("/sync", response_model=SyncRepositoryResponse)
async def api_sync_repository(
    request_data: SyncRepositoryRequest,
    current_user: User = Depends(get_current_active_user)
):
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_sync_repository(
            repo_path_str=repo_path,
            remote_name=request_data.remote_name,
            branch_name_opt=request_data.branch_name,
            push=request_data.push,
            allow_no_push=request_data.allow_no_push
        )
        return SyncRepositoryResponse(
            status=result["status"],
            branch_synced=result.get("branch_synced"),
            remote=result["remote"],
            fetch_status=SyncFetchStatus(**result["fetch_status"]),
            local_update_status=SyncLocalUpdateStatus(**result["local_update_status"]),
            push_status=SyncPushStatus(**result["push_status"])
        )
    except CoreMergeConflictError as e:
        raise HTTPException(
            status_code=409,
            detail={
                "message": f"Sync failed due to merge conflicts: {str(e.message)}",
                "conflicting_files": e.conflicting_files if hasattr(e, 'conflicting_files') else [],
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
        raise HTTPException(status_code=503, detail=f"Fetch operation failed: {str(e)}")
    except CorePushError as e:
        if "non-fast-forward" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Push rejected (non-fast-forward): {str(e)}. Try syncing again.")
        raise HTTPException(status_code=503, detail=f"Push operation failed: {str(e)}")
    except CoreGitWriteError as e:
        raise HTTPException(status_code=400, detail=f"Sync operation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during sync: {str(e)}")

@router.post("/tags", response_model=TagCreateResponse, status_code=201)
async def api_create_tag(
    request_data: TagCreateRequest,
    current_user: User = Depends(get_current_active_user)
):
    repo_path = PLACEHOLDER_REPO_PATH
    tagger_signature = None
    if request_data.message:
        user_name = current_user.username if hasattr(current_user, 'username') and current_user.username else "GitWrite API User"
        user_email = current_user.email if hasattr(current_user, 'email') and current_user.email else "api@gitwrite.com"
        try:
            tagger_signature = pygit2.Signature(user_name, user_email)
        except pygit2.GitError as e:
            raise HTTPException(status_code=400, detail=f"Failed to create tagger signature due to invalid user details: {str(e)}")
        except TypeError as e:
            if 'dev/string_type' in str(e):
                raise HTTPException(status_code=500, detail="Server configuration error: pygit2 library not available or misconfigured.")
            raise HTTPException(status_code=500, detail=f"Unexpected error creating tagger signature: {str(e)}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unexpected error creating tagger signature: {str(e)}")
    try:
        result = core_create_tag(
            repo_path_str=repo_path,
            tag_name=request_data.tag_name,
            target_commit_ish=request_data.commit_ish,
            message=request_data.message,
            force=request_data.force,
            tagger=tagger_signature
        )
        return TagCreateResponse(
            status="created",
            tag_name=result['name'],
            tag_type=result['type'],
            target_commit_oid=result['target'],
            message=result.get('message')
        )
    except CoreTagAlreadyExistsError as e:
        raise HTTPException(status_code=409, detail=str(e))
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        raise HTTPException(status_code=400, detail=f"Tag creation failed: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during tag creation: {str(e)}")

@router.get("/ignore", response_model=IgnoreListResponse)
async def api_list_ignore_patterns(current_user: User = Depends(get_current_active_user)):
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_list_gitignore_patterns(repo_path_str=repo_path)
        if not isinstance(result, dict):
            raise ValueError(f"Core function core_list_gitignore_patterns returned non-dict: {type(result)}")
        if 'status' not in result:
            raise ValueError("Core function core_list_gitignore_patterns result missing 'status' key")
        if result['status'] == 'success':
            return IgnoreListResponse(
                status=result['status'],
                patterns=result['patterns'],
                message=result['message']
            )
        elif result['status'] == 'not_found' or result['status'] == 'empty':
            return IgnoreListResponse(
                status=result['status'],
                patterns=[],
                message=result['message']
            )
        elif result['status'] == 'error':
            error_message = result.get('message', 'An error occurred while listing ignore patterns.')
            raise HTTPException(status_code=500, detail=str(error_message))
        else:
            raise HTTPException(status_code=500, detail="Unknown error from core ignore listing.")
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")

@router.get("s", response_model=RepositoriesListResponse)
async def api_list_repositories(
    current_user: User = Depends(get_current_active_user)
):
    user_repos_base_dir = Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos"
    if not user_repos_base_dir.exists() or not user_repos_base_dir.is_dir():
        return RepositoriesListResponse(repositories=[], count=0)
    repo_items: List[RepositoryListItem] = []
    try:
        for item_name in os.listdir(user_repos_base_dir):
            item_path = user_repos_base_dir / item_name
            if item_path.is_dir():
                metadata_dict = core_get_repository_metadata(item_path)
                if metadata_dict:
                    try:
                        repo_list_item = RepositoryListItem(**metadata_dict)
                        repo_items.append(repo_list_item)
                    except Exception as e:
                        pass
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Error accessing repository storage: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred while listing repositories: {e}")
    return RepositoriesListResponse(repositories=repo_items, count=len(repo_items))

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
        # Core function now returns a dict on success, or raises specific exceptions on failure.
        content_details = core_get_file_content_at_commit(
            repo_path_str=repo_path,
            file_path=file_path,
            commit_sha_str=commit_sha
        )
        # If no exception was raised, it's a success
        return FileContentResponse(
            file_path=content_details['file_path'],
            commit_sha=content_details['commit_sha'],
            content=content_details['content'],
            size=content_details['size'],
            mode=content_details['mode'],
            is_binary=content_details['is_binary']
        )
    except CoreFileNotFoundInCommitError as e:
        # Check if the message indicates it's a tree (directory)
        if "is not a file" in str(e).lower() and "tree" in str(e).lower():
            raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e))
        else: # Actual file not found
            raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e))
    except CoreCommitNotFoundError as e: # Commit not found
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e))
    except CoreRepositoryNotFoundError as e: # Bad repository path configuration issue
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
    except CoreGitWriteError as e: # Catch other specific core errors
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=str(e))
    except Exception as e:
        # Fallback for any other unexpected errors not caught above.
        # Log this error for review: logger.error(f"Unexpected error in api_get_file_content: {e}", exc_info=True)
        raise HTTPException(status_code=HTTPStatus.INTERNAL_SERVER_ERROR, detail=f"An unexpected server error occurred: {str(e)}")

@router.post("/export/epub", response_model=EPUBExportResponse)
async def api_export_to_epub(
    request_data: EPUBExportRequest,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.WRITER, UserRole.BETA_READER]))
):
    repo_path_str = PLACEHOLDER_REPO_PATH
    export_base_dir = Path(PLACEHOLDER_REPO_PATH) / "exports"
    try:
        export_base_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create base export directory: {str(e)}")
    job_id = str(uuid.uuid4())
    job_export_dir = export_base_dir / job_id
    try:
        job_export_dir.mkdir(exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create unique export job directory: {str(e)}")
    actual_output_filename = request_data.output_filename if request_data.output_filename else "export.epub"
    output_epub_server_path = job_export_dir / actual_output_filename
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
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred during EPUB export: {str(e)}")

@router.post("/export/pdf", response_model=PDFExportResponse)
async def api_export_to_pdf(
    request_data: PDFExportRequest,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.WRITER, UserRole.BETA_READER]))
):
    repo_path_str = PLACEHOLDER_REPO_PATH
    export_base_dir = Path(PLACEHOLDER_REPO_PATH) / "exports"
    try:
        export_base_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create base export directory: {str(e)}")
    job_id = str(uuid.uuid4())
    job_export_dir = export_base_dir / job_id
    try:
        job_export_dir.mkdir(exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create unique export job directory: {str(e)}")
    actual_output_filename = request_data.output_filename if request_data.output_filename else "export.pdf"
    output_pdf_server_path = job_export_dir / actual_output_filename
    from gitwrite_core.export import export_to_pdf
    from gitwrite_core.exceptions import PandocError, FileNotFoundInCommitError
    try:
        # Prepare PDF-specific options
        pandoc_options = {}
        if request_data.pdf_engine:
            pandoc_options['extra_args'] = ['--standalone', f'--pdf-engine={request_data.pdf_engine}']
        
        result = export_to_pdf(
            repo_path_str=repo_path_str,
            commit_ish_str=request_data.commit_ish,
            file_list=request_data.file_list,
            output_pdf_path_str=str(output_pdf_server_path.resolve()),
            **pandoc_options
        )
        if result["status"] == "success":
            return PDFExportResponse(
                status="success",
                message=result["message"],
                server_file_path=str(output_pdf_server_path.resolve())
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "PDF export failed due to an unknown core error."))
    except CoreRepositoryNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Repository not found or configuration error: {str(e)}")
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Commit not found: {str(e)}")
    except FileNotFoundInCommitError as e:
        raise HTTPException(status_code=404, detail=f"File not found in commit: {str(e)}")
    except PandocError as e:
        if "Pandoc not found" in str(e):
            raise HTTPException(status_code=503, detail=f"PDF generation service unavailable: Pandoc not found. {str(e)}")
        elif "pdflatex not found" in str(e) or "LaTeX" in str(e):
            raise HTTPException(status_code=503, detail=f"PDF generation service unavailable: LaTeX engine not found. {str(e)}")
        else:
            raise HTTPException(status_code=400, detail=f"PDF conversion failed: {str(e)}")
    except CoreGitWriteError as e:
        raise HTTPException(status_code=400, detail=f"PDF export failed due to a GitWrite core error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred during PDF export: {str(e)}")

@router.post("/export/docx", response_model=DOCXExportResponse)
async def api_export_to_docx(
    request_data: DOCXExportRequest,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.WRITER, UserRole.BETA_READER]))
):
    repo_path_str = PLACEHOLDER_REPO_PATH
    export_base_dir = Path(PLACEHOLDER_REPO_PATH) / "exports"
    try:
        export_base_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create base export directory: {str(e)}")
    job_id = str(uuid.uuid4())
    job_export_dir = export_base_dir / job_id
    try:
        job_export_dir.mkdir(exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create unique export job directory: {str(e)}")
    actual_output_filename = request_data.output_filename if request_data.output_filename else "export.docx"
    output_docx_server_path = job_export_dir / actual_output_filename
    from gitwrite_core.export import export_to_docx
    from gitwrite_core.exceptions import PandocError, FileNotFoundInCommitError
    try:
        result = export_to_docx(
            repo_path_str=repo_path_str,
            commit_ish_str=request_data.commit_ish,
            file_list=request_data.file_list,
            output_docx_path_str=str(output_docx_server_path.resolve())
        )
        if result["status"] == "success":
            return DOCXExportResponse(
                status="success",
                message=result["message"],
                server_file_path=str(output_docx_server_path.resolve())
            )
        else:
            raise HTTPException(status_code=500, detail=result.get("message", "DOCX export failed due to an unknown core error."))
    except CoreRepositoryNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Repository not found or configuration error: {str(e)}")
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Commit not found: {str(e)}")
    except FileNotFoundInCommitError as e:
        raise HTTPException(status_code=404, detail=f"File not found in commit: {str(e)}")
    except PandocError as e:
        if "Pandoc not found" in str(e):
            raise HTTPException(status_code=503, detail=f"DOCX generation service unavailable: Pandoc not found. {str(e)}")
        else:
            raise HTTPException(status_code=400, detail=f"DOCX conversion failed: {str(e)}")
    except CoreGitWriteError as e:
        raise HTTPException(status_code=400, detail=f"DOCX export failed due to a GitWrite core error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected server error occurred during DOCX export: {str(e)}")

@router.get("/review/{branch_name}", response_model=BranchReviewResponse)
async def api_review_branch_commits(
    branch_name: str,
    limit: Optional[int] = Query(None, description="Maximum number of commits to return.", gt=0),
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.BETA_READER]))
):
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        commits_list_core = core_get_branch_review_commits(
            repo_path_str=repo_path,
            branch_name_to_review=branch_name,
            limit=limit
        )
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
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error or not found.")
    except CoreGitWriteError as e:
        if "HEAD is unborn" in str(e):
            raise HTTPException(status_code=400, detail=f"Cannot review branch: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to review branch commits: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@router.post("/cherry-pick", response_model=CherryPickResponse)
async def api_cherry_pick_commit(
    request_data: CherryPickRequest,
    current_user: User = Depends(get_current_active_user)
):
    repo_path = PLACEHOLDER_REPO_PATH
    try:
        result = core_cherry_pick_commit(
            repo_path_str=repo_path,
            commit_oid_to_pick=request_data.commit_id,
            mainline=request_data.mainline
        )
        return CherryPickResponse(
            status=result['status'],
            message=result['message'],
            new_commit_oid=result.get('new_commit_oid')
        )
    except CoreCommitNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except CoreMergeConflictError as e:
        return CherryPickResponse(
            status="conflict",
            message=str(e.message),
            new_commit_oid=None,
            conflicting_files=e.conflicting_files if hasattr(e, 'conflicting_files') else []
        )
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")
    except CoreGitWriteError as e:
        error_detail = str(e)
        if "unborn HEAD" in error_detail or \
           "merge commit" in error_detail or \
           "mainline" in error_detail or \
           "bare repository" in error_detail:
            raise HTTPException(status_code=400, detail=error_detail)
        raise HTTPException(status_code=400, detail=f"Cherry-pick operation failed: {error_detail}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during cherry-pick: {str(e)}")

@router.post("/repositories", response_model=RepositoryCreateResponse, status_code=201)
async def api_initialize_repository(
    request_data: RepositoryCreateRequest,
    current_user: User = Depends(require_role([UserRole.OWNER]))
):
    repo_base_path = Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos"
    project_name_to_use: str
    if request_data.project_name:
        if not request_data.project_name.isalnum() and '_' not in request_data.project_name and '-' not in request_data.project_name:
             raise HTTPException(status_code=400, detail="Invalid project_name. Only alphanumeric, hyphens, and underscores are allowed.")
        project_name_to_use = request_data.project_name
        repo_path_to_initialize_at = repo_base_path
    else:
        project_name_to_use = str(uuid.uuid4())
        repo_path_to_initialize_at = repo_base_path / project_name_to_use
    try:
        repo_base_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Could not create base repository directory: {e}")
    core_project_name_arg = request_data.project_name if request_data.project_name else None
    core_path_str_arg = str(repo_base_path) if request_data.project_name else str(repo_path_to_initialize_at)
    result = core_initialize_repository(
        path_str=core_path_str_arg,
        project_name=core_project_name_arg
    )
    if result['status'] == 'success':
        created_repo_path = result.get('path', str(repo_base_path / project_name_to_use))
        return RepositoryCreateResponse(
            status="created",
            message=result.get('message', f"Repository '{project_name_to_use}' initialized successfully."),
            repository_id=project_name_to_use,
            path=created_repo_path
        )
    elif "already exists" in result.get("message", "").lower() and \
         "not empty" in result.get("message", "").lower() and \
         "not a git repository" in result.get("message", "").lower():
        raise HTTPException(status_code=409, detail=result.get('message', "Repository directory conflict."))
    elif result['status'] == 'error':
        if "a file named" in result.get("message", "").lower() and "already exists" in result.get("message", "").lower():
            raise HTTPException(status_code=409, detail=result.get('message'))
        raise HTTPException(status_code=500, detail=result.get('message', "Failed to initialize repository due to a core error."))
    else:
        raise HTTPException(status_code=500, detail=f"Unexpected response from repository initialization: {result.get('message', 'Unknown error')}")

@router.post("/ignore", response_model=IgnoreAddResponse)
async def api_add_ignore_pattern(
    request_data: IgnorePatternRequest,
    current_user: User = Depends(get_current_active_user)
):
    repo_path = PLACEHOLDER_REPO_PATH
    pattern = request_data.pattern.strip()
    if not pattern:
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
        if result['status'] == 'success':
            return IgnoreAddResponse(
                status=result['status'],
                message=result['message']
            )
        elif result['status'] == 'exists':
            error_message = result.get('message', 'Pattern already exists in .gitignore.')
            raise HTTPException(status_code=409, detail=str(error_message))
        elif result['status'] == 'error':
            error_message_core = result.get('message', '')
            if "Pattern cannot be empty" in error_message_core:
                raise HTTPException(status_code=400, detail=str(error_message_core))
            raise HTTPException(status_code=500, detail=str(error_message_core))
        else:
            raise HTTPException(status_code=500, detail="Unknown error from core ignore add operation.")
    except CoreRepositoryNotFoundError:
        raise HTTPException(status_code=500, detail="Repository configuration error.")


@router.get("/{repo_name}/tree/{ref:path}", response_model=RepositoryTreeResponse)
async def api_list_repository_tree(
    repo_name: str,
    ref: str,
    path: str = Query("", description="Path within the repository (optional, defaults to root)"),
    current_user: User = Depends(get_current_active_user)
):
    """
    Lists files and folders in a repository at a specific reference and path.
    
    Args:
        repo_name: Name of the repository
        ref: Git reference (branch, tag, or commit SHA)
        path: Optional path within the repository
    """
    # Resolve repo_name to the actual repository path
    repo_path = str(Path(PLACEHOLDER_REPO_PATH) / "gitwrite_user_repos" / repo_name)
    
    try:
        result = core_list_repository_tree(
            repo_path_str=repo_path,
            ref=ref,
            path=path
        )
        
        if result['status'] == 'success':
            return RepositoryTreeResponse(
                repo_name=result['repo_name'],
                ref=result['ref'],
                request_path=result['request_path'],
                entries=result['entries'],
                breadcrumb=result.get('breadcrumb')
            )
        elif result['status'] == 'error':
            if "not found" in result['message'].lower():
                raise HTTPException(status_code=404, detail=result['message'])
            else:
                raise HTTPException(status_code=400, detail=result['message'])
        else:
            raise HTTPException(status_code=500, detail=f"Unexpected response status: {result['status']}")
            
    except CoreRepositoryNotFoundError as e:
        raise HTTPException(status_code=500, detail=f"Repository configuration error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
