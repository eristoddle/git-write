# File Uploads

GitWrite's file upload system handles manuscript content, images, documents, and other assets with intelligent processing, validation, and integration with version control. The system supports both individual file uploads and bulk operations while maintaining data integrity and security.

## Overview

The file upload API provides:
- **Content Management**: Text files, manuscripts, and documents
- **Asset Handling**: Images, cover art, and media files
- **Bulk Operations**: Multiple file uploads and directory syncing
- **Format Detection**: Automatic file type recognition and processing
- **Version Integration**: Direct integration with Git version control
- **Security**: File validation, virus scanning, and access control

```
File Upload Flow
    │
    ├─ Upload Request → Validation → Processing → Storage → Git Integration
    │                     ↓            ↓          ↓         ↓
    ├─ Security Check → Format Check → Transform → Commit → Response
    │                     ↓            ↓          ↓         ↓
    └─ Virus Scan → Content Analysis → Optimize → Track → Notify
```

## Core Endpoints

### 1. Single File Upload

```python
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Depends, status
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import os
import mimetypes
import hashlib

router = APIRouter(prefix="/repositories/{repository_name}/files", tags=["file-uploads"])

class FileUploadResponse(BaseModel):
    """Response model for file upload operations"""
    success: bool
    file_path: str
    file_size: int
    file_type: str
    checksum: str

    # Processing info
    processed: bool
    processing_details: Optional[Dict[str, Any]] = None

    # Content analysis
    word_count: Optional[int] = None
    character_count: Optional[int] = None
    language_detected: Optional[str] = None

    # Version control
    auto_committed: bool
    commit_id: Optional[str] = None

    # Metadata
    uploaded_at: datetime
    uploaded_by: str

    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "file_path": "chapters/chapter1.md",
                "file_size": 15420,
                "file_type": "text/markdown",
                "checksum": "a1b2c3d4e5f6",
                "processed": True,
                "processing_details": {
                    "format_conversion": "docx_to_markdown",
                    "image_optimization": True
                },
                "word_count": 2847,
                "character_count": 15420,
                "language_detected": "en",
                "auto_committed": True,
                "commit_id": "abc123def",
                "uploaded_at": "2023-11-20T14:30:00Z",
                "uploaded_by": "jane@writer.com"
            }
        }

@router.post("/upload", response_model=FileUploadResponse)
async def upload_file(
    repository_name: str,
    file: UploadFile = File(...),
    file_path: Optional[str] = Form(None, description="Custom file path within repository"),
    auto_commit: bool = Form(True, description="Automatically commit the uploaded file"),
    commit_message: Optional[str] = Form(None, description="Custom commit message"),
    overwrite: bool = Form(False, description="Overwrite existing file"),
    process_content: bool = Form(True, description="Process and analyze content"),
    current_user: User = Depends(get_current_user)
) -> FileUploadResponse:
    """Upload a single file to the repository"""

    repository = await _get_user_repository(repository_name, current_user)

    # Check write permissions
    if not await permission_service.can_write(repository.id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to upload files"
        )

    try:
        # Validate file
        validation_result = await _validate_file_upload(file, repository)
        if not validation_result.valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File validation failed: {validation_result.error}"
            )

        # Determine file path
        target_path = file_path or await _generate_file_path(file, repository)

        # Check if file exists and handle overwrite
        if not overwrite and await _file_exists_in_repository(repository.id, target_path):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"File '{target_path}' already exists. Use overwrite=true to replace it."
            )

        # Read and process file content
        file_content = await file.read()
        file_checksum = hashlib.sha256(file_content).hexdigest()

        # Process content if requested
        processing_result = None
        if process_content:
            processing_result = await _process_file_content(
                file_content, file.content_type, target_path
            )
            if processing_result.transformed:
                file_content = processing_result.content
                target_path = processing_result.target_path or target_path

        # Save file to repository
        await file_service.save_file_to_repository(
            repository_id=repository.id,
            file_path=target_path,
            content=file_content,
            content_type=file.content_type
        )

        # Analyze content for text files
        content_analysis = None
        if _is_text_file(file.content_type):
            content_analysis = await _analyze_text_content(file_content, target_path)

        # Auto-commit if requested
        commit_id = None
        if auto_commit:
            commit_result = await git_service.save_changes(
                repository_id=repository.id,
                message=commit_message or f"Uploaded {os.path.basename(target_path)}",
                files=[target_path],
                author_name=current_user.name,
                author_email=current_user.email
            )
            if commit_result.success:
                commit_id = commit_result.commit_id

        # Update repository statistics
        await repository_service.update_file_statistics(repository.id)

        return FileUploadResponse(
            success=True,
            file_path=target_path,
            file_size=len(file_content),
            file_type=file.content_type,
            checksum=file_checksum,
            processed=processing_result is not None,
            processing_details=processing_result.details if processing_result else None,
            word_count=content_analysis.word_count if content_analysis else None,
            character_count=content_analysis.character_count if content_analysis else None,
            language_detected=content_analysis.language if content_analysis else None,
            auto_committed=commit_id is not None,
            commit_id=commit_id,
            uploaded_at=datetime.utcnow(),
            uploaded_by=current_user.email
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File upload failed"
        )
```

