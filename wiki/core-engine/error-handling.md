# Error Handling

GitWrite's error handling system provides comprehensive error management, user-friendly error messages, and robust recovery mechanisms. It transforms technical Git errors into actionable guidance for writers while maintaining system reliability and data integrity.

## Overview

The error handling system operates at multiple levels:
- **Prevention**: Proactive validation and safety checks
- **Detection**: Early error identification and classification
- **Translation**: Converting technical errors to writer-friendly messages
- **Recovery**: Providing clear paths to resolution
- **Learning**: Improving the system based on error patterns

```
Error Handling Flow
    │
    ├─ Error Detection → Classification → Translation → User Message
    │                                                      ↓
    ├─ Recovery Options ← Solution Suggestions ← Context Analysis
    │                                                      ↓
    └─ Logging & Analytics ← Error Tracking ← Pattern Recognition
```

## Core Components

### 1. Error Classification

```python
from typing import List, Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import traceback
import logging

class ErrorSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class ErrorCategory(Enum):
    GIT_OPERATION = "git_operation"
    FILE_SYSTEM = "file_system"
    VALIDATION = "validation"
    PERMISSION = "permission"
    NETWORK = "network"
    CONFIGURATION = "configuration"
    USER_INPUT = "user_input"
    SYSTEM = "system"
    EXPORT = "export"
    COLLABORATION = "collaboration"

@dataclass
class ErrorContext:
    """Context information for error analysis"""
    operation: str
    file_path: Optional[str] = None
    save_id: Optional[str] = None
    user_id: Optional[str] = None
    repository_path: Optional[str] = None
    command_args: Optional[Dict[str, Any]] = None
    system_state: Optional[Dict[str, Any]] = None

@dataclass
class GitWriteError:
    """Comprehensive error information"""
    error_id: str
    category: ErrorCategory
    severity: ErrorSeverity

    # Error details
    technical_message: str
    user_message: str
    error_code: str

    # Context
    context: ErrorContext
    timestamp: datetime

    # Resolution
    suggested_actions: List[str]
    recovery_options: List[Dict[str, Any]]
    help_links: List[str]

    # Technical details
    stack_trace: Optional[str] = None
    underlying_exception: Optional[Exception] = None

    # User guidance
    is_user_recoverable: bool = True
    requires_support: bool = False

class ErrorClassifier:
    """Classifies and categorizes errors"""

    ERROR_PATTERNS = {
        # Git-related errors
        r"index\.lock": {
            "category": ErrorCategory.GIT_OPERATION,
            "severity": ErrorSeverity.WARNING,
            "user_message": "Another save operation is in progress. Please wait and try again.",
            "suggested_actions": ["Wait for current operation to complete", "Retry the operation"],
            "recovery_options": [{"action": "retry", "delay_seconds": 2}]
        },

        r"merge conflict": {
            "category": ErrorCategory.GIT_OPERATION,
            "severity": ErrorSeverity.ERROR,
            "user_message": "Your changes conflict with recent edits. Manual resolution required.",
            "suggested_actions": [
                "Review conflicting sections",
                "Choose which version to keep",
                "Save the resolved version"
            ],
            "recovery_options": [
                {"action": "open_conflict_resolver"},
                {"action": "show_diff"},
                {"action": "revert_changes"}
            ]
        },

        r"nothing to commit": {
            "category": ErrorCategory.VALIDATION,
            "severity": ErrorSeverity.INFO,
            "user_message": "No changes detected since your last save.",
            "suggested_actions": ["Make changes to your files", "Check file status"],
            "recovery_options": [{"action": "show_status"}]
        },

        # File system errors
        r"Permission denied": {
            "category": ErrorCategory.PERMISSION,
            "severity": ErrorSeverity.ERROR,
            "user_message": "Permission denied. Check file and folder permissions.",
            "suggested_actions": [
                "Check file permissions",
                "Run as administrator if needed",
                "Ensure files aren't open in other applications"
            ],
            "recovery_options": [{"action": "check_permissions"}]
        },

        r"No such file or directory": {
            "category": ErrorCategory.FILE_SYSTEM,
            "severity": ErrorSeverity.ERROR,
            "user_message": "File or folder not found.",
            "suggested_actions": [
                "Check the file path",
                "Verify the file exists",
                "Check spelling"
            ],
            "recovery_options": [{"action": "browse_files"}]
        }
    }

    def classify_error(
        self,
        exception: Exception,
        context: ErrorContext
    ) -> GitWriteError:
        """Classify an exception into a GitWrite error"""

        error_message = str(exception)
        error_type = type(exception).__name__

        # Find matching pattern
        for pattern, error_info in self.ERROR_PATTERNS.items():
            if re.search(pattern, error_message, re.IGNORECASE):
                return self._create_error_from_pattern(
                    exception, context, error_info
                )

        # Default classification for unknown errors
        return self._create_generic_error(exception, context)

    def _create_error_from_pattern(
        self,
        exception: Exception,
        context: ErrorContext,
        pattern_info: Dict[str, Any]
    ) -> GitWriteError:
        """Create error from matched pattern"""

        return GitWriteError(
            error_id=self._generate_error_id(),
            category=pattern_info["category"],
            severity=pattern_info["severity"],
            technical_message=str(exception),
            user_message=pattern_info["user_message"],
            error_code=self._generate_error_code(pattern_info["category"]),
            context=context,
            timestamp=datetime.utcnow(),
            suggested_actions=pattern_info["suggested_actions"],
            recovery_options=pattern_info["recovery_options"],
            help_links=self._get_help_links(pattern_info["category"]),
            stack_trace=traceback.format_exc(),
            underlying_exception=exception
        )
```

