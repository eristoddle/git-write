import pytest
import subprocess
import os
import shutil
from pathlib import Path
import yaml

from gitwrite_api.models import Annotation, AnnotationStatus
from gitwrite_core.annotations import (
    create_annotation_commit,
    list_annotations,
    update_annotation_status,
    _run_git_command # For direct setup if needed, or use higher level funcs
)
from gitwrite_core.exceptions import RepositoryOperationError, AnnotationError

# Pytest fixture for a temporary Git repository
@pytest.fixture
def temp_git_repo(tmp_path: Path) -> Path:
    """
    Creates a temporary Git repository for testing.
    Returns the path to the repository.
    """
    repo_path = tmp_path / "test_repo"
    repo_path.mkdir()
    try:
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        # Create an initial commit so branches can be made from it
        subprocess.run(["git", "-C", str(repo_path), "commit", "--allow-empty", "-m", "Initial commit"], check=True, capture_output=True)
        # Configure user name and email for commits
        subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "test@example.com"], check=True)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to initialize Git repo or make initial commit: {e.stderr.decode()}")
    except FileNotFoundError:
        pytest.fail("Git command not found. Is Git installed and in PATH?")

    return repo_path

# --- Test Cases ---

def test_create_annotation_commit_success(temp_git_repo: Path):
    """Test successful creation of an annotation commit."""
    feedback_branch = "feedback"
    annotation_data = Annotation(
        file_path="doc.txt",
        highlighted_text="Some important text.",
        start_line=5,
        end_line=6,
        comment="This needs review.",
        author="user1@example.com",
        status=AnnotationStatus.NEW
    )

    commit_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, annotation_data)

    assert commit_sha is not None
    assert len(commit_sha) == 40 # Standard Git SHA length

    # Verify commit message and content (simplified check)
    log_output = subprocess.run(
        ["git", "-C", str(temp_git_repo), "log", "-1", "--pretty=%B", commit_sha],
        capture_output=True, text=True, check=True
    ).stdout.strip()

    assert f"Annotation: {annotation_data.file_path} (Lines {annotation_data.start_line}-{annotation_data.end_line})" in log_output
    assert annotation_data.comment in log_output

    # Check if the annotation_data object was updated with id and commit_id
    assert annotation_data.id == commit_sha
    assert annotation_data.commit_id == commit_sha

    # Verify branch was created
    branches_output = subprocess.run(
        ["git", "-C", str(temp_git_repo), "branch"], capture_output=True, text=True, check=True
    ).stdout
    assert feedback_branch in branches_output

def test_list_annotations_empty_branch(temp_git_repo: Path):
    """Test listing annotations from an empty or non-existent feedback branch."""
    annotations = list_annotations(str(temp_git_repo), "non_existent_feedback")
    assert len(annotations) == 0

    # Create an empty branch (no annotation commits)
    feedback_branch = "empty_feedback"
    subprocess.run(["git", "-C", str(temp_git_repo), "checkout", "-b", feedback_branch], check=True)
    subprocess.run(["git", "-C", str(temp_git_repo), "checkout", "master"], check=True) # switch back

    annotations_empty = list_annotations(str(temp_git_repo), feedback_branch)
    assert len(annotations_empty) == 0

def test_list_annotations_single_annotation(temp_git_repo: Path):
    """Test listing a single annotation."""
    feedback_branch = "feedback_single"
    ann_data = Annotation(
        file_path="chapter1.md", highlighted_text="typo here",
        start_line=10, end_line=10, comment="Fix this.", author="editor", status=AnnotationStatus.NEW
    )
    commit_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, ann_data)

    annotations = list_annotations(str(temp_git_repo), feedback_branch)
    assert len(annotations) == 1

    retrieved_ann = annotations[0]
    assert retrieved_ann.id == commit_sha
    assert retrieved_ann.commit_id == commit_sha
    assert retrieved_ann.file_path == ann_data.file_path
    assert retrieved_ann.comment == ann_data.comment
    assert retrieved_ann.status == AnnotationStatus.NEW
    assert retrieved_ann.original_annotation_id is None

