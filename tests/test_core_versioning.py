import os
import shutil
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
import re # For ISO date string regex matching

import pygit2
import pytest
from typing import Optional, Dict, Any # Added Dict, Any for get_diff tests

from gitwrite_core.versioning import get_commit_history, get_diff # Added get_diff
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, NotEnoughHistoryError # Added new exceptions

# Helper function to create commits
def make_commit(
    repo: pygit2.Repository,
    filename: str,
    content: str,
    message: str,
    author_name: str = "Test Author",
    author_email: str = "test@example.com",
    author_time_offset_minutes: int = 0,
    committer_name: str = "Test Committer",
    committer_email: str = "committer@example.com",
    committer_time_offset_minutes: int = 0,
    commit_time: Optional[int] = None
) -> pygit2.Oid:
    """
    Helper function to create a commit in the repository.
    If commit_time is None, current time is used.
    """
    if commit_time is None:
        commit_time = int(time.time())

    author_sig = pygit2.Signature(
        author_name, author_email, commit_time, author_time_offset_minutes
    )
    committer_sig = pygit2.Signature(
        committer_name, committer_email, commit_time, committer_time_offset_minutes
    )

    # Create a file and add it to the index
    full_path = Path(repo.workdir) / filename
    full_path.parent.mkdir(parents=True, exist_ok=True)
    with open(full_path, "w") as f:
        f.write(content)

    repo.index.add(filename)
    tree_oid = repo.index.write_tree()

    parents = []
    if not repo.is_empty and not repo.head_is_unborn:
        parents = [repo.head.target]

    commit_oid = repo.create_commit("refs/heads/main", author_sig, committer_sig, message, tree_oid, parents)
    if repo.head_is_unborn: # After first commit, point HEAD to main
        repo.set_head("refs/heads/main")
    return commit_oid