### 2. Bulk File Upload

```python
class BulkUploadRequest(BaseModel):
    """Request for bulk file upload operation"""
    files: List[str] = Field(..., description="List of file paths to upload")
    base_directory: Optional[str] = Field(None, description="Base directory for relative paths")
    auto_commit: bool = Field(True)
    commit_message: Optional[str] = Field(None)
    overwrite_existing: bool = Field(False)
    process_content: bool = Field(True)

class BulkUploadResponse(BaseModel):
    """Response for bulk upload operation"""
    success: bool
    total_files: int
    uploaded_files: int
    failed_files: int

    # Detailed results
    successful_uploads: List[FileUploadResponse]
    failed_uploads: List[Dict[str, str]]  # file_path -> error_message

    # Summary
    total_size: int
    total_word_count: int
    commit_id: Optional[str]
    processing_time_seconds: float

@router.post("/bulk-upload", response_model=BulkUploadResponse)
async def bulk_upload_files(
    repository_name: str,
    files: List[UploadFile] = File(...),
    base_directory: Optional[str] = Form(None),
    auto_commit: bool = Form(True),
    commit_message: Optional[str] = Form(None),
    overwrite_existing: bool = Form(False),
    process_content: bool = Form(True),
    current_user: User = Depends(get_current_user)
) -> BulkUploadResponse:
    """Upload multiple files to the repository"""

    repository = await _get_user_repository(repository_name, current_user)

    if not await permission_service.can_write(repository.id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to upload files"
        )

    start_time = datetime.utcnow()
    successful_uploads = []
    failed_uploads = []
    uploaded_files = []

    try:
        for file in files:
            try:
                # Determine target path
                if base_directory:
                    target_path = os.path.join(base_directory, file.filename)
                else:
                    target_path = await _generate_file_path(file, repository)

                # Upload individual file
                upload_result = await _upload_single_file_internal(
                    repository=repository,
                    file=file,
                    target_path=target_path,
                    overwrite=overwrite_existing,
                    process_content=process_content,
                    current_user=current_user,
                    auto_commit=False  # We'll commit all at once
                )

                successful_uploads.append(upload_result)
                uploaded_files.append(target_path)

            except Exception as e:
                failed_uploads.append({
                    "file_path": file.filename,
                    "error": str(e)
                })

        # Commit all uploaded files together if auto_commit is enabled
        commit_id = None
        if auto_commit and uploaded_files:
            commit_result = await git_service.save_changes(
                repository_id=repository.id,
                message=commit_message or f"Bulk upload: {len(uploaded_files)} files",
                files=uploaded_files,
                author_name=current_user.name,
                author_email=current_user.email
            )
            if commit_result.success:
                commit_id = commit_result.commit_id

        # Calculate summary statistics
        total_size = sum(upload.file_size for upload in successful_uploads)
        total_word_count = sum(
            upload.word_count for upload in successful_uploads
            if upload.word_count
        )

        processing_time = (datetime.utcnow() - start_time).total_seconds()

        return BulkUploadResponse(
            success=len(failed_uploads) == 0,
            total_files=len(files),
            uploaded_files=len(successful_uploads),
            failed_files=len(failed_uploads),
            successful_uploads=successful_uploads,
            failed_uploads=failed_uploads,
            total_size=total_size,
            total_word_count=total_word_count,
            commit_id=commit_id,
            processing_time_seconds=processing_time
        )

    except Exception as e:
        logger.error(f"Bulk upload failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bulk upload operation failed"
        )
```