### 2. Error Handler

```python
class GitWriteErrorHandler:
    """Central error handling and recovery system"""

    def __init__(self, repository_path: str = None):
        self.repo_path = repository_path
        self.classifier = ErrorClassifier()
        self.recovery_manager = ErrorRecoveryManager()
        self.logger = self._setup_logger()
        self.error_history = []

    def handle_error(
        self,
        exception: Exception,
        context: ErrorContext,
        auto_recover: bool = True
    ) -> GitWriteError:
        """Handle an error with classification and recovery"""

        # Classify the error
        error = self.classifier.classify_error(exception, context)

        # Log the error
        self._log_error(error)

        # Store in history
        self.error_history.append(error)

        # Attempt automatic recovery if enabled
        if auto_recover and error.is_user_recoverable:
            recovery_result = self.recovery_manager.attempt_recovery(error)
            if recovery_result.success:
                error.recovery_applied = recovery_result

        # Trigger notifications if critical
        if error.severity == ErrorSeverity.CRITICAL:
            self._notify_critical_error(error)

        return error

    def safe_execute(
        self,
        operation: Callable,
        operation_name: str,
        context: Optional[ErrorContext] = None,
        auto_recover: bool = True
    ) -> Tuple[Any, Optional[GitWriteError]]:
        """Safely execute an operation with error handling"""

        if context is None:
            context = ErrorContext(operation=operation_name)
        else:
            context.operation = operation_name

        try:
            result = operation()
            return result, None

        except Exception as e:
            error = self.handle_error(e, context, auto_recover)
            return None, error

    def _log_error(self, error: GitWriteError):
        """Log error with appropriate level"""

        log_data = {
            "error_id": error.error_id,
            "category": error.category.value,
            "severity": error.severity.value,
            "operation": error.context.operation,
            "message": error.technical_message
        }

        if error.severity == ErrorSeverity.CRITICAL:
            self.logger.critical("Critical error", extra=log_data)
        elif error.severity == ErrorSeverity.ERROR:
            self.logger.error("Error occurred", extra=log_data)
        elif error.severity == ErrorSeverity.WARNING:
            self.logger.warning("Warning", extra=log_data)
        else:
            self.logger.info("Info", extra=log_data)
```

### 3. Recovery System

