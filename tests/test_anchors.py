"""D15 annotation anchors: compute_anchor / locate, and anchors stored in feedback commits."""

import pygit2
import pytest

from gitwrite_core.anchors import CONTEXT_CHARS, Location, apply_anchor, compute_anchor, locate
from gitwrite_core.annotations import (
    create_annotation_commit,
    list_annotations,
    update_annotation_status,
)
from gitwrite_core.models import Annotation, AnnotationStatus
from tests.helpers import init_repo, save

ORIGINAL = (
    "Chapter One\n\n"
    "The rain had not stopped for three days, and the river was rising against the old stone bridge.\n"
    "Marta counted the sandbags twice. Then she counted them again.\n\n"
    "By evening the road was gone.\n"
)
PASSAGE = "Marta counted the sandbags twice."


def _annotated(text: str, passage: str, start_line: int | None = None, **overrides) -> Annotation:
    start_line = text[:text.index(passage)].count("\n") if start_line is None else start_line
    annotation = Annotation(file_path="draft.md", highlighted_text=passage, start_line=start_line,
                            end_line=start_line + passage.count("\n"), comment="c", author="a", **overrides)
    assert apply_anchor(annotation, text)
    return annotation


class TestComputeAnchor:
    def test_prefix_suffix_and_offset(self):
        anchor = compute_anchor(ORIGINAL, PASSAGE)

        start = ORIGINAL.index(PASSAGE)
        assert anchor.offset == start
        assert anchor.prefix == ORIGINAL[start - CONTEXT_CHARS:start]
        assert anchor.suffix == ORIGINAL[start + len(PASSAGE):start + len(PASSAGE) + CONTEXT_CHARS]
        assert len(anchor.prefix) == len(anchor.suffix) == CONTEXT_CHARS

    def test_context_is_clipped_at_the_start_of_the_file(self):
        anchor = compute_anchor("Hello world, this is the file.", "Hello")

        assert anchor.prefix == "" and anchor.offset == 0
        assert anchor.suffix == " world, this is the file."[:CONTEXT_CHARS]

    def test_context_is_clipped_at_the_end_of_the_file(self):
        text = "The file ends here"
        anchor = compute_anchor(text, "here")

        assert anchor.suffix == ""
        assert anchor.prefix == text[:-4][-CONTEXT_CHARS:]
        assert anchor.offset == len(text) - 4

    def test_the_whole_file_has_no_context(self):
        assert compute_anchor("all of it", "all of it") == compute_anchor("all of it", "all of it")
        anchor = compute_anchor("all of it", "all of it")
        assert (anchor.prefix, anchor.suffix, anchor.offset) == ("", "", 0)

    def test_text_not_in_the_file_or_empty_gives_no_anchor(self):
        assert compute_anchor(ORIGINAL, "not here at all") is None
        assert compute_anchor(ORIGINAL, "") is None

    def test_a_repeated_passage_is_anchored_on_the_requested_line(self):
        text = "same words\nsomething else\nsame words\nend\n"

        assert compute_anchor(text, "same words", start_line=0).offset == 0
        assert compute_anchor(text, "same words", start_line=2).offset == text.rindex("same words")

    def test_offsets_count_characters_not_bytes(self):
        text = "héllo wörld — “quoted” 😀 target here"
        anchor = compute_anchor(text, "target")

        assert text[anchor.offset:anchor.offset + 6] == "target"
        assert anchor.prefix.endswith("😀 ")