def test_update_annotation_status_success(temp_git_repo: Path):
    """Test successfully updating an annotation's status."""
    feedback_branch = "feedback_updates"
    # 1. Create an initial annotation
    original_ann_data = Annotation(
        file_path="intro.txt", highlighted_text="A great start",
        start_line=1, end_line=2, comment="Looks good.", author="author1", status=AnnotationStatus.NEW
    )
    original_commit_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, original_ann_data)

    # 2. Update its status
    new_status = AnnotationStatus.ACCEPTED
    update_commit_sha = update_annotation_status(
        str(temp_git_repo), feedback_branch, original_commit_sha, new_status
    )
    assert update_commit_sha is not None
    assert update_commit_sha != original_commit_sha

    # 3. List annotations and verify the update
    annotations = list_annotations(str(temp_git_repo), feedback_branch)
    assert len(annotations) == 1 # Should still be one logical annotation

    updated_ann = annotations[0]
    assert updated_ann.id == original_commit_sha # id is the original annotation's SHA
    assert updated_ann.commit_id == update_commit_sha # commit_id is the SHA of the update
    assert updated_ann.status == new_status
    assert updated_ann.comment == original_ann_data.comment # Comment should persist
    assert updated_ann.original_annotation_id == original_commit_sha

def test_list_annotations_multiple_updates_shows_latest(temp_git_repo: Path):
    """Test that listing shows the latest status after multiple updates."""
    feedback_branch = "feedback_multi_updates"
    ann_data = Annotation(
        file_path="story.txt", highlighted_text="Chapter end",
        start_line=100, end_line=100, comment="Review needed.", author="writer", status=AnnotationStatus.NEW
    )
    original_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, ann_data)

    # First update
    update_annotation_status(str(temp_git_repo), feedback_branch, original_sha, AnnotationStatus.ACCEPTED)

    # Second update (should be the final status)
    final_status = AnnotationStatus.REJECTED
    last_update_sha = update_annotation_status(str(temp_git_repo), feedback_branch, original_sha, final_status)

    annotations = list_annotations(str(temp_git_repo), feedback_branch)
    assert len(annotations) == 1

    final_ann = annotations[0]
    assert final_ann.id == original_sha
    assert final_ann.commit_id == last_update_sha
    assert final_ann.status == final_status
    assert final_ann.original_annotation_id == original_sha


def test_list_multiple_annotations_with_and_without_updates(temp_git_repo: Path):
    """Test listing multiple distinct annotations, some with updates, some without."""
    feedback_branch = "feedback_mixed"

    # Annotation 1 (will be updated)
    ann1_data = Annotation(file_path="file1.txt", highlighted_text="text1", start_line=1, end_line=1, comment="comment1", author="userA")
    ann1_orig_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, ann1_data)
    ann1_update_sha = update_annotation_status(str(temp_git_repo), feedback_branch, ann1_orig_sha, AnnotationStatus.ACCEPTED)

    # Annotation 2 (no updates)
    ann2_data = Annotation(file_path="file2.txt", highlighted_text="text2", start_line=2, end_line=2, comment="comment2", author="userB")
    ann2_orig_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, ann2_data)

    # Annotation 3 (will be updated twice)
    ann3_data = Annotation(file_path="file3.txt", highlighted_text="text3", start_line=3, end_line=3, comment="comment3", author="userC")
    ann3_orig_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, ann3_data)
    update_annotation_status(str(temp_git_repo), feedback_branch, ann3_orig_sha, AnnotationStatus.NEW) # e.g. re-opened
    ann3_final_update_sha = update_annotation_status(str(temp_git_repo), feedback_branch, ann3_orig_sha, AnnotationStatus.REJECTED)

    annotations = list_annotations(str(temp_git_repo), feedback_branch)
    assert len(annotations) == 3

    # Sort by file_path for consistent checking
    annotations.sort(key=lambda a: a.file_path)

    # Check Ann1
    assert annotations[0].id == ann1_orig_sha
    assert annotations[0].commit_id == ann1_update_sha
    assert annotations[0].status == AnnotationStatus.ACCEPTED
    assert annotations[0].original_annotation_id == ann1_orig_sha


    # Check Ann2
    assert annotations[1].id == ann2_orig_sha
    assert annotations[1].commit_id == ann2_orig_sha # No update, so commit_id is its own sha
    assert annotations[1].status == AnnotationStatus.NEW # Default status
    assert annotations[1].original_annotation_id is None

    # Check Ann3
    assert annotations[2].id == ann3_orig_sha
    assert annotations[2].commit_id == ann3_final_update_sha
    assert annotations[2].status == AnnotationStatus.REJECTED
    assert annotations[2].original_annotation_id == ann3_orig_sha