```python
@dataclass
class RecoveryResult:
    """Result of recovery attempt"""
    success: bool
    action_taken: str
    message: str
    additional_steps: List[str] = None

class ErrorRecoveryManager:
    """Manages automatic error recovery"""

    def __init__(self):
        self.recovery_strategies = {
            ErrorCategory.GIT_OPERATION: self._recover_git_operation,
            ErrorCategory.FILE_SYSTEM: self._recover_file_system,
            ErrorCategory.PERMISSION: self._recover_permission,
            ErrorCategory.VALIDATION: self._recover_validation
        }

    def attempt_recovery(self, error: GitWriteError) -> RecoveryResult:
        """Attempt to recover from error automatically"""

        if not error.is_user_recoverable:
            return RecoveryResult(
                success=False,
                action_taken="none",
                message="Error requires manual intervention"
            )

        # Try category-specific recovery
        if error.category in self.recovery_strategies:
            return self.recovery_strategies[error.category](error)

        # Try generic recovery options
        return self._attempt_generic_recovery(error)

    def _recover_git_operation(self, error: GitWriteError) -> RecoveryResult:
        """Recover from Git operation errors"""

        if "index.lock" in error.technical_message.lower():
            # Wait and retry for lock files
            import time
            time.sleep(2)

            # Try to remove stale lock file
            lock_file = os.path.join(error.context.repository_path, '.git', 'index.lock')
            if os.path.exists(lock_file):
                try:
                    os.remove(lock_file)
                    return RecoveryResult(
                        success=True,
                        action_taken="removed_stale_lock",
                        message="Removed stale lock file. You can retry the operation."
                    )
                except OSError:
                    pass

        elif "merge conflict" in error.technical_message.lower():
            # Start conflict resolution workflow
            return RecoveryResult(
                success=False,  # Requires user intervention
                action_taken="conflict_detected",
                message="Conflict resolution required",
                additional_steps=[
                    "Open conflict resolution interface",
                    "Review conflicting changes",
                    "Choose resolution strategy"
                ]
            )

        return RecoveryResult(
            success=False,
            action_taken="none",
            message="Manual recovery required"
        )

    def _recover_file_system(self, error: GitWriteError) -> RecoveryResult:
        """Recover from file system errors"""

        if "no such file" in error.technical_message.lower():
            # Try to create missing directories
            if error.context.file_path:
                dir_path = os.path.dirname(error.context.file_path)
                try:
                    os.makedirs(dir_path, exist_ok=True)
                    return RecoveryResult(
                        success=True,
                        action_taken="created_directory",
                        message=f"Created missing directory: {dir_path}"
                    )
                except OSError:
                    pass

        return RecoveryResult(
            success=False,
            action_taken="none",
            message="File system issue requires manual attention"
        )
```

### 4. User-Friendly Error Messages

```python
class ErrorMessageFormatter:
    """Formats errors for different user audiences"""

    def format_for_writer(self, error: GitWriteError) -> Dict[str, Any]:
        """Format error message for writers (non-technical users)"""

        # Use simple, action-oriented language
        formatted = {
            "title": self._get_writer_friendly_title(error),
            "message": error.user_message,
            "what_happened": self._explain_what_happened(error),
            "what_to_do": error.suggested_actions,
            "quick_fixes": self._get_quick_fixes(error),
            "need_help": error.requires_support
        }

        # Add context-specific guidance
        if error.context.file_path:
            formatted["affected_file"] = os.path.basename(error.context.file_path)

        return formatted

    def format_for_developer(self, error: GitWriteError) -> Dict[str, Any]:
        """Format error message for developers (technical users)"""

        return {
            "error_id": error.error_id,
            "category": error.category.value,
            "severity": error.severity.value,
            "technical_message": error.technical_message,
            "error_code": error.error_code,
            "stack_trace": error.stack_trace,
            "context": {
                "operation": error.context.operation,
                "file_path": error.context.file_path,
                "repository_path": error.context.repository_path,
                "system_state": error.context.system_state
            },
            "recovery_options": error.recovery_options,
            "timestamp": error.timestamp.isoformat()
        }

    def _get_writer_friendly_title(self, error: GitWriteError) -> str:
        """Generate writer-friendly error title"""

        title_map = {
            ErrorCategory.GIT_OPERATION: "Saving Issue",
            ErrorCategory.FILE_SYSTEM: "File Problem",
            ErrorCategory.PERMISSION: "Access Problem",
            ErrorCategory.VALIDATION: "Input Issue",
            ErrorCategory.EXPORT: "Export Problem",
            ErrorCategory.COLLABORATION: "Collaboration Issue"
        }

        return title_map.get(error.category, "Unexpected Issue")

    def _explain_what_happened(self, error: GitWriteError) -> str:
        """Explain what happened in simple terms"""

        explanations = {
            ErrorCategory.GIT_OPERATION: "GitWrite encountered an issue while saving your work.",
            ErrorCategory.FILE_SYSTEM: "There was a problem accessing a file or folder.",
            ErrorCategory.PERMISSION: "GitWrite doesn't have permission to access a required resource.",
            ErrorCategory.VALIDATION: "The information provided needs to be corrected.",
            ErrorCategory.EXPORT: "There was a problem creating your document export.",
            ErrorCategory.COLLABORATION: "An issue occurred while working with collaborators."
        }

        return explanations.get(
            error.category,
            "GitWrite encountered an unexpected issue."
        )
```

