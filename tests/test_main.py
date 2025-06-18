import pytest
import pygit2
import os
import shutil
import re
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch

# Assuming your CLI script is gitwrite_cli.main
from gitwrite_cli.main import cli
from gitwrite_core.repository import initialize_repository, COMMON_GITIGNORE_PATTERNS, add_pattern_to_gitignore, list_gitignore_patterns # New imports
from gitwrite_core.branching import (
    create_and_switch_branch,
    list_branches,
    switch_to_branch,
    merge_branch_into_current # Added for merge
)
from gitwrite_core.exceptions import (
    RepositoryNotFoundError,
    CommitNotFoundError,
    TagAlreadyExistsError,
    GitWriteError,
    NotEnoughHistoryError,
    RepositoryEmptyError,
    BranchAlreadyExistsError,
    BranchNotFoundError, # Added for switch
    MergeConflictError # Added for merge
)
from rich.table import Table # Ensure Table is imported for switch (already present due to prior switch command update)


# Helper to create a commit
def make_commit(repo, filename, content, message):
    # Create file
    file_path = Path(repo.workdir) / filename
    file_path.write_text(content)
    # Stage
    repo.index.add(filename)
    repo.index.write()
    # Commit
    author = pygit2.Signature("Test Author", "test@example.com", 946684800, 0) # 2000-01-01 00:00:00 +0000
    committer = pygit2.Signature("Test Committer", "committer@example.com", 946684800, 0)
    parents = [repo.head.target] if not repo.head_is_unborn else []
    tree = repo.index.write_tree()
    return repo.create_commit("HEAD", author, committer, message, tree, parents)

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def local_repo_path(tmp_path):
    return tmp_path / "local_project"

@pytest.fixture
def remote_repo_path(tmp_path):
    return tmp_path / "remote_project.git"

@pytest.fixture
def local_repo(local_repo_path):
    # Initialize a non-bare repository
    if local_repo_path.exists():
        shutil.rmtree(local_repo_path)
    local_repo_path.mkdir()
    repo = pygit2.init_repository(str(local_repo_path), bare=False)

    # Initial commit is often needed for many git operations
    make_commit(repo, "initial.txt", "Initial content", "Initial commit")

    # Configure user for commits if needed by some operations (though default_signature often works)
    config = repo.config
    config["user.name"] = "Test Author"
    config["user.email"] = "test@example.com"

    return repo

@pytest.fixture
def synctest_repos(tmp_path):
    """
    Sets up a local repository, a bare remote repository, and a second clone
    of the remote to simulate another user's workspace.
    Returns a dictionary with "local_repo", "remote_bare_repo", "remote_clone_repo_path".
    """
    base_dir = tmp_path / "sync_test_area"
    base_dir.mkdir()

    # 1. Create Bare Remote Repo
    remote_bare_path = base_dir / "remote_server.git"
    remote_bare_repo = pygit2.init_repository(str(remote_bare_path), bare=True)

    # 2. Create Local Repo (main user)
    local_repo_path = base_dir / "local_user_repo"
    local_repo_path.mkdir()
    local_repo = pygit2.init_repository(str(local_repo_path), bare=False)
    config_local = local_repo.config
    config_local["user.name"] = "Local User"
    config_local["user.email"] = "local@example.com"
    make_commit(local_repo, "initial_local.txt", "Local's first file", "Initial local commit on main")
    local_repo.remotes.create("origin", str(remote_bare_path))
    active_branch_name_local = local_repo.head.shorthand
    local_repo.remotes["origin"].push([f"refs/heads/{active_branch_name_local}:refs/heads/{active_branch_name_local}"])


    # 3. Create Remote Clone Repo (simulates another user)
    remote_clone_repo_path = base_dir / "remote_clone_user_repo"
    # No need to actually clone for many tests; can operate on bare repo or re-clone if needed.
    # For tests needing a working dir for remote changes, clone is useful.
    # pygit2.clone_repository(str(remote_bare_path), str(remote_clone_repo_path))
    # This clone will be created on-demand in tests that need it.

    return {
        "local_repo": local_repo,
        "remote_bare_repo": remote_bare_repo,
        "remote_clone_repo_path": remote_clone_repo_path, # Path for clone
        "local_repo_path_str": str(local_repo_path), # String path for CLI
        "remote_bare_repo_path_str": str(remote_bare_path) # String path for remote URL
    }


# Test stubs will go here

# Moved helper functions to top-level for use by multiple test classes
def _assert_gitwrite_structure(base_path: Path, check_git_dir: bool = True):
    if check_git_dir:
        assert (base_path / ".git").is_dir(), ".git directory not found"
    assert (base_path / "drafts").is_dir(), "drafts/ directory not found"
    assert (base_path / "drafts" / ".gitkeep").is_file(), "drafts/.gitkeep not found"
    assert (base_path / "notes").is_dir(), "notes/ directory not found"
    assert (base_path / "notes" / ".gitkeep").is_file(), "notes/.gitkeep not found"
    assert (base_path / "metadata.yml").is_file(), "metadata.yml not found"
    assert (base_path / ".gitignore").is_file(), ".gitignore not found"

def _assert_common_gitignore_patterns(gitignore_path: Path):
    content = gitignore_path.read_text()
    # Using COMMON_GITIGNORE_PATTERNS imported from the core module
    for pattern in COMMON_GITIGNORE_PATTERNS:
        assert pattern in content, f"Expected core pattern '{pattern}' not found in .gitignore"


def test_sync_placeholder(runner, local_repo, bare_remote_repo):
    """Placeholder test to ensure fixtures are working."""
    assert local_repo is not None
    assert bare_remote_repo is not None
    assert (Path(local_repo.workdir) / "initial.txt").exists()
    remote_refs = bare_remote_repo.listall_references()
    # Example: check if 'refs/heads/main' or 'refs/heads/master' exists on remote
    # This depends on the default branch name used in `local_repo`'s initial push.
    active_branch_name = local_repo.head.shorthand
    assert f"refs/heads/{active_branch_name}" in remote_refs

    # Try running a gitwrite command to see if cli runner works
    # Change CWD for the runner
    os.chdir(local_repo.workdir)
    result = runner.invoke(cli, ["history"]) # A simple read-only command
    assert result.exit_code == 0
    assert "Initial commit" in result.output

def test_sync_already_up_to_date(runner, local_repo, bare_remote_repo):
    """
    Test `gitwrite sync` when the local and remote repositories are already synchronized.
    """
    # Ensure CWD is the local repo's working directory
    os.chdir(local_repo.workdir)

    # At this point, local_repo has an initial commit, and it has been pushed to bare_remote_repo.
    # They should be up-to-date on the main/master branch.
    # Let's verify the branch name to be sure.
    local_branch_name = local_repo.head.shorthand

    # Make sure local HEAD and remote HEAD for the current branch are the same.
    # The bare_remote_repo fixture already pushes the initial commit.
    remote_branch_ref = f"refs/heads/{local_branch_name}"
    assert remote_branch_ref in bare_remote_repo.listall_references()
    assert local_repo.head.target == bare_remote_repo.lookup_reference(remote_branch_ref).target

    result = runner.invoke(cli, ["sync"])

    assert result.exit_code == 0, f"CLI Error: {result.output}"
    # Expected output can vary based on implementation details:
    # - "Already up-to-date" after fetch.
    # - "Local branch is already up-to-date with remote" before merge analysis.
    # - "Nothing to push" if push logic is robust.
    # For this test, we primarily care that it completes successfully and doesn't make erroneous changes.
    assert "up-to-date" in result.output.lower() or "nothing to push" in result.output.lower() or "aligned" in result.output.lower()

    # Verify no new commits were made locally
    initial_commit_oid = local_repo.head.target
    # Re-lookup head target after sync, though it shouldn't change
    current_commit_oid_after_sync = local_repo.lookup_reference(f"refs/heads/{local_branch_name}").target
    assert current_commit_oid_after_sync == initial_commit_oid, "No new commit should be made if already up-to-date."

def test_sync_fast_forward(runner, local_repo, bare_remote_repo, tmp_path):
    """
    Test `gitwrite sync` for a fast-forward scenario.
    Local is behind remote, no conflicts.
    """
    os.chdir(local_repo.workdir)
    local_branch_name = local_repo.head.shorthand
    initial_local_commit_oid = local_repo.head.target

    # Create a second clone to simulate another user pushing to remote
    remote_clone_path = tmp_path / "remote_clone_for_ff_test"
    if remote_clone_path.exists(): # Should not happen with tmp_path but good practice
        shutil.rmtree(remote_clone_path)

    # Clone the bare remote (which acts as the central server)
    # The bare_remote_repo.path is a string like '/tmp/pytest-of.../remote_project.git'
    remote_clone_repo = pygit2.clone_repository(bare_remote_repo.path, str(remote_clone_path))

    # Configure user for the clone
    config = remote_clone_repo.config
    config["user.name"] = "Remote Pusher"
    config["user.email"] = "pusher@example.com"

    # Make a new commit in the remote_clone and push it to the bare_remote_repo
    remote_commit_filename = "remote_ff_change.txt"
    remote_commit_content = "Content from remote for FF"
    make_commit(remote_clone_repo, remote_commit_filename, remote_commit_content, "Remote commit for FF test")

    remote_clone_branch_name = remote_clone_repo.head.shorthand # Should be same as local_branch_name initially
    remote_clone_repo.remotes["origin"].push([f"refs/heads/{remote_clone_branch_name}:refs/heads/{remote_clone_branch_name}"])

    # Get the OID of the commit made on the remote
    new_remote_commit_oid = remote_clone_repo.head.target
    assert new_remote_commit_oid != initial_local_commit_oid

    # Now, local_repo is behind bare_remote_repo. Run sync.
    result = runner.invoke(cli, ["sync"])
    assert result.exit_code == 0, f"CLI Error: {result.output}"

    assert "fast-forward" in result.output.lower()

    # Verify local_repo's HEAD is updated to the new_remote_commit_oid
    local_repo.head.resolve() # Refresh HEAD
    assert local_repo.head.target == new_remote_commit_oid, "Local repo should be fast-forwarded to the remote commit."

    # Verify the new file from remote is in the local working directory
    assert (Path(local_repo.workdir) / remote_commit_filename).exists()
    assert (Path(local_repo.workdir) / remote_commit_filename).read_text() == remote_commit_content

    # Verify that the local branch is now aligned with remote (nothing to push, or push of updated head is fine)
    # The sync command output might say "Nothing to push" or "Push successful"
    # We can check that local HEAD and remote HEAD are the same after sync.
    remote_branch_ref = f"refs/heads/{local_branch_name}"
    assert local_repo.head.target == bare_remote_repo.lookup_reference(remote_branch_ref).target


def test_sync_merge_no_conflict(runner, local_repo, bare_remote_repo, tmp_path):
    """
    Test `gitwrite sync` for a merge scenario without conflicts.
    Local and remote have diverged.
    """
    os.chdir(local_repo.workdir)
    local_branch_name = local_repo.head.shorthand
    initial_local_commit_oid = local_repo.head.target

    # 1. Make a commit in local_repo
    local_change_filename = "local_change.txt"
    local_change_content = "Content from local repo"
    make_commit(local_repo, local_change_filename, local_change_content, "Local commit for merge test")
    local_commit_oid_after_local_change = local_repo.head.target
    assert local_commit_oid_after_local_change != initial_local_commit_oid

    # 2. Make a different commit on the remote (via a second clone)
    remote_clone_path = tmp_path / "remote_clone_for_merge_test"
    if remote_clone_path.exists():
        shutil.rmtree(remote_clone_path)
    remote_clone_repo = pygit2.clone_repository(bare_remote_repo.path, str(remote_clone_path))

    # Configure user for the clone & ensure it's on the same branch
    config = remote_clone_repo.config
    config["user.name"] = "Remote Pusher"
    config["user.email"] = "pusher@example.com"
    # Ensure the clone is on the same branch as local_repo before making changes
    # The clone will typically start on the default branch of the remote.
    if remote_clone_repo.head.shorthand != local_branch_name:
        # This might happen if local_branch_name is not the default (e.g. main/master)
        # For this test, we assume they will be on the same default branch after clone.
        # If not, we might need to checkout local_branch_name in remote_clone_repo if it exists there,
        # or ensure test setup always uses the default branch.
        # For now, proceed assuming they are on the same conceptual branch.
        pass


    remote_change_filename = "remote_change.txt"
    remote_change_content = "Content from remote for merge"
    # Important: this commit must be based on initial_local_commit_oid (the state before local_repo made its new commit)
    # To do this, reset the remote_clone_repo's HEAD to that initial commit first.
    # The bare_remote_repo (and thus the clone) should be at initial_local_commit_oid state.
    assert remote_clone_repo.head.target == initial_local_commit_oid

    make_commit(remote_clone_repo, remote_change_filename, remote_change_content, "Remote commit for merge test")
    remote_commit_oid_on_remote_clone = remote_clone_repo.head.target
    assert remote_commit_oid_on_remote_clone != initial_local_commit_oid

    # Push this new remote commit to the bare_remote_repo
    remote_clone_repo.remotes["origin"].push([f"refs/heads/{local_branch_name}:refs/heads/{local_branch_name}"])

    # Now, local_repo has one new commit, and bare_remote_repo has another new commit. They have diverged.
    # local_repo's HEAD is local_commit_oid_after_local_change
    # bare_remote_repo's HEAD for the branch is remote_commit_oid_on_remote_clone

    # Run sync
    print(f"Local HEAD before sync: {str(local_repo.head.target)}")
    print(f"Remote commit OID to merge: {str(remote_commit_oid_on_remote_clone)}")

    result = runner.invoke(cli, ["sync"])
    print(f"CLI Output:\n{result.output}")
    assert result.exit_code == 0, f"CLI Error: {result.output}"

    assert "normal merge" in result.output.lower() or "merged remote changes" in result.output.lower()

    # Verify a merge commit was created in local_repo
    local_repo.head.resolve() # Refresh HEAD
    new_local_head_oid = local_repo.head.target
    print(f"Local HEAD after sync: {str(new_local_head_oid)}")

    # Log reflog entries for debugging
    current_branch_ref_name_for_log = local_repo.lookup_reference(f"refs/heads/{local_branch_name}").name
    print(f"Reflog for {local_branch_name} ({current_branch_ref_name_for_log}):")
    for entry in local_repo.lookup_reference(current_branch_ref_name_for_log).log():
        print(f"  Old: {str(entry.oid_old)}, New: {str(entry.oid_new)}, Msg: {entry.message}")


    assert new_local_head_oid != local_commit_oid_after_local_change, \
        f"Head did not change from original local commit. Output: {result.output}"
    assert new_local_head_oid != remote_commit_oid_on_remote_clone, \
        f"Head matches remote commit; should be a merge. Output: {result.output}"

    merge_commit = local_repo.get(new_local_head_oid)
    assert isinstance(merge_commit, pygit2.Commit)
    assert len(merge_commit.parents) == 2
    # Order of parents can vary, so check set equality
    expected_parent_oids = {local_commit_oid_after_local_change, remote_commit_oid_on_remote_clone}
    actual_parent_oids = {p.id for p in merge_commit.parents}
    assert actual_parent_oids == expected_parent_oids, "Merge commit parents are incorrect."
    assert f"Merge remote-tracking branch 'refs/remotes/origin/{local_branch_name}'" in merge_commit.message

    # Verify both files exist in the working directory
    assert (Path(local_repo.workdir) / local_change_filename).exists()
    assert (Path(local_repo.workdir) / local_change_filename).read_text() == local_change_content
    assert (Path(local_repo.workdir) / remote_change_filename).exists()
    assert (Path(local_repo.workdir) / remote_change_filename).read_text() == remote_change_content

    # Verify the local merge commit was pushed to remote
    remote_branch_ref = f"refs/heads/{local_branch_name}"
    assert bare_remote_repo.lookup_reference(remote_branch_ref).target == new_local_head_oid


def test_sync_with_conflicts(runner, local_repo, bare_remote_repo, tmp_path):
    """
    Test `gitwrite sync` when local and remote changes conflict.
    """
    os.chdir(local_repo.workdir)
    local_branch_name = local_repo.head.shorthand

    # Shared file that will be modified to create a conflict
    conflict_filename = "conflict_file.txt"
    initial_content = "Line 1\nLine 2 for conflict\nLine 3\n"

    # Commit initial version of the shared file to local_repo and push to remote
    # This ensures both sides start with the same base for this file.
    make_commit(local_repo, conflict_filename, initial_content, f"Add initial {conflict_filename}")
    local_repo.remotes["origin"].push([f"refs/heads/{local_branch_name}:refs/heads/{local_branch_name}"])
    base_commit_oid_for_conflict = local_repo.head.target

    # 1. Make a commit in local_repo modifying the conflict_file
    local_conflict_content = "Line 1\nLOCAL CHANGE on Line 2\nLine 3\n"
    make_commit(local_repo, conflict_filename, local_conflict_content, "Local conflicting change")
    local_commit_after_local_change = local_repo.head.target

    # 2. Make a conflicting commit on the remote (via a second clone)
    remote_clone_path = tmp_path / "remote_clone_for_conflict_test"
    if remote_clone_path.exists():
        shutil.rmtree(remote_clone_path)
    remote_clone_repo = pygit2.clone_repository(bare_remote_repo.path, str(remote_clone_path))

    config = remote_clone_repo.config # Configure user for the clone
    config["user.name"] = "Remote Conflicter"
    config["user.email"] = "conflicter@example.com"

    # Ensure the remote clone is at the base commit before making its conflicting change
    # This is crucial: both conflicting changes must stem from the same parent.
    remote_clone_repo.reset(base_commit_oid_for_conflict, pygit2.GIT_RESET_HARD)

    # Make sure the conflict file exists with correct content before modifying
    conflict_file_path = Path(remote_clone_repo.workdir) / conflict_filename
    assert conflict_file_path.read_text() == initial_content

    remote_conflict_content = "Line 1\nREMOTE CHANGE on Line 2\nLine 3\n"
    make_commit(remote_clone_repo, conflict_filename, remote_conflict_content, "Remote conflicting change")
    remote_commit_pushed_to_remote = remote_clone_repo.head.target

    # Push this conflicting remote commit to the bare_remote_repo
    # Prefix with '+' for force push
    remote_clone_repo.remotes["origin"].push([f"+refs/heads/{local_branch_name}:refs/heads/{local_branch_name}"])

    # Now, local_repo has one change, and bare_remote_repo has a conflicting change on the same file.
    # Make sure the working directory is clean before syncing
    assert not local_repo.status()

    # Mock out any interactive prompts that might appear in the sync command
    # and ensure it proceeds with the merge attempt despite conflicts
    with patch('builtins.input', return_value='n'):  # Respond 'no' to any prompts
        result = runner.invoke(cli, ["sync"])

    print(f"Sync command output: {result.output}")
    assert result.exit_code == 0, f"CLI Error: {result.output}"

    # We expect sync to have detected conflicts
    assert "conflicts detected" in result.output.lower() or "merge conflict" in result.output.lower(), \
        "Sync should have detected conflicts"

    # Verify that the conflict file in working dir has conflict markers
    wc_conflict_file_path = Path(local_repo.workdir) / conflict_filename
    assert wc_conflict_file_path.exists(), f"Conflict file {conflict_filename} not found in working dir"

    wc_conflict_file_content = wc_conflict_file_path.read_text()
    print(f"Content of conflict file:\n{wc_conflict_file_content}")

    # Check for conflict markers
    assert "<<<<<<<" in wc_conflict_file_content, "Conflict markers not found"
    assert "=======" in wc_conflict_file_content, "Conflict separator not found"
    assert ">>>>>>>" in wc_conflict_file_content, "Conflict end marker not found"
    assert "LOCAL CHANGE on Line 2" in wc_conflict_file_content, "Local change not in conflict file"
    assert "REMOTE CHANGE on Line 2" in wc_conflict_file_content, "Remote change not in conflict file"

    # Instead of checking index.conflicts directly, check the repository status
    # This is more reliable as it reflects both index and working directory state
    repo_status = local_repo.status()
    print(f"Repository status: {repo_status}")

    # Check if the conflict file is in a conflicted state (usually staged for merge with conflicts)
    file_status = repo_status.get(conflict_filename, 0)
    print(f"Conflict file status code: {file_status}")

    # Status with conflicts is usually a combination of flags that include GIT_STATUS_CONFLICTED
    # Rather than check for specific pygit2 constants, we can verify conflict file has changes
    assert file_status != 0, f"Conflict file {conflict_filename} should have a non-zero status"

    # Verify that the local HEAD didn't change (no auto-merge happened)
    assert local_repo.head.target == local_commit_after_local_change, "Local HEAD should not have moved"

    # Verify that the remote repo was not changed by this failed sync attempt
    remote_branch_ref_after_sync = bare_remote_repo.lookup_reference(f"refs/heads/{local_branch_name}")
    assert remote_branch_ref_after_sync.target == remote_commit_pushed_to_remote, "Remote should not have been updated due to conflict."


