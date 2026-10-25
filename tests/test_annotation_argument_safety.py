"""Values that reach the git CLI from annotations must not be able to act as git options.

`git log --output=/tmp/x` and `git show --output=/tmp/x` write a file, so an annotation ID or branch
name of that shape must be rejected before any command runs (audit: remote-API readiness).
"""

import pytest

from gitwrite_core.annotations import (
    create_annotation_commit,
    list_annotations,
    update_annotation_status,
)
from gitwrite_core.exceptions import AnnotationError
from gitwrite_core.models import Annotation, AnnotationStatus
from tests.helpers import init_repo, save


@pytest.fixture
def repo_path(tmp_path):
    repo = init_repo(tmp_path / "repo")
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    save(repo, {"draft.md": "one two three\n"}, "initial")
    return str(tmp_path / "repo")


def _annotation() -> Annotation:
    return Annotation(file_path="draft.md", highlighted_text="two", start_line=0, end_line=0,
                      comment="cut this", author="reader")


def test_valid_flow_still_works(repo_path):
    annotation_id = create_annotation_commit(repo_path, "feedback", _annotation())
    update_id = update_annotation_status(repo_path, "feedback", annotation_id, AnnotationStatus.ACCEPTED)

    listed = {a.id: a for a in list_annotations(repo_path, "feedback")}

    assert annotation_id in listed
    assert update_id != annotation_id


@pytest.mark.parametrize("bad_id", ["--output=OUT", "-p", "HEAD", "main", "abc", "ABCDEF12", "abcd efgh", "", "g" * 8, "a" * 41])
def test_update_rejects_a_commit_id_that_is_not_a_hex_oid(repo_path, tmp_path, bad_id):
    out = tmp_path / "pwned.txt"
    bad_id = bad_id.replace("OUT", str(out))

    with pytest.raises(AnnotationError, match="Invalid commit ID"):
        update_annotation_status(repo_path, "feedback", bad_id, AnnotationStatus.REJECTED)

    assert not out.exists()


@pytest.mark.parametrize("bad_branch", ["--output=OUT", "-b", "-", "", "a..b", "has space", "end.lock", "bad~name"])
def test_branch_names_that_git_could_read_as_options_or_are_illegal_are_rejected(repo_path, tmp_path, bad_branch):
    out = tmp_path / "pwned.txt"
    bad_branch = bad_branch.replace("OUT", str(out))

    with pytest.raises(AnnotationError, match="Invalid feedback branch name"):
        list_annotations(repo_path, bad_branch)
    with pytest.raises(AnnotationError, match="Invalid feedback branch name"):
        create_annotation_commit(repo_path, bad_branch, _annotation())
    with pytest.raises(AnnotationError, match="Invalid feedback branch name"):
        update_annotation_status(repo_path, bad_branch, "abcdef12", AnnotationStatus.ACCEPTED)

    assert not out.exists()


def test_a_branch_with_a_slash_is_fine(repo_path):
    annotation_id = create_annotation_commit(repo_path, "review/editor-1", _annotation())

    assert annotation_id in {a.id for a in list_annotations(repo_path, "review/editor-1")}