def test_update_non_existent_annotation(temp_git_repo: Path):
    """Test trying to update an annotation that doesn't exist."""
    with pytest.raises(RepositoryOperationError): # Or AnnotationError depending on how specific the check is
        update_annotation_status(
            str(temp_git_repo), "feedback_branch", "nonexistentcommitsha", AnnotationStatus.ACCEPTED
        )

def test_create_annotation_in_invalid_repo(tmp_path: Path):
    """Test creating an annotation in a path that is not a Git repository."""
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    ann_data = Annotation(file_path="f.txt", highlighted_text="t", start_line=0, end_line=0, comment="c", author="a")
    with pytest.raises(RepositoryOperationError, match="' is not a valid Git repository."):
        create_annotation_commit(str(not_a_repo), "fb", ann_data)

def test_list_annotations_invalid_repo(tmp_path: Path):
    """Test listing annotations from a path that is not a Git repository."""
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    with pytest.raises(RepositoryOperationError, match="' is not a valid Git repository."):
        list_annotations(str(not_a_repo), "fb")

def test_update_annotation_status_invalid_repo(tmp_path: Path):
    """Test updating status in a path that is not a Git repository."""
    not_a_repo = tmp_path / "not_a_repo"
    not_a_repo.mkdir()
    with pytest.raises(RepositoryOperationError, match="' is not a valid Git repository."):
        update_annotation_status(str(not_a_repo), "fb", "somecommit", AnnotationStatus.NEW)

# More tests could include:
# - Commits on the feedback branch that are not annotations (should be skipped by list_annotations).
# - Annotations with special characters in comments, file paths, etc.
# - Behavior when the feedback branch is the current branch vs. not.
# - Concurrency (though harder to unit test, consider implications).
# - Very old Git versions (if compatibility is a concern, though _run_git_command uses basic commands).
# - Annotation data with missing optional fields vs. required fields.
# - Trying to create a feedback branch when the repo is completely empty (no initial commit).
#   The current create_annotation_commit has some handling for this, could be tested.
#   The fixture currently creates an initial commit, so this case is not hit by default.

