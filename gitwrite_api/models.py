from typing import Optional, List, Dict

from pydantic import BaseModel, Field


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None


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