### 5. Error Prevention

```python
class ErrorPrevention:
    """Proactive error prevention and validation"""

    def __init__(self, repository_path: str):
        self.repo_path = repository_path

    def validate_operation_preconditions(
        self,
        operation: str,
        context: Dict[str, Any]
    ) -> List[GitWriteError]:
        """Validate preconditions before operation"""

        validation_errors = []

        if operation == "save":
            validation_errors.extend(self._validate_save_preconditions(context))
        elif operation == "create_exploration":
            validation_errors.extend(self._validate_exploration_preconditions(context))
        elif operation == "merge":
            validation_errors.extend(self._validate_merge_preconditions(context))
        elif operation == "export":
            validation_errors.extend(self._validate_export_preconditions(context))

        return validation_errors

    def _validate_save_preconditions(self, context: Dict[str, Any]) -> List[GitWriteError]:
        """Validate conditions for save operation"""

        errors = []

        # Check for repository existence
        if not os.path.exists(os.path.join(self.repo_path, '.git')):
            errors.append(self._create_validation_error(
                "Repository not found",
                "This folder is not a GitWrite project. Initialize it first.",
                ["Run 'gitwrite init' to create a new project"]
            ))

        # Check for uncommitted changes that might cause conflicts
        repo = pygit2.Repository(self.repo_path)
        if not repo.head_is_unborn:
            status = repo.status()
            conflicted_files = [
                path for path, flags in status.items()
                if flags & pygit2.GIT_STATUS_CONFLICTED
            ]

            if conflicted_files:
                errors.append(self._create_validation_error(
                    "Unresolved conflicts",
                    "Some files have unresolved conflicts that must be resolved before saving.",
                    ["Resolve conflicts in affected files", "Use conflict resolution tools"]
                ))

        # Check disk space
        if not self._check_sufficient_disk_space():
            errors.append(self._create_validation_error(
                "Insufficient disk space",
                "Not enough disk space to complete the save operation.",
                ["Free up disk space", "Check available storage"]
            ))

        return errors

    def _create_validation_error(
        self,
        title: str,
        message: str,
        actions: List[str]
    ) -> GitWriteError:
        """Create a validation error"""

        return GitWriteError(
            error_id=self._generate_error_id(),
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            technical_message=title,
            user_message=message,
            error_code="VALIDATION_FAILED",
            context=ErrorContext(operation="validation"),
            timestamp=datetime.utcnow(),
            suggested_actions=actions,
            recovery_options=[{"action": "retry_after_fix"}],
            help_links=[]
        )
```

### 6. Error Analytics