# Example for testing non-annotation commits on feedback branch:
def test_list_annotations_skips_non_annotation_commits(temp_git_repo: Path):
    feedback_branch = "feedback_mixed_commits"

    # 1. Create a valid annotation
    ann_data = Annotation(
        file_path="doc.md", highlighted_text="valid", start_line=1, end_line=1, comment="This is an annotation", author="test"
    )
    create_annotation_commit(str(temp_git_repo), feedback_branch, ann_data)

    # 2. Create a non-annotation commit on the same branch
    # Switch to branch first
    subprocess.run(["git", "-C", str(temp_git_repo), "checkout", feedback_branch], check=True)
    Path(temp_git_repo / "random_file.txt").write_text("some content")
    subprocess.run(["git", "-C", str(temp_git_repo), "add", "random_file.txt"], check=True)
    subprocess.run(["git", "-C", str(temp_git_repo), "commit", "-m", "A regular commit"], check=True)

    # 3. Create another valid annotation
    ann_data2 = Annotation(
        file_path="doc2.md", highlighted_text="valid2", start_line=2, end_line=2, comment="Another annotation", author="test2"
    )
    create_annotation_commit(str(temp_git_repo), feedback_branch, ann_data2)

    annotations = list_annotations(str(temp_git_repo), feedback_branch)
    assert len(annotations) == 2 # Should only list the two actual annotations

    # Verify content (optional, but good for sanity)
    found_doc1 = any(a.file_path == "doc.md" for a in annotations)
    found_doc2 = any(a.file_path == "doc2.md" for a in annotations)
    assert found_doc1 and found_doc2

# Test for creating feedback branch in an empty repo (no initial commit)
@pytest.fixture
def temp_empty_git_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "empty_repo"
    repo_path.mkdir()
    try:
        subprocess.run(["git", "init"], cwd=repo_path, check=True, capture_output=True)
        # DO NOT make an initial commit
        subprocess.run(["git", "-C", str(repo_path), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(repo_path), "config", "user.email", "test@example.com"], check=True)
    except subprocess.CalledProcessError as e:
        pytest.fail(f"Failed to initialize Git repo: {e.stderr.decode()}")
    return repo_path

def test_create_annotation_on_empty_repo_branch_creation(temp_empty_git_repo: Path):
    """
    Tests creating an annotation (and thus feedback branch) in a repo with no initial commit.
    The current implementation of create_annotation_commit might raise RepositoryOperationError
    because 'git checkout -b' from an unborn branch can be tricky without a starting point.
    The code has a note about this. Let's see what it does.
    It tries `checkout -b` which might fail if HEAD is unborn.
    The error message in create_annotation_commit is:
    "Failed to create feedback branch '{feedback_branch}'. Ensure the repository is initialized and has at least one commit..."
    """
    feedback_branch = "feedback_on_empty"
    annotation_data = Annotation(
        file_path="first_note.txt", highlighted_text="Hello",
        start_line=1, end_line=1, comment="First!", author="pioneer"
    )

    # Based on the current implementation, this is expected to fail because the repo has no commits for 'HEAD' to base off of.
    # The `create_annotation_commit` function's error handling for branch creation:
    # It tries `checkout -b feedback_branch`. If HEAD is invalid (e.g. new repo), this fails.
    # The error path is: `except RepositoryOperationError: # No HEAD, likely empty repo`
    # then it tries `checkout -b` again, then `raise RepositoryOperationError(...)`
    with pytest.raises(RepositoryOperationError, match=r"Failed to create feedback branch.*Ensure the repository is initialized and has at least one commit"):
        create_annotation_commit(str(temp_empty_git_repo), feedback_branch, annotation_data)

    # If the goal was for it to succeed by creating an orphan branch, the implementation of
    # create_annotation_commit would need to be more sophisticated (e.g. using git checkout --orphan).
    # For now, this test verifies the current documented failure mode.
    # To make it pass by succeeding, one would modify `create_annotation_commit` to handle this.
    # Example (conceptual change in create_annotation_commit):
    #   except RepositoryOperationError: # No HEAD (unborn branch)
    #       _run_git_command(repo_path, ['checkout', '--orphan', feedback_branch], expect_stdout=False)
    #       # An empty commit might be needed here before the annotation commit, or allow annotation commit on orphan.
    #       # The current logic for commit uses --allow-empty, so it might just work on an orphan.
    # This test confirms current behavior.

