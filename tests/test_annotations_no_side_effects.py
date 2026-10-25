"""Annotating must never touch HEAD, the index or the working tree (audit, cleanup priority 4).

The old implementation ran `git checkout <feedback branch>`, which moved HEAD onto the feedback
branch and could clobber or refuse on a writer's unsaved work.
"""

from pathlib import Path

import pygit2
import pytest

from gitwrite_core.annotations import (
    create_annotation_commit,
    list_annotations,
    update_annotation_status,
)
from gitwrite_core.exceptions import AnnotationError, RepositoryOperationError
from gitwrite_core.models import Annotation, AnnotationStatus
from tests.helpers import commit_on, init_repo, save


def _annotation(**overrides) -> Annotation:
    fields = dict(file_path="draft.md", highlighted_text="two", start_line=0, end_line=0,
                  comment="cut this", author="reader@example.com")
    fields.update(overrides)
    return Annotation(**fields)


@pytest.fixture
def repo(tmp_path) -> pygit2.Repository:
    r = init_repo(tmp_path / "repo")
    r.config["user.name"] = "Tester"
    r.config["user.email"] = "tester@example.com"
    save(r, {"draft.md": "one two three\n", "other.md": "other\n"}, "initial")
    return r


def _snapshot(repo: pygit2.Repository):
    workdir = Path(repo.workdir)
    files = {p.name: p.read_bytes() for p in workdir.iterdir() if p.is_file()}
    return {
        "head_ref": repo.references["HEAD"].target,
        "head_commit": repo.head.target,
        "status": dict(repo.status()),
        "files": files,
        "index": [(e.path, str(e.id)) for e in repo.index],
    }


def test_creating_an_annotation_leaves_head_index_and_worktree_alone(repo):
    before = _snapshot(repo)

    create_annotation_commit(repo.workdir, "feedback", _annotation())

    assert _snapshot(repo) == before
    assert repo.head.shorthand == "main"


def test_unsaved_work_survives_annotating(repo):
    workdir = Path(repo.workdir)
    (workdir / "draft.md").write_text("one two three\nan unsaved sentence\n")
    (workdir / "untracked.md").write_text("brand new\n")
    repo.index.add("other.md")
    before = _snapshot(repo)

    annotation_id = create_annotation_commit(repo.workdir, "feedback", _annotation())
    update_annotation_status(repo.workdir, "feedback", annotation_id, AnnotationStatus.ACCEPTED)

    assert _snapshot(repo) == before
    assert (workdir / "draft.md").read_text().endswith("an unsaved sentence\n")


def test_updating_status_also_leaves_everything_alone(repo):
    annotation_id = create_annotation_commit(repo.workdir, "feedback", _annotation())
    before = _snapshot(repo)

    update_annotation_status(repo.workdir, "feedback", annotation_id, AnnotationStatus.REJECTED)

    assert _snapshot(repo) == before


def test_feedback_commits_change_no_files(repo):
    base = repo.head.peel(pygit2.Commit)
    annotation_id = create_annotation_commit(repo.workdir, "feedback", _annotation())
    status_id = update_annotation_status(repo.workdir, "feedback", annotation_id, AnnotationStatus.ACCEPTED)

    annotation_commit = repo.get(annotation_id)
    status_commit = repo.get(status_id)
    assert annotation_commit.tree_id == base.tree_id == status_commit.tree_id
    assert [p.id for p in annotation_commit.parents] == [base.id]  # branch starts at HEAD
    assert [p.id for p in status_commit.parents] == [annotation_commit.id]
    assert repo.references["refs/heads/feedback"].target == status_commit.id


def test_main_history_is_not_polluted(repo):
    main_tip = repo.references["refs/heads/main"].target

    create_annotation_commit(repo.workdir, "feedback", _annotation())

    assert repo.references["refs/heads/main"].target == main_tip