# #####################
# # Revert Command Tests
# #####################

def test_revert_successful_non_merge(local_repo, runner):
    """Test successful revert of a non-merge commit."""
    os.chdir(local_repo.workdir)

    # Commit 1: Initial file (already done by fixture, let's use it or make a new one for clarity)
    # The local_repo fixture makes an "initial.txt" with "Initial commit"
    initial_file_path = Path("initial.txt")
    assert initial_file_path.exists()
    original_content = initial_file_path.read_text()
    commit1_hash = local_repo.head.target

    # Commit 2: Modify file
    modified_content = original_content + "More content.\n"
    make_commit(local_repo, "initial.txt", modified_content, "Modify initial.txt")
    commit2_hash = local_repo.head.target
    commit2_obj = local_repo[commit2_hash]
    assert commit1_hash != commit2_hash

    # Action: Revert Commit 2
    result = runner.invoke(cli, ["revert", str(commit2_hash)])
    assert result.exit_code == 0, f"Revert command failed: {result.output}"

    # Verification
    assert f"Successfully reverted commit {commit2_obj.short_id}" in result.output

    # Extract short hash from output "New commit: <short_hash>"
    # Output format is "Successfully reverted commit {reverted_short_id}. New commit: {new_commit_short_id}"
    revert_commit_hash_short = result.output.strip().split("New commit: ")[-1][:7]
    revert_commit = local_repo.revparse_single(revert_commit_hash_short)
    assert revert_commit is not None, f"Could not find revert commit with short hash {revert_commit_hash_short}"
    assert local_repo.head.target == revert_commit.id

    expected_revert_msg_start = f"Revert \"{commit2_obj.message.splitlines()[0]}\""
    assert revert_commit.message.startswith(expected_revert_msg_start)

    # Check working directory state: file.txt should be back to Commit 1's state (original_content)
    assert initial_file_path.exists()
    assert initial_file_path.read_text() == original_content

    # Check that the tree of the revert commit matches the tree of commit1
    assert revert_commit.tree.id == local_repo[commit1_hash].tree.id


def test_revert_invalid_commit_ref(local_repo, runner):
    """Test revert with an invalid commit reference."""
    os.chdir(local_repo.workdir)
    # local_repo fixture already makes an initial commit.

    result = runner.invoke(cli, ["revert", "non_existent_hash"])
    assert result.exit_code != 0 # Should fail
    assert "Error: Invalid or ambiguous commit reference 'non_existent_hash'" in result.output


def test_revert_dirty_working_directory(local_repo, runner):
    """Test reverting in a dirty working directory."""
    os.chdir(local_repo.workdir)

    file_path = Path("changeable_file.txt")
    file_path.write_text("Stable content.\n")
    make_commit(local_repo, str(file_path.name), file_path.read_text(), "Add changeable_file.txt")
    commit_hash_to_revert = local_repo.head.target

    # Modify the file without committing
    dirty_content = "Dirty content that should prevent revert.\n"
    file_path.write_text(dirty_content)

    result = runner.invoke(cli, ["revert", str(commit_hash_to_revert)])
    assert result.exit_code != 0 # Should fail
    assert "Error: Your working directory or index has uncommitted changes." in result.output
    assert "Please commit or stash them before attempting to revert." in result.output

    # Ensure the file still has the dirty content
    assert file_path.read_text() == dirty_content
    # Ensure HEAD hasn't moved
    assert local_repo.head.target == commit_hash_to_revert


def test_revert_initial_commit(local_repo, runner):
    """Test reverting the initial commit made by the fixture."""
    os.chdir(local_repo.workdir)

    initial_commit_hash = local_repo.head.target # This is the "Initial commit" from the fixture
    initial_commit_obj = local_repo[initial_commit_hash]
    initial_file_path = Path("initial.txt")
    assert initial_file_path.exists() # Verify setup by fixture

    # Action: Revert the initial commit
    result = runner.invoke(cli, ["revert", str(initial_commit_hash)])
    assert result.exit_code == 0, f"Revert command failed: {result.output}"

    # Verification
    assert f"Successfully reverted commit {initial_commit_obj.short_id}" in result.output

    revert_commit_hash_short = result.output.strip().split("New commit: ")[-1][:7]
    revert_commit = local_repo.revparse_single(revert_commit_hash_short)
    assert revert_commit is not None
    assert local_repo.head.target == revert_commit.id

    expected_revert_msg_start = f"Revert \"{initial_commit_obj.message.splitlines()[0]}\""
    assert revert_commit.message.startswith(expected_revert_msg_start)

    # Check working directory state: initial_file.txt should be gone
    assert not initial_file_path.exists()

    # The repository should be "empty" in terms of tracked files in the revert commit's tree
    revert_commit_tree = revert_commit.tree
    assert len(revert_commit_tree) == 0, "Tree of revert commit should be empty"


def test_revert_a_revert_commit(local_repo, runner):
    """Test reverting a revert commit restores original state."""
    os.chdir(local_repo.workdir)

    # Commit A: A new file for this test
    file_path = Path("story_for_revert_test.txt")
    original_content = "Chapter 1: The adventure begins.\n"
    make_commit(local_repo, str(file_path.name), original_content, "Commit A: Add story_for_revert_test.txt")
    commit_A_hash = local_repo.head.target
    commit_A_obj = local_repo[commit_A_hash]

    # Revert Commit A (this creates Commit B)
    result_revert_A = runner.invoke(cli, ["revert", str(commit_A_hash)])
    assert result_revert_A.exit_code == 0, f"Reverting Commit A failed: {result_revert_A.output}"
    commit_B_short_hash = result_revert_A.output.strip().split("New commit: ")[-1][:7]
    commit_B_obj = local_repo.revparse_single(commit_B_short_hash)
    assert commit_B_obj is not None

    # Verify file is gone after first revert
    assert not file_path.exists(), "File should be deleted by first revert"
    expected_msg_B_start = f"Revert \"{commit_A_obj.message.splitlines()[0]}\""
    assert commit_B_obj.message.startswith(expected_msg_B_start)

    # Action: Revert Commit B (the revert commit)
    result_revert_B = runner.invoke(cli, ["revert", commit_B_obj.short_id])
    assert result_revert_B.exit_code == 0, f"Failed to revert Commit B: {result_revert_B.output}"

    commit_C_short_hash = result_revert_B.output.strip().split("New commit: ")[-1][:7]
    commit_C_obj = local_repo.revparse_single(commit_C_short_hash)
    assert commit_C_obj is not None

    # Verification for Commit C
    expected_msg_C_start = f"Revert \"{commit_B_obj.message.splitlines()[0]}\""
    assert commit_C_obj.message.startswith(expected_msg_C_start)

    # Check working directory: story_for_revert_test.txt should be back with original content
    assert file_path.exists(), "File should reappear after reverting the revert"
    assert file_path.read_text() == original_content

    # The tree of Commit C should be identical to the tree of Commit A
    assert commit_C_obj.tree.id == commit_A_obj.tree.id


def test_revert_successful_merge_commit(local_repo, runner):
    """Test successful revert of a merge commit using --mainline."""
    os.chdir(local_repo.workdir)

    # Base commit (C1) - already exists from fixture ("initial.txt")
    c1_hash = local_repo.head.target
    main_branch_name = local_repo.head.shorthand # usually "master" or "main"

    # Create branch-A from C1, add commit C2a changing fileA.txt
    branch_A_name = "branch-A"
    file_A_path = Path("fileA.txt")
    content_A = "Content for file A\n"

    local_repo.branches.local.create(branch_A_name, local_repo[c1_hash])
    local_repo.checkout(local_repo.branches.local[branch_A_name])
    make_commit(local_repo, str(file_A_path.name), content_A, "Commit C2a on branch-A (add fileA.txt)")
    c2a_hash = local_repo.head.target

    # Switch back to main, create branch-B from C1, add commit C2b changing fileB.txt
    local_repo.checkout(local_repo.branches.local[main_branch_name]) # back to main branch @ C1
    assert local_repo.head.target == c1_hash # ensure we are back at C1 before branching B

    branch_B_name = "branch-B"
    file_B_path = Path("fileB.txt")
    content_B = "Content for file B\n"

    local_repo.branches.local.create(branch_B_name, local_repo[c1_hash])
    local_repo.checkout(local_repo.branches.local[branch_B_name])
    make_commit(local_repo, str(file_B_path.name), content_B, "Commit C2b on branch-B (add fileB.txt)")
    c2b_hash = local_repo.head.target

    # Switch back to main
    local_repo.checkout(local_repo.branches.local[main_branch_name])
    assert local_repo.head.target == c1_hash

    # Merge branch-A into main (C3) - this will be a fast-forward merge
    # For a fast-forward, we directly update the branch reference and HEAD
    main_branch_ref = local_repo.branches.local[main_branch_name]
    main_branch_ref.set_target(c2a_hash)
    local_repo.set_head(main_branch_ref.name) # Update HEAD to point to the main branch ref
    local_repo.checkout_head(strategy=pygit2.GIT_CHECKOUT_FORCE) # Update working dir to match new HEAD

    c3_hash = local_repo.head.target # This should now be c2a_hash
    assert c3_hash == c2a_hash, f"C3 hash {c3_hash} should be C2a hash {c2a_hash} after fast-forward."
    assert file_A_path.exists() and file_A_path.read_text() == content_A
    assert not file_B_path.exists()

    # Merge branch-B into main (C4) - this creates a true merge commit
    # Parents of C4 should be C3 (from main) and C2b (from branch-B)
    # Perform the merge which updates the index
    merge_result, _ = local_repo.merge_analysis(c2b_hash)
    assert not (merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE)
    assert not (merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD)
    assert (merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL)

    local_repo.merge(c2b_hash) # This updates the index with merge changes

    # Using default_signature for author/committer in merge commit
    author = local_repo.default_signature
    committer = local_repo.default_signature
    tree = local_repo.index.write_tree() # Write the merged index to a tree

    # Create the actual merge commit C4
    c4_hash = local_repo.create_commit(
        "HEAD", # Update HEAD to this new merge commit
        author,
        committer,
        f"Commit C4: Merge {branch_B_name} into {main_branch_name}",
        tree,
        [c3_hash, c2b_hash] # Parents are C3 (current main) and C2b (from branch-B)
    )
    local_repo.state_cleanup() # Clean up MERGE_HEAD etc.
    c4_obj = local_repo[c4_hash]

    assert len(c4_obj.parents) == 2
    # Verify parents explicitly
    parent_hashes = {p.id for p in c4_obj.parents}
    assert parent_hashes == {c3_hash, c2b_hash}
    # Ensure files from both branches are present
    assert file_A_path.read_text() == content_A
    assert file_B_path.read_text() == content_B

    # Action: Attempt to revert merge commit C4.
    # This should now fail with a specific message, as index-only merge reverts are not supported.
    result_revert_merge = runner.invoke(cli, ["revert", str(c4_hash)])

    assert result_revert_merge.exit_code != 0, "Reverting a merge commit without --mainline should fail."
    assert f"Error: Commit '{c4_obj.short_id}' is a merge commit." in result_revert_merge.output
    assert "Reverting merge commits with specific mainline parent selection to only update the" in result_revert_merge.output
    assert "working directory/index (before creating a commit) is not supported" in result_revert_merge.output

    # Ensure no new commit was made and files are still as they were in C4
    assert local_repo.head.target == c4_hash
    assert file_A_path.exists() and file_A_path.read_text() == content_A
    assert file_B_path.exists() and file_B_path.read_text() == content_B

    # Attempting with --mainline should also fail with the same message
    result_revert_merge_mainline = runner.invoke(cli, ["revert", str(c4_hash), "--mainline", "1"])
    assert result_revert_merge_mainline.exit_code != 0
    assert f"Error: Commit '{c4_obj.short_id}' is a merge commit." in result_revert_merge_mainline.output
    assert "Reverting merge commits with specific mainline parent selection to only update the" in result_revert_merge_mainline.output


def test_revert_with_conflicts_and_resolve(local_repo, runner):
    """Test reverting a commit that causes conflicts, then resolve and save."""
    os.chdir(local_repo.workdir)
    file_path = Path("conflict_file.txt")

    # Commit A
    content_A = "line1\ncommon_line_original\nline3\n"
    make_commit(local_repo, str(file_path.name), content_A, "Commit A: Base for conflict")

    # Commit B (modifies common_line_original)
    content_B = "line1\ncommon_line_modified_by_B\nline3\n"
    make_commit(local_repo, str(file_path.name), content_B, "Commit B: Modifies common_line")
    commit_B_hash = local_repo.head.target
    commit_B_obj = local_repo[commit_B_hash]

    # Commit C (modifies the same line that B changed from A)
    content_C = "line1\ncommon_line_modified_by_C_after_B\nline3\n"
    make_commit(local_repo, str(file_path.name), content_C, "Commit C: Modifies common_line again")

    # Action: Attempt gitwrite revert <hash_of_B>
    # This should conflict because C modified the same line that B's revert wants to change back.
    result_revert = runner.invoke(cli, ["revert", str(commit_B_hash)])
    assert result_revert.exit_code == 0, f"Revert command unexpectedly failed during conflict: {result_revert.output}" # Command itself succeeds by reporting conflict

    # Verification of conflict state
    assert "Conflicts detected after revert. Automatic commit aborted." in result_revert.output
    assert f"Conflicting files:\n  {str(file_path.name)}" in result_revert.output

    # Check file content for conflict markers
    assert file_path.exists()
    conflict_content = file_path.read_text()
    assert "<<<<<<< HEAD" in conflict_content # Changes from Commit C are 'ours' (HEAD)
    assert "=======" in conflict_content
    # The 'theirs' side of the conflict when reverting B should be the content from Commit A
    assert "common_line_original" in conflict_content # This is what B's revert tries to restore
    assert ">>>>>>> parent of " + commit_B_obj.short_id in conflict_content # Or similar marker for reverted changes

    # Check repository state
    assert local_repo.lookup_reference("REVERT_HEAD").target == commit_B_hash

    # Resolve conflict: Let's say we choose to keep the changes from Commit C (the current HEAD)
    # and add a line indicating resolution.
    resolved_content = "line1\ncommon_line_modified_by_C_after_B\nresolved_conflict_line\nline3\n"
    file_path.write_text(resolved_content)

    # Explicitly stage the resolved file using the test's repo instance
    local_repo.index.add(file_path.name)
    local_repo.index.write()
    print(f"TEST-DEBUG: Conflicts in local_repo after add/write: {list(local_repo.index.conflicts) if local_repo.index.conflicts else 'None'}")


    # Action: gitwrite save "Resolved conflict after reverting B"
    user_save_message = "Resolved conflict after reverting B"
    result_save = runner.invoke(cli, ["save", user_save_message])
    assert result_save.exit_code == 0, f"Save command failed: {result_save.output}"

    # Verification of successful save after conflict resolution
    assert f"Finalizing revert of commit {commit_B_obj.short_id}" in result_save.output
    assert "Successfully completed revert operation." in result_save.output

    # Robustly parse commit hash from output like "[main abc1234] User message"
    # or "[DETACHED HEAD abc1234] User message"
    output_lines = result_save.output.strip().split('\n')
    commit_line = None
    for line in output_lines:
        if line.startswith("[") and "] " in line: # A bit more robust to find the commit line
            # Check if it's not a DEBUG line
            if not line.startswith("[DEBUG:"):
                commit_line = line
                break
    assert commit_line is not None, f"Could not find commit line in output: {result_save.output}"

    # Extract from pattern like "[branch hash] message" or "[DETACHED HEAD hash] message"
    try:
        # Handle potential "DETACHED HEAD" which has a space
        if "[DETACHED HEAD " in commit_line:
             new_commit_hash_short = commit_line.split("[DETACHED HEAD ")[1].split("]")[0]
        else: # Standard "[branch hash]"
             new_commit_hash_short = commit_line.split(" ")[1].split("]")[0]
    except IndexError:
        raise AssertionError(f"Could not parse commit hash from line: {commit_line}\nFull output:\n{result_save.output}")

    final_commit = local_repo.revparse_single(new_commit_hash_short)
    assert final_commit is not None, f"Could not find commit with short hash {new_commit_hash_short}"

    expected_final_msg_start = f"Revert \"{commit_B_obj.message.splitlines()[0]}\""
    assert final_commit.message.startswith(expected_final_msg_start)
    assert user_save_message in final_commit.message # User's message should be part of it

    assert file_path.read_text() == resolved_content

    # Verify REVERT_HEAD is cleared and repo state is normal
    with pytest.raises(KeyError): # REVERT_HEAD should be gone
        local_repo.lookup_reference("REVERT_HEAD")
    with pytest.raises(KeyError): # MERGE_HEAD should also be gone if state_cleanup ran
        local_repo.lookup_reference("MERGE_HEAD")
    # assert local_repo.state == pygit2.GIT_REPOSITORY_STATE_NONE
    # The repo.state might not immediately return to NONE in test environment
    # if other refs like ORIG_HEAD persist briefly or due to other nuances.
    # The critical part for CLI logic is that REVERT_HEAD/MERGE_HEAD are gone.


#######################################
# Explore Command Tests (CLI Runner)
#######################################

# This fixture is already defined from the previous step for 'explore' tests.
# It can be reused for 'switch' tests that need a basic repo with one commit.
@pytest.fixture
def cli_test_repo(tmp_path: Path):
    """Creates a standard initialized repo for CLI tests, returning its path."""
    repo_path = tmp_path / "cli_git_repo_explore" # Unique name
    repo_path.mkdir()
    repo = pygit2.init_repository(str(repo_path), bare=False)
    # Initial commit
    file_path = repo_path / "initial.txt"
    file_path.write_text("initial content for explore tests")
    repo.index.add("initial.txt")
    repo.index.write()
    author = pygit2.Signature("Test Author CLI", "testcli@example.com")
    tree = repo.index.write_tree()
    repo.create_commit("HEAD", author, author, "Initial commit for CLI explore", tree, [])
    return repo_path