# Test for YAML content in commit message body
def test_annotation_yaml_content_in_commit(temp_git_repo: Path):
    feedback_branch = "yaml_content_test"
    annotation_data = Annotation(
        file_path="data.yml",
        highlighted_text="some_key: value",
        start_line=1,
        end_line=1,
        comment="This is a YAML annotation.",
        author="yaml_author",
        status=AnnotationStatus.NEW
    )

    commit_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, annotation_data)

    log_output = subprocess.run(
        ["git", "-C", str(temp_git_repo), "log", "-1", "--pretty=%B", commit_sha],
        capture_output=True, text=True, check=True
    ).stdout.strip()

    # Extract YAML part (after subject and blank line)
    yaml_part = log_output.split("\n\n", 1)[1]
    parsed_yaml = yaml.safe_load(yaml_part)

    assert parsed_yaml["file_path"] == annotation_data.file_path
    assert parsed_yaml["highlighted_text"] == annotation_data.highlighted_text
    assert parsed_yaml["start_line"] == annotation_data.start_line
    assert parsed_yaml["end_line"] == annotation_data.end_line
    assert parsed_yaml["comment"] == annotation_data.comment
    assert parsed_yaml["author"] == annotation_data.author
    assert parsed_yaml["status"] == annotation_data.status.value # Stored as value

    # Test that original_annotation_id is NOT in the YAML for a new annotation
    assert "original_annotation_id" not in parsed_yaml


def test_update_annotation_yaml_content_in_commit(temp_git_repo: Path):
    feedback_branch = "yaml_update_content_test"
    original_ann_data = Annotation(
            file_path="original.yml", highlighted_text="orig_text", start_line=5, end_line=5, comment="Original comment", author="orig_author"
    )
    original_commit_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, original_ann_data)

    new_status = AnnotationStatus.ACCEPTED
    update_commit_sha = update_annotation_status(
        str(temp_git_repo), feedback_branch, original_commit_sha, new_status
    )

    log_output = subprocess.run(
        ["git", "-C", str(temp_git_repo), "log", "-1", "--pretty=%B", update_commit_sha],
        capture_output=True, text=True, check=True
    ).stdout.strip()

    yaml_part = log_output.split("\n\n", 1)[1]
    parsed_yaml = yaml.safe_load(yaml_part)

    assert parsed_yaml["file_path"] == original_ann_data.file_path # Copied from original
    assert parsed_yaml["highlighted_text"] == original_ann_data.highlighted_text
    assert parsed_yaml["start_line"] == original_ann_data.start_line
    assert parsed_yaml["end_line"] == original_ann_data.end_line
    assert parsed_yaml["comment"] == original_ann_data.comment
    assert parsed_yaml["author"] == original_ann_data.author
    assert parsed_yaml["status"] == new_status.value
    assert parsed_yaml["original_annotation_id"] == original_commit_sha

# Test that list_annotations correctly populates original_annotation_id
def test_list_annotations_populates_original_id_correctly(temp_git_repo: Path):
    feedback_branch = "orig_id_test"
    ann1_data = Annotation(file_path="f1.txt", highlighted_text="t1", start_line=1, end_line=1, comment="c1", author="a1")
    ann1_orig_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, ann1_data)

    # Update ann1
    update_annotation_status(str(temp_git_repo), feedback_branch, ann1_orig_sha, AnnotationStatus.ACCEPTED)

    # ann2, no updates
    ann2_data = Annotation(file_path="f2.txt", highlighted_text="t2", start_line=2, end_line=2, comment="c2", author="a2")
    ann2_orig_sha = create_annotation_commit(str(temp_git_repo), feedback_branch, ann2_data)

    annotations = list_annotations(str(temp_git_repo), feedback_branch)
    annotations.sort(key=lambda a: a.file_path) # for consistent order

    assert len(annotations) == 2

    # ann1 (updated)
    assert annotations[0].id == ann1_orig_sha
    assert annotations[0].original_annotation_id == ann1_orig_sha # This is the key check for an updated item

    # ann2 (not updated)
    assert annotations[1].id == ann2_orig_sha
    assert annotations[1].original_annotation_id is None


