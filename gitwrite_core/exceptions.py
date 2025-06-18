class GitWriteError(Exception):
    """Base exception for all gitwrite-core errors."""
    pass

class RepositoryNotFoundError(GitWriteError):
    """Raised when a Git repository is not found."""
    pass

class DirtyWorkingDirectoryError(GitWriteError):
    """Raised when an operation cannot proceed due to uncommitted changes."""
    pass

class CommitNotFoundError(GitWriteError):
    """Raised when a specified commit reference cannot be found."""
    pass

class BranchNotFoundError(GitWriteError):
    """Raised when a specified branch cannot be found."""
    pass

class MergeConflictError(GitWriteError):
    """Raised when a merge or revert results in conflicts."""
    pass

class TagAlreadyExistsError(GitWriteError):
    """Raised when a tag with the given name already exists."""
    pass

class NotEnoughHistoryError(GitWriteError):
    """Raised when an operation cannot be performed due to insufficient commit history."""
    pass

class BranchAlreadyExistsError(GitWriteError):
    """Raised when attempting to create a branch that already exists."""
    pass

class RepositoryEmptyError(GitWriteError):
    """Raised when an operation cannot be performed on an empty repository."""
    pass

class OperationAbortedError(GitWriteError):
    """Raised when an operation is aborted due to a condition that prevents completion (e.g., unsupported operation type)."""
    pass

class NoChangesToSaveError(GitWriteError):
    """Raised when there are no changes to save."""
    pass

class RevertConflictError(MergeConflictError):
    """Raised when a revert results in conflicts."""
    pass

class DetachedHeadError(GitWriteError):
    """Raised when an operation requires a branch but HEAD is detached."""
    pass

class FetchError(GitWriteError):
    """Raised when a fetch operation fails."""
    pass

class PushError(GitWriteError):
    """Raised when a push operation fails."""
    pass

class RemoteNotFoundError(GitWriteError):
    """Raised when a specified remote is not found."""
    pass
