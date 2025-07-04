from typing import Optional, List, Dict
from enum import Enum
from datetime import datetime

from pydantic import BaseModel, Field


class UserRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    WRITER = "writer"
    BETA_READER = "beta_reader"


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    roles: List[UserRole] = Field(default_factory=list)


class UserInDB(User):
    hashed_password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    username: Optional[str] = None

class FileMetadata(BaseModel):
    file_path: str = Field(..., description="The relative path of the file in the repository.")
    file_hash: str = Field(..., description="SHA256 hash of the file content for integrity checking.")

class FileUploadInitiateRequest(BaseModel):
    commit_message: str = Field(..., description="The commit message for the save operation.")
    files: List[FileMetadata] = Field(..., description="A list of files to be uploaded.")

class FileUploadInitiateResponse(BaseModel):
    upload_urls: Dict[str, str] = Field(..., description="A dictionary mapping file paths to their unique, one-time upload URLs.")
    completion_token: str = Field(..., description="A token to be used to finalize the upload process.")

class FileUploadCompleteRequest(BaseModel):
    completion_token: str = Field(..., description="The completion token obtained from the initiation step.")

class FileUploadCompleteResponse(BaseModel):
    commit_id: Optional[str] = Field(None, description="The ID of the new commit created after successful upload and save, or None if no changes.")
    message: str = Field(..., description="A message indicating the outcome of the operation.")


class SaveFileRequest(BaseModel):
    file_path: str = Field(..., description="The relative path of the file in the repository.")
    content: str = Field(..., description="The content to be saved to the file.")
    commit_message: str = Field(..., description="The commit message for the save operation.")


class SaveFileResponse(BaseModel):
    status: str = Field(..., description="The status of the save operation (e.g., 'success', 'error').")
    message: str = Field(..., description="A message detailing the outcome of the operation.")
    commit_id: Optional[str] = Field(None, description="The ID of the new commit if the operation was successful.")

class RepositoryCreateRequest(BaseModel):
    project_name: Optional[str] = Field(None, min_length=1, pattern=r"^[a-zA-Z0-9_-]+$", description="Optional name for the repository. If provided, it will be used as the directory name. Must be alphanumeric with hyphens/underscores.")

# Models for Cherry-Pick and Branch Review API Endpoints

class CherryPickRequest(BaseModel):
    commit_id: str = Field(..., description="The OID of the commit to cherry-pick.")
    mainline: Optional[int] = Field(None, gt=0, description="For merge commits, the parent number (1-based) to consider as the mainline.")

class CherryPickResponse(BaseModel):
    status: str = Field(..., description="Outcome of the cherry-pick operation (e.g., 'success', 'conflict').")
    message: str = Field(..., description="Detailed message about the cherry-pick outcome.")
    new_commit_oid: Optional[str] = Field(None, description="The OID of the new commit created by the cherry-pick, if successful.")
    conflicting_files: Optional[List[str]] = Field(None, description="List of files with conflicts, if any.")


class BranchReviewCommit(BaseModel):
    short_hash: str = Field(..., description="Abbreviated commit hash.")
    author_name: str = Field(..., description="Name of the commit author.")
    date: str = Field(..., description="Author date of the commit (ISO 8601 format).") # Assuming core returns string for now
    message_short: str = Field(..., description="First line of the commit message.")
    oid: str = Field(..., description="Full commit OID.")

class BranchReviewResponse(BaseModel):
    status: str = Field(..., description="Outcome of the branch review operation.")
    branch_name: str = Field(..., description="The name of the branch that was reviewed.")
    commits: List[BranchReviewCommit] = Field(..., description="List of commits on the branch not present in HEAD.")
    message: str = Field(..., description="Detailed message about the review outcome.")


# Models for EPUB Export API Endpoints

class EPUBExportRequest(BaseModel):
    commit_ish: str = Field(default="HEAD", description="The commit-ish (e.g., commit hash, branch name, tag) to export from. Defaults to 'HEAD'.")
    file_list: List[str] = Field(..., min_items=1, description="A list of paths to markdown files (relative to repo root) to include in the EPUB.")
    output_filename: Optional[str] = Field(default="export.epub", min_length=1, pattern=r"^[a-zA-Z0-9_.-]+\.epub$", description="Desired filename for the EPUB (e.g., 'my-book.epub'). Must end with '.epub'. Defaults to 'export.epub'.")

