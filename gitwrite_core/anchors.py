"""Annotation anchors (D15): find a highlighted passage again after the file has changed.

An anchor is ``prefix`` and ``suffix`` (about ``CONTEXT_CHARS`` characters of surrounding text each,
clipped at the file edges) plus ``offset`` (where the highlight started). All positions are
character (Unicode code point) indexes into the file text, not bytes and not UTF-16 units; a
JavaScript implementation has to convert (``Array.from(text)``). Lines are 0-indexed and split on
``\\n``, as in ``Annotation.start_line``.

``locate`` tries, in order: prefix + text + suffix, then the text alone, then the stored lines.
"""

from dataclasses import dataclass
from typing import List, Optional

from .models import Annotation

CONTEXT_CHARS = 32


@dataclass(frozen=True)
class Anchor:
    prefix: str
    suffix: str
    offset: int


@dataclass(frozen=True)
class Location:
    """Where a passage was found: ``text[start:end]``. ``method`` is "context", "text" or "line"."""

    start: int
    end: int
    method: str


def _occurrences(text: str, needle: str) -> List[int]:
    found: List[int] = []
    index = text.find(needle)
    while index != -1:
        found.append(index)
        index = text.find(needle, index + 1)
    return found


def _line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index)


def _line_starts(text: str) -> List[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def _closest(candidates: List[int], text: str, start_line: Optional[int], offset: Optional[int],
             shift: int = 0) -> int:
    """Pick among duplicate matches: nearest the stored offset, else nearest the stored line, else first.

    ``shift`` converts a match position to the position of the highlight (used for context matches).
    """
    if len(candidates) == 1:
        return candidates[0]
    if offset is not None:
        return min(candidates, key=lambda c: (abs(c + shift - offset), c))
    if start_line is not None:
        return min(candidates, key=lambda c: (abs(_line_of(text, c + shift) - start_line), c))
    return candidates[0]


def compute_anchor(file_text: str, highlighted_text: str, start_line: Optional[int] = None) -> Optional[Anchor]:
    """Anchor for ``highlighted_text`` inside ``file_text``, or None if it is empty or not found.

    If the text occurs more than once, the occurrence on (or nearest) ``start_line`` is used.
    """
    if not highlighted_text:
        return None
    candidates = _occurrences(file_text, highlighted_text)
    if not candidates:
        return None
    start = _closest(candidates, file_text, start_line, None)
    end = start + len(highlighted_text)
    return Anchor(
        prefix=file_text[max(0, start - CONTEXT_CHARS):start],
        suffix=file_text[end:end + CONTEXT_CHARS],
        offset=start,
    )


def apply_anchor(annotation: Annotation, file_text: str) -> bool:
    """Fill ``prefix``, ``suffix`` and ``offset`` on the annotation from the file text.

    Returns False (and leaves the annotation unchanged) if the highlighted text is not in the file.
    """
    anchor = compute_anchor(file_text, annotation.highlighted_text, annotation.start_line)
    if anchor is None:
        return False
    annotation.prefix, annotation.suffix, annotation.offset = anchor.prefix, anchor.suffix, anchor.offset
    return True


def locate(annotation: Annotation, text: str) -> Optional[Location]:
    """Find the annotated passage in ``text`` (the current file content).

    1. prefix + highlighted text + suffix (skipped for annotations without anchors),
    2. the highlighted text alone,
    3. the stored line range.

    When a tier matches in several places, the match nearest the stored offset (or, without one,
    the stored line) wins. Returns None if even the stored lines are outside the text.
    """
    highlighted = annotation.highlighted_text
    if highlighted:
        if annotation.prefix is not None or annotation.suffix is not None:
            prefix = annotation.prefix or ""
            suffix = annotation.suffix or ""
            hits = _occurrences(text, prefix + highlighted + suffix)
            if hits:
                start = _closest(hits, text, annotation.start_line, annotation.offset, shift=len(prefix)) + len(prefix)
                return Location(start, start + len(highlighted), "context")

        hits = _occurrences(text, highlighted)
        if hits:
            start = _closest(hits, text, annotation.start_line, annotation.offset)
            return Location(start, start + len(highlighted), "text")

    starts = _line_starts(text)
    if annotation.start_line >= len(starts):
        return None
    last = max(annotation.start_line, min(annotation.end_line, len(starts) - 1))
    start = starts[annotation.start_line]
    end = starts[last + 1] - 1 if last + 1 < len(starts) else len(text)  # before the newline
    if end > start and text[end - 1] == "\r":
        end -= 1
    return Location(start, max(start, end), "line")