class TestLocateTiers:
    def test_tier_1_context_finds_the_passage_where_it_is(self):
        annotation = _annotated(ORIGINAL, PASSAGE)

        found = locate(annotation, ORIGINAL)

        assert found == Location(ORIGINAL.index(PASSAGE), ORIGINAL.index(PASSAGE) + len(PASSAGE), "context")

    def test_tier_1_survives_edits_elsewhere_in_the_file(self):
        annotation = _annotated(ORIGINAL, PASSAGE)
        edited = "A new opening paragraph, added later.\n\n" + ORIGINAL + "\nAnd a new ending.\n"

        found = locate(annotation, edited)

        assert found.method == "context"
        assert edited[found.start:found.end] == PASSAGE

    def test_tier_2_text_when_the_surrounding_words_changed(self):
        annotation = _annotated(ORIGINAL, PASSAGE)
        edited = ORIGINAL.replace("The rain had not stopped", "Rain kept falling").replace("Then she counted", "She recounted")

        found = locate(annotation, edited)

        assert found.method == "text"
        assert edited[found.start:found.end] == PASSAGE

    def test_tier_3_line_when_the_passage_itself_was_rewritten(self):
        annotation = _annotated(ORIGINAL, PASSAGE)
        edited = ORIGINAL.replace(PASSAGE, "Marta tallied every sandbag.")

        found = locate(annotation, edited)

        assert found.method == "line"
        assert edited[found.start:found.end] == edited.split("\n")[annotation.start_line]

    def test_tier_3_covers_the_whole_stored_line_range(self):
        text = "zero\none\ntwo\nthree\n"
        annotation = Annotation(file_path="f", highlighted_text="gone", start_line=1, end_line=2, comment="c", author="a")

        found = locate(annotation, text)

        assert (found.method, text[found.start:found.end]) == ("line", "one\ntwo")

    def test_tier_3_last_line_without_a_trailing_newline_and_crlf(self):
        annotation = Annotation(file_path="f", highlighted_text="gone", start_line=1, end_line=1, comment="c", author="a")

        assert locate(annotation, "a\nlast")  == Location(2, 6, "line")
        crlf = locate(annotation, "a\r\nb\r\nc")
        assert "a\r\nb\r\nc"[crlf.start:crlf.end] == "b"

    def test_nothing_found_when_the_lines_are_gone_too(self):
        annotation = Annotation(file_path="f", highlighted_text="gone", start_line=40, end_line=40, comment="c", author="a")

        assert locate(annotation, "short file\n") is None


class TestMovedAndDuplicatedPassages:
    def test_a_passage_moved_with_its_context_is_still_found_by_context(self):
        annotation = _annotated(ORIGINAL, PASSAGE)
        heading = "Chapter One\n\n"
        # The heading moves to the end; the body, with the passage and the text around it, moves up.
        moved = ORIGINAL[len(heading):] + "\n" + heading

        found = locate(annotation, moved)

        assert found.method == "context"
        assert moved[found.start:found.end] == PASSAGE
        assert found.start == ORIGINAL.index(PASSAGE) - len(heading)

    def test_a_passage_moved_without_its_context_is_found_by_text(self):
        annotation = _annotated(ORIGINAL, PASSAGE)
        moved = "Preface: " + PASSAGE + " (moved)\n" + ORIGINAL.replace(PASSAGE, "")

        found = locate(annotation, moved)

        assert found.method == "text"
        assert moved[found.start:found.end] == PASSAGE

    def test_duplicates_are_told_apart_by_their_context(self):
        text = "First scene.\nHe said no.\nSecond scene.\nHe said no.\nThird scene.\n"
        second = _annotated(text, "He said no.", start_line=3)

        found = locate(second, text)

        assert found.method == "context"
        assert found.start == text.rindex("He said no.")

    def test_duplicates_with_changed_context_pick_the_one_nearest_the_old_offset(self):
        text = "First scene.\nHe said no.\nSecond scene.\nHe said no.\nThird scene.\n"
        first = _annotated(text, "He said no.", start_line=1)
        second = _annotated(text, "He said no.", start_line=3)
        edited = text.replace("First scene.", "Opening.").replace("Second scene.", "Middle.").replace("Third scene.", "Close.")

        assert locate(first, edited).start == edited.index("He said no.")
        assert locate(second, edited).start == edited.rindex("He said no.")
        assert locate(first, edited).method == locate(second, edited).method == "text"

    def test_duplicates_without_an_offset_fall_back_to_the_stored_line(self):
        text = "x\nsame\ny\nsame\n"
        annotation = Annotation(file_path="f", highlighted_text="same", start_line=3, end_line=3, comment="c", author="a")

        assert locate(annotation, text).start == text.rindex("same")

    def test_an_annotation_without_anchors_goes_straight_to_text(self):
        annotation = Annotation(file_path="f", highlighted_text=PASSAGE, start_line=2, end_line=2, comment="c", author="a")

        assert locate(annotation, ORIGINAL).method == "text"


@pytest.fixture
def repo(tmp_path) -> pygit2.Repository:
    r = init_repo(tmp_path / "repo")
    r.config["user.name"] = "Tester"
    r.config["user.email"] = "tester@example.com"
    save(r, {"draft.md": ORIGINAL}, "initial")
    return r


