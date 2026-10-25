"""pygit2 <-> isomorphic-git interop (D8, D12).

Veneer drives git with isomorphic-git; GitWrite's core and CLI use pygit2. A repo made by one must
open cleanly in the other, and must pass `git fsck --strict`.

Needs `node` and `npm ci` run in interop/. Locally the tests skip with a message when those are
missing; with GITWRITE_REQUIRE_INTEROP=1 (set in CI) a missing prerequisite is a failure instead.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pygit2
import pytest
from click.testing import CliRunner

from gitwrite_cli.main import cli
from gitwrite_core.anchors import locate
from gitwrite_core.annotations import (
    create_annotation_commit,
    list_annotations,
    update_annotation_status,
)
from gitwrite_core.branching import list_branches
from gitwrite_core.models import Annotation, AnnotationStatus
from gitwrite_core.repository import list_commits
from gitwrite_core.tagging import list_tags

INTEROP = Path(__file__).parent.parent / "interop"


@pytest.fixture(scope="module", autouse=True)
def node_ready():
    problem = None
    if shutil.which("node") is None:
        problem = "node is not installed"
    elif not (INTEROP / "node_modules" / "isomorphic-git").is_dir():
        problem = f"run `npm ci` in {INTEROP} first"
    if problem:
        if os.environ.get("GITWRITE_REQUIRE_INTEROP") == "1":
            pytest.fail(f"interop prerequisites missing in CI: {problem}")
        pytest.skip(f"interop tests skipped: {problem}")


def node(script: str, *args: str) -> dict:
    done = subprocess.run(["node", str(INTEROP / script), *args], capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"node {script} failed:\n{done.stderr}"
    return json.loads(done.stdout)


def fsck_strict(repo_dir) -> None:
    done = subprocess.run(["git", "-C", str(repo_dir), "fsck", "--strict"], capture_output=True, text=True, check=False)
    assert done.returncode == 0, f"git fsck --strict failed:\n{done.stdout}\n{done.stderr}"


def run_cli(*args: str) -> str:
    result = CliRunner().invoke(cli, list(args))
    assert result.exit_code == 0, f"gitwrite {' '.join(args)} failed:\n{result.output}"
    return result.output


def test_a_repo_made_by_the_gitwrite_cli_reads_cleanly_in_isomorphic_git(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    run_cli("init", "novel")
    project = tmp_path / "novel"
    repo = pygit2.Repository(str(project))
    repo.config["user.name"] = "Py Writer"
    repo.config["user.email"] = "py@example.com"
    monkeypatch.chdir(project)
    main = repo.head.shorthand

    passage = "Marta counted the sandbags twice."
    (project / "chapter1.md").write_text(f"The rain had not stopped.\n{passage} Then she counted them again.\n")
    run_cli("save", "Chapter 1 draft")
    run_cli("explore", "alt-ending")
    (project / "ending.md").write_text("She left at dawn.\n")
    run_cli("save", "Alternate ending")
    run_cli("switch", main)
    run_cli("tag", "add", "draft-1")
    run_cli("tag", "add", "v1", "-m", "First complete draft")

    annotation = Annotation(file_path="chapter1.md", highlighted_text=passage, start_line=1, end_line=1,
                            comment="Show, don't tell.", author="reader@example.com")
    annotation_id = create_annotation_commit(str(project), "feedback", annotation)
    update_annotation_status(str(project), "feedback", annotation_id, AnnotationStatus.ACCEPTED)
    assert repo.head.shorthand == main  # annotating did not move HEAD

    seen = node("read-repo.mjs", str(project))

    assert seen["branches"] == sorted(repo.branches.local)
    assert seen["current"] == main
    expected_history = [str(c.id) for c in repo.walk(repo.branches.local[main].target, pygit2.GIT_SORT_TOPOLOGICAL)]
    assert [c["oid"] for c in seen["history"]] == expected_history
    assert seen["history"][0]["subject"] == "Chapter 1 draft"

    tags = {t["name"]: t for t in seen["tags"]}
    head = str(repo.branches.local[main].target)
    assert tags["draft-1"] == {"name": "draft-1", "type": "lightweight", "target": head}
    assert tags["v1"] == {"name": "v1", "type": "annotated", "target": head, "message": "First complete draft"}

    assert [c["sameTreeAsParent"] for c in seen["feedbackCommits"][:2]] == [True, True]
    (read,) = seen["annotations"]
    assert read["id"] == annotation_id
    assert read["status"] == "accepted"
    assert read["original_annotation_id"] == annotation_id
    assert read["comment"] == "Show, don't tell."
    assert read["highlighted_text"] == passage
    assert read["offset"] == (project / "chapter1.md").read_text().index(passage)
    assert read["prefix"] == "The rain had not stopped.\n"

    fsck_strict(project)


def test_a_repo_made_by_isomorphic_git_reads_cleanly_in_gitwrite_core_and_cli(tmp_path, monkeypatch):
    project = tmp_path / "iso-project"
    made = node("write-repo.mjs", str(project))
    fsck_strict(project)
    repo_path = str(project)

    # history and branches
    commits = list_commits(repo_path)["commits"]
    assert [c["sha"] for c in commits] == [made["second"], made["first"]]
    assert [c["message"] for c in commits] == ["Main revision", "Chapter 1 draft"]
    assert commits[0]["author_name"] == "Iso Writer"
    branches = {b["name"]: b for b in list_branches(repo_path)}
    assert set(branches) == {"alt-ending", "feedback", "main"}
    assert branches["main"]["is_current"] and branches["alt-ending"]["target_oid"] == made["altTip"]

    # tags
    tags = {t["name"]: t for t in list_tags(repo_path)}
    assert tags["draft-1"] == {"name": "draft-1", "type": "lightweight", "target": made["first"]}
    assert tags["v1"] == {"name": "v1", "type": "annotated", "target": made["second"], "message": "First complete draft"}

    # annotations written by isomorphic-git: multi-line prefix, emoji, a colon in the comment
    (annotation,) = list_annotations(repo_path, "feedback")
    assert annotation.id == made["annotationId"] and annotation.commit_id == made["statusId"]
    assert annotation.status == AnnotationStatus.ACCEPTED
    assert annotation.comment == made["comment"]
    assert annotation.highlighted_text == made["highlighted"]
    assert (annotation.prefix, annotation.suffix, annotation.offset) == (
        made["anchor"]["prefix"], made["anchor"]["suffix"], made["anchor"]["offset"])
    chapter = (project / "chapter1.md").read_text()
    chapter_at_annotation = chapter.removesuffix("The end, for now.\n")
    found = locate(annotation, chapter_at_annotation)
    assert found.method == "context" and found.start == made["anchor"]["offset"]  # code-point offsets agree
    assert chapter_at_annotation[found.start:found.end] == made["highlighted"]

    # the CLI works on it, and GitWrite can add to it
    monkeypatch.chdir(project)
    assert "Main revision" in run_cli("history")
    assert "v1" in run_cli("tag", "list") and "draft-1" in run_cli("tag", "list")
    assert "Alternate ending" in run_cli("review", "alt-ending")
    run_cli("status")
    repo = pygit2.Repository(repo_path)
    repo.config["user.name"] = "Py Writer"
    repo.config["user.email"] = "py@example.com"
    (project / "chapter1.md").write_text(chapter + "More from GitWrite.\n")
    run_cli("save", "Saved by GitWrite")
    run_cli("tag", "add", "v2", "-m", "Second")
    reply = Annotation(file_path="chapter1.md", highlighted_text="The end, for now.", start_line=3, end_line=3,
                       comment="Cut this?", author="py@example.com")
    reply_id = create_annotation_commit(repo_path, "feedback", reply)

    again = node("read-repo.mjs", repo_path)
    assert again["history"][0]["subject"] == "Saved by GitWrite"
    assert {t["name"] for t in again["tags"]} == {"draft-1", "v1", "v2"}
    assert [a["id"] for a in again["annotations"]] == [made["annotationId"], reply_id]
    assert again["annotations"][1]["status"] == "new"
    assert again["current"] == "main"
    fsck_strict(project)
