"""docs/annotation-locate-vectors.json: what `locate` returns for a set of cases, as data.

The Veneer plugin re-implements `locate` in TypeScript (it cannot call Python). Both sides read this
file, so the two cannot drift: the plugin's tests check its answers against it, and this test checks
that the file still says what the Python code does. Positions are code points, as in Python; the
plugin converts. Set UPDATE_LOCATE_VECTORS=1 to rewrite the file after an intentional change.

The status-commit case does the same for the commit a plugin writes when a comment is accepted or
rejected: the plugin's message must carry exactly these fields.
"""

import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest
import yaml

from gitwrite_core.anchors import compute_anchor, locate
from gitwrite_core.annotations import create_annotation_commit, update_annotation_status
from gitwrite_core.models import Annotation, AnnotationStatus
from tests.helpers import init_repo, save

VECTORS = Path(__file__).parent.parent / "docs" / "annotation-locate-vectors.json"
FIXED_SHA = "8c1f6e0b4d2a9f37c5e18b60a47d3e92f1b5c7d4"

STORY = (
    "The rain had not stopped for three days, and the river was rising against the old stone bridge.\n"
    "Marta counted the sandbags twice. Then she counted them again.\n"
    "By evening the road was gone.\n"
)
PASSAGE = "Marta counted the sandbags twice."
SCENE = "First scene.\nHe said no.\nSecond scene.\nHe said no.\nThird scene.\n"


def _annotation(text: str, passage: str, start_line: int | None = None, **overrides) -> dict:
    """An anchored annotation as a plain dict (what the plugin reads from a commit)."""
    if start_line is None:
        start_line = text[: text.index(passage)].count("\n")
    anchor = compute_anchor(text, passage, start_line)
    fields = dict(
        highlighted_text=passage, start_line=start_line, end_line=start_line + passage.count("\n"),
        prefix=anchor.prefix if anchor else None, suffix=anchor.suffix if anchor else None,
        offset=anchor.offset if anchor else None,
    )
    fields.update(overrides)
    return fields


def _bare(passage: str, start_line: int, end_line: int | None = None, **overrides) -> dict:
    fields = dict(highlighted_text=passage, start_line=start_line,
                  end_line=start_line if end_line is None else end_line, prefix=None, suffix=None, offset=None)
    fields.update(overrides)
    return fields


def cases() -> list[tuple[str, str, dict]]:
    moved_head = "Chapter One\n\n"
    edited = STORY.replace("The rain had not stopped", "Rain kept falling").replace("Then she counted", "She recounted")
    emoji = "😀 intro 😀\nMarta counted the sandbags twice. 😀 Then she counted them again.\nEnd.\n"
    return [
        ("context tier finds the passage where it is", STORY, _annotation(STORY, PASSAGE)),
        ("context survives edits elsewhere", "New opening.\n\n" + STORY + "\nNew ending.\n", _annotation(STORY, PASSAGE)),
        ("text tier when the words around it changed", edited, _annotation(STORY, PASSAGE)),
        ("line tier when the passage itself was rewritten",
         STORY.replace(PASSAGE, "Marta tallied every sandbag."), _annotation(STORY, PASSAGE)),
        ("moved with its context", STORY[len(moved_head):] + "\n" + moved_head, _annotation(STORY, PASSAGE)),
        ("moved without its context", "Preface: " + PASSAGE + " (moved)\n" + STORY.replace(PASSAGE, ""),
         _annotation(STORY, PASSAGE)),
        ("duplicates told apart by context", SCENE, _annotation(SCENE, "He said no.", start_line=3)),
        ("duplicates, context changed: nearest the old offset",
         SCENE.replace("First scene.", "Opening.").replace("Second scene.", "Middle.").replace("Third scene.", "Close."),
         _annotation(SCENE, "He said no.", start_line=3)),
        ("duplicates, no offset: nearest the stored line", "x\nsame\ny\nsame\n", _bare("same", 3)),
        ("no anchors goes straight to text", STORY, _bare(PASSAGE, 1)),
        ("anchor clipped at the start of the file", "Hello world, this is the file.", _annotation("Hello world, this is the file.", "Hello")),
        ("anchor clipped at the end of the file", "The file ends here", _annotation("The file ends here", "here")),
        ("whole file is the passage", "all of it", _annotation("all of it", "all of it")),
        ("line range covers several lines", "zero\none\ntwo\nthree\n", _bare("gone", 1, 2)),
        ("last line without a newline", "a\nlast", _bare("gone", 1)),
        ("crlf line endings", "a\r\nb\r\nc", _bare("gone", 1)),
        ("end line is clamped to the last line", "a\nb", _bare("gone", 1, 40)),
        ("end line before start line is raised to it", "a\nb\nc", _bare("gone", 1, 0)),
        ("nothing found when the lines are gone too", "short file\n", _bare("gone", 40)),
        ("empty highlighted text skips text matching", STORY, _bare("", 2)),
        # A case-insensitive search would see two matches here and take the one on line 0.
        ("matching is exact, not case-insensitive", "The Lazy Dog\nthe lazy dog\n", _bare("the lazy dog", 0)),
        ("overlapping occurrences are all candidates", "aaaa", _bare("aaa", 0, offset=1, prefix="", suffix="")),
        ("code points not UTF-16 units (emoji before the passage)", emoji,
         _annotation(emoji, "Marta counted the sandbags twice. 😀")),
        ("emoji, text tier, offset in code points", emoji.replace("intro", "opening"),
         _annotation(emoji, "Marta counted the sandbags twice. 😀")),
        # Offset 30 is the second "same" in code points; counted in UTF-16 units the first one would be nearest.
        ("nearest the stored offset is measured in code points",
         "😀" * 6 + "a" * 18 + "same" + "bb" + "same", _bare("same", 0, prefix="zzz", suffix="", offset=30)),
        ("a tie in offset distance goes to the earlier match",
         "a" * 5 + "same" + "b" * 6 + "same", _bare("same", 0, prefix="zzz", suffix="", offset=10)),
        ("a tie in line distance goes to the earlier match", "same\nx\nsame", _bare("same", 1)),
        ("a duplicate after an emoji picks the right one by code-point offset",
         "😀😀😀 a\nsame\n😀😀😀 b\nsame\n", _annotation("😀😀😀 a\nsame\n😀😀😀 b\nsame\n", "same", start_line=3)),
    ]