# Test specific error for trying to update an annotation commit that isn't in annotation format
def test_update_non_annotation_commit(temp_git_repo: Path):
    feedback_branch = "update_non_ann"
    # Create a regular commit
    subprocess.run(["git", "-C", str(temp_git_repo), "checkout", "-b", feedback_branch], check=True)
    Path(temp_git_repo / "some_file.txt").write_text("content")
    subprocess.run(["git", "-C", str(temp_git_repo), "add", "some_file.txt"], check=True)
    non_ann_commit_sha = subprocess.run(
        ["git", "-C", str(temp_git_repo), "commit", "-m", "Not an annotation commit"],
        capture_output=True, text=True, check=True
    ).stdout.strip().split(" ")[1][:40] # Simplified way to get SHA, might need refinement

    # Need to get the SHA more reliably
    non_ann_commit_sha = _run_git_command(str(temp_git_repo), ["rev-parse", "HEAD"])


    with pytest.raises(AnnotationError, match=r"Commit .* is not in the expected annotation format"):
        update_annotation_status(
            str(temp_git_repo), feedback_branch, non_ann_commit_sha, AnnotationStatus.ACCEPTED
        )

# Test parsing of commit with missing YAML fields
def test_list_annotations_handles_malformed_yaml_gracefully(temp_git_repo: Path):
    feedback_branch = "malformed_yaml"

    # Commit 1: Valid annotation
    valid_ann_data = Annotation(file_path="valid.txt", highlighted_text="text", start_line=1, end_line=1, comment="Valid", author="author")
    create_annotation_commit(str(temp_git_repo), feedback_branch, valid_ann_data)

    # Commit 2: Malformed annotation (missing 'comment' field in YAML)
    malformed_commit_data = {
        "file_path": "malformed.txt",
        "highlighted_text": "bad text",
        "start_line": 2,
        "end_line": 2,
        # "comment": "This is missing", # Missing comment
        "author": "bad_author",
        "status": "new"
    }
    yaml_content = yaml.dump(malformed_commit_data)
    commit_subject = "Annotation: malformed.txt (Lines 2-2)"
    commit_message = f"{commit_subject}\n\n{yaml_content}"

    tmp_commit_msg_file = Path(temp_git_repo) / ".git" / "MALFORMED_COMMIT_MSG.tmp"
    with open(tmp_commit_msg_file, 'w', encoding='utf-8') as f:
        f.write(commit_message)

    # Need to be on the branch to commit
    subprocess.run(["git", "-C", str(temp_git_repo), "checkout", feedback_branch], check=True)
    _run_git_command(str(temp_git_repo), ['commit', '--allow-empty', '-F', str(tmp_commit_msg_file)], expect_stdout=False)
    if tmp_commit_msg_file.exists():
        tmp_commit_msg_file.unlink()

    annotations = list_annotations(str(temp_git_repo), feedback_branch)
    # Should only list the valid annotation, skipping the malformed one
    assert len(annotations) == 1
    assert annotations[0].file_path == "valid.txt"

# Test that `original_annotation_id` is correctly set in the YAML of an update commit
# This was implicitly tested by `test_update_annotation_yaml_content_in_commit`
# and `test_list_annotations_populates_original_id_correctly`, but an explicit check on the
# Annotation object constructed by list_annotations for an updated item is good.

# The test `test_list_annotations_populates_original_id_correctly` already covers this:
# `assert annotations[0].original_annotation_id == ann1_orig_sha`
# This confirms that when listing an updated annotation, the `Annotation` object has its
# `original_annotation_id` field populated correctly from the update commit's YAML.