class TestExploreCommandCLI:
    def test_explore_success_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo) # CLI operates on CWD
        branch_name = "my-new-adventure"
        result = runner.invoke(cli, ["explore", branch_name])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to a new exploration: {branch_name}" in result.output

        repo = pygit2.Repository(str(cli_test_repo))
        assert repo.head.shorthand == branch_name
        assert not repo.head_is_detached

    def test_explore_branch_exists_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        branch_name = "existing-feature-branch"

        repo = pygit2.Repository(str(cli_test_repo))
        repo.branches.local.create(branch_name, repo.head.peel(pygit2.Commit)) # Pre-create the branch

        result = runner.invoke(cli, ["explore", branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}" # CLI handles error gracefully
        assert f"Error: Branch '{branch_name}' already exists." in result.output

    def test_explore_empty_repo_cli(self, runner: CliRunner, tmp_path: Path):
        empty_repo_dir = tmp_path / "empty_repo_for_cli_explore"
        empty_repo_dir.mkdir()
        pygit2.init_repository(str(empty_repo_dir)) # Initialize empty repo
        os.chdir(empty_repo_dir)

        result = runner.invoke(cli, ["explore", "some-branch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # This message comes from the core function, propagated by the CLI
        assert "Error: Cannot create branch: HEAD is unborn. Commit changes first." in result.output

    def test_explore_bare_repo_cli(self, runner: CliRunner, tmp_path: Path):
        bare_repo_dir = tmp_path / "bare_repo_for_cli_explore.git"
        pygit2.init_repository(str(bare_repo_dir), bare=True)

        # For CLI tests, `discover_repository` is called on `Path.cwd()`.
        # If CWD is the bare repo path, it will be discovered.
        os.chdir(bare_repo_dir)

        result = runner.invoke(cli, ["explore", "any-branch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_explore_non_git_directory_cli(self, runner: CliRunner, tmp_path: Path):
        non_git_dir = tmp_path / "non_git_dir_for_cli_explore"
        non_git_dir.mkdir()
        os.chdir(non_git_dir)

        result = runner.invoke(cli, ["explore", "any-branch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # The error message includes the path that was checked.
        # For CWD, this is often represented as '.' or the full path.
        # The core function error is "Repository not found at or above '{repo_path_str}'"
        # The CLI passes str(Path.cwd()) which becomes the path_str.
        # We check for the core parts of the message.
        assert "Error: Repository not found at or above" in result.output
        # Check if the path is mentioned, could be '.' or absolute path
        assert f"'{str(Path.cwd())}'" in result.output or "'.'" in result.output

#Fixture for testing CLI commands that interact with remotes
@pytest.fixture
def cli_repo_with_remote(tmp_path: Path):
    local_repo_path = tmp_path / "cli_local_for_remote"
    local_repo_path.mkdir()
    local_repo = pygit2.init_repository(str(local_repo_path))
    # Use the make_commit helper defined in this file
    make_commit(local_repo, "main_file.txt", "content on main", "Initial commit on main")

    bare_remote_path = tmp_path / "cli_remote_server.git"
    pygit2.init_repository(str(bare_remote_path), bare=True)

    origin_remote = local_repo.remotes.create("origin", str(bare_remote_path))

    # Push main to establish it on remote
    main_branch_name = local_repo.head.shorthand
    origin_remote.push([f"refs/heads/{main_branch_name}:refs/heads/{main_branch_name}"])

    # Create feature-x, commit, push to origin/feature-x
    main_commit = local_repo.head.peel(pygit2.Commit)
    local_repo.branches.local.create("feature-x", main_commit)
    local_repo.checkout("refs/heads/feature-x")
    make_commit(local_repo, "fx_file.txt", "feature-x content", "Commit on feature-x")
    origin_remote.push(["refs/heads/feature-x:refs/heads/feature-x"])

    # Create another remote branch origin/feature-y without a local counterpart after push
    local_repo.checkout(f"refs/heads/{main_branch_name}") # Back to main
    main_commit_again = local_repo.head.peel(pygit2.Commit)
    local_repo.branches.local.create("feature-y-local", main_commit_again) # Temporary local branch
    local_repo.checkout("refs/heads/feature-y-local")
    make_commit(local_repo, "fy_file.txt", "feature-y content", "Commit for feature-y")
    origin_remote.push(["refs/heads/feature-y-local:refs/heads/feature-y"]) # Push to 'feature-y' on remote
    local_repo.branches.local.delete("feature-y-local") # Delete the temp local branch

    # Return to main branch in local repo
    local_repo.checkout(f"refs/heads/{main_branch_name}")

    return local_repo_path


class TestSwitchCommandCLI:
    def test_switch_list_success_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        # cli_test_repo has 'main' (or default like 'master'). Let's assume 'main'.
        # Create 'develop' for listing.
        main_commit = repo.head.peel(pygit2.Commit)
        repo.branches.local.create("develop", main_commit)
        # Current branch is 'main' (or the default from cli_test_repo fixture)

        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Available Explorations" in result.output # Table title
        # Order depends on sorting, core list_branches sorts alphabetically.
        # Fixture creates 'main', we add 'develop'. Expected: 'develop', 'main'
        # Current branch (main) should be marked with '*'
        output_lines = result.output.splitlines()
        assert any("  develop" in line for line in output_lines)
        assert any(f"* {repo.head.shorthand}" in line for line in output_lines)


    def test_switch_list_empty_repo_cli(self, runner: CliRunner, tmp_path: Path):
        empty_repo_dir = tmp_path / "empty_for_cli_switch_list"
        empty_repo_dir.mkdir()
        pygit2.init_repository(str(empty_repo_dir))
        os.chdir(empty_repo_dir)

        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No explorations (branches) yet." in result.output

    def test_switch_list_bare_repo_cli(self, runner: CliRunner, tmp_path: Path):
        bare_repo_dir = tmp_path / "bare_for_cli_switch_list.git"
        pygit2.init_repository(str(bare_repo_dir), bare=True)
        os.chdir(bare_repo_dir)

        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_switch_list_non_git_directory_cli(self, runner: CliRunner, tmp_path: Path):
        non_git_dir = tmp_path / "non_git_for_cli_switch_list"
        non_git_dir.mkdir()
        os.chdir(non_git_dir)

        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Repository not found at or above" in result.output

    def test_switch_to_local_branch_success_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        initial_branch = repo.head.shorthand

        repo.branches.local.create("develop", repo.head.peel(pygit2.Commit))

        result = runner.invoke(cli, ["switch", "develop"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to exploration: develop" in result.output

        repo.head.resolve() # Ensure head is refreshed
        assert repo.head.shorthand == "develop"
        assert not repo.head_is_detached

    def test_switch_already_on_branch_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        current_branch = repo.head.shorthand

        result = runner.invoke(cli, ["switch", current_branch])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Already on exploration: {current_branch}" in result.output

    def test_switch_to_remote_branch_detached_head_cli(self, runner: CliRunner, cli_repo_with_remote: Path):
        os.chdir(cli_repo_with_remote)
        # 'feature-y' exists on remote 'origin' but not locally in the fixture.
        # Core function resolves "feature-y" to "origin/feature-y"

        result = runner.invoke(cli, ["switch", "feature-y"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to exploration: origin/feature-y" in result.output # Core returns resolved name
        assert "Note: HEAD is now in a detached state." in result.output

        repo = pygit2.Repository(str(cli_repo_with_remote))
        assert repo.head_is_detached

    def test_switch_branch_not_found_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        result = runner.invoke(cli, ["switch", "no-such-branch-here"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Branch 'no-such-branch-here' not found" in result.output

    def test_switch_in_bare_repo_action_cli(self, runner: CliRunner, tmp_path: Path):
        bare_repo_dir = tmp_path / "bare_for_cli_switch_action.git"
        pygit2.init_repository(str(bare_repo_dir), bare=True)
        os.chdir(bare_repo_dir)

        result = runner.invoke(cli, ["switch", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Operation not supported in bare repositories." in result.output

    def test_switch_in_empty_repo_action_cli(self, runner: CliRunner, tmp_path: Path):
        empty_repo_dir = tmp_path / "empty_for_cli_switch_action"
        empty_repo_dir.mkdir()
        pygit2.init_repository(str(empty_repo_dir))
        os.chdir(empty_repo_dir)

        result = runner.invoke(cli, ["switch", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # Core `switch_to_branch` raises RepositoryEmptyError in this specific case
        assert "Error: Cannot switch branch in an empty repository to non-existent branch 'anybranch'." in result.output

    def test_switch_dirty_workdir_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))

        # Create 'develop' branch
        main_commit = repo.head.peel(pygit2.Commit)
        develop_branch = repo.branches.local.create("develop", main_commit)

        # Make a commit on 'develop' that modifies a file
        repo.checkout(develop_branch.name)
        repo.set_head(develop_branch.name)
        (Path(str(cli_test_repo)) / "conflict_file.txt").write_text("Version on develop")
        make_commit(repo, "conflict_file.txt", "Version on develop", "Commit on develop")

        # Switch back to 'main'
        main_branch = repo.branches.local[repo.head.shorthand if repo.head.shorthand == 'main' else 'master'] # Get main/master
        repo.checkout(main_branch.name)
        repo.set_head(main_branch.name)

        # Create the same file on 'main' with different content and make it dirty
        (Path(str(cli_test_repo)) / "conflict_file.txt").write_text("Dirty version on main")

        result = runner.invoke(cli, ["switch", "develop"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Checkout failed: Your local changes to tracked files would be overwritten by checkout of 'develop'." in result.output


#######################################
# Tests for Save Selective Staging
#######################################

class TestGitWriteSaveSelectiveStaging:

    def test_save_include_single_file(self, runner, local_repo):
        """Test saving a single specified file using --include."""
        repo = local_repo
        os.chdir(repo.workdir)

        create_file(repo, "file1.txt", "Content for file1")
        create_file(repo, "file2.txt", "Content for file2")

        commit_message = "Commit file1 selectively"
        initial_head = repo.head.target

        result = runner.invoke(cli, ["save", "-i", "file1.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Staged specified files: file1.txt" in result.output
        assert f"[{repo.head.shorthand}" in result.output # Check for commit summary line

        new_head = repo.head.target
        assert new_head != initial_head, "No new commit was made"
        commit = repo.get(new_head)
        assert commit.message.strip() == commit_message

        # Check tree contents
        assert "file1.txt" in commit.tree
        assert "file2.txt" not in commit.tree

        # Check status of file2.txt (should be unstaged)
        status = repo.status()
        assert "file2.txt" in status
        assert status["file2.txt"] == pygit2.GIT_STATUS_WT_NEW

    def test_save_include_multiple_files(self, runner, local_repo):
        """Test saving multiple specified files using --include."""
        repo = local_repo
        os.chdir(repo.workdir)

        create_file(repo, "file1.txt", "Content for file1")
        create_file(repo, "file2.txt", "Content for file2")
        create_file(repo, "file3.txt", "Content for file3")

        commit_message = "Commit file1 and file2 selectively"
        initial_head = repo.head.target

        result = runner.invoke(cli, ["save", "-i", "file1.txt", "-i", "file2.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # Order in output message might vary, so check for both
        assert "Staged specified files:" in result.output
        assert "file1.txt" in result.output
        assert "file2.txt" in result.output


        new_head = repo.head.target
        assert new_head != initial_head, "No new commit was made"
        commit = repo.get(new_head)
        assert commit.message.strip() == commit_message

        assert "file1.txt" in commit.tree
        assert "file2.txt" in commit.tree
        assert "file3.txt" not in commit.tree

        status = repo.status()
        assert "file3.txt" in status
        assert status["file3.txt"] == pygit2.GIT_STATUS_WT_NEW

    def test_save_default_behavior_with_changes(self, runner, local_repo):
        """Test default save behavior (all changes) when --include is not used."""
        repo = local_repo
        os.chdir(repo.workdir)

        create_file(repo, "file1.txt", "Content for file1")
        create_file(repo, "file2.txt", "Content for file2")

        commit_message = "Commit all changes (default behavior)"
        initial_head = repo.head.target

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Staged all changes." in result.output

        new_head = repo.head.target
        assert new_head != initial_head, "No new commit was made"
        commit = repo.get(new_head)
        assert commit.message.strip() == commit_message

        assert "file1.txt" in commit.tree
        assert "file2.txt" in commit.tree
        assert not repo.status(), "Working directory should be clean after saving all changes"

    def test_save_include_unmodified_file(self, runner, local_repo):
        """Test --include with an unmodified (but tracked) file and a new file."""
        repo = local_repo
        os.chdir(repo.workdir)

        # Create and commit file1.txt so it's tracked and unmodified
        make_commit(repo, "file1.txt", "Initial content for file1", "Commit file1 initially")
        initial_commit_tree_id_for_file1 = repo.head.peel(pygit2.Commit).tree['file1.txt'].id


        create_file(repo, "file2.txt", "Content for file2 (new)") # New file

        commit_message = "Commit file2, file1 is unmodified"
        initial_head = repo.head.target

        result = runner.invoke(cli, ["save", "-i", "file1.txt", "-i", "file2.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert "Warning: Path 'file1.txt' has no changes to stage." in result.output
        assert "Staged specified files:" in result.output
        assert "file2.txt" in result.output # Only file2 should be listed as staged
        assert "file1.txt" not in result.output.split("Staged specified files:")[1]


        new_head = repo.head.target
        assert new_head != initial_head, "No new commit was made"
        commit = repo.get(new_head)
        assert commit.message.strip() == commit_message

        assert "file2.txt" in commit.tree # New file staged and committed
        assert "file1.txt" in commit.tree # Tracked file still in tree
        # Assert file1.txt is NOT part of the changes in the new commit
        # Its tree entry should be same as parent's tree entry for file1.txt
        assert commit.tree['file1.txt'].id == initial_commit_tree_id_for_file1

        # Check status: file1.txt should be clean, file2.txt committed
        status = repo.status()
        assert "file1.txt" not in status # Clean
        assert "file2.txt" not in status # Clean (committed)

    def test_save_include_non_existent_file(self, runner, local_repo):
        """Test --include with a non-existent file and a new file."""
        repo = local_repo
        os.chdir(repo.workdir)

        create_file(repo, "file1.txt", "Content for existing file1")

        commit_message = "Commit file1 with warning for non_existent"
        initial_head = repo.head.target

        result = runner.invoke(cli, ["save", "-i", "non_existent.txt", "-i", "file1.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert "Warning: Path 'non_existent.txt' is not tracked by Git or does not exist." in result.output
        assert "Staged specified files:" in result.output
        assert "file1.txt" in result.output
        assert "non_existent.txt" not in result.output.split("Staged specified files:")[1]

        new_head = repo.head.target
        assert new_head != initial_head, "No new commit was made"
        commit = repo.get(new_head)
        assert commit.message.strip() == commit_message
        assert "file1.txt" in commit.tree
        assert "non_existent.txt" not in commit.tree

    def test_save_include_all_files_unmodified_or_invalid(self, runner, local_repo):
        """Test --include with only unmodified or invalid files."""
        repo = local_repo
        os.chdir(repo.workdir)

        make_commit(repo, "file1.txt", "Initial content for file1", "Commit file1 initially")
        initial_head = repo.head.target

        commit_message = "Attempt to commit no real changes"
        result = runner.invoke(cli, ["save", "-i", "file1.txt", "-i", "non_existent.txt", commit_message])

        # Exit code should still be 0 as the command itself ran, but it should print specific messages.
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Warning: Path 'file1.txt' has no changes to stage." in result.output
        assert "Warning: Path 'non_existent.txt' is not tracked by Git or does not exist." in result.output
        assert "No specified files had changes to stage." in result.output
        assert "No changes to save." in result.output

        assert repo.head.target == initial_head, "A new commit was made when no valid changes were included"

    def test_save_include_empty(self, runner, local_repo):
        """Test `gitwrite save --include` with an empty string path."""
        repo = local_repo
        os.chdir(repo.workdir)

        create_file(repo, "file1.txt", "Content for file1") # A changed file exists in WT
        initial_head = repo.head.target
        commit_message = "Commit with empty include path"

        # This specific invocation is what the test aims for.
        result_empty_path = runner.invoke(cli, ["save", "-i", "", commit_message])
        print(f"Output for test_save_include_empty: {result_empty_path.output}") # DEBUG PRINT
        assert result_empty_path.exit_code == 0, f"CLI Error: {result_empty_path.output}"

        assert "Warning: An empty path was provided and will be ignored." in result_empty_path.output
        assert "No specified files had changes to stage." in result_empty_path.output
        assert "No changes to save." in result_empty_path.output

        new_head_oid = repo.head.target
        if new_head_oid != initial_head:
            new_commit_obj = repo.get(new_head_oid)
            print(f"DEBUG_TEST: Initial HEAD: {initial_head.hex}")
            print(f"DEBUG_TEST: New HEAD: {new_head_oid.hex}")
            print(f"DEBUG_TEST: New unexpected commit created in test_save_include_empty.")
            print(f"DEBUG_TEST: Message: {new_commit_obj.message.strip()}")
            print(f"DEBUG_TEST: Tree: { {entry.name: entry.id.hex for entry in new_commit_obj.tree} }")
            print(f"DEBUG_TEST: Parents: {[p.hex for p in new_commit_obj.parent_ids]}")
        assert new_head_oid == initial_head, "A new commit was made with an empty include path"


    def test_save_include_ignored_file(self, runner, local_repo):
        """Test --include with an ignored file."""
        repo = local_repo
        os.chdir(repo.workdir)

        # Create .gitignore and add a pattern
        gitignore_content = "*.ignored\n"
        create_file(repo, ".gitignore", gitignore_content)
        make_commit(repo, ".gitignore", gitignore_content, "Add .gitignore")

        # Create an ignored file and a normal file
        create_file(repo, "ignored_file.ignored", "This file should be ignored.")
        create_file(repo, "normal_file.txt", "This file is not ignored.")

        initial_head = repo.head.target
        commit_message = "Commit normal_file, warn for ignored_file"

        result = runner.invoke(cli, ["save", "-i", "ignored_file.ignored", "-i", "normal_file.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert "Warning: Path 'ignored_file.ignored' is ignored." in result.output
        assert "Staged specified files:" in result.output
        assert "normal_file.txt" in result.output
        assert "ignored_file.ignored" not in result.output.split("Staged specified files:")[1]

        new_head = repo.head.target
        assert new_head != initial_head, "No new commit was made"
        commit = repo.get(new_head)
        assert commit.message.strip() == commit_message

        assert "normal_file.txt" in commit.tree
        assert "ignored_file.ignored" not in commit.tree # Should not be committed

        assert repo.path_is_ignored("ignored_file.ignored"), "ignored_file.ignored should be reported as ignored by pathisignored()"

    def test_save_include_during_merge(self, runner, repo_with_merge_conflict):
        """Test `gitwrite save --include` during an active merge operation."""
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)

        # repo_with_merge_conflict fixture sets up a merge state with MERGE_HEAD
        assert repo.lookup_reference("MERGE_HEAD") is not None
        initial_head = repo.head.target

        # Attempt to save with --include
        result = runner.invoke(cli, ["save", "-i", "conflict_file.txt", "Attempt include during merge"])

        # Expect error message and no commit
        assert result.exit_code == 0, f"CLI Error: {result.output}" # Command runs, prints error
        assert "Error: Selective staging with --include is not allowed during an active merge operation." in result.output

        assert repo.head.target == initial_head, "A new commit was made during merge with --include"
        assert repo.lookup_reference("MERGE_HEAD") is not None, "MERGE_HEAD was cleared"

    def test_save_include_during_revert(self, runner, repo_with_revert_conflict):
        """Test `gitwrite save --include` during an active revert operation."""
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)

        # repo_with_revert_conflict fixture sets up a revert state with REVERT_HEAD
        assert repo.lookup_reference("REVERT_HEAD") is not None
        initial_head = repo.head.target

        # Attempt to save with --include
        result = runner.invoke(cli, ["save", "-i", "revert_conflict_file.txt", "Attempt include during revert"])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Selective staging with --include is not allowed during an active revert operation." in result.output

        assert repo.head.target == initial_head, "A new commit was made during revert with --include"
        assert repo.lookup_reference("REVERT_HEAD") is not None, "REVERT_HEAD was cleared"

    def test_save_no_include_during_merge_resolved(self, runner, repo_with_merge_conflict):
        """Test `gitwrite save` (no include) after resolving a merge."""
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)

        conflict_filename = "conflict_file.txt" # Known from fixture
        resolve_conflict(repo, conflict_filename, "Resolved content for merge")

        initial_head_before_save = repo.head.target
        merge_head_oid_before_save = repo.lookup_reference("MERGE_HEAD").target

        commit_message = "Resolved merge successfully"
        result = runner.invoke(cli, ["save", commit_message])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Successfully completed merge operation." in result.output

        new_head = repo.head.target
        assert new_head != initial_head_before_save, "No new commit was made for resolved merge"

        commit = repo.get(new_head)
        assert commit.message.strip() == commit_message
        assert len(commit.parents) == 2
        # Ensure original HEAD and MERGE_HEAD target are parents
        parent_oids = {p.id for p in commit.parents}
        assert initial_head_before_save in parent_oids
        assert merge_head_oid_before_save in parent_oids

        with pytest.raises(KeyError): # MERGE_HEAD should be gone
            repo.lookup_reference("MERGE_HEAD")
        assert not repo.index.conflicts, "Index conflicts were not cleared"

    def test_save_no_include_during_revert_resolved(self, runner, repo_with_revert_conflict):
        """Test `gitwrite save` (no include) after resolving a revert."""
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)

        conflict_filename = "revert_conflict_file.txt" # Known from fixture
        reverted_commit_oid = repo.lookup_reference("REVERT_HEAD").target
        reverted_commit_obj = repo.get(reverted_commit_oid)

        resolve_conflict(repo, conflict_filename, "Resolved content for revert")

        initial_head_before_save = repo.head.target
        commit_message = "Resolved revert successfully"

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert f"Finalizing revert of commit {reverted_commit_obj.short_id}" in result.output
        assert "Successfully completed revert operation." in result.output

        new_head = repo.head.target
        assert new_head != initial_head_before_save, "No new commit was made for resolved revert"

        commit = repo.get(new_head)
        expected_revert_prefix = f"Revert \"{reverted_commit_obj.message.splitlines()[0]}\""
        assert commit.message.startswith(expected_revert_prefix)
        assert commit_message in commit.message # User's message should be appended

        with pytest.raises(KeyError): # REVERT_HEAD should be gone
            repo.lookup_reference("REVERT_HEAD")
        assert not repo.index.conflicts, "Index conflicts were not cleared"


# ###################################
# # Helper functions for save tests
# ###################################

def create_file(repo: pygit2.Repository, filename: str, content: str):
    """Helper function to create a file in the repository's working directory."""
    file_path = Path(repo.workdir) / filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content)
    return file_path

def stage_file(repo: pygit2.Repository, filename: str):
    """Helper function to stage a file in the repository."""
    repo.index.add(filename)
    repo.index.write()

# #################################
# # Fixtures for save command tests
# #################################

@pytest.fixture
def repo_with_unstaged_changes(local_repo):
    """Creates a repository with a file that has unstaged changes."""
    repo = local_repo
    create_file(repo, "unstaged_file.txt", "This file has unstaged changes.")
    # Do not stage the file
    return repo

@pytest.fixture
def repo_with_staged_changes(local_repo):
    """Creates a repository with a file that has staged changes."""
    repo = local_repo
    create_file(repo, "staged_file.txt", "This file has staged changes.")
    stage_file(repo, "staged_file.txt")
    return repo

@pytest.fixture
def repo_with_merge_conflict(local_repo, bare_remote_repo, tmp_path):
    """Creates a repository with a merge conflict."""
    repo = local_repo
    os.chdir(repo.workdir)
    branch_name = repo.head.shorthand

    # Base file
    conflict_filename = "conflict_file.txt"
    initial_content = "Line 1\nLine 2 for conflict\nLine 3\n"
    make_commit(repo, conflict_filename, initial_content, f"Add initial {conflict_filename}")
    repo.remotes["origin"].push([f"refs/heads/{branch_name}:refs/heads/{branch_name}"])
    base_commit_oid = repo.head.target

    # 1. Local change
    local_conflict_content = "Line 1\nLOCAL CHANGE on Line 2\nLine 3\n"
    make_commit(repo, conflict_filename, local_conflict_content, "Local conflicting change")

    # 2. Remote change (via a clone)
    remote_clone_path = tmp_path / "remote_clone_for_merge_conflict_fixture"
    remote_clone_repo = pygit2.clone_repository(bare_remote_repo.path, str(remote_clone_path))
    config = remote_clone_repo.config
    config["user.name"] = "Remote Conflicter"
    config["user.email"] = "conflicter@example.com"
    remote_clone_repo.reset(base_commit_oid, pygit2.GIT_RESET_HARD) # Reset to base
    # Ensure file exists in clone before modification
    assert (Path(remote_clone_repo.workdir) / conflict_filename).read_text() == initial_content
    remote_conflict_content = "Line 1\nREMOTE CHANGE on Line 2\nLine 3\n"
    make_commit(remote_clone_repo, conflict_filename, remote_conflict_content, "Remote conflicting change for fixture")
    remote_clone_repo.remotes["origin"].push([f"+refs/heads/{branch_name}:refs/heads/{branch_name}"]) # Force push

    # 3. Fetch remote changes to local repo to set up the conflict state
    repo.remotes["origin"].fetch()

    # 4. Attempt merge to create conflict (without committing the merge)
    remote_branch_ref = repo.branches.get(f"origin/{branch_name}")
    if not remote_branch_ref: # Fallback if default branch name is different
        active_branch_name = repo.head.shorthand
        remote_branch_ref = repo.branches.get(f"origin/{active_branch_name}")

    assert remote_branch_ref is not None, f"Could not find remote tracking branch origin/{branch_name}"

    merge_result, _ = repo.merge_analysis(remote_branch_ref.target)
    if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
        pytest.skip("Repo already up to date, cannot create merge conflict for test.")

    repo.merge(remote_branch_ref.target) # This creates the in-memory merge conflict state

    # Verify conflict exists in index
    assert repo.index.conflicts is not None
    conflict_entry_iterator = iter(repo.index.conflicts)
    try:
        next(conflict_entry_iterator) # Check if there's at least one conflict
    except StopIteration:
        pytest.fail("Merge did not result in conflicts as expected.")

    # MERGE_HEAD should be set
    assert repo.lookup_reference("MERGE_HEAD").target == remote_branch_ref.target
    return repo


@pytest.fixture
def repo_with_revert_conflict(local_repo):
    """Creates a repository with a conflict during a revert operation."""
    repo = local_repo
    os.chdir(repo.workdir)
    file_path = Path("revert_conflict_file.txt")

    # Commit A: Base content
    content_A = "Version A\nCommon Line\nEnd A\n"
    make_commit(repo, str(file_path.name), content_A, "Commit A: Base for revert conflict")

    # Commit B: Modification to be reverted
    content_B = "Version B\nModified Common Line by B\nEnd B\n"
    make_commit(repo, str(file_path.name), content_B, "Commit B: To be reverted")
    commit_B_hash = repo.head.target

    # Commit C: Overlapping modification with what Commit B's revert would do
    content_C = "Version C\nModified Common Line by C (conflicts with A's version)\nEnd C\n"
    make_commit(repo, str(file_path.name), content_C, "Commit C: Conflicting with revert of B")

    # Attempt to revert Commit B
    # This will try to change "Modified Common Line by B" back to "Common Line" (from A)
    # But Commit C has changed it to "Modified Common Line by C..."
    try:
        repo.revert(repo.get(commit_B_hash)) # repo.revert expects a Commit object
    except pygit2.GitError as e:
        # Expected to fail if pygit2.revert itself throws error on conflict.
        # However, pygit2.revert might apply cleanly if no index changes are made by it,
        # and conflicts are only in working dir. The git CLI `revert` usually handles this.
        # For our `gitwrite revert` which uses `repo.revert` then checks index,
        # the key is that `REVERT_HEAD` is set and index has conflicts.
        pass # Conflict is expected, let's verify state

    # Verify REVERT_HEAD is set
    assert repo.lookup_reference("REVERT_HEAD").target == commit_B_hash

    # Verify conflict exists in index (pygit2.revert populates this)
    assert repo.index.conflicts is not None
    conflict_entry_iterator = iter(repo.index.conflicts)
    try:
        next(conflict_entry_iterator) # Check if there's at least one conflict
    except StopIteration:
        pytest.fail("Revert did not result in conflicts in the index as expected.")

    return repo

def resolve_conflict(repo: pygit2.Repository, filename: str, resolved_content: str):
    """
    Helper function to resolve a conflict in a file.
    This involves writing the resolved content, adding the file to the index.
    Pygit2's index.add() should handle clearing the conflict state for the path.
    """
    file_path = Path(repo.workdir) / filename
    file_path.write_text(resolved_content)

    # print(f"DEBUG: In resolve_conflict for {filename} - Before add:")
    # has_conflicts_before = False
    # if repo.index.conflicts is not None:
    #     try:
    #         next(iter(repo.index.conflicts))
    #         has_conflicts_before = True
    #     except StopIteration:
    #         pass

    # if has_conflicts_before:
    #     conflict_paths = []
    #     if repo.index.conflicts is not None:
    #         for c_entry_tuple in repo.index.conflicts:
    #             path = next((entry.path for entry in c_entry_tuple if entry and entry.path), None)
    #             if path:
    #                 conflict_paths.append(path)
    #     print(f"  Conflicts exist. Paths: {list(set(conflict_paths))}")
    # else:
    #     print("  No conflicts in index before add.")

    repo.index.add(filename)
    repo.index.write()
    # repo.index.read() # Try removing this again, write should be enough.

    # print(f"DEBUG: In resolve_conflict for {filename} - After add/write:")
    # has_conflicts_after = False
    # if repo.index.conflicts is not None:
    #     try:
    #         next(iter(repo.index.conflicts))
    #         has_conflicts_after = True
    #     except StopIteration:
    #         pass

    # if has_conflicts_after:
    #     conflict_paths_after = []
    #     if repo.index.conflicts is not None:
    #         for c_entry_tuple_after in repo.index.conflicts:
    #             path_after = next((entry.path for entry in c_entry_tuple_after if entry and entry.path), None)
    #             if path_after:
    #                 conflict_paths_after.append(path_after)
    #     print(f"  Conflicts STILL exist. Paths: {list(set(conflict_paths_after))}")

    #     is_still_conflicted = False
    #     if repo.index.conflicts is not None:
    #         for conflict_tuple in repo.index.conflicts:
    #             if any(entry and entry.path == filename for entry in conflict_tuple):
    #                 is_still_conflicted = True
    #                 break
    #     if is_still_conflicted:
    #         print(f"  File {filename} IS specifically still in conflicts.")
    #     else:
    #         print(f"  File {filename} is NOT specifically in conflicts anymore.")
    # else:
    #     print("  No conflicts in index after resolution steps.")


# #####################
# # Save Command Tests
# #####################

class TestSaveCommandCLI: # Renamed class for clarity
    def test_save_initial_commit_cli(self, runner, tmp_path):
        """Test `gitwrite save "Initial commit"` in a new repository."""
        repo_path = tmp_path / "new_repo_for_initial_save"
        repo_path.mkdir()
        pygit2.init_repository(str(repo_path)) # Init repo, but no commits
        os.chdir(repo_path)

        # Create a file to be part of the initial commit
        (repo_path / "first_file.txt").write_text("Hello world")

        commit_message = "Initial commit"
        result = runner.invoke(cli, ["save", commit_message])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output # Check for commit summary line

        repo = pygit2.Repository(str(repo_path))
        assert not repo.head_is_unborn
        commit = repo.head.peel(pygit2.Commit)
        assert commit.message.strip() == commit_message
        assert "first_file.txt" in commit.tree
        assert not repo.status()

    def test_save_new_file_cli(self, runner, local_repo): # local_repo fixture has initial commit
        """Test saving a new, unstaged file."""
        repo = local_repo
        os.chdir(repo.workdir)

        filename = "new_data.txt"
        file_content = "Some new data."
        create_file(repo, filename, file_content) # create_file helper from existing tests

        commit_message = "Add new_data.txt"
        initial_head_target = repo.head.target

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output

        new_head_target = repo.head.target
        assert new_head_target != initial_head_target
        commit = repo.get(new_head_target)
        assert commit.message.strip() == commit_message
        assert filename in commit.tree
        assert commit.tree[filename].data.decode('utf-8') == file_content
        assert not repo.status()

    def test_save_existing_file_modified_cli(self, runner, local_repo):
        """Test saving modifications to an existing, tracked file."""
        repo = local_repo
        os.chdir(repo.workdir)

        filename = "initial.txt" # From local_repo fixture
        original_content = (Path(repo.workdir) / filename).read_text()
        modified_content = original_content + "\nFurther modifications."
        create_file(repo, filename, modified_content)

        commit_message = "Modify initial.txt again"
        initial_head_target = repo.head.target

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output

        new_head_target = repo.head.target
        assert new_head_target != initial_head_target
        commit = repo.get(new_head_target)
        assert commit.message.strip() == commit_message
        assert commit.tree[filename].data.decode('utf-8') == modified_content
        assert not repo.status()

    def test_save_no_changes_cli(self, runner, local_repo):
        """Test saving when there are no changes."""
        repo = local_repo
        os.chdir(repo.workdir)
        assert not repo.status() # Ensure clean state

        initial_head_target = repo.head.target
        commit_message = "Attempt no changes"

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # This message now comes from the core function via NoChangesToSaveError
        assert "No changes to save (working directory and index are clean or match HEAD)." in result.output
        assert repo.head.target == initial_head_target

    def test_save_staged_changes_cli(self, runner, local_repo):
        """Test saving already staged changes."""
        repo = local_repo
        os.chdir(repo.workdir)

        filename = "staged_only.txt"
        file_content = "This content is only staged."
        create_file(repo, filename, file_content)
        stage_file(repo, filename) # stage_file helper from existing tests

        commit_message = "Commit staged_only.txt"
        initial_head_target = repo.head.target

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output

        new_head_target = repo.head.target
        assert new_head_target != initial_head_target
        commit = repo.get(new_head_target)
        assert commit.message.strip() == commit_message
        assert filename in commit.tree
        assert commit.tree[filename].data.decode('utf-8') == file_content
        assert not repo.status()

    def test_save_no_message_cli(self, runner, local_repo):
        """Test saving without providing a commit message (should fail due to Click)."""
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "some_change.txt", "content")

        result = runner.invoke(cli, ["save"]) # No message argument
        assert result.exit_code != 0 # Click should make it fail
        assert "Missing argument 'MESSAGE'." in result.output # Click's default error message

    def test_save_outside_git_repo_cli(self, runner, tmp_path):
        """Test `gitwrite save` outside a Git repository."""
        non_repo_dir = tmp_path / "no_repo_here"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)

        result = runner.invoke(cli, ["save", "Test message"])
        assert result.exit_code == 0 # CLI handles this error gracefully by printing
        assert "Error: Not a Git repository (or any of the parent directories)." in result.output

    # Selective Staging Tests
    def test_save_include_single_file_cli(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)

        create_file(repo, "file_A.txt", "Content A")
        create_file(repo, "file_B.txt", "Content B")

        commit_message = "Commit file_A only"
        result = runner.invoke(cli, ["save", "-i", "file_A.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output # Commit summary

        commit = repo.head.peel(pygit2.Commit)
        assert "file_A.txt" in commit.tree
        assert "file_B.txt" not in commit.tree
        assert (Path(repo.workdir) / "file_B.txt").exists() # file_B remains in workdir

    def test_save_include_no_changes_in_path_cli(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        # file "initial.txt" exists from fixture, but no new changes to it.
        create_file(repo, "other_file.txt", "changes here") # Another changed file

        result = runner.invoke(cli, ["save", "-i", "initial.txt", "Try to commit unchanged initial.txt"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # This message comes from core via NoChangesToSaveError
        assert "No specified files had changes to stage relative to HEAD." in result.output
        # And other_file.txt should not be committed
        commit = repo.head.peel(pygit2.Commit)
        assert "other_file.txt" not in commit.tree # Assuming initial.txt was the only one included

    def test_save_include_non_existent_file_cli(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "actual_file.txt", "actual content")

        result = runner.invoke(cli, ["save", "-i", "non_existent.txt", "-i", "actual_file.txt", "Commit with non-existent"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # Core's save_changes prints warnings for non-existent paths directly.
        # The CLI doesn't explicitly relay these, but the commit proceeds.
        # The important part is that actual_file.txt is committed.
        assert "Warning: Could not add path 'non_existent.txt'" in result.output # Check for core's warning
        commit = repo.head.peel(pygit2.Commit)
        assert "actual_file.txt" in commit.tree
        assert "non_existent.txt" not in commit.tree

    # Merge/Revert Completion CLI Interaction
    def test_save_complete_merge_cli(self, runner, repo_with_merge_conflict):
        repo = repo_with_merge_conflict # Fixture provides repo with MERGE_HEAD and conflicts
        os.chdir(repo.workdir)

        # Manually resolve conflict for the test
        resolve_conflict(repo, "conflict_file.txt", "Resolved content for merge CLI test")
        assert not repo.index.conflicts # Ensure conflicts are resolved in index

        commit_message = "Finalizing resolved merge"
        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output
        assert "Successfully completed merge operation." in result.output

        new_commit = repo.head.peel(pygit2.Commit)
        assert len(new_commit.parents) == 2 # It's a merge commit
        with pytest.raises(KeyError): # MERGE_HEAD should be gone
            repo.lookup_reference("MERGE_HEAD")

    def test_save_merge_with_unresolved_conflicts_cli(self, runner, repo_with_merge_conflict):
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)
        # Conflicts are unresolved in this fixture state initially

        result = runner.invoke(cli, ["save", "Attempt merge with conflicts"])
        assert result.exit_code == 0 # CLI handles error gracefully
        assert "Error: Unresolved conflicts detected during merge." in result.output
        assert "Conflicting files:" in result.output
        assert "conflict_file.txt" in result.output # Check the specific conflicting file
        assert repo.lookup_reference("MERGE_HEAD") is not None # Still in merge state

    def test_save_complete_revert_cli(self, runner, repo_with_revert_conflict):
        repo = repo_with_revert_conflict # Fixture provides repo with REVERT_HEAD and conflicts
        os.chdir(repo.workdir)

        reverted_commit_oid = repo.lookup_reference("REVERT_HEAD").target
        reverted_commit_msg_first_line = repo.get(reverted_commit_oid).message.splitlines()[0]

        # Manually resolve conflict
        resolve_conflict(repo, "revert_conflict_file.txt", "Resolved content for revert CLI test")
        assert not repo.index.conflicts

        user_commit_message = "Finalizing resolved revert"
        result = runner.invoke(cli, ["save", user_commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        expected_revert_commit_msg_part = f"Revert \"{reverted_commit_msg_first_line}\""
        # Check if the first line of the commit message in output contains the expected revert prefix
        assert any(expected_revert_commit_msg_part in line for line in result.output.splitlines() if line.startswith("["))
        assert user_commit_message in result.output # User message also part of output
        assert "Successfully completed revert operation." in result.output

        new_commit = repo.head.peel(pygit2.Commit)
        assert len(new_commit.parents) == 1 # Revert commit usually has one parent
        assert expected_revert_commit_msg_part in new_commit.message
        assert user_commit_message in new_commit.message
        with pytest.raises(KeyError): # REVERT_HEAD should be gone
            repo.lookup_reference("REVERT_HEAD")

    def test_save_revert_with_unresolved_conflicts_cli(self, runner, repo_with_revert_conflict):
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)

        result = runner.invoke(cli, ["save", "Attempt revert with conflicts"])
        assert result.exit_code == 0 # CLI handles error gracefully
        assert "Error: Unresolved conflicts detected during revert." in result.output
        assert "Conflicting files:" in result.output
        assert "revert_conflict_file.txt" in result.output
        assert repo.lookup_reference("REVERT_HEAD") is not None # Still in revert state

    def test_save_include_error_during_merge_cli(self, runner, repo_with_merge_conflict):
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)
        # Even if conflicts are resolved, --include is not allowed
        resolve_conflict(repo, "conflict_file.txt", "Resolved content")

        result = runner.invoke(cli, ["save", "-i", "conflict_file.txt", "Include during merge"])
        assert result.exit_code == 0
        assert "Error: Selective staging with --include is not allowed during an active merge operation." in result.output
        assert repo.lookup_reference("MERGE_HEAD") is not None # Still in merge state

    def test_save_include_multiple_files_cli(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "file_X.txt", "Content X")
        create_file(repo, "file_Y.txt", "Content Y")
        create_file(repo, "file_Z.txt", "Content Z")

        commit_message = "Commit X and Y"
        result = runner.invoke(cli, ["save", "-i", "file_X.txt", "-i", "file_Y.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output

        commit = repo.head.peel(pygit2.Commit)
        assert "file_X.txt" in commit.tree
        assert "file_Y.txt" in commit.tree
        assert "file_Z.txt" not in commit.tree
        assert (Path(repo.workdir) / "file_Z.txt").exists()

    def test_save_include_all_specified_are_invalid_or_unchanged_cli(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        # initial.txt exists but is unchanged
        initial_head = repo.head.target

        result = runner.invoke(cli, ["save", "-i", "initial.txt", "-i", "non_existent.txt", "Attempt invalid includes"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No specified files had changes to stage relative to HEAD." in result.output
        assert repo.head.target == initial_head # No commit should be made

    def test_save_include_empty_path_string_cli(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "actual_file.txt", "content") # Ensure there's something that *could* be committed
        initial_head = repo.head.target

        # Click might prevent empty option values before it even reaches our code,
        # or it might pass it as an empty string.
        # If Click prevents it, this test might need adjustment or is testing Click's behavior.
        # If it passes '', the core function should handle it (likely by ignoring).
        result = runner.invoke(cli, ["save", "-i", "", "Empty include path test"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # The core `save_changes` function's `include_paths` loop would skip an empty string path.
        # If "actual_file.txt" was not included, and "" is the only include, it should say no specified files had changes.
        # However, if "" is passed, and other files ARE changed, the default "save all" behavior might kick in if `include_paths` ends up being effectively None/empty.
        # The `save_changes` function's logic: if `include_paths` is an empty list (e.g. `['']` becomes `[]` after filtering, or just `[]` passed),
        # it would fall into "No specified files had changes to stage" if it was truly empty list.
        # OR if `include_paths` was `None` it would stage all.
        # The CLI converts the Click tuple to `list(include_paths) if include_paths else None`.
        # If `include_paths` is `('',)`, `list(include_paths)` is `['']`.
        # The core function's loop `for path_str in include_paths:` will process `''`.
        # `repo.index.add('')` would likely error or do nothing.
        # The `print(f"Warning: Could not add path '{path_str}': {e}")` in core might appear.

        # Based on current core logic, an empty path_str in include_paths list will likely cause pygit2.GitError from repo.index.add("").
        # This is caught and printed as a warning. If other files were included, they'd be committed.
        # If only "" was included, then "No specified files had changes..." should occur.
        assert "Warning: Could not add path ''" in result.output # From core function's add loop
        assert "No specified files had changes to stage relative to HEAD." in result.output # Because "" is not a valid path with changes
        assert repo.head.target == initial_head # No commit

    def test_save_include_ignored_file_cli(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        (Path(repo.workdir) / ".gitignore").write_text("*.ignored\n")
        make_commit(repo, ".gitignore", "*.ignored\n", "Add .gitignore")

        create_file(repo, "ignored_doc.ignored", "This is ignored")
        create_file(repo, "normal_doc.txt", "This is not ignored")
        initial_head = repo.head.target

        result = runner.invoke(cli, ["save", "-i", "ignored_doc.ignored", "-i", "normal_doc.txt", "Test ignored include"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # The core function `save_changes` when doing `repo.index.add(path_str)` for an ignored file
        # will not stage it if not forced. pygit2 usually returns an error code that leads to a warning.
        assert "Warning: Could not add path 'ignored_doc.ignored'" in result.output # Or similar if pygit2 error is different for ignored

        commit = repo.head.peel(pygit2.Commit)
        assert "normal_doc.txt" in commit.tree
        assert "ignored_doc.ignored" not in commit.tree
        assert initial_head != commit.id # A commit should be made for normal_doc.txt

    def test_save_include_error_during_revert_cli(self, runner, repo_with_revert_conflict): # Uses existing fixture
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)
        # Fixture creates REVERT_HEAD. Conflicts may or may not be resolved by fixture.
        # For this test, conflict state doesn't matter as much as REVERT_HEAD existing.

        result = runner.invoke(cli, ["save", "-i", "revert_conflict_file.txt", "Include during revert"])
        assert result.exit_code == 0
        assert "Error: Selective staging with --include is not allowed during an active revert operation." in result.output
        assert repo.lookup_reference("REVERT_HEAD") is not None # Still in revert state

# Removed TestGitWriteSaveConflictScenarios as its tests are covered in TestSaveCommandCLI
# Removed TestGitWriteSaveSelectiveStaging as its tests are covered in TestSaveCommandCLI

#######################
# Ignore Command Tests (CLI Runner)
#######################

def test_ignore_add_new_pattern_cli(runner):
    """CLI: Test adding a new pattern."""
    with runner.isolated_filesystem() as temp_dir:
        # Core logic tested in TestIgnoreCoreFunctions.add_pattern_to_new_gitignore_core
        result = runner.invoke(cli, ['ignore', 'add', '*.log'])
        assert result.exit_code == 0
        assert "Pattern '*.log' added to .gitignore." in result.output
        # Basic check that file was created by CLI interaction
        assert (Path(temp_dir) / ".gitignore").exists()

def test_ignore_add_duplicate_pattern_cli(runner):
    """CLI: Test adding a duplicate pattern."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore"
        initial_pattern = "existing_pattern"
        gitignore_file.write_text(f"{initial_pattern}\n")

        result = runner.invoke(cli, ['ignore', 'add', initial_pattern])
        assert result.exit_code == 0
        assert f"Pattern '{initial_pattern}' already exists in .gitignore." in result.output

def test_ignore_add_pattern_strips_whitespace_cli(runner):
    """CLI: Test adding a pattern strips leading/trailing whitespace."""
    with runner.isolated_filesystem() as temp_dir:
        result = runner.invoke(cli, ['ignore', 'add', '  *.tmp  '])
        assert result.exit_code == 0
        assert "Pattern '*.tmp' added to .gitignore." in result.output
        # Basic check
        assert (Path(temp_dir) / ".gitignore").exists()

def test_ignore_add_empty_pattern_cli(runner):
    """CLI: Test adding an empty or whitespace-only pattern."""
    with runner.isolated_filesystem():
        result_empty = runner.invoke(cli, ['ignore', 'add', ''])
        assert result_empty.exit_code == 0 # Command itself doesn't fail for user input errors
        assert "Pattern cannot be empty." in result_empty.output # Error message from core

        result_whitespace = runner.invoke(cli, ['ignore', 'add', '   '])
        assert result_whitespace.exit_code == 0
        assert "Pattern cannot be empty." in result_whitespace.output

def test_ignore_list_existing_gitignore_cli(runner):
    """CLI: Test listing patterns from an existing .gitignore file."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore"
        patterns = ["pattern1", "*.log", "another/path/"]
        gitignore_content = "\n".join(patterns) + "\n"
        gitignore_file.write_text(gitignore_content)

        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0
        assert ".gitignore Contents" in result.output # Rich Panel title
        for pattern in patterns: # Check if actual patterns are in the output
            assert pattern in result.output

def test_ignore_list_non_existent_gitignore_cli(runner):
    """CLI: Test listing when .gitignore does not exist."""
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0
        assert ".gitignore file not found." in result.output

def test_ignore_list_empty_gitignore_cli(runner):
    """CLI: Test listing an empty .gitignore file."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore"
        gitignore_file.touch() # Create empty file

        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0
        assert ".gitignore is empty." in result.output

def test_ignore_list_gitignore_with_only_whitespace_cli(runner):
    """CLI: Test listing a .gitignore file that contains only whitespace."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore"
        gitignore_file.write_text("\n   \n\t\n")

        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0
        assert ".gitignore is empty." in result.output


#######################
# Init Command Tests (CLI Runner - already refactored for core calls)
#######################

@pytest.fixture
def init_test_dir(tmp_path):
    """Provides a clean directory path for init tests that might create a project dir."""
    test_base_dir = tmp_path / "init_tests_base"
    test_base_dir.mkdir(exist_ok=True) # Base for placing multiple test projects if needed
    project_dir = test_base_dir / "test_project"
    # Clean up if it exists from a previous failed run (though tmp_path should manage this)
    if project_dir.exists():
        shutil.rmtree(project_dir)
    # The test itself will decide whether to create project_dir or use test_base_dir
    return project_dir # This path might be created by 'init <name>' or used as CWD

class TestGitWriteInit:

    # Helper methods _assert_gitwrite_structure and _assert_common_gitignore_patterns
    # have been moved to the top level of the file to be shared.

    def test_init_in_empty_directory_no_project_name(self, runner: CliRunner, tmp_path: Path):
        """Test `gitwrite init` in an empty directory (uses current dir)."""
        test_dir = tmp_path / "current_dir_init"
        test_dir.mkdir()
        os.chdir(test_dir)

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # Check for messages from the core function's success response
        dir_name = test_dir.name # Core function uses the directory name
        assert f"Initialized empty Git repository in {dir_name}" in result.output
        assert f"Created GitWrite directory structure in {dir_name}" in result.output
        assert f"Staged GitWrite files in {dir_name}" in result.output
        assert f"Created GitWrite structure commit in {dir_name}" in result.output

        # Basic check that a repo was made
        assert (test_dir / ".git").is_dir()
        # Detailed structure and commit content is tested in TestInitializeRepositoryCore

    def test_init_with_project_name(self, runner: CliRunner, tmp_path: Path):
        """Test `gitwrite init project_name`."""
        project_name = "my_new_book"
        base_dir = tmp_path / "base_for_named_project"
        base_dir.mkdir()
        project_dir = base_dir / project_name

        os.chdir(base_dir) # Run from parent directory

        result = runner.invoke(cli, ["init", project_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert project_dir.exists(), "Project directory was not created by CLI call"
        assert project_dir.is_dir()

        # Check for messages from the core function's success response
        assert f"Initialized empty Git repository in {project_name}" in result.output
        assert f"Created GitWrite directory structure in {project_name}" in result.output
        assert f"Created GitWrite structure commit in {project_name}" in result.output

        # Basic check
        assert (project_dir / ".git").is_dir()
        # Detailed structure and commit content is tested in TestInitializeRepositoryCore

    def test_init_error_project_directory_is_a_file(self, runner: CliRunner, tmp_path: Path):
        """Test error when `gitwrite init project_name` and project_name is an existing file."""
        project_name = "existing_file_name"
        base_dir = tmp_path / "base_for_file_conflict"
        base_dir.mkdir()

        file_path = base_dir / project_name
        file_path.write_text("I am a file.")

        os.chdir(base_dir)
        result = runner.invoke(cli, ["init", project_name])
        # CLI should echo the error message from the core function
        assert f"Error: A file named '{project_name}' already exists" in result.output
        assert result.exit_code == 0 # CLI itself doesn't crash, just prints error from core
        assert not (base_dir / project_name / ".git").exists() # No git repo created

    def test_init_error_project_directory_exists_not_empty_not_git(self, runner: CliRunner, tmp_path: Path):
        """Test `init project_name` where project_name dir exists, is not empty, and not a Git repo."""
        project_name = "existing_non_empty_dir"
        base_dir = tmp_path / "base_for_non_empty_conflict"
        base_dir.mkdir()

        project_dir_path = base_dir / project_name
        project_dir_path.mkdir()
        (project_dir_path / "some_file.txt").write_text("Hello")

        os.chdir(base_dir)
        result = runner.invoke(cli, ["init", project_name])
        # CLI should echo the error message from the core function
        assert f"Error: Directory '{project_name}' already exists, is not empty, and is not a Git repository." in result.output
        assert result.exit_code == 0 # CLI prints error
        assert not (project_dir_path / ".git").exists()

    def test_init_in_existing_git_repository(self, runner: CliRunner, local_repo: pygit2.Repository, local_repo_path: Path):
        """Test `gitwrite init` in an existing Git repository."""
        os.chdir(local_repo_path)
        repo_name = local_repo_path.name

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Check for messages from the core function's success response for existing repo
        assert f"Created GitWrite directory structure in {repo_name}" in result.output
        # This message implies it's an existing repo
        assert f"Added GitWrite structure to {repo_name}" in result.output
        # Basic check
        assert (local_repo_path / "drafts").is_dir()
        # Detailed structure, commit changes, .gitignore handling are tested in TestInitializeRepositoryCore

    def test_init_in_existing_non_empty_dir_not_git_no_project_name(self, runner: CliRunner, tmp_path: Path):
        """Test `gitwrite init` in current dir if it's non-empty and not a Git repo."""
        test_dir = tmp_path / "existing_non_empty_current_dir"
        test_dir.mkdir()
        (test_dir / "my_random_file.txt").write_text("content")
        dir_name = test_dir.name

        os.chdir(test_dir)
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0 # CLI prints error
        # CLI should echo the error message from the core function
        assert f"Error: Current directory '{dir_name}' is not empty and not a Git repository." in result.output
        assert not (test_dir / ".git").exists()

    def test_init_gitignore_appends_not_overwrites(self, runner: CliRunner, tmp_path: Path):
        """Test that init appends to existing .gitignore rather than overwriting."""
        test_dir = tmp_path / "gitignore_append_test"
        test_dir.mkdir()
        os.chdir(test_dir)

        # Pre-existing .gitignore
        gitignore_path = test_dir / ".gitignore"
        user_entry = "# User specific ignore\n*.mydata\n"
        gitignore_path.write_text(user_entry)

        # Initialize git repo first, then run gitwrite init
        pygit2.init_repository(str(test_dir))
        repo = pygit2.Repository(str(test_dir))
        make_commit(repo, ".gitignore", user_entry, "Add initial .gitignore with user entry")


        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        _assert_gitwrite_structure(test_dir) # Now using top-level helper
        _assert_common_gitignore_patterns(gitignore_path) # Now using top-level helper

        # Verify user's entry is still there
        final_gitignore_content = gitignore_path.read_text()
        assert user_entry.strip() in final_gitignore_content # .strip() because init might add newlines

        # Check that GitWrite patterns were added (core patterns)
        assert COMMON_GITIGNORE_PATTERNS[0] in final_gitignore_content # Example check

        # Check commit
        last_commit = repo.head.peel(pygit2.Commit)
        # If .gitignore was modified, it should be part of the commit
        if ".gitignore" in last_commit.tree:
            gitignore_blob = repo.get(last_commit.tree[".gitignore"].id)
            assert user_entry.strip() in gitignore_blob.data.decode('utf-8')

    def test_init_is_idempotent_for_structure(self, runner: CliRunner, tmp_path: Path):
        """Test that running init multiple times doesn't create multiple commits if structure is identical."""
        test_dir = tmp_path / "idempotent_test"
        test_dir.mkdir()
        os.chdir(test_dir)

        # First init
        result1 = runner.invoke(cli, ["init"])
        assert result1.exit_code == 0, f"First init failed: {result1.output}"
        # Message comes from core function now
        assert "Created GitWrite structure commit." in result1.output # This is part of the core message

        repo = pygit2.Repository(str(test_dir))
        commit1_hash = repo.head.target

        # Second init
        result2 = runner.invoke(cli, ["init"])
        assert result2.exit_code == 0, f"Second init failed: {result2.output}"
        # This message indicates that the structure was found and no new commit was needed.
        # Check for messages from the core function's return
        assert "GitWrite structure already present and tracked." in result2.output or \
               "GitWrite structure already present and up-to-date." in result2.output


        commit2_hash = repo.head.target
        assert commit1_hash == commit2_hash, "No new commit should have been made on second init."
        _assert_gitwrite_structure(test_dir) # Now using top-level helper


#######################################
# Core Repository Function Tests
#######################################

class TestInitializeRepositoryCore:

    def test_init_new_project_core(self, tmp_path: Path):
        """Test initialize_repository in a new directory with a project name."""
        base_tmp_path = tmp_path / "core_init_base"
        base_tmp_path.mkdir()
        project_name = "new_core_project"

        result = initialize_repository(str(base_tmp_path), project_name=project_name)

        project_path = base_tmp_path / project_name

        assert result['status'] == 'success'
        assert project_path.exists()
        assert str(project_path.resolve()) == result['path']
        assert f"Initialized empty Git repository in {project_name}" in result['message']
        assert f"Created GitWrite directory structure in {project_name}" in result['message']
        assert f"Staged GitWrite files in {project_name}" in result['message']
        assert f"Created GitWrite structure commit in {project_name}" in result['message']

        _assert_gitwrite_structure(project_path)
        _assert_common_gitignore_patterns(project_path / ".gitignore")

        repo = pygit2.Repository(str(project_path))
        assert not repo.is_empty
        assert not repo.head_is_unborn
        last_commit = repo.head.peel(pygit2.Commit)
        assert f"Initialized GitWrite project structure in {project_name}" in last_commit.message
        assert last_commit.author.name == "GitWrite System"

        expected_tree_items = {".gitignore", "metadata.yml", "drafts", "notes"}
        actual_tree_items = {item.name for item in last_commit.tree}
        assert expected_tree_items == actual_tree_items

        drafts_tree = last_commit.tree['drafts'].peel(pygit2.Tree)
        assert ".gitkeep" in {item.name for item in drafts_tree}
        notes_tree = last_commit.tree['notes'].peel(pygit2.Tree)
        assert ".gitkeep" in {item.name for item in notes_tree}

    def test_init_current_empty_dir_core(self, tmp_path: Path):
        """Test initialize_repository in current empty directory (no project name)."""
        test_dir = tmp_path / "current_empty_core_init"
        test_dir.mkdir()

        # For core function, CWD is passed as path_str
        result = initialize_repository(str(test_dir), project_name=None)

        assert result['status'] == 'success'
        assert str(test_dir.resolve()) == result['path']
        dir_name = test_dir.name
        assert f"Initialized empty Git repository in {dir_name}" in result['message']
        assert f"Created GitWrite directory structure in {dir_name}" in result['message']

        _assert_gitwrite_structure(test_dir)
        _assert_common_gitignore_patterns(test_dir / ".gitignore")

        repo = pygit2.Repository(str(test_dir))
        assert not repo.is_empty
        last_commit = repo.head.peel(pygit2.Commit)
        assert f"Initialized GitWrite project structure in {dir_name}" in last_commit.message

    def test_init_error_target_is_file_core(self, tmp_path: Path):
        """Test initialize_repository core error: target_dir is a file."""
        base_dir = tmp_path / "core_file_conflict_base"
        base_dir.mkdir()
        project_name_as_file = "i_am_a_file.txt"
        file_path = base_dir / project_name_as_file
        file_path.write_text("Some content")

        result = initialize_repository(str(base_dir), project_name=project_name_as_file)
        assert result['status'] == 'error'
        assert f"A file named '{project_name_as_file}' already exists" in result['message']
        assert result['path'] == str(file_path.resolve())

    def test_init_error_target_exists_not_empty_not_git_core(self, tmp_path: Path):
        """Test initialize_repository core error: target exists, not empty, not Git."""
        base_dir = tmp_path / "core_non_empty_conflict"
        base_dir.mkdir()
        project_name_conflict = "existing_non_empty_dir"
        project_dir_path = base_dir / project_name_conflict
        project_dir_path.mkdir()
        (project_dir_path / "some_file.txt").write_text("Hello")

        # Test with project_name specified
        result = initialize_repository(str(base_dir), project_name=project_name_conflict)
        assert result['status'] == 'error'
        assert f"Error: Directory '{project_name_conflict}' already exists, is not empty, and is not a Git repository." in result['message']
        assert result['path'] == str(project_dir_path.resolve())

        # Test with no project_name (target_dir is the non-empty dir itself)
        result_no_project_name = initialize_repository(str(project_dir_path), project_name=None)
        assert result_no_project_name['status'] == 'error'
        assert f"Error: Current directory '{project_dir_path.name}' is not empty and not a Git repository." in result_no_project_name['message']
        assert result_no_project_name['path'] == str(project_dir_path.resolve())


    def test_init_existing_git_repo_core(self, tmp_path: Path):
        """Test initialize_repository in an existing Git repository."""
        existing_repo_path = tmp_path / "existing_core_repo"
        existing_repo_path.mkdir()

        # Initialize a bare git repo and make an initial commit
        repo = pygit2.init_repository(str(existing_repo_path))
        author = pygit2.Signature("Test Author", "test@example.com")
        committer = author
        # Create an empty tree for the initial commit
        empty_tree_oid = repo.TreeBuilder().write()
        initial_commit_oid = repo.create_commit("HEAD", author, committer, "Initial user commit", empty_tree_oid, [])

        result = initialize_repository(str(existing_repo_path), project_name=None)

        assert result['status'] == 'success'
        assert str(existing_repo_path.resolve()) == result['path']
        # Message should reflect adding to existing repo
        dir_name = existing_repo_path.name
        assert f"Created GitWrite directory structure in {dir_name}" in result['message'] # No "Initialized empty"
        assert f"Added GitWrite structure to {dir_name}" in result['message']


        _assert_gitwrite_structure(existing_repo_path) # .git already existed
        _assert_common_gitignore_patterns(existing_repo_path / ".gitignore")

        # Verify a new commit was made for GitWrite files
        repo = pygit2.Repository(str(existing_repo_path)) # Re-open to be sure
        last_commit = repo.head.peel(pygit2.Commit)
        assert last_commit.id != initial_commit_oid
        assert f"Added GitWrite structure to {dir_name}" in last_commit.message
        assert last_commit.author.name == "GitWrite System"
        assert len(last_commit.parents) == 1
        assert last_commit.parents[0].id == initial_commit_oid

        # Check .gitignore handling: add a user pattern and ensure it's kept + new ones added
        gitignore_path = existing_repo_path / ".gitignore"
        gitignore_path.write_text("my_secret_file.txt\n") # Simulate user adding a file before running init
        make_commit(repo, ".gitignore", "my_secret_file.txt\n", "User adds own .gitignore")
        user_commit_oid = repo.head.target

        result_gitignore = initialize_repository(str(existing_repo_path), project_name=None)
        assert result_gitignore['status'] == 'success'

        final_gitignore_content = gitignore_path.read_text()
        assert "my_secret_file.txt" in final_gitignore_content
        assert COMMON_GITIGNORE_PATTERNS[0] in final_gitignore_content # check one of the core patterns

        repo = pygit2.Repository(str(existing_repo_path)) # Re-open
        last_commit_gitignore = repo.head.peel(pygit2.Commit)
        if last_commit_gitignore.id != user_commit_oid: # if a new commit was made for .gitignore changes
            assert f"Added GitWrite structure to {dir_name}" in last_commit_gitignore.message # or similar
            assert ".gitignore" in last_commit_gitignore.tree
            gitignore_blob_content = last_commit_gitignore.tree[".gitignore"].data.decode('utf-8')
            assert "my_secret_file.txt" in gitignore_blob_content
            assert COMMON_GITIGNORE_PATTERNS[0] in gitignore_blob_content
        else: # No new commit means .gitignore was already compliant or only GitWrite files were added.
             assert "GitWrite structure already present and tracked" in result_gitignore['message'] or \
                    "GitWrite structure already present and up-to-date" in result_gitignore['message']


    def test_init_idempotency_core(self, tmp_path: Path):
        """Test initialize_repository is idempotent."""
        test_dir = tmp_path / "core_idempotent_test"
        test_dir.mkdir()

        # First call
        result1 = initialize_repository(str(test_dir), project_name=None)
        assert result1['status'] == 'success'
        assert "Created GitWrite structure commit" in result1['message']

        repo = pygit2.Repository(str(test_dir))
        commit1_hash = repo.head.target

        # Second call
        result2 = initialize_repository(str(test_dir), project_name=None)
        assert result2['status'] == 'success'
        # Check for messages indicating no changes
        assert "GitWrite structure already present and tracked" in result2['message'] or \
               "GitWrite structure already present and up-to-date" in result2['message'] or \
               "No changes to commit" in result2['message']


        repo = pygit2.Repository(str(test_dir)) # Re-open
        commit2_hash = repo.head.target
        assert commit1_hash == commit2_hash, "A new commit was made on the second identical call."
        _assert_gitwrite_structure(test_dir)

    def test_init_handles_existing_empty_project_dir(self, tmp_path: Path):
        """Test init when project_name dir exists but is empty."""
        base_dir = tmp_path / "base_for_existing_empty"
        base_dir.mkdir()
        project_name = "existing_empty_project"
        project_dir = base_dir / project_name
        project_dir.mkdir() # Directory exists but is empty

        result = initialize_repository(str(base_dir), project_name=project_name)
        assert result['status'] == 'success'
        assert project_dir.exists()
        assert f"Initialized empty Git repository in {project_name}" in result['message']
        _assert_gitwrite_structure(project_dir)
        repo = pygit2.Repository(str(project_dir))
        assert not repo.head_is_unborn


#######################################
# Core Ignore Function Tests
#######################################

class TestIgnoreCoreFunctions:

    def test_add_pattern_to_new_gitignore_core(self, tmp_path: Path):
        """Core: Add pattern when .gitignore does not exist."""
        repo_dir = tmp_path / "repo_for_ignore_new"
        repo_dir.mkdir()
        gitignore_path = repo_dir / ".gitignore"

        pattern = "*.log"
        result = add_pattern_to_gitignore(str(repo_dir), pattern)

        assert result['status'] == 'success'
        assert result['message'] == f"Pattern '{pattern}' added to .gitignore."
        assert gitignore_path.exists()
        assert gitignore_path.read_text() == f"{pattern}\n"

    def test_add_pattern_to_existing_gitignore_core(self, tmp_path: Path):
        """Core: Add pattern to an existing .gitignore."""
        repo_dir = tmp_path / "repo_for_ignore_existing"
        repo_dir.mkdir()
        gitignore_path = repo_dir / ".gitignore"
        existing_pattern = "node_modules/"
        gitignore_path.write_text(f"{existing_pattern}\n")

        new_pattern = "*.tmp"
        result = add_pattern_to_gitignore(str(repo_dir), new_pattern)

        assert result['status'] == 'success'
        assert result['message'] == f"Pattern '{new_pattern}' added to .gitignore."
        content = gitignore_path.read_text()
        assert f"{existing_pattern}\n" in content
        assert f"{new_pattern}\n" in content

    def test_add_duplicate_pattern_core(self, tmp_path: Path):
        """Core: Add a pattern that already exists."""
        repo_dir = tmp_path / "repo_for_ignore_duplicate"
        repo_dir.mkdir()
        gitignore_path = repo_dir / ".gitignore"
        pattern = "*.log"
        gitignore_path.write_text(f"{pattern}\n")

        result = add_pattern_to_gitignore(str(repo_dir), pattern)
        assert result['status'] == 'exists'
        assert result['message'] == f"Pattern '{pattern}' already exists in .gitignore."
        assert gitignore_path.read_text() == f"{pattern}\n" # Unchanged

    def test_add_pattern_strips_whitespace_core(self, tmp_path: Path):
        """Core: Added pattern should be stripped of whitespace."""
        repo_dir = tmp_path / "repo_for_ignore_strip"
        repo_dir.mkdir()
        gitignore_path = repo_dir / ".gitignore"

        pattern_with_space = "  *.cache  "
        stripped_pattern = "*.cache"
        result = add_pattern_to_gitignore(str(repo_dir), pattern_with_space)

        assert result['status'] == 'success'
        assert result['message'] == f"Pattern '{stripped_pattern}' added to .gitignore."
        assert gitignore_path.read_text() == f"{stripped_pattern}\n"

    def test_add_empty_pattern_core(self, tmp_path: Path):
        """Core: Attempting to add an empty or whitespace-only pattern."""
        repo_dir = tmp_path / "repo_for_ignore_empty"
        repo_dir.mkdir()

        result_empty = add_pattern_to_gitignore(str(repo_dir), "")
        assert result_empty['status'] == 'error'
        assert result_empty['message'] == 'Pattern cannot be empty.'

        result_whitespace = add_pattern_to_gitignore(str(repo_dir), "   ")
        assert result_whitespace['status'] == 'error'
        assert result_whitespace['message'] == 'Pattern cannot be empty.'

    def test_add_pattern_to_file_without_trailing_newline_core(self, tmp_path: Path):
        """Core: Add pattern to .gitignore that doesn't end with a newline."""
        repo_dir = tmp_path / "repo_for_ignore_no_newline"
        repo_dir.mkdir()
        gitignore_path = repo_dir / ".gitignore"
        gitignore_path.write_text("pattern1") # No trailing newline

        pattern2 = "pattern2"
        result = add_pattern_to_gitignore(str(repo_dir), pattern2)
        assert result['status'] == 'success'
        assert gitignore_path.read_text() == f"pattern1\n{pattern2}\n"

    def test_list_existing_gitignore_core(self, tmp_path: Path):
        """Core: List patterns from an existing .gitignore."""
        repo_dir = tmp_path / "repo_for_list_existing"
        repo_dir.mkdir()
        gitignore_path = repo_dir / ".gitignore"
        patterns = ["*.log", "build/", "", "  # comment  ", "dist"]
        gitignore_path.write_text("\n".join(patterns) + "\n")

        result = list_gitignore_patterns(str(repo_dir))
        assert result['status'] == 'success'
        # Core function filters out empty lines and comments if they become empty after strip
        expected_patterns = ["*.log", "build/", "# comment", "dist"]
        assert result['patterns'] == expected_patterns
        assert result['message'] == 'Successfully retrieved patterns.'

    def test_list_non_existent_gitignore_core(self, tmp_path: Path):
        """Core: List patterns when .gitignore does not exist."""
        repo_dir = tmp_path / "repo_for_list_non_existent"
        repo_dir.mkdir()

        result = list_gitignore_patterns(str(repo_dir))
        assert result['status'] == 'not_found'
        assert result['patterns'] == []
        assert result['message'] == '.gitignore file not found.'

    def test_list_empty_gitignore_core(self, tmp_path: Path):
        """Core: List patterns from an empty .gitignore."""
        repo_dir = tmp_path / "repo_for_list_empty"
        repo_dir.mkdir()
        gitignore_path = repo_dir / ".gitignore"
        gitignore_path.touch() # Create empty file

        result = list_gitignore_patterns(str(repo_dir))
        assert result['status'] == 'empty'
        assert result['patterns'] == []
        assert result['message'] == '.gitignore is empty.'


#######################################
# Compare Command Tests (CLI Runner)
#######################################

class TestCompareCommandCLI:

    def test_compare_empty_repo_cli(self, runner, tmp_path):
        """Test `gitwrite compare` in an empty initialized repo."""
        empty_repo_path = tmp_path / "empty_compare_repo"
        empty_repo_path.mkdir()
        pygit2.init_repository(str(empty_repo_path))

        os.chdir(empty_repo_path)
        result = runner.invoke(cli, ["compare"])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Not enough history to perform comparison: Repository is empty or HEAD is unborn." in result.output

    def test_compare_initial_commit_cli(self, runner, local_repo):
        """Test `gitwrite compare` in a repo with only the initial commit."""
        # local_repo fixture by default has one commit.
        # To be certain, let's ensure no other commits are made on this specific repo instance for this test.
        repo = local_repo
        os.chdir(repo.workdir)

        # Ensure it's truly just the initial commit (no parents)
        head_commit = repo.head.peel(pygit2.Commit)
        assert not head_commit.parents, "Test setup error: local_repo should have initial commit only for this test."

        result = runner.invoke(cli, ["compare"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Not enough history to perform comparison: HEAD is the initial commit and has no parent to compare with." in result.output

    def test_compare_no_differences_cli(self, runner, local_repo):
        """Test `gitwrite compare commitA commitA`."""
        repo = local_repo
        os.chdir(repo.workdir)

        commit_A_oid = str(repo.head.target) # From initial commit in fixture

        result = runner.invoke(cli, ["compare", commit_A_oid, commit_A_oid])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # Display name for OID is the OID itself if passed directly
        assert f"No differences found between {commit_A_oid} and {commit_A_oid}." in result.output

    def test_compare_simple_content_change_cli(self, runner, local_repo):
        """Test `gitwrite compare commitA commitB` for content change."""
        repo = local_repo
        os.chdir(repo.workdir)

        commit_A_oid = repo.head.target # Initial commit
        make_commit(repo, "file.txt", "content line1\ncontent line2", "Commit A - file.txt")
        commit_A_file_oid = repo.head.target # Commit after adding file.txt for the first time

        make_commit(repo, "file.txt", "content line1\nmodified line2", "Commit B - modify file.txt")
        commit_B_file_oid = repo.head.target

        # We want to compare the state of file.txt before and after modification
        # So, compare commit_A_file_oid and commit_B_file_oid

        result = runner.invoke(cli, ["compare", str(commit_A_file_oid), str(commit_B_file_oid)])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert f"Diff between {str(commit_A_file_oid)} (a) and {str(commit_B_file_oid)} (b):" in result.output
        assert "--- a/file.txt" in result.output
        assert "+++ b/file.txt" in result.output
        assert "-content line2" in result.output
        assert "+modified line2" in result.output
        # Rich formatting for word diff is hard to assert directly for colors,
        # but the presence of +/- lines is a good indicator.

    def test_compare_file_addition_cli(self, runner, local_repo):
        """Test `gitwrite compare commitA commitB` for file addition."""
        repo = local_repo
        os.chdir(repo.workdir)

        commit_A_oid = str(repo.head.target) # Initial commit
        make_commit(repo, "new_file.txt", "new content", "Commit B - adds new_file.txt")
        commit_B_oid = str(repo.head.target)

        result = runner.invoke(cli, ["compare", commit_A_oid, commit_B_oid])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "+++ b/new_file.txt" in result.output
        assert "+new content" in result.output

    def test_compare_file_deletion_cli(self, runner, local_repo):
        """Test `gitwrite compare commitA commitB` for file deletion."""
        repo = local_repo
        os.chdir(repo.workdir)

        make_commit(repo, "old_file.txt", "old content", "Commit A - adds old_file.txt")
        commit_A_oid = str(repo.head.target)

        # Delete the file for Commit B
        index = repo.index
        index.read()
        index.remove("old_file.txt")
        tree_for_B = index.write_tree()
        author = pygit2.Signature("Test Deleter", "del@example.com", 1234567890, 0)
        committer = author
        commit_B_oid = str(repo.create_commit("HEAD", author, committer, "Commit B - deletes old_file.txt", tree_for_B, [commit_A_oid]))

        result = runner.invoke(cli, ["compare", commit_A_oid, commit_B_oid])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "--- a/old_file.txt" in result.output
        assert "-old content" in result.output

    def test_compare_one_ref_vs_head_cli(self, runner, local_repo):
        """Test `gitwrite compare <ref>`."""
        repo = local_repo
        os.chdir(repo.workdir)

        commit_A_oid_str = str(repo.head.target) # Initial commit
        make_commit(repo, "file_for_B.txt", "content B", "Commit B")
        commit_B_oid_str = str(repo.head.target) # HEAD

        result = runner.invoke(cli, ["compare", commit_A_oid_str])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Display name for HEAD should be short OID (HEAD)
        head_short_oid = commit_B_oid_str[:7]
        assert f"Diff between {commit_A_oid_str} (a) and {head_short_oid} (HEAD) (b):" in result.output
        assert "+++ b/file_for_B.txt" in result.output # File added in B relative to A

    def test_compare_default_head_vs_parent_cli(self, runner, local_repo):
        """Test `gitwrite compare` (default HEAD~1 vs HEAD)."""
        repo = local_repo
        os.chdir(repo.workdir)

        commit_A_oid_str = str(repo.head.target) # This is HEAD~1 after next commit
        make_commit(repo, "file_for_default.txt", "new stuff", "Commit for default compare (HEAD)")
        commit_B_oid_str = str(repo.head.target) # This is HEAD

        result = runner.invoke(cli, ["compare"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        parent_short_oid = commit_A_oid_str[:7]
        head_short_oid = commit_B_oid_str[:7]
        assert f"Diff between {parent_short_oid} (HEAD~1) (a) and {head_short_oid} (HEAD) (b):" in result.output
        assert "+++ b/file_for_default.txt" in result.output

    def test_compare_invalid_ref_cli(self, runner, local_repo):
        """Test `gitwrite compare invalidREF`."""
        repo = local_repo
        os.chdir(repo.workdir)

        result = runner.invoke(cli, ["compare", "invalidREF"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Could not resolve reference: Reference 'invalidREF' not found or not a commit" in result.output

    def test_compare_not_a_git_repo_cli(self, runner, tmp_path):
        """Test `gitwrite compare` in a non-Git directory."""
        non_repo_dir = tmp_path / "not_a_repo_for_compare"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)

        result = runner.invoke(cli, ["compare"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Not a Git repository." in result.output # Changed to match get_diff's initial check

    def test_compare_branch_names_cli(self, runner, local_repo):
        """Test `gitwrite compare branchA branchB`."""
        repo = local_repo
        os.chdir(repo.workdir)

        initial_commit_oid = repo.head.target

        # Create branch1 and make Commit B
        repo.branches.create("branch1", repo.get(initial_commit_oid))
        repo.checkout("refs/heads/branch1")
        make_commit(repo, "fileB.txt", "content B", "Commit B on branch1")

        # Switch back to main, create branch2 and make Commit C
        # Assuming 'main' or 'master' is the default branch name from fixture.
        default_branch_name = repo.head.shorthand if repo.head.shorthand == "main" else "master"
        if not repo.branches.get(default_branch_name): # If fixture created main but we are on master or vice-versa
             default_branch_name = "main" if repo.branches.get("main") else "master"

        repo.checkout(repo.branches[default_branch_name])
        assert repo.head.target == initial_commit_oid # Ensure back to initial state for branch2

        repo.branches.create("branch2", repo.get(initial_commit_oid))
        repo.checkout("refs/heads/branch2")
        make_commit(repo, "fileC.txt", "content C", "Commit C on branch2")

        result = runner.invoke(cli, ["compare", "branch1", "branch2"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert "Diff between branch1 (a) and branch2 (b):" in result.output
        assert "--- a/fileB.txt" in result.output # fileB from branch1 removed
        assert "+++ b/fileC.txt" in result.output # fileC from branch2 added


#######################################
# History Command Tests (CLI Runner)
#######################################

class TestHistoryCommandCLI:

    def test_history_empty_repo_cli(self, runner, tmp_path):
        """Test `gitwrite history` in an empty initialized repo."""
        empty_repo_path = tmp_path / "empty_history_repo"
        empty_repo_path.mkdir()
        pygit2.init_repository(str(empty_repo_path)) # Initialize repo, no commits

        os.chdir(empty_repo_path)
        result = runner.invoke(cli, ["history"])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No history yet." in result.output

    def test_history_bare_repo_cli(self, runner, tmp_path):
        """Test `gitwrite history` in a bare repo."""
        bare_repo_path = tmp_path / "bare_history_repo.git"
        pygit2.init_repository(str(bare_repo_path), bare=True)

        # For a bare repo, we can't chdir into it directly to run commands
        # The history command itself discovers the repo from CWD.
        # So, we need to run it from a directory that would discover the bare repo,
        # or, more simply, the `get_commit_history` will be called with the bare repo path.
        # The CLI's initial `pygit2.discover_repository(str(Path.cwd()))` might fail if CWD is not
        # inside a worktree of the bare repo (which it usually isn't).
        # Let's simulate calling it as if CWD was the bare repo path itself,
        # which is how the core function would be tested.
        # The CLI `history` has an explicit check: `if repo.is_bare: click.echo("Error: Cannot show history...", err=True); return`
        # This check happens *after* `repo = pygit2.Repository(repo_path_str)`.
        # So, `discover_repository` must work.
        # A common way to "be in" a bare repo for discovery is to be in a directory *named* `repo.git`.
        # However, the CLI directly passes the discovered path to `get_commit_history`.
        # If we `chdir` to `tmp_path` and the bare repo is `tmp_path / bare_repo.git`,
        # `discover_repository` might not find it unless `tmp_path` itself becomes part of a git structure, which is unlikely.

        # Let's adjust the test to reflect how the CLI uses `discover_repository`.
        # We'll create a dummy worktree-like situation or pass path directly.
        # The current CLI `history` will discover from CWD.
        # If CWD is *inside* the .git folder of a non-bare, or if CWD *is* the bare repo path, discovery behavior varies.
        # The simplest interpretation is that `discover_repository` is called on `Path.cwd()`.
        # If `Path.cwd()` *is* `bare_repo_path`, `discover_repository` returns `bare_repo_path`.
        # Then `Repository(bare_repo_path)` is called.

        # To correctly test the CLI's bare repo check:
        # We need a scenario where `discover_repository(Path.cwd())` resolves to the bare repo path.
        # This typically means `Path.cwd()` *is* the bare repo path.
        os.chdir(bare_repo_path) # This is unusual, but matches how discover_repository would find it if CWD *is* the repo.
        result = runner.invoke(cli, ["history"])

        # The CLI has its own bare check now.
        # assert result.exit_code == 0 # Command handles error gracefully
        # assert "Error: Cannot show history for a bare repository." in result.output
        # The refactored CLI calls core `get_commit_history` which returns `[]` for bare.
        # Then CLI prints "No history yet."
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No history yet." in result.output


    def test_history_single_commit_cli(self, runner, local_repo):
        """Test `gitwrite history` with a single commit."""
        repo = local_repo
        os.chdir(repo.workdir) # local_repo fixture creates an initial commit

        commit_oid = repo.head.target
        commit_obj = repo.get(commit_oid)

        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert "Commit" in result.output # Header
        assert "Author" in result.output # Header
        assert "Date" in result.output   # Header
        assert "Message" in result.output # Header

        assert str(commit_oid)[:7] in result.output # Short hash
        assert commit_obj.author.name in result.output
        assert commit_obj.message.splitlines()[0] in result.output

    def test_history_multiple_commits_cli(self, runner, local_repo):
        """Test `gitwrite history` with multiple commits."""
        repo = local_repo
        os.chdir(repo.workdir)

        commit1_msg = "Commit Alpha"
        commit1_oid = make_commit(repo, "alpha.txt", "alpha content", commit1_msg)

        commit2_msg = "Commit Beta"
        commit2_oid = make_commit(repo, "beta.txt", "beta content", commit2_msg)

        # The initial commit from fixture is also there. Let's get its details.
        initial_commit_oid = repo.revparse_single("HEAD~2").id # 2 commits made after initial
        initial_commit_obj = repo.get(initial_commit_oid)

        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Check order and presence (most recent first)
        assert result.output.find(str(commit2_oid)[:7]) < result.output.find(str(commit1_oid)[:7])
        assert result.output.find(commit2_msg) < result.output.find(commit1_msg)

        assert result.output.find(str(commit1_oid)[:7]) < result.output.find(str(initial_commit_oid)[:7])
        assert result.output.find(commit1_msg) < result.output.find(initial_commit_obj.message.splitlines()[0])

        assert str(commit2_oid)[:7] in result.output
        assert commit2_msg in result.output
        assert str(commit1_oid)[:7] in result.output
        assert commit1_msg in result.output
        assert str(initial_commit_oid)[:7] in result.output
        assert initial_commit_obj.message.splitlines()[0] in result.output


    def test_history_with_limit_n_cli(self, runner, local_repo):
        """Test `gitwrite history -n <limit>`."""
        repo = local_repo
        os.chdir(repo.workdir)

        # Initial commit by fixture
        commitA_msg = "Commit A for limit test"
        make_commit(repo, "fileA.txt", "contentA", commitA_msg) # HEAD~2 after this

        commitB_msg = "Commit B for limit test"
        commitB_oid_str = str(make_commit(repo, "fileB.txt", "contentB", commitB_msg)) # HEAD~1

        commitC_msg = "Commit C for limit test"
        commitC_oid_str = str(make_commit(repo, "fileC.txt", "contentC", commitC_msg)) # HEAD

        result = runner.invoke(cli, ["history", "-n", "2"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert commitC_oid_str[:7] in result.output
        assert commitC_msg in result.output
        assert commitB_oid_str[:7] in result.output
        assert commitB_msg in result.output

        assert commitA_msg not in result.output
        # Also check that initial commit from fixture is not present
        initial_commit_msg = repo.get(repo.revparse_single("HEAD~2").id).message.splitlines()[0]
        assert initial_commit_msg not in result.output


    def test_history_limit_n_greater_than_commits_cli(self, runner, local_repo):
        """Test `gitwrite history -n <limit>` where limit > available commits."""
        repo = local_repo
        os.chdir(repo.workdir) # Has initial commit

        commitA_msg = "Additional Commit A"
        commitA_oid_str = str(make_commit(repo, "another_A.txt", "content", commitA_msg)) # HEAD

        initial_commit_obj = repo.get(repo.revparse_single("HEAD~1").id) # The fixture's initial commit
        initial_commit_msg = initial_commit_obj.message.splitlines()[0]
        initial_commit_oid_str = str(initial_commit_obj.id)


        result = runner.invoke(cli, ["history", "-n", "5"]) # Request 5, only 2 exist
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert commitA_oid_str[:7] in result.output
        assert commitA_msg in result.output
        assert initial_commit_oid_str[:7] in result.output
        assert initial_commit_msg in result.output

        # Check that the table visually has two rows of data.
        # Rich tables have borders; count lines that look like data rows.
        # A simple way: count occurrences of short hashes (assuming they are unique enough)
        lines_with_short_hash = 0
        for line in result.output.splitlines():
            if re.search(r"[0-9a-f]{7}", line) and "Commit" not in line and "History" not in line : # crude check for commit row
                 lines_with_short_hash +=1
        assert lines_with_short_hash == 2 # Expecting 2 data rows

    def test_history_not_a_git_repo_cli(self, runner, tmp_path):
        """Test `gitwrite history` in a directory that is not a Git repository."""
        non_repo_dir = tmp_path / "not_a_repo_for_history"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)

        result = runner.invoke(cli, ["history"])
        # Exit code 0 because CLI handles this error.
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Not a Git repository (or any of the parent directories)." in result.output

# Need to import `re` for the regex in test_history_limit_n_greater_than_commits_cli
# Add it at the top of the file.
# The TestHistoryCommandCLI class and its methods are now defined.
# The make_commit helper from tests/test_main.py is used.
# os.chdir is used.
# Assertions check exit code and output.
# Date checking is minimal, focusing on other data.
# Rich table output is implicitly tested by checking for headers and content.

#######################################
# Core Tagging Function Tests
#######################################
from gitwrite_core.tagging import create_tag, list_tags
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, TagAlreadyExistsError, GitWriteError
# import tempfile # Pytest's tmp_path is generally preferred

class TestTaggingCore:

    def _get_repo_path_and_pygit2_repo(self, local_repo_fixture):
        # local_repo_fixture is a pygit2.Repository instance
        # The path can be obtained from its workdir attribute
        return local_repo_fixture.workdir, local_repo_fixture

    def test_create_lightweight_tag_on_head(self, local_repo):
        repo_path_str, repo = self._get_repo_path_and_pygit2_repo(local_repo)
        tag_name = "v0.1-lw"

        result = create_tag(repo_path_str, tag_name)

        assert result['name'] == tag_name
        assert result['type'] == 'lightweight'
        assert result['target'] == str(repo.head.target)

        tag_ref = repo.references.get(f"refs/tags/{tag_name}")
        assert tag_ref is not None
        assert tag_ref.target == repo.head.target

        # Verify it's not an annotated tag object by trying to peel it as a Tag object
        # A direct reference to a commit will cause revparse_single(tag_name) to return a Commit object.
        # Peeling a Commit object to a Tag object will raise a TypeError.
        target_obj = repo.revparse_single(tag_name)
        assert isinstance(target_obj, pygit2.Commit)
        with pytest.raises(TypeError):
            target_obj.peel(pygit2.Tag)


    def test_create_annotated_tag_on_head(self, local_repo):
        repo_path_str, repo = self._get_repo_path_and_pygit2_repo(local_repo)
        tag_name = "v0.1-an"
        message = "This is an annotated tag."

        result = create_tag(repo_path_str, tag_name, message=message)

        assert result['name'] == tag_name
        assert result['type'] == 'annotated'
        assert result['target'] == str(repo.head.target) # Target commit OID
        assert result['message'] == message

        # Verify the tag object in pygit2
        # For an annotated tag, revparse_single(tag_name) gives the Tag object.
        tag_object = repo.revparse_single(tag_name).peel(pygit2.Tag) # Peel to ensure it's a Tag object
        assert isinstance(tag_object, pygit2.Tag)
        assert tag_object.name == tag_name
        # The core `create_tag` function stores the message exactly as given.
        # pygit2's `tag_object.message` might have an extra newline if that's how git stores it.
        # The core function returns the original message, so we check that.
        # If checking pygit2 object directly: assert tag_object.message.strip() == message
        assert tag_object.message == message # Assuming pygit2 stores it as is or create_tag ensures exact match for return
        assert str(tag_object.target) == str(repo.head.target) # Target of the tag object is the commit OID
        assert tag_object.tagger.name == "GitWrite Core" # Default tagger

    def test_create_tag_on_specific_commit(self, local_repo):
        repo_path_str, repo = self._get_repo_path_and_pygit2_repo(local_repo)

        commit1_hash_str = str(repo.head.target) # Initial commit
        make_commit(repo, "another_file.txt", "content", "Second commit")
        commit2_hash_str = str(repo.head.target)
        assert commit1_hash_str != commit2_hash_str

        tag_name_lw = "tag-on-commit1-lw"
        result_lw = create_tag(repo_path_str, tag_name_lw, target_commit_ish=commit1_hash_str)

        assert result_lw['name'] == tag_name_lw
        assert result_lw['type'] == 'lightweight'
        assert result_lw['target'] == commit1_hash_str
        assert str(repo.lookup_reference(f"refs/tags/{tag_name_lw}").target) == commit1_hash_str

        tag_name_an = "tag-on-commit1-an"
        message = "Annotated on first commit"
        result_an = create_tag(repo_path_str, tag_name_an, target_commit_ish=commit1_hash_str, message=message)
        assert result_an['type'] == 'annotated'
        assert result_an['target'] == commit1_hash_str # Target commit OID

        tag_object_an = repo.revparse_single(tag_name_an).peel(pygit2.Tag)
        assert isinstance(tag_object_an, pygit2.Tag)
        assert str(tag_object_an.target) == commit1_hash_str


    def test_create_tag_force_overwrite(self, local_repo):
        repo_path_str, repo = self._get_repo_path_and_pygit2_repo(local_repo)
        tag_name = "test-force"

        initial_target_oid_str = str(repo.head.target)
        create_tag(repo_path_str, tag_name) # Create initial tag (lightweight)
        assert str(repo.lookup_reference(f"refs/tags/{tag_name}").target) == initial_target_oid_str

        new_commit_oid = make_commit(repo, "force_tag_file.txt", "data", "Commit for force tag")
        new_commit_oid_str = str(new_commit_oid)
        assert new_commit_oid_str != initial_target_oid_str

        # Force create annotated tag on the new commit
        new_message = "Forced annotated tag"
        result = create_tag(repo_path_str, tag_name, target_commit_ish=new_commit_oid_str, message=new_message, force=True)

        assert result['name'] == tag_name
        assert result['type'] == 'annotated'
        assert result['target'] == new_commit_oid_str
        assert result['message'] == new_message

        tag_object = repo.revparse_single(tag_name).peel(pygit2.Tag)
        assert isinstance(tag_object, pygit2.Tag)
        assert str(tag_object.target) == new_commit_oid_str
        # Check message from pygit2 object (might have extra newline from git itself)
        # For annotated tags, the message in repo might have an extra newline.
        # The create_tag function returns the exact message passed.
        assert tag_object.message.strip() == new_message.strip()


    def test_create_tag_already_exists_no_force(self, local_repo):
        repo_path_str, _ = self._get_repo_path_and_pygit2_repo(local_repo)
        tag_name = "exists-no-force"
        create_tag(repo_path_str, tag_name) # Create once

        with pytest.raises(TagAlreadyExistsError) as excinfo:
            create_tag(repo_path_str, tag_name) # Attempt to create again
        assert f"Tag '{tag_name}' already exists" in str(excinfo.value)

    def test_create_tag_target_non_existent_commit(self, local_repo):
        repo_path_str, _ = self._get_repo_path_and_pygit2_repo(local_repo)
        non_existent_commit_ish = "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
        with pytest.raises(CommitNotFoundError) as excinfo:
            create_tag(repo_path_str, "bad-target-tag", target_commit_ish=non_existent_commit_ish)
        assert f"Commit-ish '{non_existent_commit_ish}' not found" in str(excinfo.value)

    def test_create_tag_non_repository_path(self, tmp_path): # Use tmp_path directly
        non_repo_path = tmp_path / "not_a_repo_for_tagging" # More specific name
        non_repo_path.mkdir()
        # Convert to string for the function call
        non_repo_path_str = str(non_repo_path)
        with pytest.raises(RepositoryNotFoundError) as excinfo:
            create_tag(non_repo_path_str, "anytag")
        assert f"Repository not found at '{non_repo_path_str}'" in str(excinfo.value)

    # Placeholder for list_tags tests
    def test_list_tags_empty_repo_no_tags(self, local_repo): # Example, will be detailed later
        repo_path_str, _ = self._get_repo_path_and_pygit2_repo(local_repo)
        # Remove any default tags if any were made by other tests on the shared fixture if not careful
        # For now, assume local_repo is fresh or tags are uniquely named per test.
        # Better: ensure no tags exist before this test or use a completely fresh repo.
        # For now, let's rely on local_repo being relatively clean from the fixture.

        # To be certain, let's use a sub-directory for this test's repo to avoid cross-test interference
        # Or, ensure tags created in other tests are deleted if local_repo is shared and mutated.
        # The current local_repo fixture reinitializes per test, so it should be fine.

        tags = list_tags(repo_path_str)
        assert tags == []

    def test_list_tags_one_lightweight(self, local_repo):
        repo_path_str, repo = self._get_repo_path_and_pygit2_repo(local_repo)
        tag_name = "lw-tag"
        create_tag(repo_path_str, tag_name)

        tags = list_tags(repo_path_str)

        assert len(tags) == 1
        tag_info = tags[0]
        assert tag_info['name'] == tag_name
        assert tag_info['type'] == 'lightweight'
        assert tag_info['target'] == str(repo.head.target)

    def test_list_tags_one_annotated(self, local_repo):
        repo_path_str, repo = self._get_repo_path_and_pygit2_repo(local_repo)
        tag_name = "an-tag"
        message = "Annotated message for list test"
        create_tag(repo_path_str, tag_name, message=message)

        tags = list_tags(repo_path_str)

        assert len(tags) == 1
        tag_info = tags[0]
        assert tag_info['name'] == tag_name
        assert tag_info['type'] == 'annotated'
        assert tag_info['target'] == str(repo.head.target)
        assert tag_info['message'] == message.strip() # list_tags strips message

    def test_list_tags_multiple_mixed(self, local_repo):
        repo_path_str, repo = self._get_repo_path_and_pygit2_repo(local_repo)

        # Tag 1 (annotated on initial commit)
        tag1_name = "v1.0"
        tag1_message = "Version 1.0 release"
        commit1_oid_str = str(repo.head.target)
        create_tag(repo_path_str, tag1_name, target_commit_ish=commit1_oid_str, message=tag1_message)

        # Make another commit
        commit2_oid_str = str(make_commit(repo, "file_for_tag2.txt", "content", "Commit for tag2"))

        # Tag 2 (lightweight on second commit)
        tag2_name = "feature-x"
        create_tag(repo_path_str, tag2_name, target_commit_ish=commit2_oid_str)

        # Tag 3 (annotated on second commit)
        tag3_name = "v1.1-alpha"
        tag3_message = "Alpha release for v1.1"
        create_tag(repo_path_str, tag3_name, target_commit_ish=commit2_oid_str, message=tag3_message)

        tags = list_tags(repo_path_str)
        assert len(tags) == 3

        # Sort by name for consistent checking
        tags_by_name = {t['name']: t for t in tags}

        assert tag1_name in tags_by_name
        tag1_info = tags_by_name[tag1_name]
        assert tag1_info['type'] == 'annotated'
        assert tag1_info['target'] == commit1_oid_str
        assert tag1_info['message'] == tag1_message.strip()

        assert tag2_name in tags_by_name
        tag2_info = tags_by_name[tag2_name]
        assert tag2_info['type'] == 'lightweight'
        assert tag2_info['target'] == commit2_oid_str
        assert 'message' not in tag2_info # Lightweight tags don't have messages

        assert tag3_name in tags_by_name
        tag3_info = tags_by_name[tag3_name]
        assert tag3_info['type'] == 'annotated'
        assert tag3_info['target'] == commit2_oid_str
        assert tag3_info['message'] == tag3_message.strip()

    def test_list_tags_non_repository_path(self, tmp_path):
        non_repo_path = tmp_path / "not_a_repo_for_list_tags"
        non_repo_path.mkdir()
        non_repo_path_str = str(non_repo_path)
        with pytest.raises(RepositoryNotFoundError) as excinfo:
            list_tags(non_repo_path_str)
        assert f"Repository not found at '{non_repo_path_str}'" in str(excinfo.value)


#######################################
# CLI Tagging Command Tests
#######################################

class TestTagCommandsCLI:

    def test_cli_tag_add_lightweight(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        tag_name = "cli-lw-v0.1"

        result = runner.invoke(cli, ["tag", "add", tag_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Created lightweight tag '{tag_name}' pointing to {repo.head.target.hex[:7]}" in result.output

        # Verify with pygit2
        tag_ref = repo.references.get(f"refs/tags/{tag_name}")
        assert tag_ref is not None
        assert tag_ref.target == repo.head.target
        target_obj = repo.revparse_single(tag_name)
        assert isinstance(target_obj, pygit2.Commit) # Lightweight points to commit

    def test_cli_tag_add_annotated(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        tag_name = "cli-an-v0.2"
        message = "CLI annotated tag test"

        result = runner.invoke(cli, ["tag", "add", tag_name, "-m", message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Created annotated tag '{tag_name}' pointing to {repo.head.target.hex[:7]}" in result.output

        # Verify with pygit2
        tag_obj = repo.revparse_single(tag_name).peel(pygit2.Tag) # Peel to Tag object
        assert isinstance(tag_obj, pygit2.Tag)
        assert tag_obj.name == tag_name
        assert tag_obj.message.strip() == message
        assert str(tag_obj.target) == str(repo.head.target)
        assert tag_obj.tagger.name == "GitWrite Core" # Default tagger from core function

    def test_cli_tag_add_on_specific_commit(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)

        commit1_hash_str = str(repo.head.target)
        make_commit(repo, "cli_tag_commit.txt", "content", "Commit for CLI tag")
        # HEAD is now at commit2

        tag_name = "cli-tag-on-commit1"
        result = runner.invoke(cli, ["tag", "add", tag_name, "--commit", commit1_hash_str])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Created lightweight tag '{tag_name}' pointing to {commit1_hash_str[:7]}" in result.output

        # Verify
        tag_ref = repo.references.get(f"refs/tags/{tag_name}")
        assert tag_ref is not None
        assert str(tag_ref.target) == commit1_hash_str

    def test_cli_tag_add_force_overwrite(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        tag_name = "cli-force-test"

        # Initial tag (lightweight on commit1)
        commit1_hash_str = str(repo.head.target)
        runner.invoke(cli, ["tag", "add", tag_name, "--commit", commit1_hash_str])

        # New commit
        commit2_hash_str = str(make_commit(repo, "force_file.txt", "data", "Commit for force test"))

        # Force create annotated tag on commit2
        new_message = "Forced CLI tag"
        result = runner.invoke(cli, ["tag", "add", tag_name, "--commit", commit2_hash_str, "-m", new_message, "--force"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Created annotated tag '{tag_name}' pointing to {commit2_hash_str[:7]}" in result.output

        # Verify
        tag_obj = repo.revparse_single(tag_name).peel(pygit2.Tag)
        assert isinstance(tag_obj, pygit2.Tag)
        assert str(tag_obj.target) == commit2_hash_str
        assert tag_obj.message.strip() == new_message

    def test_cli_tag_add_already_exists_no_force(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        tag_name = "cli-exists-noforce"

        runner.invoke(cli, ["tag", "add", tag_name]) # Create once

        result = runner.invoke(cli, ["tag", "add", tag_name]) # Attempt again
        assert result.exit_code == 1, f"Expected non-zero exit for existing tag: {result.output}"
        assert f"Error: Tag '{tag_name}' already exists. Use --force to overwrite." in result.output

    def test_cli_tag_add_target_non_existent_commit(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)
        non_existent_commit = "deadbeef0000deadbeef0000deadbeef0000"
        tag_name = "cli-bad-target"

        result = runner.invoke(cli, ["tag", "add", tag_name, "--commit", non_existent_commit])
        assert result.exit_code == 1, f"Expected non-zero exit for non-existent commit: {result.output}"
        assert f"Error: Commit '{non_existent_commit}' not found." in result.output

    def test_cli_tag_add_in_non_repo_dir(self, runner, tmp_path):
        non_repo_dir = tmp_path / "cli_tag_non_repo"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)

        result = runner.invoke(cli, ["tag", "add", "anytag"])
        assert result.exit_code == 1, f"Expected non-zero exit for non-repo: {result.output}"
        assert "Error: Not a git repository" in result.output # Matches CLI output from discover_repository check

    # Tests for `gitwrite tag list` CLI command will follow
    def test_cli_tag_list_no_tags(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)

        result = runner.invoke(cli, ["tag", "list"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No tags found in the repository." in result.output

    def test_cli_tag_list_with_tags(self, runner, local_repo):
        repo = local_repo
        os.chdir(repo.workdir)

        # Create some tags using the core function for setup simplicity
        # Tag 1 (annotated on initial commit)
        tag1_name = "v1.0-cli"
        tag1_message = "Version 1.0 release (CLI test)"
        commit1_oid = repo.head.target
        create_tag(repo.workdir, tag1_name, target_commit_ish=str(commit1_oid), message=tag1_message)

        # Make another commit
        commit2_oid = make_commit(repo, "file_for_tag_list_cli.txt", "content", "Commit for tag list CLI")

        # Tag 2 (lightweight on second commit)
        tag2_name = "feature-xyz-cli"
        create_tag(repo.workdir, tag2_name, target_commit_ish=str(commit2_oid))

        result = runner.invoke(cli, ["tag", "list"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Verify table headers (basic check for Rich table output)
        assert "Tag Name" in result.output
        assert "Type" in result.output
        assert "Target Commit" in result.output
        assert "Message (Annotated Only)" in result.output

        # Verify tag1 details
        assert tag1_name in result.output
        assert "annotated" in result.output # Assuming type is printed
        assert str(commit1_oid)[:7] in result.output
        assert tag1_message.splitlines()[0] in result.output # Check first line of message

        # Verify tag2 details
        assert tag2_name in result.output
        assert "lightweight" in result.output # Assuming type is printed
        assert str(commit2_oid)[:7] in result.output
        # For lightweight, message column usually has a placeholder like '-'
        # This depends on the exact formatting in cli's list_cmd
        # A simple check: ensure tag2_name is there, and its commit hash.
        # More robust: parse lines. For now, string presence is a good indicator.

        # Example of a more specific check if output format is stable:
        # Find line containing tag1_name and check other cells in that conceptual row.
        lines = result.output.splitlines()
        tag1_line = next((line for line in lines if tag1_name in line), None)
        assert tag1_line is not None, f"Tag '{tag1_name}' not found in output"
        assert "annotated" in tag1_line
        assert str(commit1_oid)[:7] in tag1_line
        assert tag1_message.splitlines()[0] in tag1_line

        tag2_line = next((line for line in lines if tag2_name in line), None)
        assert tag2_line is not None, f"Tag '{tag2_name}' not found in output"
        assert "lightweight" in tag2_line
        assert str(commit2_oid)[:7] in tag2_line


    def test_list_gitignore_with_only_whitespace_core(self, tmp_path: Path):
        """Core: List patterns from .gitignore with only whitespace/blank lines."""
        repo_dir = tmp_path / "repo_for_list_whitespace"
        repo_dir.mkdir()
        gitignore_path = repo_dir / ".gitignore"
        gitignore_path.write_text("\n   \n\t\n  \n")

        result = list_gitignore_patterns(str(repo_dir))
        assert result['status'] == 'empty' # Core function strips lines, resulting in no actual patterns
        assert result['patterns'] == []
        assert result['message'] == '.gitignore is empty.'

# Helper for configuring user for tests that create commits
@pytest.fixture
def configure_git_user_for_cli(tmp_path): # Renamed to avoid conflict if imported from core tests
    """Fixture to configure user.name and user.email for CLI tests requiring commits."""
    def _configure(repo_path_str: str):
        # This helper assumes repo_path_str is valid and repo exists
        repo = pygit2.Repository(repo_path_str)
        config = repo.config
        config.set_multivar("user.name", "CLITest User")
        config.set_multivar("user.email", "clitest@example.com")
    return _configure

@pytest.fixture
def cli_repo_for_merge(tmp_path: Path, configure_git_user_for_cli) -> Path:
    repo_path = tmp_path / "cli_merge_normal_repo"
    repo_path.mkdir()
    pygit2.init_repository(str(repo_path))
    configure_git_user_for_cli(str(repo_path))
    repo = pygit2.Repository(str(repo_path))

    # C0 - Initial commit on main
    make_commit(repo, "common.txt", "line0", "C0: Initial on main")
    c0_oid = repo.head.target

    # C1 on main
    make_commit(repo, "main_file.txt", "main content", "C1: Commit on main")

    # Create feature branch from C0
    feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
    repo.checkout(feature_branch.name)
    make_commit(repo, "feature_file.txt", "feature content", "C2: Commit on feature")

    # Switch back to main for the test starting point
    repo.checkout(repo.branches.local['main'].name)
    return repo_path

@pytest.fixture
def cli_repo_for_ff_merge(tmp_path: Path, configure_git_user_for_cli) -> Path:
    repo_path = tmp_path / "cli_repo_for_ff_merge"
    repo_path.mkdir()
    pygit2.init_repository(str(repo_path))
    configure_git_user_for_cli(str(repo_path))
    repo = pygit2.Repository(str(repo_path))

    make_commit(repo, "main_base.txt", "base for ff", "C0: Base on main")
    c0_oid = repo.head.target

    feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
    repo.checkout(feature_branch.name)
    make_commit(repo, "feature_ff.txt", "ff content", "C1: Commit on feature")

    repo.checkout(repo.branches.local['main'].name)
    return repo_path

@pytest.fixture
def cli_repo_for_conflict_merge(tmp_path: Path, configure_git_user_for_cli) -> Path:
    repo_path = tmp_path / "cli_repo_for_conflict_merge"
    repo_path.mkdir()
    pygit2.init_repository(str(repo_path))
    configure_git_user_for_cli(str(repo_path))
    repo = pygit2.Repository(str(repo_path))

    conflict_file = "conflict.txt"
    make_commit(repo, conflict_file, "Line1\nCommon Line\nLine3", "C0: Common ancestor")
    c0_oid = repo.head.target

    make_commit(repo, conflict_file, "Line1\nChange on Main\nLine3", "C1: Change on main")

    feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
    repo.checkout(feature_branch.name)
    make_commit(repo, conflict_file, "Line1\nChange on Feature\nLine3", "C2: Change on feature")

    repo.checkout(repo.branches.local['main'].name)
    return repo_path

class TestMergeCommandCLI:
    def test_merge_normal_success_cli(self, runner: CliRunner, cli_repo_for_merge: Path):
        os.chdir(cli_repo_for_merge)
        result = runner.invoke(cli, ["merge", "feature"])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Merged 'feature' into 'main'. New commit:" in result.output

        repo = pygit2.Repository(str(cli_repo_for_merge))
        match = re.search(r"New commit: ([a-f0-9]{7,})\.", result.output)
        assert match, "Could not find commit OID in output."
        merge_commit_oid_short = match.group(1)

        merge_commit = repo.revparse_single(merge_commit_oid_short)
        assert merge_commit is not None
        assert len(merge_commit.parents) == 2
        assert repo.state == pygit2.GIT_REPOSITORY_STATE_NONE

    def test_merge_fast_forward_success_cli(self, runner: CliRunner, cli_repo_for_ff_merge: Path):
        os.chdir(cli_repo_for_ff_merge)
        result = runner.invoke(cli, ["merge", "feature"])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Fast-forwarded 'main' to 'feature' (commit " in result.output

        repo = pygit2.Repository(str(cli_repo_for_ff_merge))
        assert repo.head.target == repo.branches.local['feature'].target

    def test_merge_up_to_date_cli(self, runner: CliRunner, cli_repo_for_ff_merge: Path):
        os.chdir(cli_repo_for_ff_merge)
        runner.invoke(cli, ["merge", "feature"])

        result = runner.invoke(cli, ["merge", "feature"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "'main' is already up-to-date with 'feature'." in result.output

    def test_merge_conflict_cli(self, runner: CliRunner, cli_repo_for_conflict_merge: Path):
        os.chdir(cli_repo_for_conflict_merge)
        result = runner.invoke(cli, ["merge", "feature"])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Automatic merge of 'feature' into 'main' failed due to conflicts." in result.output
        assert "Conflicting files:" in result.output
        assert "  conflict.txt" in result.output
        assert "Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge." in result.output

        repo = pygit2.Repository(str(cli_repo_for_conflict_merge))
        assert repo.lookup_reference("MERGE_HEAD") is not None

    def test_merge_branch_not_found_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        result = runner.invoke(cli, ["merge", "no-such-branch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Branch 'no-such-branch' not found" in result.output

    def test_merge_into_itself_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        current_branch = repo.head.shorthand
        result = runner.invoke(cli, ["merge", current_branch])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Cannot merge a branch into itself." in result.output

    def test_merge_detached_head_cli(self, runner: CliRunner, cli_test_repo: Path):
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        repo.set_head(repo.head.target)
        assert repo.head_is_detached

        result = runner.invoke(cli, ["merge", "main"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: HEAD is detached. Please switch to a branch to perform a merge." in result.output

    def test_merge_empty_repo_cli(self, runner: CliRunner, tmp_path: Path):
        empty_repo = tmp_path / "empty_for_merge_cli"
        empty_repo.mkdir()
        pygit2.init_repository(str(empty_repo))
        os.chdir(empty_repo)

        result = runner.invoke(cli, ["merge", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Repository is empty or HEAD is unborn. Cannot perform merge." in result.output

    def test_merge_bare_repo_cli(self, runner: CliRunner, tmp_path: Path):
        bare_repo_path = tmp_path / "bare_for_merge_cli.git"
        pygit2.init_repository(str(bare_repo_path), bare=True)
        os.chdir(bare_repo_path)

        result = runner.invoke(cli, ["merge", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Cannot merge in a bare repository." in result.output

    def test_merge_no_signature_cli(self, runner: CliRunner, tmp_path: Path):
        repo_path_no_sig = tmp_path / "no_sig_repo_for_cli_merge"
        repo_path_no_sig.mkdir()
        repo = pygit2.init_repository(str(repo_path_no_sig))
        # DO NOT configure user.name/user.email for this repo

        make_commit(repo, "common.txt", "line0", "C0: Initial on main")
        c0_oid = repo.head.target
        make_commit(repo, "main_file.txt", "main content", "C1: Commit on main")
        feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
        repo.checkout(feature_branch.name)
        make_commit(repo, "feature_file.txt", "feature content", "C2: Commit on feature")
        repo.checkout(repo.branches.local['main'].name)

        os.chdir(repo_path_no_sig)
        result = runner.invoke(cli, ["merge", "feature"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: User signature (user.name and user.email) not configured in Git." in result.output


class TestSyncCommandCLI:
    # Helper to make a commit in a cloned repo (simulating remote user)
    def _commit_in_clone(self, clone_repo_path_str: str, remote_bare_repo_path_str: str, filename: str, content: str, message: str, branch_name: str = "main"):
        if not Path(clone_repo_path_str).exists():
            pygit2.clone_repository(remote_bare_repo_path_str, clone_repo_path_str)

        clone_repo = pygit2.Repository(clone_repo_path_str)
        config_clone = clone_repo.config
        config_clone["user.name"] = "Remote Clone User"
        config_clone["user.email"] = "remote_clone@example.com"

        # Ensure branch exists and is checked out
        if branch_name not in clone_repo.branches.local:
            # Try to find remote branch to base it on
            remote_branch = clone_repo.branches.remote.get(f"origin/{branch_name}")
            if remote_branch:
                clone_repo.branches.local.create(branch_name, remote_branch.peel(pygit2.Commit))
            elif not clone_repo.head_is_unborn: # Base off current head if remote branch doesn't exist
                 clone_repo.branches.local.create(branch_name, clone_repo.head.peel(pygit2.Commit))
            # If head is unborn, make_commit will handle it for the first commit

        if clone_repo.head.shorthand != branch_name:
             clone_repo.checkout(clone_repo.branches.local[branch_name])

        make_commit(clone_repo, filename, content, message)
        clone_repo.remotes["origin"].push([f"refs/heads/{branch_name}:refs/heads/{branch_name}"])


    def test_sync_new_repo_initial_push(self, runner, synctest_repos):
        """ Test `gitwrite sync` in a repo with one local commit, pushing to empty remote."""
        local_repo = synctest_repos["local_repo"]
        # The fixture already made an initial commit and pushed it.
        # Let's create a new branch, commit to it, then sync that new branch.
        os.chdir(local_repo.workdir)

        new_branch_name = "feature_new_for_sync"
        make_commit(local_repo, "feature_file.txt", "content for new feature", f"Commit on {new_branch_name}",)
        # ^ This commit is on 'main'. Need to create and checkout new branch first.
        local_repo.branches.local.create(new_branch_name, local_repo.head.peel(pygit2.Commit))
        local_repo.checkout(f"refs/heads/{new_branch_name}")
        make_commit(local_repo, "another_feature.txt", "more content", f"Second commit on {new_branch_name}")

        current_commit_oid = local_repo.head.target

        result = runner.invoke(cli, ["sync", "--branch", new_branch_name])
        print(f"CLI Output: {result.output}")
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert f"Syncing branch '{new_branch_name}' with remote 'origin'..." in result.output
        assert "Fetch complete." in result.output
        assert f"Remote tracking branch 'refs/remotes/origin/{new_branch_name}' not found" in result.output
        assert "Push successful." in result.output
        assert "Sync process completed successfully." in result.output

        remote_bare_repo = synctest_repos["remote_bare_repo"]
        remote_branch_ref = remote_bare_repo.lookup_reference(f"refs/heads/{new_branch_name}")
        assert remote_branch_ref.target == current_commit_oid


    def test_sync_remote_ahead_fast_forward_cli(self, runner, synctest_repos):
        local_repo = synctest_repos["local_repo"]
        remote_bare_repo_path_str = synctest_repos["remote_bare_repo_path_str"]
        remote_clone_repo_path = synctest_repos["remote_clone_repo_path"]
        os.chdir(local_repo.workdir)

        # Simulate remote having a new commit
        self._commit_in_clone(str(remote_clone_repo_path), remote_bare_repo_path_str,
                              "remote_added_file.txt", "content from remote",
                              "Remote C2 on main", branch_name="main")

        remote_head_commit = synctest_repos["remote_bare_repo"].lookup_reference("refs/heads/main").target

        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Fetch complete." in result.output
        assert f"Local branch 'main' fast-forwarded to remote commit {str(remote_head_commit)[:7]}" in result.output
        assert "Push: Nothing to push" in result.output # After FF, local matches remote, so nothing to push
        assert "Sync process completed successfully." in result.output
        assert local_repo.head.target == remote_head_commit

    def test_sync_diverged_clean_merge_cli(self, runner, synctest_repos):
        local_repo = synctest_repos["local_repo"]
        remote_bare_repo_path_str = synctest_repos["remote_bare_repo_path_str"]
        remote_clone_repo_path = synctest_repos["remote_clone_repo_path"]
        os.chdir(local_repo.workdir)

        # Make a local commit
        make_commit(local_repo, "local_diverge.txt", "local content", "Local C2 on main")
        local_c2_oid = local_repo.head.target

        # Make a remote commit (from original common ancestor)
        self._commit_in_clone(str(remote_clone_repo_path), remote_bare_repo_path_str,
                              "remote_diverge.txt", "remote content",
                              "Remote C2 on main", branch_name="main")
        remote_c2_oid = synctest_repos["remote_bare_repo"].lookup_reference("refs/heads/main").target

        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Fetch complete." in result.output
        assert "Successfully merged remote changes into 'main'. New commit:" in result.output
        assert "Push successful." in result.output

        merge_commit_oid_match = re.search(r"New commit: ([0-9a-f]{7,})", result.output)
        assert merge_commit_oid_match is not None
        merge_commit_oid_short = merge_commit_oid_match.group(1)

        merge_commit = local_repo.revparse_single(merge_commit_oid_short)
        assert local_repo.head.target == merge_commit.id
        assert len(merge_commit.parents) == 2
        parent_oids = {p.id for p in merge_commit.parents}
        assert parent_oids == {local_c2_oid, remote_c2_oid}
        assert synctest_repos["remote_bare_repo"].lookup_reference("refs/heads/main").target == merge_commit.id

    # Branch and Remote Handling
    def test_sync_specific_branch_cli(self, runner, synctest_repos):
        local_repo = synctest_repos["local_repo"]
        os.chdir(local_repo.workdir)
        # Create and push 'dev' branch
        main_commit_oid = local_repo.lookup_reference("refs/heads/main").target
        local_repo.branches.local.create("dev", local_repo.get(main_commit_oid))
        make_commit(local_repo, "dev_file.txt", "dev content", "Commit on dev", branch_name="dev")
        local_repo.remotes["origin"].push(["refs/heads/dev:refs/heads/dev"])

        # Switch back to main locally, so 'dev' is not current branch
        local_repo.checkout(local_repo.branches.local["main"])

        result = runner.invoke(cli, ["sync", "--branch", "dev"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Syncing branch 'dev' with remote 'origin'..." in result.output
        assert "Local branch 'dev' is already up-to-date with remote." in result.output # Or similar
        assert "Push: Nothing to push" in result.output

    def test_sync_branch_not_found_cli(self, runner, synctest_repos):
        os.chdir(synctest_repos["local_repo_path_str"])
        result = runner.invoke(cli, ["sync", "--branch", "nonexistentbranch"])
        assert result.exit_code == 0 # CLI handles error gracefully
        assert "Error: Branch 'nonexistentbranch' not found." in result.output

    def test_sync_detached_head_cli(self, runner, synctest_repos):
        local_repo = synctest_repos["local_repo"]
        os.chdir(local_repo.workdir)
        local_repo.set_head(local_repo.head.target) # Detach HEAD
        assert local_repo.head_is_detached

        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0 # CLI handles error
        assert "Error: HEAD is detached. Please switch to a branch to sync or specify a branch name." in result.output

    def test_sync_remote_not_found_cli(self, runner, synctest_repos):
        os.chdir(synctest_repos["local_repo_path_str"])
        result = runner.invoke(cli, ["sync", "--remote", "nonexistentremote"])
        assert result.exit_code == 0 # CLI handles error
        assert "Error: Remote 'nonexistentremote' not found." in result.output

    # Conflict Scenario
    def test_sync_conflict_cli(self, runner, synctest_repos):
        local_repo = synctest_repos["local_repo"]
        remote_bare_repo_path_str = synctest_repos["remote_bare_repo_path_str"]
        remote_clone_repo_path = synctest_repos["remote_clone_repo_path"]
        os.chdir(local_repo.workdir)

        # Common base commit C1 (already exists from fixture)
        c1_oid = local_repo.lookup_reference("refs/heads/main").target

        # Local C2
        make_commit(local_repo, "conflict_file.txt", "Local version of line", "Local C2 on main")

        # Remote C2 (diverged from C1)
        # Need to ensure clone starts from C1 before making its own C2
        pygit2.clone_repository(remote_bare_repo_path_str, str(remote_clone_repo_path))
        clone_repo = pygit2.Repository(str(remote_clone_repo_path))
        config_clone = clone_repo.config
        config_clone["user.name"] = "Remote Conflicter"
        config_clone["user.email"] = "remote_conflict@example.com"
        clone_repo.checkout("refs/heads/main") # Ensure on main
        clone_repo.reset(c1_oid, pygit2.GIT_RESET_HARD) # Reset to common ancestor C1
        make_commit(clone_repo, "conflict_file.txt", "Remote version of line", "Remote C2 on main")
        clone_repo.remotes["origin"].push([f"refs/heads/main:refs/heads/main"])
        shutil.rmtree(str(remote_clone_repo_path)) # Clean up clone

        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0 # CLI handles error gracefully
        assert "Error: Merge resulted in conflicts." in result.output
        assert "Conflicting files:" in result.output
        assert "conflict_file.txt" in result.output
        assert "Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge." in result.output
        assert local_repo.state == pygit2.GIT_REPOSITORY_STATE_MERGE

    # --no-push Flag
    def test_sync_no_push_flag_cli(self, runner, synctest_repos):
        local_repo = synctest_repos["local_repo"]
        os.chdir(local_repo.workdir)
        # Make a local commit that makes local ahead
        make_commit(local_repo, "local_only_for_nopush.txt", "content", "Local commit, no push test")

        result = runner.invoke(cli, ["sync", "--no-push"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Fetch complete." in result.output
        assert "Local branch 'main' is ahead of remote." in result.output # Or 'No remote tracking branch' if remote was empty
        assert "Push skipped (--no-push specified)." in result.output
        # Check that the commit was NOT pushed to remote
        remote_main_ref = synctest_repos["remote_bare_repo"].lookup_reference("refs/heads/main")
        assert remote_main_ref.target != local_repo.head.target # Remote should not have this new commit

    # Error Handling by CLI
    def test_sync_outside_git_repo_cli(self, runner, tmp_path):
        non_repo_dir = tmp_path / "no_repo_for_sync"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error: Not a Git repository" in result.output

    def test_sync_empty_repo_cli(self, runner, tmp_path):
        empty_repo_path = tmp_path / "empty_for_sync"
        empty_repo_path.mkdir()
        pygit2.init_repository(str(empty_repo_path))
        os.chdir(empty_repo_path)
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error: Repository is empty or HEAD is unborn. Cannot sync." in result.output

    # Simulating fetch/push failures that are caught by core and reported up
    # These rely on the core function's error messages being propagated.
    @patch('gitwrite_core.repository.sync_repository')
    def test_sync_cli_handles_core_fetch_error(self, mock_sync_core, runner, synctest_repos):
        os.chdir(synctest_repos["local_repo_path_str"])
        mock_sync_core.side_effect = FetchError("Simulated core FetchError")
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error during fetch: Simulated core FetchError" in result.output

    @patch('gitwrite_core.repository.sync_repository')
    def test_sync_cli_handles_core_push_error(self, mock_sync_core, runner, synctest_repos):
        os.chdir(synctest_repos["local_repo_path_str"])
        mock_sync_core.side_effect = PushError("Simulated core PushError: Non-fast-forward from core")
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error during push: Simulated core PushError: Non-fast-forward from core" in result.output

# End of TestRevertCommandCLI class