def build_vectors(tmp_path: Path) -> dict:
    located = []
    for name, text, fields in cases():
        annotation = Annotation(file_path="draft.md", comment="c", author="a", **fields)
        found = locate(annotation, text)
        located.append({
            "name": name,
            "text": text,
            "annotation": fields,
            "expected": None if found is None else {"start": found.start, "end": found.end, "method": found.method},
        })
    return {"locate": located, "statusCommit": _status_commit(tmp_path)}


def _status_commit(tmp_path: Path) -> dict:
    """The commit `update_annotation_status` writes, parsed, with the SHA replaced by a fixed one."""
    repo = init_repo(tmp_path / "project")
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    save(repo, {"chapter1.md": STORY}, "Chapter 1 draft")
    annotation = Annotation(file_path="chapter1.md", highlighted_text=PASSAGE, start_line=1, end_line=1,
                            comment="Show her fear: \"tell\" less, and mind the colon: here.",
                            author="reader@example.com")
    annotation_id = create_annotation_commit(repo.workdir, "feedback", annotation)
    created = yaml.safe_load(repo.get(annotation_id).message.split("\n", 2)[2])
    status_id = update_annotation_status(repo.workdir, "feedback", annotation_id, AnnotationStatus.ACCEPTED)
    message = repo.get(status_id).message.replace(annotation_id, FIXED_SHA).replace(annotation_id[:7], FIXED_SHA[:7])
    subject, _, body = message.split("\n", 2)[0], None, message.split("\n", 2)[2]
    return {
        "annotationId": FIXED_SHA,
        "created": created,
        "newStatus": "accepted",
        "subject": subject,
        "body": yaml.safe_load(body),
        "fieldOrder": list(yaml.safe_load(body).keys()),
    }


def test_vectors_file_matches_what_locate_does(tmp_path):
    built = build_vectors(tmp_path)
    text = json.dumps(built, indent=1, ensure_ascii=False) + "\n"
    if os.environ.get("UPDATE_LOCATE_VECTORS") == "1":
        VECTORS.write_text(text, encoding="utf-8")
        pytest.skip("rewrote docs/annotation-locate-vectors.json")
    assert VECTORS.read_text(encoding="utf-8") == text, (
        "docs/annotation-locate-vectors.json is out of date; run "
        "UPDATE_LOCATE_VECTORS=1 uv run pytest tests/test_locate_vectors.py"
    )


def test_every_case_is_a_real_decision(tmp_path):
    """The vectors cover all three tiers and the no-match case, so a plugin cannot pass by returning one answer."""
    built = build_vectors(tmp_path)
    methods = {c["expected"]["method"] if c["expected"] else None for c in built["locate"]}
    assert methods == {"context", "text", "line", None}
    assert len({json.dumps(c["expected"]) for c in built["locate"]}) > 15
    assert asdict(Annotation(file_path="f", highlighted_text="t", start_line=0, end_line=0, comment="c", author="a"))
