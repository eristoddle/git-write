"""docs/ANNOTATION_FORMAT.md must show what the code really writes.

The example blocks between the BEGIN/END GENERATED markers are rebuilt from real commits.
Set UPDATE_ANNOTATION_DOC=1 to rewrite them after an intentional format change.
"""

import os
import re
from pathlib import Path

import pytest

from gitwrite_core.annotations import create_annotation_commit, update_annotation_status
from gitwrite_core.models import Annotation, AnnotationStatus
from tests.helpers import init_repo, save

DOC = Path(__file__).parent.parent / "docs" / "ANNOTATION_FORMAT.md"
PLACEHOLDER_SHA = "8c1f6e0b4d2a9f37c5e18b60a47d3e92f1b5c7d4"

FILE_TEXT = (
    "The rain had not stopped for three days, and the river was rising against the old stone bridge.\n"
    "Marta counted the sandbags twice. Then she counted them again.\n"
    "By evening the road was gone.\n"
)


def render_examples(tmp_path: Path) -> dict[str, str]:
    repo = init_repo(tmp_path / "project")
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    save(repo, {"chapter1.md": FILE_TEXT}, "Chapter 1 draft")

    annotation = Annotation(
        file_path="chapter1.md", highlighted_text="Marta counted the sandbags twice.",
        start_line=1, end_line=1, comment="Show her fear here instead of telling us.",
        author="beta-reader@example.com",
    )
    annotation_id = create_annotation_commit(repo.workdir, "feedback", annotation)
    status_id = update_annotation_status(repo.workdir, "feedback", annotation_id, AnnotationStatus.ACCEPTED)

    def fence(text: str) -> str:
        return f"```\n{text.rstrip(chr(10))}\n```"

    def stable(message: str) -> str:
        # Real SHAs depend on the commit time: show a fixed one, full in the body and short in the subject.
        return message.replace(annotation_id, PLACEHOLDER_SHA).replace(annotation_id[:7], PLACEHOLDER_SHA[:7])

    return {
        "file": fence("chapter1.md\n\n" + FILE_TEXT),
        "annotation-commit": fence(stable(repo.get(annotation_id).message)),
        "status-commit": fence(stable(repo.get(status_id).message)),
    }


def _block(name: str) -> re.Pattern:
    return re.compile(
        rf"(<!-- BEGIN GENERATED: {re.escape(name)} -->\n)(.*?)(<!-- END GENERATED: {re.escape(name)} -->)", re.S
    )


def test_examples_in_the_format_doc_match_what_the_code_writes(tmp_path):
    examples = render_examples(tmp_path)
    doc = DOC.read_text()
    updated = doc
    for name, rendered in examples.items():
        assert _block(name).search(updated), f"missing generated block '{name}' in {DOC.name}"
        updated = _block(name).sub(lambda m, r=rendered: f"{m.group(1)}{r}\n{m.group(3)}", updated)

    if updated != doc and os.environ.get("UPDATE_ANNOTATION_DOC") == "1":
        DOC.write_text(updated)
        pytest.skip("rewrote the generated blocks in docs/ANNOTATION_FORMAT.md")

    assert updated == doc, (
        "docs/ANNOTATION_FORMAT.md is out of date; run "
        "UPDATE_ANNOTATION_DOC=1 uv run pytest tests/test_annotation_format_doc.py"
    )


def test_every_field_the_code_writes_is_documented(tmp_path):
    doc = DOC.read_text()
    for field in ("file_path", "highlighted_text", "start_line", "end_line", "comment", "author", "status",
                  "prefix", "suffix", "offset", "original_annotation_id"):
        assert f"| `{field}` |" in doc


# --- The reader rules stated in the doc ---

BODY = ("file_path: draft.md\nhighlighted_text: some text\nstart_line: 0\nend_line: 0\n"
        "comment: c\nauthor: a\nstatus: new\n")


def _commit_message(tmp_path: Path, message: str) -> list:
    import pygit2

    from gitwrite_core.annotations import list_annotations

    repo = init_repo(tmp_path / "rules")
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    save(repo, {"draft.md": "some text\n"}, "initial")
    tip = repo.head.peel(pygit2.Commit)
    sig = pygit2.Signature("Tester", "tester@example.com", 946684800, 0)
    oid = repo.create_commit(None, sig, sig, message, tip.tree_id, [tip.id])
    repo.references.create("refs/heads/feedback", oid)
    return list_annotations(repo.workdir, "feedback")


@pytest.mark.parametrize("message,expected_count", [
    (f"Any subject at all\n\n{BODY}", 1),                       # the subject is never parsed
    (f"Annotation: x\n\n{BODY}extra_key: ignored\n", 1),        # unknown keys are ignored
    (f"Annotation: x\nno blank line\n{BODY}", 0),               # the blank second line is required
    (f"Annotation: x\n\n{BODY.replace('status: new', 'status: archived')}", 0),   # unknown status
    (f"Annotation: x\n\n{BODY.replace('status: new', '')}", 0),                   # missing required field
    (f"Annotation: x\n\n{BODY.replace('start_line: 0', 'start_line: zero')}", 0),  # wrong type
    ("Annotation: x\n\n- just\n- a list\n", 0),                 # body must be a mapping
])
def test_reader_rules(tmp_path, message, expected_count):
    assert len(_commit_message(tmp_path, message)) == expected_count