class TestGetCommitHistoryCore:
    # ISO 8601 date format regex (simplified for YYYY-MM-DD HH:MM:SS +/-ZZZZ)
    ISO_8601_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4}$")

    def test_get_history_non_repository(self, tmp_path: Path):
        """Test calling get_commit_history on a non-repository path."""
        non_repo_path = tmp_path / "not_a_repo"
        non_repo_path.mkdir()
        with pytest.raises(RepositoryNotFoundError):
            get_commit_history(str(non_repo_path))

    def test_get_history_bare_repository(self, tmp_path: Path):
        """Test get_commit_history on a bare repository."""
        bare_repo_path = tmp_path / "bare_repo.git"
        pygit2.init_repository(str(bare_repo_path), bare=True)
        history = get_commit_history(str(bare_repo_path))
        assert history == []

    def test_get_history_empty_repository(self, tmp_path: Path):
        """Test get_commit_history on an empty (non-bare) repository."""
        empty_repo_path = tmp_path / "empty_repo"
        pygit2.init_repository(str(empty_repo_path)) # Non-bare
        history = get_commit_history(str(empty_repo_path))
        assert history == []

    def test_get_history_unborn_head(self, tmp_path: Path):
        """Test get_commit_history on a repository with an unborn HEAD."""
        repo_path = tmp_path / "unborn_head_repo"
        # Initialize repo, but make no commits
        pygit2.init_repository(str(repo_path))
        history = get_commit_history(str(repo_path))
        assert history == []

    def test_get_history_single_commit(self, tmp_path: Path):
        """Test history with a single commit."""
        repo_path = tmp_path / "single_commit_repo"
        repo = pygit2.init_repository(str(repo_path))

        commit_msg = "Initial commit"
        commit_oid = make_commit(repo, "file.txt", "content", commit_msg)

        history = get_commit_history(str(repo_path))

        assert len(history) == 1
        commit_info = history[0]

        expected_keys = [
            "short_hash", "author_name", "author_email", "date",
            "committer_name", "committer_email", "committer_date",
            "message", "message_short", "oid"
        ]
        for key in expected_keys:
            assert key in commit_info

        assert len(commit_info["short_hash"]) == 7
        assert commit_info["oid"] == str(commit_oid)
        assert commit_info["message"] == commit_msg
        assert commit_info["message_short"] == commit_msg # Single line message
        assert self.ISO_8601_PATTERN.match(commit_info["date"])
        assert self.ISO_8601_PATTERN.match(commit_info["committer_date"])

    def test_get_history_multiple_commits_default_order(self, tmp_path: Path):
        """Test history with multiple commits, checking default order (reverse chronological)."""
        repo_path = tmp_path / "multi_commit_repo"
        repo = pygit2.init_repository(str(repo_path))

        commit_oid1 = make_commit(repo, "file1.txt", "content1", "Commit 1", commit_time=int(time.time()) - 200)
        time.sleep(0.1) # Ensure time difference for ordering
        commit_oid2 = make_commit(repo, "file2.txt", "content2", "Commit 2", commit_time=int(time.time()) - 100)
        time.sleep(0.1)
        commit_oid3 = make_commit(repo, "file3.txt", "content3", "Commit 3", commit_time=int(time.time()))

        history = get_commit_history(str(repo_path))

        assert len(history) == 3
        assert history[0]["oid"] == str(commit_oid3) # Most recent
        assert history[1]["oid"] == str(commit_oid2)
        assert history[2]["oid"] == str(commit_oid1) # Oldest

    def test_get_history_with_count_limit(self, tmp_path: Path):
        """Test history with a count limit."""
        repo_path = tmp_path / "count_limit_repo"
        repo = pygit2.init_repository(str(repo_path))

        make_commit(repo, "file1.txt", "c1", "Commit 1", commit_time=int(time.time()) - 300)
        time.sleep(0.1)
        commit_oid2 = make_commit(repo, "file2.txt", "c2", "Commit 2", commit_time=int(time.time()) - 200)
        time.sleep(0.1)
        commit_oid3 = make_commit(repo, "file3.txt", "c3", "Commit 3", commit_time=int(time.time()) - 100)

        history = get_commit_history(str(repo_path), count=2)

        assert len(history) == 2
        assert history[0]["oid"] == str(commit_oid3) # Most recent
        assert history[1]["oid"] == str(commit_oid2)

    def test_get_history_count_greater_than_commits(self, tmp_path: Path):
        """Test history when count is greater than available commits."""
        repo_path = tmp_path / "count_over_repo"
        repo = pygit2.init_repository(str(repo_path))

        commit_oid1 = make_commit(repo, "file1.txt", "c1", "Commit 1", commit_time=int(time.time()) - 100)
        time.sleep(0.1)
        commit_oid2 = make_commit(repo, "file2.txt", "c2", "Commit 2", commit_time=int(time.time()))

        history = get_commit_history(str(repo_path), count=5)

        assert len(history) == 2
        assert history[0]["oid"] == str(commit_oid2)
        assert history[1]["oid"] == str(commit_oid1)

    def test_get_history_commit_details_accuracy(self, tmp_path: Path):
        """Thoroughly test commit details for accuracy, including multi-line messages and timezones."""
        repo_path = tmp_path / "details_repo"
        repo = pygit2.init_repository(str(repo_path))

        author_name = "Detailed Author"
        author_email = "detailed.author@example.com"
        committer_name = "Meticulous Committer"
        committer_email = "meticulous.committer@example.com"

        # Specific timestamp (e.g., 2023-03-15 12:00:00 UTC)
        fixed_commit_time = 1678881600
        author_offset_mins = -480  # UTC-8
        committer_offset_mins = 120   # UTC+2

        commit_msg_full = "Detailed commit message.\n\nThis is the second line.\nAnd a third."
        commit_msg_short = "Detailed commit message."

        commit_oid = make_commit(
            repo,
            "detail.txt",
            "detailed content",
            commit_msg_full,
            author_name=author_name,
            author_email=author_email,
            author_time_offset_minutes=author_offset_mins,
            committer_name=committer_name,
            committer_email=committer_email,
            committer_time_offset_minutes=committer_offset_mins,
            commit_time=fixed_commit_time
        )

        history = get_commit_history(str(repo_path))
        assert len(history) == 1
        commit_info = history[0]

        assert commit_info["oid"] == str(commit_oid)
        assert commit_info["short_hash"] == str(commit_oid)[:7]
        assert commit_info["message"] == commit_msg_full.strip() # core function strips message
        assert commit_info["message_short"] == commit_msg_short

        assert commit_info["author_name"] == author_name
        assert commit_info["author_email"] == author_email
        assert commit_info["committer_name"] == committer_name
        assert commit_info["committer_email"] == committer_email

        # Verify date strings
        assert self.ISO_8601_PATTERN.match(commit_info["date"])
        assert self.ISO_8601_PATTERN.match(commit_info["committer_date"])

        # More precise date verification
        # Author: 2023-03-15 12:00:00 UTC, offset -480 minutes (UTC-8) -> 2023-03-15 04:00:00 -0800
        # Committer: 2023-03-15 12:00:00 UTC, offset +120 minutes (UTC+2) -> 2023-03-15 14:00:00 +0200

        # Construct expected datetime objects with timezone awareness
        expected_author_dt = datetime.fromtimestamp(fixed_commit_time, tz=timezone(timedelta(minutes=author_offset_mins)))
        expected_committer_dt = datetime.fromtimestamp(fixed_commit_time, tz=timezone(timedelta(minutes=committer_offset_mins)))

        # Format them to the expected string format
        expected_author_date_str = expected_author_dt.strftime('%Y-%m-%d %H:%M:%S %z')
        expected_committer_date_str = expected_committer_dt.strftime('%Y-%m-%d %H:%M:%S %z')

        # If %z outputs "+HHMM" or "-HHMM", we might need to add a colon for full fromisoformat compatibility,
        # but the current format in get_commit_history is "%Y-%m-%d %H:%M:%S %z" which usually gives "+HHMM"
        # Let's check if the output string matches this logic.
        # The function output is 'YYYY-MM-DD HH:MM:SS SZZZZ' (S is sign, ZZZZ is offset like 0800)
        # Example: '2023-03-15 04:00:00 -0800'

        assert commit_info["date"] == expected_author_date_str
        assert commit_info["committer_date"] == expected_committer_date_str

        # Test with a zero offset to ensure it's handled correctly (e.g., +0000)
        zero_offset_commit_time = 1678890000 # 2023-03-15 14:20:00 UTC
        zero_offset_oid = make_commit(
            repo, "zero_offset.txt", "content", "Zero offset commit",
            author_time_offset_minutes=0,
            committer_time_offset_minutes=0,
            commit_time=zero_offset_commit_time
        )
        history_zero_offset = get_commit_history(str(repo_path), count=1) # Get the latest
        assert history_zero_offset[0]["oid"] == str(zero_offset_oid)

        expected_zero_offset_dt = datetime.fromtimestamp(zero_offset_commit_time, tz=timezone.utc)
        # strftime with %z for UTC might give +0000 or Z. pygit2 uses offset in minutes, so it should be +0000 or -0000.
        # Our function datetime.fromtimestamp(..., tz=timezone(timedelta(minutes=0))).strftime('%Y-%m-%d %H:%M:%S %z')
        # For timedelta(minutes=0), strftime %z gives "+0000"
        assert "+0000" in history_zero_offset[0]["date"]
        assert history_zero_offset[0]["date"] == expected_zero_offset_dt.strftime('%Y-%m-%d %H:%M:%S %z')