class EPUBExportResponse(BaseModel):
    status: str = Field(..., description="Outcome of the EPUB export operation (e.g., 'success', 'error').")
    message: str = Field(..., description="Detailed message about the export outcome.")
    # Initially, we'll return a server path. A download URL or job ID could be future enhancements.
    server_file_path: Optional[str] = Field(None, description="Server-side path to the generated EPUB file, present on success.")
    # download_url: Optional[str] = Field(None, description="A direct download URL for the EPUB file, if applicable.")
    # export_job_id: Optional[str] = Field(None, description="An ID for tracking an asynchronous export job, if applicable.")


# Models for Annotation Handling

class AnnotationStatus(str, Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Annotation(BaseModel):
    id: Optional[str] = Field(None, description="Unique identifier for the annotation, typically the commit SHA of its creation.")
    file_path: str = Field(..., description="The relative path of the file in the repository that this annotation refers to.")
    highlighted_text: str = Field(..., description="The specific text that was highlighted for annotation.")
    start_line: int = Field(..., ge=0, description="The 0-indexed starting line number of the highlighted text.")
    end_line: int = Field(..., ge=0, description="The 0-indexed ending line number of the highlighted text.")
    comment: str = Field(..., description="The comment or note provided by the annotator.")
    author: str = Field(..., description="The author of the annotation (e.g., username or email).")
    status: AnnotationStatus = Field(default=AnnotationStatus.NEW, description="The current status of the annotation.")
    commit_id: Optional[str] = Field(None, description="The Git commit SHA where this version of the annotation (especially its status) is recorded. For a new annotation, this is its creation commit. For a status update, this is the SHA of the status update commit.")
    original_annotation_id: Optional[str] = Field(None, description="If this annotation represents a status update, this field stores the ID (commit_id) of the original annotation being updated.")


# --- API Request/Response Models for Annotations ---

class CreateAnnotationRequest(BaseModel):
    file_path: str = Field(..., description="The relative path of the file in the repository that this annotation refers to.")
    highlighted_text: str = Field(..., description="The specific text that was highlighted for annotation.")
    start_line: int = Field(..., ge=0, description="The 0-indexed starting line number of the highlighted text.")
    end_line: int = Field(..., ge=0, description="The 0-indexed ending line number of the highlighted text.")
    comment: str = Field(..., description="The comment or note provided by the annotator.")
    author: str = Field(..., description="The author of the annotation (e.g., username or email).")
    feedback_branch: str = Field(..., description="The name of the feedback branch where the annotation will be stored.")
    # Status will default to NEW in the core logic, so not needed in request.

class AnnotationResponse(Annotation): # Inherits all fields from Annotation
    # This can be used directly if the Annotation model itself is sufficient for responses.
    # If additional fields are needed for API response context, they can be added here.
    # For example:
    # status_message: Optional[str] = Field(None, description="A message related to the response status.")
    pass

class AnnotationListResponse(BaseModel):
    annotations: List[Annotation] = Field(..., description="A list of annotations.")
    count: int = Field(..., description="The total number of annotations returned.")

class UpdateAnnotationStatusRequest(BaseModel):
    new_status: AnnotationStatus = Field(..., description="The new status for the annotation.")
    feedback_branch: str = Field(..., description="The name of the feedback branch where the annotation exists.") # Required to find/update the annotation

class UpdateAnnotationStatusResponse(BaseModel):
    annotation: Annotation = Field(..., description="The full annotation object with its updated status.")
    message: str = Field(..., description="A message indicating the outcome of the status update.")


# --- API Request/Response Models for File Content ---

class FileContentResponse(BaseModel):
    file_path: str = Field(..., description="The path of the retrieved file.")
    commit_sha: str = Field(..., description="The commit SHA from which the file content was retrieved.")
    content: str = Field(..., description="The content of the file.")
    size: int = Field(..., description="The size of the file in bytes.")
    mode: str = Field(..., description="The file mode (e.g., '100644' for a regular file).")
    is_binary: bool = Field(..., description="Indicates if the content is binary.")


# --- API Request/Response Models for Repository Listing ---

class RepositoryMetadata(BaseModel):
    name: str = Field(..., description="Name of the repository.")
    last_modified: datetime = Field(..., description="Timestamp of the last modification (e.g., last commit date).")
    description: Optional[str] = Field(None, description="Optional description of the repository.")
    # path: str # Full path on server, might not be needed for client

class RepositoryListItem(RepositoryMetadata): # Inherits from RepositoryMetadata
    # For now, this is identical to RepositoryMetadata.
    # It can be extended if specific list item properties are needed later.
    pass

class RepositoriesListResponse(BaseModel):
    repositories: List[RepositoryListItem] = Field(..., description="A list of available repositories.")
    count: int = Field(..., description="The total number of repositories returned.")
