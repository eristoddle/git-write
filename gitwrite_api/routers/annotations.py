from fastapi import APIRouter, Depends, HTTPException, Query, Path as FastApiPath
from typing import List, Optional

from gitwrite_api.models import (
    User, UserRole,
    CreateAnnotationRequest, AnnotationResponse, AnnotationListResponse,
    UpdateAnnotationStatusRequest, UpdateAnnotationStatusResponse, Annotation
)
from gitwrite_api.security import require_role, get_current_active_user

from gitwrite_core.annotations import (
    create_annotation_commit as core_create_annotation_commit,
    list_annotations as core_list_annotations,
    update_annotation_status as core_update_annotation_status
    # get_annotation_by_original_id was assumed and is handled by a local helper _get_annotation_by_original_id_from_list
)
from gitwrite_core.exceptions import (
    RepositoryNotFoundError, AnnotationError, CommitNotFoundError, RepositoryOperationError
)

# TODO: Make this configurable or dynamically determined per user/request
PLACEHOLDER_REPO_PATH = "/tmp/gitwrite_repos_api"

router = APIRouter(
    prefix="/repository/annotations", # Changed prefix to be more specific
    tags=["annotations"],
    responses={
        404: {"description": "Annotation or related resource not found"},
        400: {"description": "Invalid request"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden"},
        500: {"description": "Internal server error"}
    },
)

# Placeholder for get_annotation_by_original_id if it needs to be defined in core
# For now, we will adapt list_annotations or assume it's added to core.
# Example of how it might be used:
# async def get_annotation_after_update(repo_path: str, feedback_branch: str, original_annotation_id: str) -> Optional[Annotation]:
#     annotations = await core_list_annotations(repo_path, feedback_branch) # Assuming async version or wrapper
#     for ann in annotations:
#         if ann.id == original_annotation_id:
#             return ann
#     return None


@router.post("", response_model=AnnotationResponse, status_code=201)
async def create_annotation(
    request_data: CreateAnnotationRequest,
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.WRITER, UserRole.BETA_READER]))
):
    """
    Creates a new annotation on a specified feedback branch.
    The annotation data is stored as a commit on that branch.
    """
    repo_path = PLACEHOLDER_REPO_PATH

    # The core create_annotation_commit function expects a dictionary for annotation_data,
    # not the full Annotation model yet, as it will populate id, commit_id, and status.
    # We also need to ensure the author from the request is used.
    # The status will be set to NEW by default in the core function.
    annotation_payload_for_core = {
        "file_path": request_data.file_path,
        "highlighted_text": request_data.highlighted_text,
        "start_line": request_data.start_line,
        "end_line": request_data.end_line,
        "comment": request_data.comment,
        "author": request_data.author, # Using author from request
        # 'status' will be defaulted to NEW by core_create_annotation_commit
    }

    try:
        # The core function modifies the input dict to add 'id' and 'commit_id'
        # and returns the commit_sha of the annotation.
        # Let's assume it returns the full annotation object or enough info to build it.
        # Based on Task 10.2, create_annotation_commit updates an input Annotation object and returns the SHA.
        # For the API, it's cleaner if the core function returns the created Annotation object directly
        # or a dictionary that can be parsed into it.
        # Let's adjust the expectation for core_create_annotation_commit:
        # It takes the payload and returns a dictionary representing the full Annotation.

        # For now, let's stick to the current core function signature which expects an Annotation object
        # and updates it. We'll construct a partial one.
        temp_annotation_obj = Annotation(
            file_path=request_data.file_path,
            highlighted_text=request_data.highlighted_text,
            start_line=request_data.start_line,
            end_line=request_data.end_line,
            comment=request_data.comment,
            author=request_data.author,
            status=AnnotationStatus.NEW # Core will use this
        )

        commit_sha = core_create_annotation_commit(
            repo_path_str=repo_path,
            feedback_branch_name=request_data.feedback_branch,
            annotation_obj=temp_annotation_obj # Pass the object to be updated
        )

        # After core_create_annotation_commit, temp_annotation_obj should have id and commit_id populated.
        # The id should be the commit_sha itself for new annotations.
        # temp_annotation_obj.id = commit_sha (core function should do this)
        # temp_annotation_obj.commit_id = commit_sha (core function should do this)

        return AnnotationResponse(**temp_annotation_obj.model_dump())

    except RepositoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Repository not found: {str(e)}")
    except RepositoryOperationError as e: # Covers errors like feedback branch creation failure
        raise HTTPException(status_code=500, detail=f"Repository operation error: {str(e)}")
    except AnnotationError as e: # Generic annotation error from core
        raise HTTPException(status_code=400, detail=f"Annotation creation error: {str(e)}")
    except Exception as e:
        # Log this exception for debugging
        # logger.error(f"Unexpected error in create_annotation: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@router.get("", response_model=AnnotationListResponse)
