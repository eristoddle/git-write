"""Plain data types shared by gitwrite_core."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AnnotationStatus(str, Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass
class Annotation:
    """One reader annotation, stored as a commit on the feedback branch.

    Line numbers are 0-indexed. ``id`` is the SHA of the creation commit;
    ``commit_id`` is the commit that recorded this version (a status update
    points back at the original through ``original_annotation_id``).
    """

    file_path: str
    highlighted_text: str
    start_line: int
    end_line: int
    comment: str
    author: str
    id: Optional[str] = None
    status: AnnotationStatus = AnnotationStatus.NEW
    commit_id: Optional[str] = None
    original_annotation_id: Optional[str] = None

    def __post_init__(self) -> None:
        if self.start_line < 0 or self.end_line < 0:
            raise ValueError("start_line and end_line must be >= 0")