```python
class ErrorAnalytics:
    """Analyze error patterns and provide insights"""

    def __init__(self, error_handler: GitWriteErrorHandler):
        self.error_handler = error_handler

    def analyze_error_patterns(self) -> Dict[str, Any]:
        """Analyze patterns in error history"""

        errors = self.error_handler.error_history

        if not errors:
            return {"message": "No errors to analyze"}

        # Count by category
        category_counts = {}
        for error in errors:
            category = error.category.value
            category_counts[category] = category_counts.get(category, 0) + 1

        # Count by severity
        severity_counts = {}
        for error in errors:
            severity = error.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1

        # Find common operations that fail
        operation_failures = {}
        for error in errors:
            op = error.context.operation
            operation_failures[op] = operation_failures.get(op, 0) + 1

        # Calculate recovery success rate
        recoverable_errors = [e for e in errors if e.is_user_recoverable]
        recovery_attempts = [e for e in recoverable_errors if hasattr(e, 'recovery_applied')]
        successful_recoveries = [e for e in recovery_attempts if e.recovery_applied.success]

        recovery_rate = len(successful_recoveries) / max(len(recovery_attempts), 1)

        return {
            "total_errors": len(errors),
            "category_breakdown": category_counts,
            "severity_breakdown": severity_counts,
            "most_common_failures": sorted(
                operation_failures.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5],
            "recovery_success_rate": recovery_rate,
            "recommendations": self._generate_error_recommendations(errors)
        }

    def _generate_error_recommendations(self, errors: List[GitWriteError]) -> List[str]:
        """Generate recommendations based on error patterns"""

        recommendations = []

        # Check for frequent file system errors
        fs_errors = [e for e in errors if e.category == ErrorCategory.FILE_SYSTEM]
        if len(fs_errors) > len(errors) * 0.3:
            recommendations.append(
                "Consider checking file permissions and disk space regularly"
            )

        # Check for Git operation errors
        git_errors = [e for e in errors if e.category == ErrorCategory.GIT_OPERATION]
        if len(git_errors) > len(errors) * 0.4:
            recommendations.append(
                "Consider using smaller, more frequent saves to reduce Git conflicts"
            )

        # Check for validation errors
        validation_errors = [e for e in errors if e.category == ErrorCategory.VALIDATION]
        if len(validation_errors) > len(errors) * 0.2:
            recommendations.append(
                "Review input validation guidelines to prevent common mistakes"
            )

        return recommendations
```

## Integration with User Interface

### Error Display Components

```python
class ErrorDisplayManager:
    """Manages how errors are displayed to users"""

    def create_error_notification(
        self,
        error: GitWriteError,
        user_type: str = "writer"
    ) -> Dict[str, Any]:
        """Create user interface notification for error"""

        formatter = ErrorMessageFormatter()

        if user_type == "writer":
            message_data = formatter.format_for_writer(error)
        else:
            message_data = formatter.format_for_developer(error)

        notification = {
            "type": "error",
            "severity": error.severity.value,
            "title": message_data.get("title", "Error"),
            "message": message_data["message"],
            "actions": self._create_action_buttons(error),
            "dismissible": error.severity != ErrorSeverity.CRITICAL,
            "auto_hide": error.severity == ErrorSeverity.INFO,
            "help_available": bool(error.help_links)
        }

        return notification

    def _create_action_buttons(self, error: GitWriteError) -> List[Dict[str, str]]:
        """Create action buttons for error resolution"""

        actions = []

        for recovery_option in error.recovery_options:
            action_type = recovery_option.get("action")

            if action_type == "retry":
                actions.append({
                    "label": "Try Again",
                    "action": "retry_operation",
                    "style": "primary"
                })
            elif action_type == "open_conflict_resolver":
                actions.append({
                    "label": "Resolve Conflicts",
                    "action": "open_conflict_ui",
                    "style": "secondary"
                })
            elif action_type == "show_help":
                actions.append({
                    "label": "Get Help",
                    "action": "show_help",
                    "style": "tertiary"
                })

        # Always add "More Info" button
        actions.append({
            "label": "More Info",
            "action": "show_error_details",
            "style": "link"
        })

        return actions
```

---

*GitWrite's error handling system ensures that writers can work confidently, knowing that errors will be handled gracefully with clear guidance for resolution. The system prioritizes user experience while maintaining robust error tracking and recovery capabilities.*