class TestAnchorsInFeedbackCommits:
    def test_create_computes_the_anchor_from_the_file_in_head(self, repo):
        annotation = Annotation(file_path="draft.md", highlighted_text=PASSAGE, start_line=3, end_line=3,
                                comment="tighten", author="reader")

        annotation_id = create_annotation_commit(repo.workdir, "feedback", annotation)

        stored = list_annotations(repo.workdir, "feedback")[0]
        expected = compute_anchor(ORIGINAL, PASSAGE, 3)
        assert (stored.prefix, stored.suffix, stored.offset) == (expected.prefix, expected.suffix, expected.offset)
        assert stored.id == annotation_id
        assert f"offset: {expected.offset}\n" in repo.get(annotation_id).message

    def test_a_caller_supplied_anchor_is_kept(self, repo):
        annotation = Annotation(file_path="draft.md", highlighted_text=PASSAGE, start_line=3, end_line=3,
                                comment="c", author="a", prefix="P", suffix="S", offset=7)

        create_annotation_commit(repo.workdir, "feedback", annotation)

        stored = list_annotations(repo.workdir, "feedback")[0]
        assert (stored.prefix, stored.suffix, stored.offset) == ("P", "S", 7)

    @pytest.mark.parametrize("file_path,text", [("missing.md", PASSAGE), ("draft.md", "text that is not in the file")])
    def test_no_anchor_when_the_file_or_text_cannot_be_found(self, repo, file_path, text):
        annotation = Annotation(file_path=file_path, highlighted_text=text, start_line=0, end_line=0, comment="c", author="a")

        annotation_id = create_annotation_commit(repo.workdir, "feedback", annotation)

        stored = list_annotations(repo.workdir, "feedback")[0]
        assert (stored.prefix, stored.suffix, stored.offset) == (None, None, None)
        message = repo.get(annotation_id).message
        assert "prefix" not in message and "offset" not in message

    def test_the_anchor_survives_a_status_change(self, repo):
        annotation = Annotation(file_path="draft.md", highlighted_text=PASSAGE, start_line=3, end_line=3, comment="c", author="a")
        annotation_id = create_annotation_commit(repo.workdir, "feedback", annotation)
        before = list_annotations(repo.workdir, "feedback")[0]

        update_annotation_status(repo.workdir, "feedback", annotation_id, AnnotationStatus.ACCEPTED)

        after = list_annotations(repo.workdir, "feedback")[0]
        assert (after.prefix, after.suffix, after.offset) == (before.prefix, before.suffix, before.offset)
        assert after.status == AnnotationStatus.ACCEPTED

    def test_a_stored_anchor_finds_the_passage_after_the_file_changes(self, repo):
        annotation = Annotation(file_path="draft.md", highlighted_text=PASSAGE, start_line=3, end_line=3, comment="c", author="a")
        create_annotation_commit(repo.workdir, "feedback", annotation)
        stored = list_annotations(repo.workdir, "feedback")[0]
        edited = "Inserted line.\n" + ORIGINAL

        found = locate(stored, edited)

        assert found.method == "context" and edited[found.start:found.end] == PASSAGE

    def test_annotations_written_before_anchors_existed_still_read(self, repo):
        tip = repo.head.peel(pygit2.Commit)
        sig = pygit2.Signature("Tester", "tester@example.com", 946684800, 0)
        legacy = (f"Annotation: draft.md (Lines 3-3)\n\nfile_path: draft.md\nhighlighted_text: {PASSAGE}\n"
                  "start_line: 3\nend_line: 3\ncomment: old format\nauthor: reader\nstatus: new\n")
        repo.create_commit(None, sig, sig, legacy, tip.tree_id, [tip.id])
        repo.references.create("refs/heads/feedback", repo.revparse_single("HEAD").id)
        oid = repo.create_commit("refs/heads/feedback", sig, sig, legacy, tip.tree_id, [tip.id])

        listed = list_annotations(repo.workdir, "feedback")

        assert [(a.id, a.comment, a.prefix, a.suffix, a.offset) for a in listed] == [(str(oid), "old format", None, None, None)]
        assert locate(listed[0], ORIGINAL).method == "text"

    @pytest.mark.parametrize("bad", ["prefix: [1, 2]", "suffix: 5", "offset: not-a-number", "offset: -3", "offset: true"])
    def test_malformed_anchor_values_are_ignored_not_fatal(self, repo, bad):
        tip = repo.head.peel(pygit2.Commit)
        sig = pygit2.Signature("Tester", "tester@example.com", 946684800, 0)
        message = (f"Annotation: draft.md (Lines 3-3)\n\nfile_path: draft.md\nhighlighted_text: {PASSAGE}\n"
                   f"start_line: 3\nend_line: 3\ncomment: c\nauthor: a\nstatus: new\n{bad}\n")
        oid = repo.create_commit(None, sig, sig, message, tip.tree_id, [tip.id])
        repo.references.create("refs/heads/feedback", oid)

        listed = list_annotations(repo.workdir, "feedback")

        assert len(listed) == 1
        assert (listed[0].prefix, listed[0].suffix, listed[0].offset) == (None, None, None)