### 3. File Management

```python
class FileInfo(BaseModel):
    """Information about a file in the repository"""
    path: str
    name: str
    size: int
    type: str
    checksum: str

    # Timestamps
    created_at: datetime
    modified_at: datetime
    last_commit: Optional[str]

    # Content info
    word_count: Optional[int]
    character_count: Optional[int]
    line_count: Optional[int]
    language: Optional[str]

    # Version info
    save_count: int
    last_modified_by: str

@router.get("/", response_model=List[FileInfo])
async def list_files(
    repository_name: str,
    directory: Optional[str] = None,
    file_type: Optional[str] = None,
    recursive: bool = Field(True),
    include_stats: bool = Field(True),
    current_user: User = Depends(get_current_user)
) -> List[FileInfo]:
    """List files in the repository"""

    repository = await _get_user_repository(repository_name, current_user)

    try:
        files = await file_service.list_repository_files(
            repository_id=repository.id,
            directory=directory,
            file_type=file_type,
            recursive=recursive,
            include_stats=include_stats
        )

        return files

    except Exception as e:
        logger.error(f"Failed to list files: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list repository files"
        )

@router.get("/{file_path:path}")
async def download_file(
    repository_name: str,
    file_path: str,
    version: Optional[str] = None,  # Specific commit/save ID
    current_user: User = Depends(get_current_user)
):
    """Download a file from the repository"""

    repository = await _get_user_repository(repository_name, current_user)

    try:
        # Get file content
        if version:
            file_content = await git_service.get_file_at_version(
                repository_id=repository.id,
                file_path=file_path,
                commit_id=version
            )
        else:
            file_content = await file_service.get_file_content(
                repository_id=repository.id,
                file_path=file_path
            )

        if file_content is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{file_path}' not found"
            )

        # Determine content type
        content_type = mimetypes.guess_type(file_path)[0] or 'application/octet-stream'

        return StreamingResponse(
            io.BytesIO(file_content),
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={os.path.basename(file_path)}"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File download failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File download failed"
        )

@router.delete("/{file_path:path}")
async def delete_file(
    repository_name: str,
    file_path: str,
    auto_commit: bool = Field(True),
    commit_message: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """Delete a file from the repository"""

    repository = await _get_user_repository(repository_name, current_user)

    if not await permission_service.can_write(repository.id, current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to delete files"
        )

    try:
        # Check if file exists
        if not await file_service.file_exists(repository.id, file_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"File '{file_path}' not found"
            )

        # Delete file
        await file_service.delete_file(repository.id, file_path)

        # Auto-commit if requested
        if auto_commit:
            await git_service.save_changes(
                repository_id=repository.id,
                message=commit_message or f"Deleted {os.path.basename(file_path)}",
                files=[file_path],
                author_name=current_user.name,
                author_email=current_user.email
            )

        return {"success": True, "message": f"File '{file_path}' deleted successfully"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File deletion failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="File deletion failed"
        )
```

### 4. File Processing

```python
class FileProcessingService:
    """Service for processing uploaded files"""

    async def process_file_content(
        self,
        content: bytes,
        content_type: str,
        file_path: str
    ) -> ProcessingResult:
        """Process uploaded file content"""

        processing_details = {}
        transformed = False

        # Handle different file types
        if content_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            # Convert DOCX to Markdown
            content = await self._convert_docx_to_markdown(content)
            file_path = file_path.replace('.docx', '.md')
            processing_details['format_conversion'] = 'docx_to_markdown'
            transformed = True

        elif content_type == 'application/rtf':
            # Convert RTF to Markdown
            content = await self._convert_rtf_to_markdown(content)
            file_path = file_path.replace('.rtf', '.md')
            processing_details['format_conversion'] = 'rtf_to_markdown'
            transformed = True

        elif content_type.startswith('image/'):
            # Optimize images
            content = await self._optimize_image(content, content_type)
            processing_details['image_optimization'] = True
            transformed = True

        # Clean and normalize text content
        if _is_text_file(content_type):
            content = await self._clean_text_content(content)
            processing_details['text_cleaning'] = True

        return ProcessingResult(
            content=content,
            target_path=file_path if transformed else None,
            transformed=transformed,
            details=processing_details
        )

    async def _convert_docx_to_markdown(self, docx_content: bytes) -> bytes:
        """Convert DOCX content to Markdown"""
        # Implementation using python-docx and pypandoc
        import tempfile
        import subprocess

        with tempfile.NamedTemporaryFile(suffix='.docx') as temp_docx:
            temp_docx.write(docx_content)
            temp_docx.flush()

            with tempfile.NamedTemporaryFile(suffix='.md') as temp_md:
                # Use pandoc for conversion
                subprocess.run([
                    'pandoc',
                    '--from', 'docx',
                    '--to', 'markdown',
                    '--output', temp_md.name,
                    temp_docx.name
                ], check=True)

                return temp_md.read()

    async def _optimize_image(self, image_content: bytes, content_type: str) -> bytes:
        """Optimize image content"""
        from PIL import Image
        import io

        # Open image
        image = Image.open(io.BytesIO(image_content))

        # Resize if too large
        max_width = 1920
        max_height = 1080

        if image.width > max_width or image.height > max_height:
            image.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)

        # Save optimized version
        output = io.BytesIO()
        format_map = {
            'image/jpeg': 'JPEG',
            'image/png': 'PNG',
            'image/webp': 'WEBP'
        }

        image_format = format_map.get(content_type, 'JPEG')

        if image_format == 'JPEG':
            image.save(output, format=image_format, quality=85, optimize=True)
        else:
            image.save(output, format=image_format, optimize=True)

        return output.getvalue()
```