class TestGetDiffCore:
    def test_get_diff_non_repository(self, tmp_path: Path):
        """Test get_diff with a non-repository path."""
        non_repo_path = tmp_path / "not_a_repo_for_diff"
        non_repo_path.mkdir()
        with pytest.raises(RepositoryNotFoundError):
            get_diff(str(non_repo_path))

    def test_get_diff_empty_repository_default_compare(self, tmp_path: Path):
        """Test get_diff on an empty repo (HEAD~1 vs HEAD)."""
        repo_path = tmp_path / "empty_repo_for_diff"
        pygit2.init_repository(str(repo_path))
        with pytest.raises(NotEnoughHistoryError, match="Repository is empty or HEAD is unborn."):
            get_diff(str(repo_path))

    def test_get_diff_initial_commit_default_compare(self, tmp_path: Path):
        """Test get_diff on a repo with only the initial commit (HEAD~1 vs HEAD)."""
        repo_path = tmp_path / "initial_commit_repo_for_diff"
        repo = pygit2.init_repository(str(repo_path))
        make_commit(repo, "file.txt", "content", "Initial commit")
        with pytest.raises(NotEnoughHistoryError, match="HEAD is the initial commit and has no parent to compare with."):
            get_diff(str(repo_path))

    def test_get_diff_no_differences(self, tmp_path: Path):
        """Test get_diff when there are no differences between two commits."""
        repo_path = tmp_path / "no_diff_repo"
        repo = pygit2.init_repository(str(repo_path))
        commit1_oid = make_commit(repo, "file.txt", "content", "Commit 1")
        # No changes before commit 2, but make_commit creates a new commit object if called.
        # To ensure identical trees, we can compare commit1 to itself.

        diff_data = get_diff(str(repo_path), ref1_str=str(commit1_oid), ref2_str=str(commit1_oid))

        assert diff_data["ref1_oid"] == str(commit1_oid)
        assert diff_data["ref2_oid"] == str(commit1_oid)
        assert diff_data["ref1_display_name"] == str(commit1_oid) # Was passed as str
        assert diff_data["ref2_display_name"] == str(commit1_oid) # Was passed as str
        assert diff_data["patch_text"] == ""

    def test_get_diff_simple_content_change(self, tmp_path: Path):
        """Test get_diff with a simple content change in a file."""
        repo_path = tmp_path / "content_change_repo"
        repo = pygit2.init_repository(str(repo_path))

        commit1_oid = make_commit(repo, "file.txt", "content A", "Commit A")
        commit2_oid = make_commit(repo, "file.txt", "content B", "Commit B")

        diff_data = get_diff(str(repo_path), ref1_str=str(commit1_oid), ref2_str=str(commit2_oid))

        assert diff_data["ref1_oid"] == str(commit1_oid)
        assert diff_data["ref2_oid"] == str(commit2_oid)
        assert diff_data["patch_text"] != ""
        assert "--- a/file.txt" in diff_data["patch_text"]
        assert "+++ b/file.txt" in diff_data["patch_text"]
        assert "-content A" in diff_data["patch_text"]
        assert "+content B" in diff_data["patch_text"]

    def test_get_diff_file_addition(self, tmp_path: Path):
        """Test get_diff when a file is added."""
        repo_path = tmp_path / "file_add_repo"
        repo = pygit2.init_repository(str(repo_path))

        commit1_oid = make_commit(repo, "old_file.txt", "old content", "Commit 1")
        commit2_oid = make_commit(repo, "new_file.txt", "new content", "Commit 2 adds new_file.txt")

        diff_data = get_diff(str(repo_path), ref1_str=str(commit1_oid), ref2_str=str(commit2_oid))

        assert "+++ b/new_file.txt" in diff_data["patch_text"]
        assert "+new content" in diff_data["patch_text"]
        # old_file.txt should not appear as changed in this diff context if it wasn't touched by commit2's tree vs commit1's tree
        # The diff is tree-to-tree. If new_file.txt is the only change between the trees, only it appears.
        # If make_commit for commit2 re-added old_file.txt with same content, it's not a diff.
        # This test implicitly relies on make_commit behavior.
        # Let's ensure old_file.txt is not in the patch:
        assert "old_file.txt" not in diff_data["patch_text"]


    def test_get_diff_file_deletion(self, tmp_path: Path):
        """Test get_diff when a file is deleted."""
        repo_path = tmp_path / "file_delete_repo"
        repo = pygit2.init_repository(str(repo_path))

        make_commit(repo, "file_to_delete.txt", "some content", "Commit 1 adds file")
        commit1_oid = repo.head.target

        # To delete, we need to operate on the index before the next commit
        index = repo.index
        index.read() # Load current index
        index.remove("file_to_delete.txt")
        tree_oid_for_commit2 = index.write_tree()

        author_sig = pygit2.Signature("Test Author", "del@example.com", int(time.time()), 0)
        committer_sig = author_sig
        commit2_oid = repo.create_commit("refs/heads/main", author_sig, committer_sig, "Commit 2 deletes file", tree_oid_for_commit2, [commit1_oid])
        repo.set_head("refs/heads/main") # Ensure HEAD is updated

        diff_data = get_diff(str(repo_path), ref1_str=str(commit1_oid), ref2_str=str(commit2_oid))

        assert "--- a/file_to_delete.txt" in diff_data["patch_text"]
        assert "-some content" in diff_data["patch_text"]

    def test_get_diff_compare_ref_vs_head(self, tmp_path: Path):
        """Test get_diff comparing a specific ref against HEAD."""
        repo_path = tmp_path / "ref_vs_head_repo"
        repo = pygit2.init_repository(str(repo_path))

        commitA_oid = make_commit(repo, "fileA.txt", "content A", "Commit A")
        commitB_oid = make_commit(repo, "fileB.txt", "content B", "Commit B (HEAD)")

        diff_data = get_diff(str(repo_path), ref1_str=str(commitA_oid))

        assert diff_data["ref1_oid"] == str(commitA_oid)
        assert diff_data["ref2_oid"] == str(commitB_oid) # HEAD resolved to commitB_oid
        assert diff_data["ref1_display_name"] == str(commitA_oid)
        assert diff_data["ref2_display_name"] == f"{str(commitB_oid)[:7]} (HEAD)"
        assert "+++ b/fileB.txt" in diff_data["patch_text"] # fileB was added in B relative to A's tree

    def test_get_diff_default_compare_head_vs_parent(self, tmp_path: Path):
        """Test get_diff default (HEAD~1 vs HEAD)."""
        repo_path = tmp_path / "head_vs_parent_repo"
        repo = pygit2.init_repository(str(repo_path))

        commitA_oid = make_commit(repo, "file.txt", "content A", "Commit A (Parent)")
        commitB_oid = make_commit(repo, "file.txt", "content B", "Commit B (HEAD)")

        diff_data = get_diff(str(repo_path)) # Default comparison

        assert diff_data["ref1_oid"] == str(commitA_oid)
        assert diff_data["ref2_oid"] == str(commitB_oid)
        assert diff_data["ref1_display_name"] == f"{str(commitA_oid)[:7]} (HEAD~1)"
        assert diff_data["ref2_display_name"] == f"{str(commitB_oid)[:7]} (HEAD)"
        assert "-content A" in diff_data["patch_text"]
        assert "+content B" in diff_data["patch_text"]

    def test_get_diff_invalid_ref1(self, tmp_path: Path):
        """Test get_diff with an invalid ref1."""
        repo_path = tmp_path / "invalid_ref1_repo"
        repo = pygit2.init_repository(str(repo_path))
        make_commit(repo, "file.txt", "content", "Initial Commit")

        with pytest.raises(CommitNotFoundError, match="Reference 'invalid_ref' not found or not a commit"):
            get_diff(str(repo_path), ref1_str="invalid_ref")

    def test_get_diff_invalid_ref2(self, tmp_path: Path):
        """Test get_diff with an invalid ref2."""
        repo_path = tmp_path / "invalid_ref2_repo"
        repo = pygit2.init_repository(str(repo_path))
        make_commit(repo, "file.txt", "content", "Initial Commit")

        with pytest.raises(CommitNotFoundError, match="Reference 'invalid_ref' not found or not a commit"):
            get_diff(str(repo_path), ref1_str="HEAD", ref2_str="invalid_ref")

    def test_get_diff_branch_names_as_refs(self, tmp_path: Path):
        """Test get_diff comparing two branches."""
        repo_path = tmp_path / "branch_compare_repo"
        repo = pygit2.init_repository(str(repo_path))

        # Main branch starts with common_base.txt
        commit_base_oid = make_commit(repo, "common_base.txt", "base", "Base commit")

        # Create branchA
        repo.branches.create("branchA", repo.get(commit_base_oid))
        repo.checkout("refs/heads/branchA")
        commitA_oid = make_commit(repo, "fileA.txt", "content A", "Commit on branchA")

        # Create branchB from base
        repo.checkout("refs/heads/main") # Back to main which is at commit_base_oid
        repo.branches.create("branchB", repo.get(commit_base_oid))
        repo.checkout("refs/heads/branchB")
        commitB_oid = make_commit(repo, "fileB.txt", "content B", "Commit on branchB")

        diff_data = get_diff(str(repo_path), ref1_str="branchA", ref2_str="branchB")

        assert diff_data["ref1_oid"] == str(commitA_oid)
        assert diff_data["ref2_oid"] == str(commitB_oid)
        assert diff_data["ref1_display_name"] == "branchA"
        assert diff_data["ref2_display_name"] == "branchB"
        assert "--- a/fileA.txt" in diff_data["patch_text"] # fileA removed
        assert "+++ b/fileB.txt" in diff_data["patch_text"] # fileB added
        assert "common_base.txt" not in diff_data["patch_text"] # common_base.txt is same in both trees relative to their common ancestor

    def test_get_diff_tag_names_as_refs(self, tmp_path: Path):
        """Test get_diff comparing two tags."""
        repo_path = tmp_path / "tag_compare_repo"
        repo = pygit2.init_repository(str(repo_path))

        commitA_oid = make_commit(repo, "fileA.txt", "content A", "Commit A for tagA")
        repo.create_tag("tagA", commitA_oid, pygit2.GIT_OBJECT_COMMIT, repo.default_signature, "Tag A")

        commitB_oid = make_commit(repo, "fileB.txt", "content B", "Commit B for tagB")
        repo.create_tag("tagB", commitB_oid, pygit2.GIT_OBJECT_COMMIT, repo.default_signature, "Tag B")

        diff_data = get_diff(str(repo_path), ref1_str="tagA", ref2_str="tagB")

        assert diff_data["ref1_oid"] == str(commitA_oid)
        assert diff_data["ref2_oid"] == str(commitB_oid)
        assert diff_data["ref1_display_name"] == "tagA"
        assert diff_data["ref2_display_name"] == "tagB"
        assert "--- a/fileA.txt" in diff_data["patch_text"] # Original fileA from commitA is gone
        assert "+++ b/fileB.txt" in diff_data["patch_text"] # New fileB from commitB is added
        # If fileA was also in commitB, it would show as modified or same.
        # Here, make_commit creates a new file if filename is different.
        # To be more precise: diff shows fileA deleted, fileB added.

    def test_get_diff_invalid_ref_combination_value_error(self, tmp_path: Path):
        """Test get_diff raises ValueError for invalid ref combination (ref1=None, ref2=Some)."""
        repo_path = tmp_path / "invalid_combo_repo"
        repo = pygit2.init_repository(str(repo_path))
        make_commit(repo, "file.txt", "content", "Initial Commit")

        with pytest.raises(ValueError, match="Invalid reference combination for diff."):
            get_diff(str(repo_path), ref1_str=None, ref2_str="HEAD")