# Final check for `id` field in `Annotation` object from `list_annotations`
# The `id` should always be the SHA of the *first* commit in the annotation thread.
# The `commit_id` should be the SHA of the commit defining the *current state*.
# `test_list_multiple_annotations_with_and_without_updates` checks this:
#   `assert annotations[0].id == ann1_orig_sha` (for updated one)
#   `assert annotations[1].id == ann2_orig_sha` (for non-updated one)
# This seems correct.

print("Initial test structure for test_core_annotations.py created.")

# Placeholder for actual test execution and debugging
# To run these tests (assuming pytest is set up and PYTHONPATH includes the project root):
# Ensure gitwrite_core and gitwrite_api are importable.
# `pytest tests/test_core_annotations.py`

# Note: Shortened ht, sl, el, c, a for some test data for brevity in test setup.
# These correspond to highlighted_text, start_line, end_line, comment, author.
# In Annotation instantiation, full names are used.
# This is just for the raw data dicts in `test_list_multiple_annotations_with_and_without_updates`
# It should be `highlighted_text`, etc. when creating Annotation objects. I'll fix that.

# Correcting the data in test_list_multiple_annotations_with_and_without_updates
# Ann1: file_path="file1.txt", highlighted_text="text1", start_line=1, end_line=1, comment="comment1", author="userA"
# Ann2: file_path="file2.txt", highlighted_text="text2", start_line=2, end_line=2, comment="comment2", author="userB"
# Ann3: file_path="file3.txt", highlighted_text="text3", start_line=3, end_line=3, comment="comment3", author="userC"
# This was just a mental note, the Annotation objects are created correctly with full names.
# The fixture `temp_git_repo` uses `master` as the default main branch after initial commit.
# Some tests might implicitly assume this (e.g., `checkout master`). This is fine for typical Git setups.
# If `main` is preferred, the fixture could be updated.
# Added git user.name and user.email config to fixture to avoid commit errors on some systems.

# One more check: the `ht`, `sl`, etc. short names in `test_list_multiple_annotations_with_and_without_updates`
# are used when creating the `Annotation` instances. This is fine as long as the `Annotation` model's
# `__init__` can map them or if the `Annotation` constructor is called with keyword arguments matching
# the model's field names. Pydantic models are typically initialized with keyword arguments matching field names.
# `Annotation(file_path="file1.txt", ht="text1", ...)` would fail.
# It should be `Annotation(file_path="file1.txt", highlighted_text="text1", ...)`
# I will correct this in the actual test code.
# The current code for `test_list_multiple_annotations_with_and_without_updates` has this:
# `ann1_data = Annotation(file_path="file1.txt", ht="text1", sl=1, el=1, c="comment1", a="userA")`
# This needs to be:
# `ann1_data = Annotation(file_path="file1.txt", highlighted_text="text1", start_line=1, end_line=1, comment="comment1", author="userA")`
# I will make this correction in the next step when I refine the tests.

# For `test_update_non_annotation_commit` getting the SHA:
# `non_ann_commit_sha = subprocess.run(...).stdout.strip().split(" ")[1][:40]` is fragile.
# Changed to use `_run_git_command(str(temp_git_repo), ["rev-parse", "HEAD"])` which is robust.

# In `test_list_annotations_handles_malformed_yaml_gracefully`:
# `malformed_commit_data` uses "status": "new". This should be `AnnotationStatus.NEW.value`
# if being strict, or rely on `AnnotationStatus(data["status"])` to handle the string.
# The parsing logic `status_enum = AnnotationStatus(data["status"])` should handle "new".
# So, `status: "new"` in the YAML is acceptable.

# The `ht`, `sl` `c`, `a` shorthands were only in my mental model / comments, not in the actual
# `Annotation(...)` calls in the generated test code. The generated code uses full field names.
# Example: `ann1_data = Annotation(file_path="file1.txt", highlighted_text="text1", start_line=1, end_line=1, comment="comment1", author="userA")`
# This is correct. My self-correction note was based on a misreading of my own plan vs. generated code. The generated code IS using full names.
# So, no change needed for that.