def test_an_existing_feedback_branch_is_extended_not_recreated(repo):
    first = create_annotation_commit(repo.workdir, "feedback", _annotation(comment="first"))
    save(repo, {"draft.md": "changed on main\n"}, "main moves on")

    second = create_annotation_commit(repo.workdir, "feedback", _annotation(comment="second"))

    assert [p.id for p in repo.get(second).parents] == [repo.get(first).id]
    assert [a.comment for a in list_annotations(repo.workdir, "feedback")] == ["first", "second"]


def test_works_in_a_bare_repository(tmp_path, repo):
    bare_path = tmp_path / "bare.git"
    pygit2.clone_repository(repo.workdir, str(bare_path), bare=True)

    annotation_id = create_annotation_commit(str(bare_path), "feedback", _annotation())

    assert [a.id for a in list_annotations(str(bare_path), "feedback")] == [annotation_id]


def test_naming_a_status_commit_updates_the_original_thread(repo):
    annotation_id = create_annotation_commit(repo.workdir, "feedback", _annotation())
    first_status = update_annotation_status(repo.workdir, "feedback", annotation_id, AnnotationStatus.ACCEPTED)

    update_annotation_status(repo.workdir, "feedback", first_status, AnnotationStatus.REJECTED)

    listed = list_annotations(repo.workdir, "feedback")
    assert [(a.id, a.status) for a in listed] == [(annotation_id, AnnotationStatus.REJECTED)]


def test_an_abbreviated_id_is_stored_in_full(repo):
    annotation_id = create_annotation_commit(repo.workdir, "feedback", _annotation())

    status_id = update_annotation_status(repo.workdir, "feedback", annotation_id[:8], AnnotationStatus.ACCEPTED)

    assert f"original_annotation_id: {annotation_id}\n" in repo.get(status_id).message
    assert list_annotations(repo.workdir, "feedback")[0].id == annotation_id


def test_a_commit_that_is_not_on_the_feedback_branch_is_refused(repo):
    create_annotation_commit(repo.workdir, "feedback", _annotation())
    foreign = commit_on(repo, "elsewhere", {"x.md": "x\n"}, "not feedback")

    with pytest.raises(RepositoryOperationError, match="not found on branch 'feedback'"):
        update_annotation_status(repo.workdir, "feedback", str(foreign), AnnotationStatus.ACCEPTED)


def test_updating_a_missing_branch(repo):
    with pytest.raises(RepositoryOperationError, match="Feedback branch 'nope' not found"):
        update_annotation_status(repo.workdir, "nope", "0123456789abcdef", AnnotationStatus.ACCEPTED)


def test_an_unborn_repository_cannot_start_a_feedback_branch(tmp_path):
    empty = init_repo(tmp_path / "empty")

    with pytest.raises(RepositoryOperationError, match="at least one commit"):
        create_annotation_commit(empty.workdir, "feedback", _annotation())

    assert "refs/heads/feedback" not in empty.references


def test_the_annotation_object_gets_its_ids(repo):
    annotation = _annotation()

    sha = create_annotation_commit(repo.workdir, "feedback", annotation)

    assert annotation.id == annotation.commit_id == sha


def test_a_wrong_typed_field_in_a_commit_is_skipped_not_fatal(repo):
    create_annotation_commit(repo.workdir, "feedback", _annotation(comment="good"))
    tip = repo.references["refs/heads/feedback"].peel(pygit2.Commit)
    sig = pygit2.Signature("Tester", "tester@example.com", 946684800, 0)
    bad = ("Annotation: bad.md (Lines x-y)\n\nfile_path: bad.md\nhighlighted_text: t\nstart_line: not-a-number\n"
           "end_line: 1\ncomment: c\nauthor: a\nstatus: new\n")
    repo.create_commit("refs/heads/feedback", sig, sig, bad, tip.tree_id, [tip.id])

    listed = list_annotations(repo.workdir, "feedback")

    assert [a.comment for a in listed] == ["good"]


def test_no_git_cli_is_used_by_annotations():
    source = (Path(__file__).parent.parent / "gitwrite_core" / "annotations.py").read_text()
    assert "subprocess" not in source


def test_annotations_error_types(repo):
    with pytest.raises(AnnotationError):
        update_annotation_status(repo.workdir, "feedback", "--output=x", AnnotationStatus.ACCEPTED)