async def list_annotations(
    feedback_branch: str = Query(..., description="The name of the feedback branch from which to list annotations."),
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR, UserRole.WRITER, UserRole.BETA_READER]))
):
    """
    Lists all annotations from a specified feedback branch.
    """
    repo_path = PLACEHOLDER_REPO_PATH

    try:
        annotations_list = core_list_annotations(
            repo_path_str=repo_path,
            feedback_branch_name=feedback_branch
        )
        # core_list_annotations returns List[Annotation]

        return AnnotationListResponse(
            annotations=annotations_list,
            count=len(annotations_list)
        )

    except RepositoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Repository not found: {str(e)}")
    except RepositoryOperationError as e: # e.g. branch not found
        # Check if the error message indicates a branch not found, which should be a 404 for the branch.
        if "branch not found" in str(e).lower() or "invalid branch" in str(e).lower() : # Make this check more robust if core provides specific exception types
            raise HTTPException(status_code=404, detail=f"Feedback branch '{feedback_branch}' not found or invalid: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Repository operation error: {str(e)}")
    except AnnotationError as e: # Generic annotation error from core during listing
        raise HTTPException(status_code=500, detail=f"Annotation listing error: {str(e)}") # Potentially some malformed data
    except Exception as e:
        # Log this exception
        # logger.error(f"Unexpected error in list_annotations: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


async def _get_annotation_by_original_id_from_list(
    repo_path: str, feedback_branch: str, original_annotation_id: str
) -> Optional[Annotation]:
    """
    Helper to find a specific annotation by its original ID after an update.
    This simulates a more direct core.get_annotation_by_original_id if not available.
    """
    annotations = core_list_annotations(repo_path, feedback_branch)
    for ann in annotations:
        # The 'id' of an annotation is its original creation commit SHA.
        # 'commit_id' is the SHA of the commit defining its current state.
        if ann.id == original_annotation_id:
            return ann
    return None


@router.put("/{annotation_commit_id}", response_model=UpdateAnnotationStatusResponse)
async def update_annotation_status(
    annotation_commit_id: str = FastApiPath(..., description="The commit ID (SHA) of the original annotation to update."),
    request_data: UpdateAnnotationStatusRequest = ..., # Ellipsis indicates Body
    current_user: User = Depends(require_role([UserRole.OWNER, UserRole.EDITOR])) # Typically editors or owners manage status
):
    """
    Updates the status of an existing annotation.
    This creates a new commit on the feedback branch to record the status change.
    """
    repo_path = PLACEHOLDER_REPO_PATH

    try:
        # Core function returns the SHA of the status update commit.
        update_commit_sha = core_update_annotation_status(
            repo_path_str=repo_path,
            feedback_branch_name=request_data.feedback_branch,
            annotation_commit_id=annotation_commit_id,
            new_status=request_data.new_status,
            # Assuming author of status update can be implicitly handled by git committer
            # or core_update_annotation_status could take an optional 'updated_by_author'
            updated_by_author=current_user.username # Pass the current user as the author of the update
        )

        # After successful update, fetch the full state of the updated annotation.
        # The 'id' of the annotation remains the original_annotation_id.
        # Its 'commit_id' will be the new update_commit_sha, and 'status' will be the new_status.
        updated_annotation = await _get_annotation_by_original_id_from_list(
            repo_path=repo_path,
            feedback_branch=request_data.feedback_branch,
            original_annotation_id=annotation_commit_id
        )

        if not updated_annotation:
            # This case should ideally not happen if core_update_annotation_status succeeded
            # and core_list_annotations is consistent.
            # It might indicate an issue or a race condition if the annotation was deleted post-update but pre-fetch.
            raise HTTPException(
                status_code=404, # Or 500 if this implies inconsistency
                detail=f"Annotation with original ID '{annotation_commit_id}' not found after status update. The update commit was '{update_commit_sha}'."
            )

        return UpdateAnnotationStatusResponse(
            annotation=updated_annotation,
            message=f"Annotation '{annotation_commit_id}' status updated to '{request_data.new_status.value}'. Update recorded in commit '{update_commit_sha}'."
        )

    except CommitNotFoundError as e: # Raised if original annotation_commit_id is not found by core_update_annotation_status
        raise HTTPException(status_code=404, detail=f"Original annotation commit ID '{annotation_commit_id}' not found: {str(e)}")
    except RepositoryNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Repository not found: {str(e)}")
    except RepositoryOperationError as e:
        # This could be due to the feedback branch not found, or other git issues during the update commit.
        if "branch not found" in str(e).lower() or "invalid branch" in str(e).lower():
             raise HTTPException(status_code=404, detail=f"Feedback branch '{request_data.feedback_branch}' not found or invalid: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Repository operation error during status update: {str(e)}")
    except AnnotationError as e: # Generic annotation error from core during update (e.g., invalid status transition)
        raise HTTPException(status_code=400, detail=f"Annotation status update error: {str(e)}")
    except ValueError as e: # e.g. Pydantic validation error for AnnotationStatus if not caught by FastAPI
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        # Log this exception
        # logger.error(f"Unexpected error in update_annotation_status: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")
