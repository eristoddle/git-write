"""The Veneer plugin's own TypeScript writes a status commit; GitWrite's Python must read it back unchanged.

The plugin writes YAML with the `yaml` package and GitWrite reads it with PyYAML. They follow different
YAML versions, and under the default rules a comment of `yes` or `2026-10-25` is written bare and read
back as a boolean or a date. This test bundles veneer-plugin/src/feedback.ts, has it write the commit for
a set of awkward annotations, and reads the result with `list_annotations`.

Needs node and `npm ci` in veneer-plugin/. Skips with a message when they are missing; with
GITWRITE_REQUIRE_INTEROP=1 (CI) that is a failure.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pygit2
import pytest

from gitwrite_core.annotations import create_annotation_commit, list_annotations
from gitwrite_core.models import Annotation, AnnotationStatus
from tests.helpers import init_repo, save

PLUGIN = Path(__file__).parent.parent / "veneer-plugin"
ESBUILD = PLUGIN / "node_modules" / ".bin" / "esbuild"

AWKWARD = [
    "yes", "no", "on", "off", "y", "n", "null", "~", "true", "False", "1_000", "0x1F", "0o7", "1:30",
    "2026-10-25", "12e3", "1e5", ".5", "+1", "0123", "", " lead", "trail ", "a: b", "#c", "- d",
    "He said: \"no\" — #hashtag, [brackets], {braces} 😀", "line one\nline two\n  indented", "ünïcödé ✓",
]


@pytest.fixture(scope="module", autouse=True)
def plugin_ready():
    problem = None
    if shutil.which("node") is None:
        problem = "node is not installed"
    elif not ESBUILD.exists():
        problem = f"run `npm ci` in {PLUGIN} first"
    if problem:
        if os.environ.get("GITWRITE_REQUIRE_INTEROP") == "1":
            pytest.fail(f"plugin prerequisites missing in CI: {problem}")
        pytest.skip(f"plugin status-commit test skipped: {problem}")


def _ts_status_messages(tmp_path: Path, annotations: list[dict]) -> list[str]:
    """What the plugin's `statusMessage` writes for each annotation (status: accepted)."""
    bundle = tmp_path / "feedback.mjs"
    built = subprocess.run(
        [str(ESBUILD), str(PLUGIN / "src" / "feedback.ts"), "--bundle", "--platform=neutral", "--format=esm",
         f"--outfile={bundle}", "--log-level=error"],
        capture_output=True, text=True, check=False,
    )
    assert built.returncode == 0, built.stderr
    runner = tmp_path / "run.mjs"
    runner.write_text(
        "import { readFileSync } from 'node:fs'\n"
        "import { statusMessage } from './feedback.mjs'\n"
        "const input = JSON.parse(readFileSync(process.argv[2], 'utf8'))\n"
        "console.log(JSON.stringify(input.map((a) => statusMessage(a, 'accepted'))))\n"
    )
    data = tmp_path / "annotations.json"
    data.write_text(json.dumps(annotations))
    done = subprocess.run(["node", str(runner), str(data)], capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_text_the_plugin_writes_comes_back_from_python_unchanged(tmp_path):
    repo = init_repo(tmp_path / "project")
    repo.config["user.name"] = "Tester"
    repo.config["user.email"] = "tester@example.com"
    save(repo, {"draft.md": "some text\n"}, "initial")

    # GitWrite (PyYAML) creates one annotation per awkward string, in every text field.
    originals = []
    for i, awkward in enumerate(AWKWARD):
        annotation = Annotation(
            file_path="draft.md", highlighted_text=awkward or "x", start_line=0, end_line=0,
            comment=awkward, author=awkward or "someone", prefix=awkward, suffix=awkward, offset=i,
        )
        create_annotation_commit(repo.workdir, "feedback", annotation)
        originals.append(annotation)
    assert [a.comment for a in list_annotations(repo.workdir, "feedback")] == [a.comment for a in originals]

    # The plugin (yaml package) writes the status commit for each; Python then reads the branch again.
    as_plugin = [
        {"id": a.id, "commitId": a.id, "filePath": a.file_path, "text": a.highlighted_text,
         "startLine": a.start_line, "endLine": a.end_line, "comment": a.comment, "author": a.author,
         "status": "new", "prefix": a.prefix, "suffix": a.suffix, "offset": a.offset}
        for a in originals
    ]
    messages = _ts_status_messages(tmp_path, as_plugin)
    sig = pygit2.Signature("Plugin", "plugin@example.com", 946684800, 0)
    for message in messages:
        tip = repo.references["refs/heads/feedback"].peel(pygit2.Commit)
        repo.create_commit("refs/heads/feedback", sig, sig, message, tip.tree_id, [tip.id])

    after = list_annotations(repo.workdir, "feedback")
    assert len(after) == len(originals)  # each status commit joined its annotation; none became a new one
    for before, now in zip(originals, after, strict=True):
        assert now.id == before.id
        assert now.status == AnnotationStatus.ACCEPTED
        assert now.original_annotation_id == before.id
        for field in ("file_path", "highlighted_text", "comment", "author", "prefix", "suffix", "offset"):
            assert getattr(now, field) == getattr(before, field), (field, getattr(before, field))
            assert type(getattr(now, field)) is type(getattr(before, field))  # not a bool, number or date