### 5. File Validation

```python
class FileValidationService:
    """Service for validating uploaded files"""

    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    ALLOWED_TEXT_TYPES = {
        'text/plain',
        'text/markdown',
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        'application/rtf',
        'text/html'
    }
    ALLOWED_IMAGE_TYPES = {
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp'
    }

    async def validate_file_upload(
        self,
        file: UploadFile,
        repository: Repository
    ) -> ValidationResult:
        """Validate file upload"""

        errors = []

        # Check file size
        if file.size > self.MAX_FILE_SIZE:
            errors.append(f"File size ({file.size} bytes) exceeds maximum allowed size ({self.MAX_FILE_SIZE} bytes)")

        # Check file type
        if file.content_type not in (self.ALLOWED_TEXT_TYPES | self.ALLOWED_IMAGE_TYPES):
            errors.append(f"File type '{file.content_type}' is not allowed")

        # Check filename
        if not self._is_valid_filename(file.filename):
            errors.append("Invalid filename characters")

        # Virus scan (placeholder for actual implementation)
        if await self._scan_for_viruses(file):
            errors.append("File failed security scan")

        # Check repository limits
        repo_stats = await repository_service.get_statistics(repository.id)
        if repo_stats.total_size + file.size > repository.size_limit:
            errors.append("Repository size limit would be exceeded")

        return ValidationResult(
            valid=len(errors) == 0,
            error='; '.join(errors) if errors else None
        )

    def _is_valid_filename(self, filename: str) -> bool:
        """Check if filename is valid"""
        import re

        # Check for dangerous characters
        if re.search(r'[<>:"/\\|?*]', filename):
            return False

        # Check for reserved names
        reserved_names = {'CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'}
        if filename.upper() in reserved_names:
            return False

        return True

    async def _scan_for_viruses(self, file: UploadFile) -> bool:
        """Scan file for viruses (placeholder)"""
        # In a real implementation, this would integrate with antivirus software
        return False
```

## Security and Performance

### Rate Limiting

```python
from fastapi_limiter.depends import RateLimiter

# Rate limit uploads
@router.post("/upload")
@rate_limit("20/minute")  # 20 uploads per minute
async def upload_file(...):
    pass

# Stricter limits for bulk uploads
@router.post("/bulk-upload")
@rate_limit("5/hour")  # 5 bulk operations per hour
async def bulk_upload_files(...):
    pass
```

### Async Processing

```python
import asyncio
from celery import Celery

# Background task for large file processing
@celery_app.task
def process_large_file_async(repository_id: str, file_path: str, content: bytes):
    """Process large files in background"""
    # Perform heavy processing operations
    # Update database when complete
    pass

# Use background processing for files > 10MB
if file.size > 10 * 1024 * 1024:
    process_large_file_async.delay(repository.id, target_path, file_content)
```

---

*GitWrite's file upload system provides robust content management with intelligent processing, security validation, and seamless version control integration, enabling writers to focus on content creation while maintaining data integrity and workflow efficiency.*