# Add from typing import Optional to top of file for commit_time: Optional[int]
# This will be done in a follow-up if there's an error, or if I remember before submitting.
# For now, assuming Python 3.9+ where Optional from typing might not be strictly needed for hints if | None is used,
# but explicit `from typing import Optional` is better for compatibility.
# Okay, pygit2.Repository type hint also needs `from typing import TYPE_CHECKING` guard or similar if it's just for hinting.
# Let's add Optional for now.
# The `make_commit` signature `commit_time: Optional[int] = None` is fine in Python 3.7+ if `from __future__ import annotations` is used,
# or if we just rely on it for type checking and not runtime. For explicit type hinting, `Optional` is better.
# The current `pyproject.toml` implies Python 3.7+, so `Optional` should be imported.
# I will add `from typing import Optional` in the actual tool call.

# Final check of make_commit:
# - It handles initial commit (parents=[])
# - It handles subsequent commits (parents=[repo.head.target])
# - It creates file and adds to index
# - It uses Signature with time and offset
# - It updates HEAD for the first commit on 'main'
# Looks reasonable.

# ISO_8601_PATTERN: The pattern `[+-]\d{4}` correctly matches "+0000" or "-0800".
# The strftime format `%Y-%m-%d %H:%M:%S %z` produces this.
# datetime.fromisoformat can parse this if the %z part is like +HHMM.
# If it's +HH:MM, then fromisoformat is fine. My current format does not include the colon.
# However, the test primarily checks if the output string matches the strftime output of a known datetime object,
# which is a solid check. The regex is an additional structural check.
# The core function produces `YYYY-MM-DD HH:MM:SS +/-ZZZZ` (e.g., `2023-10-05 12:30:00 -0700`)
# This format is common. `datetime.fromisoformat` might be picky without the colon in offset in older Python,
# but direct string comparison with expected `strftime` output is robust here.
# Python 3.7+ `datetime.fromisoformat` handles `+HHMM` without colon.
# So, `datetime.fromisoformat(commit_info["date"])` should work if needed.
# For now, string comparison with expected strftime output is the primary validation for date values.
# The regex `ISO_8601_PATTERN` is a good structural check.
# `commit_msg_full.strip()` is correct because `commit_obj.message.strip()` is used in the core function.
# `time.sleep(0.1)` is a bit fragile for ensuring time differences but usually works for local tests.
# A more robust way would be to pass explicit, distinct timestamps to `make_commit`.
# I've updated `test_get_history_multiple_commits_default_order` and `test_get_history_with_count_limit` to use `commit_time` for this.
# This should make those tests more reliable.
# The `make_commit` helper has `commit_time: Optional[int] = None`. I need to import `Optional`.
# The `repo: pygit2.Repository` type hint is fine.
# Okay, looks good.Okay, I've drafted the complete test file `tests/test_core_versioning.py` including the `make_commit` helper and all the specified test cases. I've tried to make the tests robust, especially around commit ordering and date/time validation. I've also added `from typing import Optional` for the `make_commit` helper's type hint.

One detail: the `make_commit` helper creates and switches to a `refs/heads/main` branch after the first commit. This is a common practice and makes testing subsequent commits easier.

I'll now use `create_file_with_block` to write this to `tests/test_core_versioning.py`.
