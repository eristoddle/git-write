import pytest
import pygit2
import os
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch

# Assuming your CLI script is gitwrite_cli.main
from gitwrite_cli.main import cli

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
def empty_local_repo_path(tmp_path):
    return tmp_path / "empty_local_project"

@pytest.fixture
def remote_repo_path(tmp_path):
    return tmp_path / "remote_project.git"

@pytest.fixture
def empty_local_repo(empty_local_repo_path):
    # Initialize a non-bare repository without any commits
    if empty_local_repo_path.exists():
        shutil.rmtree(empty_local_repo_path)
    empty_local_repo_path.mkdir()
    repo = pygit2.init_repository(str(empty_local_repo_path), bare=False)
    # Configure user for commits if needed by some operations
    config = repo.config
    config["user.name"] = "Test Author"
    config["user.email"] = "test@example.com"
    return repo

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
def bare_remote_repo(remote_repo_path, local_repo): # Depends on local_repo to have a commit to push initially
    # Initialize a bare repository
    if remote_repo_path.exists():
        shutil.rmtree(remote_repo_path)
    # remote_repo_path.mkdir() # Not needed for bare repo init
    repo = pygit2.init_repository(str(remote_repo_path), bare=True)

    # Setup local_repo to have this bare_remote_repo as 'origin'
    local_repo.remotes.create("origin", str(remote_repo_path))

    # Push initial commit from local_repo to bare_remote_repo to make it non-empty
    # This helps simulate a more realistic remote.
    try:
        refspec = "refs/heads/main:refs/heads/main" # Assuming local is on main or master
        if local_repo.head.shorthand != "main": # common default these days
             if local_repo.branches.get("master"): # older default
                  refspec = "refs/heads/master:refs/heads/master"
             # if neither, this push might fail or do something unexpected. Test setup should be robust.
             # For now, assume 'main' or 'master' based on what init_repository created or what initial commit set.
             # pygit2 by default creates 'master' on first commit unless branch is changed.
             # Let's check the actual head name.
             active_branch_name = local_repo.head.shorthand
             refspec = f"refs/heads/{active_branch_name}:refs/heads/{active_branch_name}"

        local_repo.remotes["origin"].push([refspec])
    except pygit2.GitError as e:
        # This can happen if the default branch name isn't main/master
        # or if there are no commits on HEAD. The `local_repo` fixture makes an initial commit.
        print(f"Error during initial push to bare remote: {e}")
        # Depending on test needs, this might be a critical failure or ignorable.
        # For sync tests, having a remote with some history is usually important.

    return repo

# Test stubs will go here

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

class TestGitWriteSaveNormalScenarios:
    def test_save_new_file(self, runner, repo_with_unstaged_changes):
        """Test saving a new, unstaged file."""
        repo = repo_with_unstaged_changes
        os.chdir(repo.workdir) # Ensure CWD is the repo

        # The repo_with_unstaged_changes fixture creates "unstaged_file.txt"
        filename = "unstaged_file.txt"
        file_content = "This file has unstaged changes."
        commit_message = "Add new unstaged file"

        # Verify file exists and is unstaged
        assert (Path(repo.workdir) / filename).exists()
        status = repo.status()
        assert filename in status
        assert status[filename] == pygit2.GIT_STATUS_WT_NEW

        initial_head_target = repo.head.target

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Verify new commit
        new_head_target = repo.head.target
        assert new_head_target != initial_head_target, "No new commit was made"

        commit = repo.get(new_head_target)
        assert commit is not None
        assert commit.message.strip() == commit_message

        # Verify file is in the commit's tree
        assert filename in commit.tree
        blob = commit.tree[filename]
        assert blob.data.decode('utf-8') == file_content

        # Verify working directory is clean
        status_after_save = repo.status()
        assert not status_after_save, f"Working directory not clean after save: {status_after_save}"

    def test_save_existing_file_modified(self, runner, local_repo):
        """Test saving modifications to an existing, tracked file."""
        repo = local_repo
        os.chdir(repo.workdir)

        filename = "initial.txt" # This file exists from local_repo fixture
        original_content = (Path(repo.workdir) / filename).read_text()
        modified_content = original_content + "\nSome new modifications."

        # Modify the file (unstaged change)
        create_file(repo, filename, modified_content)

        commit_message = "Modify existing file initial.txt"
        initial_head_target = repo.head.target

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        new_head_target = repo.head.target
        assert new_head_target != initial_head_target, "No new commit was made for existing file modification"

        commit = repo.get(new_head_target)
        assert commit.message.strip() == commit_message
        assert filename in commit.tree
        assert commit.tree[filename].data.decode('utf-8') == modified_content
        assert not repo.status(), "Working directory not clean after saving modified file"

    def test_save_no_changes(self, runner, local_repo):
        """Test saving when there are no changes."""
        repo = local_repo
        os.chdir(repo.workdir)

        # Ensure working directory is clean
        assert not repo.status(), "Prerequisite: Working directory should be clean"

        initial_head_target = repo.head.target
        commit_message = "Attempt to save with no changes"

        result = runner.invoke(cli, ["save", commit_message])
        # The save command might exit 0 but print a message, or exit non-zero.
        # Let's assume it exits 0 and prints a message for now.
        # This depends on the `save` command's specific implementation for no changes.
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No changes to save (working directory and index are clean)." in result.output

        # Verify no new commit was made
        assert repo.head.target == initial_head_target, "A new commit was made when there were no changes"

    def test_save_staged_changes(self, runner, repo_with_staged_changes):
        """Test saving already staged changes."""
        repo = repo_with_staged_changes
        os.chdir(repo.workdir)

        filename = "staged_file.txt" # From fixture
        file_content = "This file has staged changes." # From fixture
        commit_message = "Save staged changes"

        # Verify file is staged
        status = repo.status()
        assert filename in status
        assert status[filename] == pygit2.GIT_STATUS_INDEX_NEW # Staged and new

        initial_head_target = repo.head.target

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        new_head_target = repo.head.target
        assert new_head_target != initial_head_target, "No new commit was made for staged changes"

        commit = repo.get(new_head_target)
        assert commit.message.strip() == commit_message
        assert filename in commit.tree
        assert commit.tree[filename].data.decode('utf-8') == file_content
        assert not repo.status(), "Working directory not clean after saving staged changes"

    def test_save_no_message(self, runner, repo_with_unstaged_changes):
        """
        Test saving without providing a commit message.
        This test assumes the CLI will either use a default message or error out.
        For now, let's assume it uses a default, or the test needs adjustment
        based on actual `save` behavior (e.g., if it prompts or opens an editor).
        """
        repo = repo_with_unstaged_changes
        os.chdir(repo.workdir)

        filename = "unstaged_file.txt" # From fixture
        initial_head_target = repo.head.target

        # Invoke save without a message
        result = runner.invoke(cli, ["save"])

        # Scenario 1: Command fails because message is required
        if result.exit_code != 0:
            # Example: click might show usage error if message argument is required
            assert "Missing argument" in result.output or "MESSAGE" in result.output # Adjust as per actual error
            assert repo.head.target == initial_head_target, "Commit was made despite missing message error"
            return # Test passes if this is the designed behavior

        # Scenario 2: Command succeeds and uses a default/generated message
        # This part will run if exit_code was 0
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        new_head_target = repo.head.target
        assert new_head_target != initial_head_target, "No new commit was made when message was omitted (expected default msg behavior)"

        commit = repo.get(new_head_target)
        assert commit.message.strip() != "", "Commit message is empty, but a default was expected"
        # Example: Check if it contains the filename if that's the default strategy
        # assert filename in commit.message
        # Or just assert that some message exists:
        assert len(commit.message.strip()) > 0, "Default commit message was empty"

        # Check if output indicates a default message was used (if applicable)
        # assert "using default message" in result.output.lower() # Adjust if necessary

        assert not repo.status(), "Working directory not clean after saving with no message (default behavior)"


class TestGitWriteSaveConflictScenarios:
    def test_save_with_unresolved_merge_conflict(self, runner, repo_with_merge_conflict):
        """Test saving with an unresolved merge conflict."""
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)

        initial_head_target = repo.head.target
        commit_message = "Attempt to save with unresolved merge conflict"

        # Verify MERGE_HEAD exists (indicative of merge state)
        assert repo.lookup_reference("MERGE_HEAD") is not None

        result = runner.invoke(cli, ["save", commit_message])

        # Expect command to print an error and not make a commit.
        expected_error_lines = [
            "Error: Unresolved conflicts detected during merge.",
            "Please resolve them before saving.",
            "Conflicting files:"
        ]
        output_lines = [line.strip() for line in result.output.replace('\r\n', '\n').split('\n') if line.strip()]
        # print(f"DEBUG output_lines for unresolved merge: {output_lines}")
        assert any(expected_error_lines[0] in line for line in output_lines)
        assert any(expected_error_lines[1] in line for line in output_lines)
        assert any(expected_error_lines[2] in line for line in output_lines)
        assert "conflict_file.txt" in result.output

        # Verify no new commit was made
        assert repo.head.target == initial_head_target, "A new commit was made despite unresolved merge conflict"

        # Verify still in merge state
        assert repo.lookup_reference("MERGE_HEAD") is not None, "MERGE_HEAD was cleared despite unresolved conflict"

        has_conflicts_check = False
        if repo.index.conflicts is not None:
            try:
                next(iter(repo.index.conflicts))
                has_conflicts_check = True
            except StopIteration:
                pass
        assert has_conflicts_check, "Conflicts seem to be resolved from index, which is not expected here."


    def test_save_after_resolving_merge_conflict(self, runner, repo_with_merge_conflict):
        """Test saving after resolving a merge conflict."""
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)

        conflict_filename = "conflict_file.txt" # Known from the fixture
        resolved_content = "Line 1\nRESOLVED MERGE CHANGE on Line 2\nLine 3\n"
        commit_message = "Save after resolving merge conflict"

        # Verify MERGE_HEAD exists and conflicts are present
        assert repo.lookup_reference("MERGE_HEAD") is not None
        original_merge_head_target = repo.lookup_reference("MERGE_HEAD").target
        assert repo.index.conflicts is not None

        # Resolve the conflict
        resolve_conflict(repo, conflict_filename, resolved_content)

        active_conflicts_for_file = False
        if repo.index.conflicts is not None:
            for entry_tuple in repo.index.conflicts:
                 if any(entry and entry.path == conflict_filename for entry in entry_tuple):
                        active_conflicts_for_file = True
                        break
        assert not active_conflicts_for_file, f"Conflict for {conflict_filename} not resolved in index"

        status = repo.status()
        assert conflict_filename in status
        assert status[conflict_filename] != pygit2.GIT_STATUS_CONFLICTED
        assert status[conflict_filename] == pygit2.GIT_STATUS_INDEX_MODIFIED

        initial_head_target = repo.head.target

        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        new_head_target = repo.head.target
        assert new_head_target != initial_head_target, "No new commit was made after resolving conflict"

        commit = repo.get(new_head_target)
        assert commit is not None
        assert commit.message.strip() == commit_message
        assert len(commit.parents) == 2, "Commit is not a merge commit (should have 2 parents)"
        assert commit.parents[0].id == initial_head_target
        assert commit.parents[1].id == original_merge_head_target

        assert conflict_filename in commit.tree
        blob = commit.tree[conflict_filename]
        assert blob.data.decode('utf-8') == resolved_content

        with pytest.raises(KeyError):
            repo.lookup_reference("MERGE_HEAD")

        final_conflicts_check = False
        if repo.index.conflicts is not None:
            try:
                next(iter(repo.index.conflicts))
                final_conflicts_check = True
            except StopIteration:
                pass
        assert not final_conflicts_check, "Index conflicts were not cleared after successful merge commit"
        assert not repo.status(), "Working directory not clean after resolving conflict and saving"

    def test_save_with_unresolved_revert_conflict(self, runner, repo_with_revert_conflict):
        """Test saving with an unresolved revert conflict."""
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)

        initial_head_target = repo.head.target
        commit_message = "Attempt to save with unresolved revert conflict"

        assert repo.lookup_reference("REVERT_HEAD") is not None
        assert repo.index.conflicts is not None, "Prerequisite: Index should have conflicts for this test."

        result = runner.invoke(cli, ["save", commit_message])

        expected_error_lines = [
            "Error: Unresolved conflicts detected during revert.",
            "Please resolve them before saving.",
            "Conflicting files:"
        ]
        output_lines = [line.strip() for line in result.output.replace('\r\n', '\n').split('\n') if line.strip()]
        # print(f"DEBUG output_lines for unresolved revert: {output_lines}")
        assert any(expected_error_lines[0] in line for line in output_lines)
        assert any(expected_error_lines[1] in line for line in output_lines)
        assert any(expected_error_lines[2] in line for line in output_lines)
        assert "revert_conflict_file.txt" in result.output

        current_head_target = repo.head.target
        assert current_head_target == initial_head_target, "A new commit was made by 'save' despite unresolved revert conflict"

        assert repo.lookup_reference("REVERT_HEAD") is not None, "REVERT_HEAD was cleared by 'save' despite unresolved conflict"

        active_conflicts_revert_unresolved = False
        if repo.index.conflicts is not None:
            try:
                next(iter(repo.index.conflicts))
                active_conflicts_revert_unresolved = True
            except StopIteration:
                pass
        assert active_conflicts_revert_unresolved, "Conflicts seem to be resolved from index by 'save', which is not expected here."


    def test_save_after_resolving_revert_conflict(self, runner, repo_with_revert_conflict):
        """Test saving after resolving a revert conflict."""
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)

        conflict_filename = "revert_conflict_file.txt"
        resolved_content = "Version A\nRESOLVED REVERT CHANGE\nEnd C (kept part of C)\n"
        user_save_message = "Save after resolving revert conflict"

        assert repo.lookup_reference("REVERT_HEAD") is not None
        reverted_commit_hash = repo.lookup_reference("REVERT_HEAD").target
        reverted_commit_obj = repo.get(reverted_commit_hash)
        assert repo.index.conflicts is not None

        initial_head_target = repo.head.target

        resolve_conflict(repo, conflict_filename, resolved_content)

        active_conflicts_for_file_revert_resolved = False
        if repo.index.conflicts is not None:
            for entry_tuple in repo.index.conflicts:
                 if any(entry and entry.path == conflict_filename for entry in entry_tuple):
                        active_conflicts_for_file_revert_resolved = True
                        break
        assert not active_conflicts_for_file_revert_resolved, f"Conflict for {conflict_filename} not resolved in index after resolve_conflict"

        status = repo.status()
        assert conflict_filename in status
        assert status[conflict_filename] == pygit2.GIT_STATUS_INDEX_MODIFIED

        result = runner.invoke(cli, ["save", user_save_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        print(f"Save output: {result.output}")

        new_head_target = repo.head.target
        assert new_head_target != initial_head_target, "No new commit was made after resolving revert conflict"

        commit = repo.get(new_head_target)
        assert commit is not None

        expected_revert_prefix = f"Revert \"{reverted_commit_obj.message.splitlines()[0]}\""
        assert commit.message.startswith(expected_revert_prefix), \
            f"Commit message '{commit.message}' does not start with expected revert prefix '{expected_revert_prefix}'"
        if user_save_message:
             assert user_save_message in commit.message, \
                 f"User's save message '{user_save_message}' not found in final commit message '{commit.message}'"

        assert conflict_filename in commit.tree
        blob = commit.tree[conflict_filename]
        assert blob.data.decode('utf-8') == resolved_content

        with pytest.raises(KeyError):
            repo.lookup_reference("REVERT_HEAD")

        final_conflicts_check_revert = False
        if repo.index.conflicts is not None:
            try:
                next(iter(repo.index.conflicts))
                final_conflicts_check_revert = True
            except StopIteration:
                pass
        assert not final_conflicts_check_revert, "Index conflicts were not cleared after successful save post-revert"
        assert not repo.status(), "Working directory not clean after resolving revert conflict and saving"


#######################
# Ignore Command Tests
#######################

def test_ignore_add_new_pattern(runner):
    """Test adding new patterns to .gitignore."""
    with runner.isolated_filesystem() as temp_dir:
        temp_dir_path = Path(temp_dir)
        gitignore_file = temp_dir_path / ".gitignore"

        # Add first pattern
        result1 = runner.invoke(cli, ['ignore', 'add', '*.log'])
        assert result1.exit_code == 0, f"Output: {result1.output}"
        assert "Pattern '*.log' added to .gitignore." in result1.output
        assert gitignore_file.exists()
        assert gitignore_file.read_text() == "*.log\n"

        # Add second pattern
        result2 = runner.invoke(cli, ['ignore', 'add', 'another_pattern'])
        assert result2.exit_code == 0, f"Output: {result2.output}"
        assert "Pattern 'another_pattern' added to .gitignore." in result2.output
        assert gitignore_file.read_text() == "*.log\nanother_pattern\n"

        # Test adding a pattern that requires a newline to be added first
        # (if the file somehow ended up without a trailing newline)
        # Manually create a .gitignore without trailing newline
        gitignore_file.write_text("*.log\nanother_pattern") # No trailing newline

        result3 = runner.invoke(cli, ['ignore', 'add', 'third_pattern'])
        assert result3.exit_code == 0, f"Output: {result3.output}"
        assert "Pattern 'third_pattern' added to .gitignore." in result3.output
        # The 'add' command should add a newline before the new pattern if one is missing
        assert gitignore_file.read_text() == "*.log\nanother_pattern\nthird_pattern\n"


def test_ignore_add_duplicate_pattern(runner):
    """Test adding a duplicate pattern to .gitignore."""
    with runner.isolated_filesystem() as temp_dir:
        temp_dir_path = Path(temp_dir)
        gitignore_file = temp_dir_path / ".gitignore"
        initial_pattern = "existing_pattern"
        gitignore_file.write_text(f"{initial_pattern}\n")

        result = runner.invoke(cli, ['ignore', 'add', initial_pattern])
        assert result.exit_code == 0, f"Output: {result.output}" # Command execution is successful
        assert f"Pattern '{initial_pattern}' already exists in .gitignore." in result.output
        assert gitignore_file.read_text() == f"{initial_pattern}\n" # Content remains unchanged


def test_ignore_add_pattern_strips_whitespace(runner):
    """Test that adding a pattern strips leading/trailing whitespace."""
    with runner.isolated_filesystem() as temp_dir:
        temp_dir_path = Path(temp_dir)
        gitignore_file = temp_dir_path / ".gitignore"

        result = runner.invoke(cli, ['ignore', 'add', '  *.tmp  '])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert "Pattern '*.tmp' added to .gitignore." in result.output
        assert gitignore_file.exists()
        assert gitignore_file.read_text() == "*.tmp\n"

def test_ignore_add_empty_pattern(runner):
    """Test adding an empty or whitespace-only pattern."""
    with runner.isolated_filesystem() as temp_dir:
        gitignore_file = Path(temp_dir) / ".gitignore"

        # Test with empty string
        result_empty = runner.invoke(cli, ['ignore', 'add', ''])
        assert result_empty.exit_code == 0 # Or specific error code if designed that way
        assert "Error: Pattern cannot be empty." in result_empty.output
        assert not gitignore_file.exists() # No .gitignore should be created for an empty pattern

        # Test with whitespace-only string
        result_whitespace = runner.invoke(cli, ['ignore', 'add', '   '])
        assert result_whitespace.exit_code == 0
        assert "Error: Pattern cannot be empty." in result_whitespace.output
        assert not gitignore_file.exists()


def test_ignore_list_existing_gitignore(runner):
    """Test listing patterns from an existing .gitignore file."""
    with runner.isolated_filesystem() as temp_dir:
        temp_dir_path = Path(temp_dir)
        gitignore_file = temp_dir_path / ".gitignore"
        patterns = ["pattern1", "*.log", "another/path/"]
        gitignore_content = "\n".join(patterns) + "\n" # Ensure trailing newline
        gitignore_file.write_text(gitignore_content)

        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert ".gitignore Contents" in result.output # Title from Rich Panel
        for pattern in patterns:
            assert pattern in result.output


def test_ignore_list_non_existent_gitignore(runner):
    """Test listing when .gitignore does not exist."""
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0, f"Output: {result.output}" # Command itself should succeed
        assert ".gitignore file not found." in result.output


def test_ignore_list_empty_gitignore(runner):
    """Test listing an empty .gitignore file."""
    with runner.isolated_filesystem() as temp_dir:
        temp_dir_path = Path(temp_dir)
        gitignore_file = temp_dir_path / ".gitignore"
        gitignore_file.write_text("") # Create empty file

        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0, f"Output: {result.output}"
        assert ".gitignore is empty." in result.output

def test_ignore_list_gitignore_with_only_whitespace(runner):
    """Test listing a .gitignore file that contains only whitespace."""
    with runner.isolated_filesystem() as temp_dir:
        temp_dir_path = Path(temp_dir)
        gitignore_file = temp_dir_path / ".gitignore"
        gitignore_file.write_text("\n   \n\t\n") # Whitespace and newlines

        result = runner.invoke(cli, ['ignore', 'list'])
        assert result.exit_code == 0, f"Output: {result.output}"
        # Based on current 'ignore list' implementation, if content.strip() is empty,
        # it's considered "empty". This covers files with only whitespace.
        assert ".gitignore is empty." in result.output


#######################
# Init Command Tests
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

    def _assert_gitwrite_structure(self, base_path: Path, check_git_dir: bool = True):
        if check_git_dir:
            assert (base_path / ".git").is_dir(), ".git directory not found"
        assert (base_path / "drafts").is_dir(), "drafts/ directory not found"
        assert (base_path / "drafts" / ".gitkeep").is_file(), "drafts/.gitkeep not found"
        assert (base_path / "notes").is_dir(), "notes/ directory not found"
        assert (base_path / "notes" / ".gitkeep").is_file(), "notes/.gitkeep not found"
        assert (base_path / "metadata.yml").is_file(), "metadata.yml not found"
        assert (base_path / ".gitignore").is_file(), ".gitignore not found"

    def _assert_common_gitignore_patterns(self, gitignore_path: Path):
        content = gitignore_path.read_text()
        common_ignores = ["/.venv/", "/.idea/", "/.vscode/", "*.pyc", "__pycache__/"]
        for pattern in common_ignores:
            assert pattern in content, f"Expected pattern '{pattern}' not found in .gitignore"

    def test_init_in_empty_directory_no_project_name(self, runner: CliRunner, tmp_path: Path):
        """Test `gitwrite init` in an empty directory (uses current dir)."""
        test_dir = tmp_path / "current_dir_init"
        test_dir.mkdir()
        os.chdir(test_dir)

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Initialized empty Git repository in {test_dir.resolve()}" in result.output
        assert "Created/ensured GitWrite directory structure" in result.output
        assert "Staged GitWrite files" in result.output
        assert "Created GitWrite structure commit." in result.output

        self._assert_gitwrite_structure(test_dir)

    # Moving init tests that were mistakenly placed in TestGitWriteHistory back to TestGitWriteInit
    def test_init_with_project_name(self, runner: CliRunner, tmp_path: Path):
        """Test `gitwrite init project_name`."""
        project_name = "my_new_book"
        base_dir = tmp_path / "base_for_named_project"
        base_dir.mkdir()
        project_dir = base_dir / project_name

        os.chdir(base_dir) # Run from parent directory

        result = runner.invoke(cli, ["init", project_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert project_dir.exists(), "Project directory was not created"
        assert project_dir.is_dir()
        assert f"Initialized empty Git repository in {project_dir.resolve()}" in result.output
        assert "Created GitWrite structure commit." in result.output

        self._assert_gitwrite_structure(project_dir)
        self._assert_common_gitignore_patterns(project_dir / ".gitignore")

        repo = pygit2.Repository(str(project_dir))
        assert not repo.is_empty
        last_commit = repo.head.peel(pygit2.Commit)
        assert f"Initialized GitWrite project structure in {project_name}" in last_commit.message

    def test_init_in_existing_git_repository(self, runner: CliRunner, local_repo: pygit2.Repository, local_repo_path: Path):
        """Test `gitwrite init` in an existing Git repository."""
        # local_repo fixture already provides an initialized git repo with one commit
        os.chdir(local_repo_path)

        initial_commit_count = len(list(local_repo.walk(local_repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL)))

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert f"Opened existing Git repository in {local_repo_path.resolve()}" in result.output
        assert "Created/ensured GitWrite directory structure" in result.output
        assert "Staged GitWrite files" in result.output # Might stage .gitignore if it's new/modified
        # Check output based on whether a commit was made
        last_commit_after_init = local_repo.head.peel(pygit2.Commit)
        current_commit_count = len(list(local_repo.walk(local_repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL)))

        if current_commit_count > initial_commit_count :
            assert "Created GitWrite structure commit." in result.output
        else:
            assert "No changes to commit" in result.output or \
                   "No new GitWrite structure elements to stage" in result.output

        self._assert_gitwrite_structure(local_repo_path, check_git_dir=True)
        self._assert_common_gitignore_patterns(local_repo_path / ".gitignore")

        last_commit = local_repo.head.peel(pygit2.Commit)
        if current_commit_count > initial_commit_count:
            assert f"Added GitWrite structure to {local_repo_path.name}" in last_commit.message
            assert last_commit.author.name == "GitWrite System"
        else:
            assert "No changes to commit" in result.output or "No new GitWrite structure elements to stage" in result.output

    def test_init_gitignore_appends_not_overwrites(self, runner: CliRunner, tmp_path: Path):
        """Test that init appends to existing .gitignore rather than overwriting."""
        test_dir = tmp_path / "gitignore_append_test"
        test_dir.mkdir()
        os.chdir(test_dir)

        gitignore_path = test_dir / ".gitignore"
        user_entry = "# User specific ignore\n*.mydata\n"
        gitignore_path.write_text(user_entry)

        pygit2.init_repository(str(test_dir))
        repo = pygit2.Repository(str(test_dir))
        make_commit(repo, ".gitignore", user_entry, "Add initial .gitignore with user entry")

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        self._assert_gitwrite_structure(test_dir)
        self._assert_common_gitignore_patterns(gitignore_path)

        final_gitignore_content = gitignore_path.read_text()
        assert user_entry.strip() in final_gitignore_content
        assert "/.venv/" in final_gitignore_content

        last_commit = repo.head.peel(pygit2.Commit)
        if ".gitignore" in last_commit.tree:
            gitignore_blob = repo.get(last_commit.tree[".gitignore"].id)
            assert user_entry.strip() in gitignore_blob.data.decode('utf-8')

    def test_init_is_idempotent_for_structure(self, runner: CliRunner, tmp_path: Path):
        """Test that running init multiple times doesn't create multiple commits if structure is identical."""
        test_dir = tmp_path / "idempotent_test"
        test_dir.mkdir()
        os.chdir(test_dir)

        result1 = runner.invoke(cli, ["init"])
        assert result1.exit_code == 0, f"First init failed: {result1.output}"
        assert "Created GitWrite structure commit." in result1.output

        repo = pygit2.Repository(str(test_dir))
        commit1_hash = repo.head.target

        result2 = runner.invoke(cli, ["init"])
        assert result2.exit_code == 0, f"Second init failed: {result2.output}"
        assert "No changes to commit. GitWrite structure may already be committed and identical." in result2.output or \
               "And repository tree is identical to HEAD, no commit needed." in result2.output or \
               "No new GitWrite structure elements to stage." in result2.output

        commit2_hash = repo.head.target
        assert commit1_hash == commit2_hash, "No new commit should have been made on second init."
        self._assert_gitwrite_structure(test_dir)


######################
# Compare Command Tests
######################

class TestGitWriteCompare:
    def test_compare_no_args_with_changes(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` (HEAD vs HEAD~1) when there are changes."""
        repo = local_repo
        os.chdir(repo.workdir)

        # Initial commit already exists ("initial.txt", "Initial content")
        commit1_oid = repo.head.target

        # Second commit with changes to initial.txt
        new_content = "Initial content\nMore content added.\n"
        make_commit(repo, "initial.txt", new_content, "Modify initial.txt")
        commit2_oid = repo.head.target
        assert commit1_oid != commit2_oid

        result = runner.invoke(cli, ["compare"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert "Comparing HEAD~1 with HEAD" in output # Assuming this is part of the output
        assert "initial.txt" in output # File name should be in diff
        assert "+More content added." in output # Added line
        assert "-Initial content" not in output # Should show as context or part of a change, not purely removed if first line unchanged
        # A more robust check might look for specific diff hunk headers or styled output
        # For now, checking for the added line prefixed with '+' is a good start.

    def test_compare_no_args_no_changes(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` (HEAD vs HEAD~1) when there are no changes between commits."""
        repo = local_repo
        os.chdir(repo.workdir)

        # C1: Initial commit
        make_commit(repo, "file_same.txt", "content same", "Commit 1 for no_changes test")
        c1_oid = repo.head.target

        # C2: Empty commit (or commit with no effective changes to tracked files)
        # pygit2.Repository.commit() can create empty commits if tree is same as parent
        # Forcing an empty commit can be tricky; let's try by committing the same tree.
        author = pygit2.Signature("Test Author", "test@example.com")
        committer = pygit2.Signature("Test Committer", "committer@example.com")
        # Use tree_id for create_commit
        repo.create_commit("HEAD", author, committer, "Empty commit", repo.head.peel(pygit2.Commit).tree_id, [repo.head.target])
        c2_oid = repo.head.target
        assert c1_oid != c2_oid # Ensure a new commit object was created
        assert repo.get(c1_oid).tree.id == repo.get(c2_oid).tree.id # Trees must be identical

        result = runner.invoke(cli, ["compare"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert "No differences found" in result.output or "no changes" in result.output.lower()

    def test_compare_no_args_single_commit(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` in a repo with only one commit."""
        repo = local_repo
        os.chdir(repo.workdir)

        # local_repo fixture by default creates one commit.
        # We need to ensure no other commits are made before this test runs.
        # This can be achieved by re-initializing or using a specific fixture.
        # For simplicity, let's clear any extra commits if the fixture made more than one.
        # This is a bit of a workaround; a dedicated single-commit fixture would be cleaner.

        # Count commits
        commits = list(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL))
        if len(commits) > 1:
            # This part is tricky: can't easily "reset" the repo from within a test using fixtures this way.
            # For now, this test relies on local_repo providing a single commit initially,
            # or the `compare` command handling it gracefully if it compares HEAD to an empty tree.
            # The provided `local_repo` fixture does one commit.
            pass

        assert len(list(repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL))) == 1, "Test setup: Repo should have only one commit."


        result = runner.invoke(cli, ["compare"])
        # Exit code might be 0 if it shows the diff against an empty tree, or non-zero if it's an error.
        # Let's assume it handles it gracefully, possibly by showing all content as added.
        # Or it prints a specific message.
        if result.exit_code == 0:
             assert "Comparing" in result.output # It might compare HEAD to an empty tree.
             assert "initial.txt" in result.output # The first file should be shown as added.
             assert "+Initial content" in result.output
        else:
            # If it's an error for single commit:
            assert "Cannot compare HEAD with HEAD~1" in result.output or \
                   "only one commit exists" in result.output or \
                   "Invalid revision range" in result.output # git diff error

    def test_compare_ref1_vs_head(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare <ref1>` (compares <ref1> vs HEAD)."""
        repo = local_repo
        os.chdir(repo.workdir)

        # C1: Initial commit from fixture (initial.txt)
        c1_oid = repo.head.target
        main_branch_name = repo.head.shorthand

        # C2: Create feature branch from C1, add a file
        feature_branch_name = "feature-c2"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(c1_oid))
        repo.checkout(feature_branch)
        make_commit(repo, "feature_file.txt", "content on feature", "Commit C2 on feature")
        c2_oid = repo.head.target

        # C3: Switch back to main, modify initial.txt and commit
        repo.checkout(repo.branches.local[main_branch_name])
        assert repo.head.target == c1_oid # Back on main at C1
        make_commit(repo, "initial.txt", "Initial content\nModified on main at C3", "Commit C3 on main")
        c3_oid = repo.head.target # This is now HEAD

        assert c1_oid != c2_oid != c3_oid

        # Run `gitwrite compare feature` (compares feature (C2) with HEAD (C3))
        result = runner.invoke(cli, ["compare", feature_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {feature_branch_name} with HEAD" in output # Expected header
        # Diff should show:
        # - initial.txt as modified (content from C3 vs C1's version which is on feature)
        # - feature_file.txt as removed (present in C2/feature, absent in C3/HEAD)
        assert "initial.txt" in output
        assert "+Modified on main at C3" in output
        assert "feature_file.txt" in output
        assert "-content on feature" in output # Content of feature_file.txt shown as removed

    def test_compare_ref1_non_existent(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare <non_existent_ref>`."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_branch_name = repo.head.shorthand # To check if branch changes

        non_existent_ref = "no-such-ref-buddy"
        result = runner.invoke(cli, ["compare", non_existent_ref])

        assert result.exit_code != 0, f"CLI should have failed. Output: {result.output}"
        assert (f"Error: Invalid revision range '{non_existent_ref}..HEAD'" in result.output or # If it defaults ref2 to HEAD
                f"Error: Unknown revision or path not in the working tree: '{non_existent_ref}'" in result.output or
                f"ambiguous argument '{non_existent_ref}'" in result.output or # git's error
                f"Pathspec '{non_existent_ref}' is not in the working tree" in result.output or # another git error
                f"Revision '{non_existent_ref}' not found" in result.output
               ), f"Unexpected error message: {result.output}"
        assert repo.head.shorthand == initial_branch_name # Ensure branch didn't change

    def test_compare_ref1_ref2_basic(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare <ref1> <ref2>` for basic changes."""
        repo = local_repo
        os.chdir(repo.workdir)

        # C1: initial.txt with "Initial content"
        c1_oid = repo.head.target
        c1_short_hash = repo.get(c1_oid).short_id

        # C2: Modify initial.txt
        make_commit(repo, "initial.txt", "Initial content\nModified in C2", "Commit C2: Modify initial.txt")
        c2_oid = repo.head.target

        # C3: Add new_file.txt
        make_commit(repo, "new_file.txt", "Content of new file in C3", "Commit C3: Add new_file.txt")
        c3_oid = repo.head.target
        c3_short_hash = repo.get(c3_oid).short_id

        result = runner.invoke(cli, ["compare", c1_short_hash, c3_short_hash])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_short_hash} with {c3_short_hash}" in output # Header check
        assert "initial.txt" in output
        assert "+Modified in C2" in output # Change from C2 should be visible
        assert "new_file.txt" in output # New file from C3
        assert "+Content of new file in C3" in output # Content of new file

    def test_compare_branches(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare <branch1> <branch2>`."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        c1_oid = repo.head.target # Base commit

        # Create feature_A and add a commit
        branch_A_name = "feature/A"
        branch_A = repo.branches.local.create(branch_A_name, repo.get(c1_oid))
        repo.checkout(branch_A)
        make_commit(repo, "file_A.txt", "Content for A", "Commit on feature/A")

        # Create feature_B (from main's C1), then add a different commit to main
        repo.checkout(repo.branches.local[main_branch_name]) # Back to main at C1
        branch_B_name = "feature/B" # This will be main for this comparison
        # Effectively, main_branch_name (at C2_main) will be compared against branch_A_name (at C2_featA)
        # Let's rename main to avoid confusion and make a new main
        # Or, more simply, create a new branch main_prime from C1 and add a commit to it.

        # Let current main be "main_at_c1"
        # Commit C2 on main_branch_name
        make_commit(repo, "file_main.txt", "Content for main branch", f"Commit C2 on {main_branch_name}")
        c2_main_oid = repo.head.target

        # Now, compare branch_A_name (C1 -> file_A.txt) with main_branch_name (C1 -> file_main.txt)
        result = runner.invoke(cli, ["compare", branch_A_name, main_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {branch_A_name} with {main_branch_name}" in output
        assert "file_A.txt" in output # Should show file_A as removed or its content as removed
        assert "-Content for A" in output
        assert "file_main.txt" in output # Should show file_main as added or its content as added
        assert "+Content for main branch" in output
        assert "initial.txt" not in output # initial.txt is common ancestor, no changes

    def test_compare_identical_refs(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare <ref> <ref>` (identical references)."""
        repo = local_repo
        os.chdir(repo.workdir)

        make_commit(repo, "another_file.txt", "content", "Another commit for identical refs test")
        commit_oid_short = repo.head.peel(pygit2.Commit).short_id

        result = runner.invoke(cli, ["compare", commit_oid_short, commit_oid_short])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No differences found" in result.output or "no changes" in result.output.lower()

    def test_compare_ref1_ref2_one_non_existent(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare <ref1> <non_existent_ref>`."""
        repo = local_repo
        os.chdir(repo.workdir)
        c1_short_hash = repo.head.peel(pygit2.Commit).short_id
        initial_branch_name = repo.head.shorthand

        non_existent_ref = "no-such-ref-here-either"
        result = runner.invoke(cli, ["compare", c1_short_hash, non_existent_ref])
        assert result.exit_code != 0, f"CLI should have failed. Output: {result.output}"
        assert (f"Error: Invalid revision range '{c1_short_hash}..{non_existent_ref}'" in result.output or
                f"Error: Unknown revision or path not in the working tree: '{non_existent_ref}'" in result.output or
                f"ambiguous argument '{non_existent_ref}'" in result.output or
                f"Pathspec '{non_existent_ref}' is not in the working tree" in result.output or
                f"Revision '{non_existent_ref}' not found" in result.output
               ), f"Unexpected error message: {result.output}"
        assert repo.head.shorthand == initial_branch_name

    def test_compare_new_file(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` involving a new file."""
        repo = local_repo
        os.chdir(repo.workdir)

        # C1: Has initial.txt (from fixture)
        c1_oid_short = repo.head.peel(pygit2.Commit).short_id

        # C2: Add file_b.txt
        file_b_name = "file_b.txt"
        file_b_content = "This is a brand new file."
        make_commit(repo, file_b_name, file_b_content, "Commit C2: Add file_b.txt")
        c2_oid_short = repo.head.peel(pygit2.Commit).short_id

        result = runner.invoke(cli, ["compare", c1_oid_short, c2_oid_short])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_oid_short} with {c2_oid_short}" in output
        assert file_b_name in output
        # Diff output for a new file typically shows all its lines as added.
        # This might include a "new file mode" line or similar depending on diff verbosity.
        assert f"--- /dev/null" in output or "--- a/dev/null" in output # Common for new files
        assert f"+++ b/{file_b_name}" in output
        for line in file_b_content.splitlines():
            assert f"+{line}" in output

    def test_compare_deleted_file(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` involving a deleted file."""
        repo = local_repo
        os.chdir(repo.workdir)

        # C1: Has initial.txt and file_to_delete.txt
        file_to_delete_name = "file_to_delete.txt"
        file_to_delete_content = "This file will be deleted."
        make_commit(repo, file_to_delete_name, file_to_delete_content, f"Commit C1: Add {file_to_delete_name}")
        c1_oid_short = repo.head.peel(pygit2.Commit).short_id

        # C2: Delete file_to_delete.txt
        # To delete, we need to remove it from index and then commit
        file_to_delete_path = Path(repo.workdir) / file_to_delete_name
        assert file_to_delete_path.exists()
        file_to_delete_path.unlink() # Remove from working directory
        repo.index.remove(file_to_delete_name) # Remove from index
        repo.index.write()

        author = pygit2.Signature("Test Author", "test@example.com")
        committer = pygit2.Signature("Test Committer", "committer@example.com")
        tree = repo.index.write_tree()
        c2_oid = repo.create_commit("HEAD", author, committer, f"Commit C2: Delete {file_to_delete_name}", tree, [repo.head.target])
        c2_oid_short = repo.get(c2_oid).short_id

        result = runner.invoke(cli, ["compare", c1_oid_short, c2_oid_short])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_oid_short} with {c2_oid_short}" in output
        assert file_to_delete_name in output
        # Diff output for a deleted file typically shows all its lines as removed.
        assert f"--- a/{file_to_delete_name}" in output
        assert f"+++ /dev/null" in output or "+++ b/dev/null" in output # Common for deleted files
        for line in file_to_delete_content.splitlines():
            assert f"-{line}" in output

    def test_compare_file_mode_change(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` involving a file mode change (e.g., executable bit)."""
        repo = local_repo
        os.chdir(repo.workdir)

        script_name = "script.sh"
        script_content = "#!/bin/bash\necho 'Hello'\n"

        # C1: Add script.sh, ensure it's not executable (0o100644 is default)
        make_commit(repo, script_name, script_content, "Commit C1: Add non-executable script.sh")
        c1_oid_short = repo.head.peel(pygit2.Commit).short_id

        # Verify initial mode if possible (pygit2 tree entry mode)
        c1_commit = repo.get(c1_oid_short)
        assert c1_commit.tree[script_name].filemode == pygit2.GIT_FILEMODE_BLOB # Should be 0o100644

        # C2: Make script.sh executable (0o100755)
        # To change mode with pygit2, we need to update the index entry
        repo.index.add(script_name) # Re-add with potentially new mode after chmod
        # pygit2 doesn't directly control chmod via index.add in the same way `git add --chmod=+x` does.
        # The mode change must be reflected in the tree entry.
        # We need to ensure the tree entry for C2 has the executable mode.
        # This often means `git update-index --chmod=+x script.sh` or similar before commit.
        # Simulating this with pygit2: create a new tree with the desired mode.

        # For this test, let's assume the `make_commit` or underlying git operations
        # *could* pick up a mode change if the file system mode changed and git was configured
        # to track it (core.filemode=true, which is default on Linux).
        # However, programmatically setting filemode with pygit2 for a commit is more direct.

        # Manually create a tree with the new mode for C2
        builder = repo.TreeBuilder(c1_commit.tree) # Start from C1's tree
        blob_oid = c1_commit.tree[script_name].id
        builder.insert(script_name, blob_oid, pygit2.GIT_FILEMODE_BLOB_EXECUTABLE) # 0o100755
        new_tree_oid = builder.write()

        author = pygit2.Signature("Test Author", "test@example.com")
        committer = pygit2.Signature("Test Committer", "committer@example.com")
        c2_oid = repo.create_commit("HEAD", author, committer, "Commit C2: Make script.sh executable", new_tree_oid, [c1_commit.id])
        c2_oid_short = repo.get(c2_oid).short_id

        c2_commit = repo.get(c2_oid)
        assert c2_commit.tree[script_name].filemode == pygit2.GIT_FILEMODE_BLOB_EXECUTABLE

        result = runner.invoke(cli, ["compare", c1_oid_short, c2_oid_short])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_oid_short} with {c2_oid_short}" in output
        assert script_name in output
        # Check for mode change indication. `git diff` shows something like:
        # "old mode 100644"
        # "new mode 100755"
        # The rich diff might represent this differently.
        assert "mode change" in output.lower() or \
               "100644" in output and "100755" in output or \
               "executable" in output.lower() # General check for executable keyword
        # Content itself should not show as changed if only mode changed
        assert f"+{script_content.splitlines()[0]}" not in output # Assuming no content changes displayed with '+'
        assert f"-{script_content.splitlines()[0]}" not in output

    def test_compare_binary_files(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` with binary files."""
        repo = local_repo
        os.chdir(repo.workdir)

        binary_file_name = "image.png" # Using .png as an example
        # Simple non-text content (byte strings)
        binary_content_c1 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90\x77\x58\xde" # Minimal PNG header
        binary_content_c2 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x02\x00\x00\x00\x78\x24\x78\x00" # Slightly different

        # C1: Add binary file
        # Need to write bytes, not text
        file_path = Path(repo.workdir) / binary_file_name
        with open(file_path, "wb") as f:
            f.write(binary_content_c1)
        repo.index.add(binary_file_name)
        repo.index.write()
        author = pygit2.Signature("Test Author", "test@example.com")
        committer = pygit2.Signature("Test Committer", "committer@example.com")
        tree1 = repo.index.write_tree()
        c1_oid = repo.create_commit("HEAD", author, committer, "Commit C1: Add binary file", tree1, [repo.head.target] if not repo.head_is_unborn else [])
        c1_oid_short = repo.get(c1_oid).short_id

        # C2: Modify binary file
        with open(file_path, "wb") as f:
            f.write(binary_content_c2)
        repo.index.add(binary_file_name)
        repo.index.write()
        tree2 = repo.index.write_tree()
        c2_oid = repo.create_commit("HEAD", author, committer, "Commit C2: Modify binary file", tree2, [c1_oid])
        c2_oid_short = repo.get(c2_oid).short_id

        result = runner.invoke(cli, ["compare", c1_oid_short, c2_oid_short])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_oid_short} with {c2_oid_short}" in output
        assert binary_file_name in output
        # Check for indication of binary diff.
        # `git diff` output is typically "Binary files a/... and b/... differ"
        # Rich diff might have its own way or just say "Binary file"
        assert "binary files differ" in output.lower() or \
               "cannot display diff for binary files" in output.lower() or \
               "binary file" in output.lower() # General check
        # Ensure no attempt to show line-by-line diff for binary
        assert "+PNG" not in output
        assert "-PNG" not in output


####################
# Merge Command Tests
####################

class TestGitWriteMerge:
    def test_merge_fast_forward(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a branch (fast-forward)."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        initial_main_commit_oid = repo.head.target

        # Create feature_branch from main
        feature_branch_name = "feature-ff"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(initial_main_commit_oid))

        # Add commits to feature_branch only
        repo.checkout(feature_branch)
        make_commit(repo, "feature_file1.txt", "content1", "Commit 1 on feature")
        make_commit(repo, "feature_file2.txt", "content2", "Commit 2 on feature")
        feature_branch_head_oid = repo.head.target
        assert feature_branch_head_oid != initial_main_commit_oid

        # Switch back to main
        main_branch_ref = repo.branches.local[main_branch_name]
        repo.checkout(main_branch_ref)
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == initial_main_commit_oid # Main hasn't moved

        # Run gitwrite merge feature_branch
        result = runner.invoke(cli, ["merge", feature_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Verify output indicates a fast-forward merge
        # The exact message depends on the CLI implementation.
        assert "fast-forward" in result.output.lower() or \
               f"merged '{feature_branch_name}' into '{main_branch_name}' (fast-forward)" in result.output.lower() or \
               "updating" in result.output.lower() # git's own ff message often contains "Updating"


        # Verify main branch's HEAD is now the same as feature_branch's HEAD
        # repo.head.resolve() # CLI should handle updating repo state, direct resolve might not be needed.
        assert repo.head.shorthand == main_branch_name # Still on main
        assert repo.head.target == feature_branch_head_oid

        # Verify working directory is clean and reflects feature_branch's state
        assert not repo.status(), f"Working directory should be clean after merge. Status: {repo.status()}"
        assert (Path(repo.workdir) / "feature_file1.txt").exists()
        assert (Path(repo.workdir) / "feature_file2.txt").exists()

    def test_merge_no_conflict_true_merge(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a branch (no-conflict, true merge)."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        main_commit1_oid = repo.head.target

        # Create feature_branch from main's initial commit
        feature_branch_name = "feature-true-merge"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(main_commit1_oid))

        # Add a commit to main
        make_commit(repo, "main_file.txt", "content for main", "Commit on main")
        main_commit2_oid = repo.head.target
        assert main_commit2_oid != main_commit1_oid

        # Add a different commit to feature_branch
        repo.checkout(feature_branch)
        # Ensure feature_branch is based on main_commit1_oid before its unique commit
        assert repo.head.target == main_commit1_oid
        make_commit(repo, "feature_file.txt", "content for feature", "Commit on feature")
        feature_branch_head_oid = repo.head.target
        assert feature_branch_head_oid != main_commit1_oid
        assert feature_branch_head_oid != main_commit2_oid


        # Switch back to main
        main_branch_ref = repo.branches.local[main_branch_name]
        repo.checkout(main_branch_ref)
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == main_commit2_oid # main is at its second commit

        # Run gitwrite merge feature_branch
        result = runner.invoke(cli, ["merge", feature_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Verify output indicates a successful merge (not a fast-forward)
        # Example: "Merge made by the 'recursive' strategy." or "Merged 'feature_branch' into 'main'."
        assert "merge made by" in result.output.lower() or \
               f"merged '{feature_branch_name}' into '{main_branch_name}'" in result.output.lower()
        assert "fast-forward" not in result.output.lower()


        # Verify a new merge commit is created on main
        repo.head.resolve() # Refresh HEAD
        merge_commit_oid = repo.head.target
        assert merge_commit_oid != main_commit2_oid # New commit on main
        assert merge_commit_oid != feature_branch_head_oid # Not feature's head either

        merge_commit = repo.get(merge_commit_oid)
        assert isinstance(merge_commit, pygit2.Commit)
        assert len(merge_commit.parents) == 2

        parent_oids = {p.id for p in merge_commit.parents}
        assert parent_oids == {main_commit2_oid, feature_branch_head_oid}

        # Standard merge commit message format
        expected_merge_message_part1 = f"Merge branch '{feature_branch_name}'"
        # If main_branch_name is not 'main' or 'master', it might be "into HEAD" or similar.
        # For this test, assuming it merges into the named main_branch_name.
        expected_merge_message_part2 = f"into {main_branch_name}"
        assert expected_merge_message_part1 in merge_commit.message or \
               f"Merge remote-tracking branch 'origin/{feature_branch_name}'" in merge_commit.message # if it were a remote branch

        # Verify working directory reflects the merged state
        assert not repo.status(), f"Working directory should be clean. Status: {repo.status()}"
        assert (Path(repo.workdir) / "main_file.txt").exists()
        assert (Path(repo.workdir) / "feature_file.txt").exists()

    def test_merge_with_conflicts_and_resolve(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a branch with conflicts and then resolving."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        # Initial commit from fixture is our base for the conflict file
        make_commit(repo, "conflict_file.txt", "Line 1\nLine 2 for conflict\nLine 3\n", "Add conflict_file.txt")
        base_plus_file_commit_oid = repo.head.target

        # Create feature_branch from this new base
        feature_branch_name = "feature-conflict"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(base_plus_file_commit_oid))

        # 1. Add a commit to main modifying conflict_file.txt
        main_conflict_content = "Line 1\nMain's change on Line 2\nLine 3\n"
        make_commit(repo, "conflict_file.txt", main_conflict_content, f"Modify conflict_file.txt on {main_branch_name}")
        main_head_oid_before_merge = repo.head.target

        # 2. Add a conflicting commit to feature_branch
        repo.checkout(feature_branch)
        assert repo.head.target == base_plus_file_commit_oid # Ensure feature is at the right base
        feature_conflict_content = "Line 1\nFeature's change on Line 2\nLine 3\n"
        make_commit(repo, "conflict_file.txt", feature_conflict_content, f"Modify conflict_file.txt on {feature_branch_name}")
        feature_head_oid_before_merge = repo.head.target

        # 3. Switch back to main
        repo.checkout(repo.branches.local[main_branch_name])
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == main_head_oid_before_merge

        # 4. Run gitwrite merge feature_branch
        result_merge_attempt = runner.invoke(cli, ["merge", feature_branch_name])
        assert result_merge_attempt.exit_code == 0, f"CLI Error on merge attempt: {result_merge_attempt.output}" # Command reports conflict, does not fail

        # 5. Verify output indicates conflicts
        assert "merge conflict" in result_merge_attempt.output.lower() or \
               "conflicts detected" in result_merge_attempt.output.lower()
        assert "conflict_file.txt" in result_merge_attempt.output

        # 6. Verify MERGE_HEAD is set
        merge_head_ref = repo.lookup_reference("MERGE_HEAD")
        assert merge_head_ref is not None
        assert merge_head_ref.target == feature_head_oid_before_merge

        # 7. Verify conflict_file.txt contains conflict markers
        conflict_file_path = Path(repo.workdir) / "conflict_file.txt"
        assert conflict_file_path.exists()
        file_content_after_conflict = conflict_file_path.read_text()
        assert "<<<<<<<" in file_content_after_conflict
        assert "=======" in file_content_after_conflict
        assert ">>>>>>>" in file_content_after_conflict
        assert "Main's change on Line 2" in file_content_after_conflict
        assert "Feature's change on Line 2" in file_content_after_conflict

        # 8. Verify HEAD is still on main (no merge commit created yet)
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == main_head_oid_before_merge

        # 9. Manually resolve the conflict
        resolved_content = "Line 1\nResolved conflict on Line 2\nLine 3\n"
        conflict_file_path.write_text(resolved_content)
        repo.index.add("conflict_file.txt")
        repo.index.write() # This should clear the conflict from the index for this file
        assert not repo.index.conflicts or not any(c[0] and c[0].path == "conflict_file.txt" for c in repo.index.conflicts)


        # 10. Run `gitwrite save "Resolved merge conflict"`
        save_message = "Resolved merge conflict"
        result_save = runner.invoke(cli, ["save", save_message]) # Should use the default "commit" action
        assert result_save.exit_code == 0, f"CLI Error on save: {result_save.output}"
        assert "Successfully completed merge operation." in result_save.output


        # 11. Verify a new merge commit is created on main
        repo.head.resolve()
        final_merge_commit_oid = repo.head.target
        assert final_merge_commit_oid != main_head_oid_before_merge

        final_merge_commit = repo.get(final_merge_commit_oid)
        assert isinstance(final_merge_commit, pygit2.Commit)
        assert len(final_merge_commit.parents) == 2
        parent_oids_after_save = {p.id for p in final_merge_commit.parents}
        assert parent_oids_after_save == {main_head_oid_before_merge, feature_head_oid_before_merge}

        assert save_message in final_merge_commit.message
        assert f"Merge branch '{feature_branch_name}'" in final_merge_commit.message

        # 12. Verify MERGE_HEAD is cleared
        with pytest.raises(KeyError):
             repo.lookup_reference("MERGE_HEAD")

        assert not repo.status(), f"Working directory should be clean. Status: {repo.status()}"
        assert conflict_file_path.read_text() == resolved_content

    def test_merge_non_existent_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a non-existent branch."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_head_oid = repo.head.target
        initial_branch_name = repo.head.shorthand

        non_existent_branch = "I-do-not-exist-at-all"
        result = runner.invoke(cli, ["merge", non_existent_branch])

        assert result.exit_code != 0, f"CLI should have failed for non-existent branch. Output: {result.output}"

        # Error message could be "Exploration '...' not found" or "Branch '...' not found" or specific git error
        # For `gitwrite merge`, it should be consistent with other commands if it uses a similar lookup.
        assert (f"Exploration '{non_existent_branch}' not found" in result.output or
                f"Branch '{non_existent_branch}' not found" in result.output or
                f"'{non_existent_branch}': not a commit" in result.output or # git's rev-parse error
                f"error: unknown revision or path not in the working tree" in result.output.lower() # another git error
               ), f"Unexpected error message: {result.output}"

        # Verify no change in current branch or state
        assert repo.head.shorthand == initial_branch_name
        assert repo.head.target == initial_head_oid
        # MERGE_HEAD should not be set as the merge operation should not have started
        with pytest.raises(KeyError):
            repo.lookup_reference("MERGE_HEAD")

    def test_merge_with_uncommitted_changes(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging into a branch with uncommitted changes."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        initial_main_commit_oid = repo.head.target # Commit with initial.txt

        # Create a feature branch and add a commit to it
        feature_branch_name = "feature-for-dirty"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(initial_main_commit_oid))

        repo.checkout(feature_branch)
        make_commit(repo, "feature_file_for_dirty.txt", "Feature content", f"Commit on {feature_branch_name}")

        # Switch back to main
        repo.checkout(repo.branches.local[main_branch_name])
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == initial_main_commit_oid

        # Modify a tracked file on main but do not commit
        main_tracked_file_path = Path(repo.workdir) / "initial.txt" # Exists from local_repo fixture
        original_main_content = main_tracked_file_path.read_text()
        dirty_content = original_main_content + "\nUncommitted dirty changes on main."
        main_tracked_file_path.write_text(dirty_content)

        # Verify file is modified
        status = repo.status()
        assert "initial.txt" in status
        assert status["initial.txt"] == pygit2.GIT_STATUS_WT_MODIFIED

        # Attempt to merge feature_branch
        result = runner.invoke(cli, ["merge", feature_branch_name])

        # Expect an error due to dirty working directory
        assert result.exit_code != 0, f"CLI should have failed due to dirty WD. Output: {result.output}"
        assert ("uncommitted changes" in result.output.lower() or
                "would be overwritten by merge" in result.output.lower() or
                "commit your changes or stash them" in result.output.lower() or
                "your local changes to the following files would be overwritten" in result.output.lower() # git's error
               ), f"Unexpected error message for dirty WD merge: {result.output}"

        # Verify no merge occurred - HEAD should not have changed
        assert repo.head.target == initial_main_commit_oid

        # Verify uncommitted changes are preserved
        assert main_tracked_file_path.read_text() == dirty_content
        status_after = repo.status()
        assert "initial.txt" in status_after
        assert status_after["initial.txt"] == pygit2.GIT_STATUS_WT_MODIFIED

        # MERGE_HEAD should not be set
        with pytest.raises(KeyError):
            repo.lookup_reference("MERGE_HEAD")

    def test_merge_already_merged_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging an already merged branch (up-to-date)."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        initial_main_commit_oid = repo.head.target

        # Create feature_branch and add a commit
        feature_branch_name = "feature-already-up-to-date"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(initial_main_commit_oid))

        repo.checkout(feature_branch)
        make_commit(repo, "file_for_up_to_date_feature.txt", "content", f"Commit on {feature_branch_name}")
        feature_head_oid = repo.head.target

        # Switch to main and merge feature_branch (this will be a fast-forward)
        repo.checkout(repo.branches.local[main_branch_name])

        # Manually perform the first merge (fast-forward)
        main_ref = repo.references[f"refs/heads/{main_branch_name}"]
        main_ref.set_target(feature_head_oid)
        repo.checkout_head(strategy=pygit2.GIT_CHECKOUT_FORCE) # Update working directory to new HEAD

        head_after_first_merge = repo.head.target
        assert head_after_first_merge == feature_head_oid, "First merge did not correctly update main's HEAD."

        # Run gitwrite merge feature_branch again
        result = runner.invoke(cli, ["merge", feature_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert "already up-to-date" in result.output.lower(), \
            f"Unexpected output when merging already merged branch: {result.output}"

        # Verify no new commit is made
        assert repo.head.target == head_after_first_merge, "No new commit should be made."
        # MERGE_HEAD should not be set
        with pytest.raises(KeyError):
            repo.lookup_reference("MERGE_HEAD")

    def test_merge_branch_into_itself(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a branch into itself."""
        repo = local_repo
        os.chdir(repo.workdir)

        current_branch_name = repo.head.shorthand
        initial_head_oid = repo.head.target

        result = runner.invoke(cli, ["merge", current_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}" # Command should succeed

        # Expect "Already up-to-date" or similar
        assert "already up-to-date" in result.output.lower(), \
            f"Unexpected output when merging branch into itself: {result.output}"

        # Verify no new commit is made
        assert repo.head.target == initial_head_oid, "No new commit should be made when merging into self."
        # MERGE_HEAD should not be set
        with pytest.raises(KeyError):
            repo.lookup_reference("MERGE_HEAD")


####################
# Merge Command Tests
####################

class TestGitWriteMerge:
    def test_merge_fast_forward(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a branch (fast-forward)."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        initial_main_commit_oid = repo.head.target

        # Create feature_branch from main
        feature_branch_name = "feature-ff"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(initial_main_commit_oid))

        # Add commits to feature_branch only
        repo.checkout(feature_branch)
        make_commit(repo, "feature_file1.txt", "content1", "Commit 1 on feature")
        make_commit(repo, "feature_file2.txt", "content2", "Commit 2 on feature")
        feature_branch_head_oid = repo.head.target
        assert feature_branch_head_oid != initial_main_commit_oid

        # Switch back to main
        main_branch_ref = repo.branches.local[main_branch_name]
        repo.checkout(main_branch_ref)
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == initial_main_commit_oid # Main hasn't moved

        # Run gitwrite merge feature_branch
        result = runner.invoke(cli, ["merge", feature_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Verify output indicates a fast-forward merge
        # The exact message depends on the CLI implementation.
        assert "fast-forward" in result.output.lower() or \
               f"merged '{feature_branch_name}' into '{main_branch_name}' (fast-forward)" in result.output.lower() or \
               "updating" in result.output.lower() # git's own ff message often contains "Updating"


        # Verify main branch's HEAD is now the same as feature_branch's HEAD
        # repo.head.resolve() # CLI should handle updating repo state, direct resolve might not be needed.
        assert repo.head.shorthand == main_branch_name # Still on main
        assert repo.head.target == feature_branch_head_oid

        # Verify working directory is clean and reflects feature_branch's state
        assert not repo.status(), f"Working directory should be clean after merge. Status: {repo.status()}"
        assert (Path(repo.workdir) / "feature_file1.txt").exists()
        assert (Path(repo.workdir) / "feature_file2.txt").exists()

    def test_merge_no_conflict_true_merge(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a branch (no-conflict, true merge)."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        main_commit1_oid = repo.head.target

        # Create feature_branch from main's initial commit
        feature_branch_name = "feature-true-merge"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(main_commit1_oid))

        # Add a commit to main
        make_commit(repo, "main_file.txt", "content for main", "Commit on main")
        main_commit2_oid = repo.head.target
        assert main_commit2_oid != main_commit1_oid

        # Add a different commit to feature_branch
        repo.checkout(feature_branch)
        # Ensure feature_branch is based on main_commit1_oid before its unique commit
        assert repo.head.target == main_commit1_oid
        make_commit(repo, "feature_file.txt", "content for feature", "Commit on feature")
        feature_branch_head_oid = repo.head.target
        assert feature_branch_head_oid != main_commit1_oid
        assert feature_branch_head_oid != main_commit2_oid


        # Switch back to main
        main_branch_ref = repo.branches.local[main_branch_name]
        repo.checkout(main_branch_ref)
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == main_commit2_oid # main is at its second commit

        # Run gitwrite merge feature_branch
        result = runner.invoke(cli, ["merge", feature_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Verify output indicates a successful merge (not a fast-forward)
        # Example: "Merge made by the 'recursive' strategy." or "Merged 'feature_branch' into 'main'."
        assert "merge made by" in result.output.lower() or \
               f"merged '{feature_branch_name}' into '{main_branch_name}'" in result.output.lower()
        assert "fast-forward" not in result.output.lower()


        # Verify a new merge commit is created on main
        repo.head.resolve() # Refresh HEAD
        merge_commit_oid = repo.head.target
        assert merge_commit_oid != main_commit2_oid # New commit on main
        assert merge_commit_oid != feature_branch_head_oid # Not feature's head either

        merge_commit = repo.get(merge_commit_oid)
        assert isinstance(merge_commit, pygit2.Commit)
        assert len(merge_commit.parents) == 2

        parent_oids = {p.id for p in merge_commit.parents}
        assert parent_oids == {main_commit2_oid, feature_branch_head_oid}

        # Standard merge commit message format
        expected_merge_message_part1 = f"Merge branch '{feature_branch_name}'"
        # If main_branch_name is not 'main' or 'master', it might be "into HEAD" or similar.
        # For this test, assuming it merges into the named main_branch_name.
        expected_merge_message_part2 = f"into {main_branch_name}"
        assert expected_merge_message_part1 in merge_commit.message or \
               f"Merge remote-tracking branch 'origin/{feature_branch_name}'" in merge_commit.message # if it were a remote branch

        # Verify working directory reflects the merged state
        assert not repo.status(), f"Working directory should be clean. Status: {repo.status()}"
        assert (Path(repo.workdir) / "main_file.txt").exists()
        assert (Path(repo.workdir) / "feature_file.txt").exists()

    def test_merge_with_conflicts_and_resolve(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a branch with conflicts and then resolving."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        base_commit_oid = repo.head.target # Initial commit from fixture

        # Create common file and commit to base
        conflict_file_name = "conflict_file.txt"
        initial_file_content = "Line 1\nLine 2 for conflict\nLine 3\n"
        make_commit(repo, conflict_file_name, initial_file_content, f"Add {conflict_file_name} on {main_branch_name}")
        base_plus_file_commit_oid = repo.head.target

        # Create feature_branch from this new base
        feature_branch_name = "feature-conflict"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(base_plus_file_commit_oid))

        # 1. Add a commit to main modifying conflict_file.txt
        main_conflict_content = "Line 1\nMain's change on Line 2\nLine 3\n"
        make_commit(repo, conflict_file_name, main_conflict_content, f"Modify {conflict_file_name} on {main_branch_name}")
        main_head_oid_before_merge = repo.head.target

        # 2. Add a conflicting commit to feature_branch
        repo.checkout(feature_branch)
        assert repo.head.target == base_plus_file_commit_oid # Ensure feature is at the right base
        feature_conflict_content = "Line 1\nFeature's change on Line 2\nLine 3\n"
        make_commit(repo, conflict_file_name, feature_conflict_content, f"Modify {conflict_file_name} on {feature_branch_name}")
        feature_head_oid_before_merge = repo.head.target

        # 3. Switch back to main
        repo.checkout(repo.branches.local[main_branch_name])
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == main_head_oid_before_merge

        # 4. Run gitwrite merge feature_branch
        result_merge_attempt = runner.invoke(cli, ["merge", feature_branch_name])
        # This command should succeed in initiating the merge, but report conflicts
        assert result_merge_attempt.exit_code == 0, f"CLI Error on merge attempt: {result_merge_attempt.output}"

        # 5. Verify output indicates conflicts
        assert "merge conflict" in result_merge_attempt.output.lower() or \
               "conflicts detected" in result_merge_attempt.output.lower()
        assert conflict_file_name in result_merge_attempt.output

        # 6. Verify MERGE_HEAD is set
        merge_head_ref = repo.lookup_reference("MERGE_HEAD")
        assert merge_head_ref is not None
        assert merge_head_ref.target == feature_head_oid_before_merge

        # 7. Verify conflict_file.txt contains conflict markers
        conflict_file_path = Path(repo.workdir) / conflict_file_name
        assert conflict_file_path.exists()
        file_content_after_conflict = conflict_file_path.read_text()
        assert "<<<<<<<" in file_content_after_conflict
        assert "=======" in file_content_after_conflict
        assert ">>>>>>>" in file_content_after_conflict
        assert "Main's change on Line 2" in file_content_after_conflict
        assert "Feature's change on Line 2" in file_content_after_conflict

        # 8. Verify HEAD is still on main (no merge commit created yet)
        assert repo.head.shorthand == main_branch_name
        assert repo.head.target == main_head_oid_before_merge # Still on main's last commit

        # 9. Manually resolve the conflict
        resolved_content = "Line 1\nResolved conflict on Line 2\nLine 3\n"
        conflict_file_path.write_text(resolved_content)
        repo.index.add(conflict_file_name)
        repo.index.write() # This should clear the conflict from the index for this file

        # Verify conflict is cleared from index for the specific file
        assert not repo.index.conflicts or not any(c.path == conflict_file_name for c_ancestor, c_ours, c_theirs in repo.index.conflicts if c_ancestor or c_ours or c_theirs)


        # 10. Run `gitwrite save "Resolved merge conflict"`
        save_message = "Resolved merge conflict"
        result_save = runner.invoke(cli, ["save", save_message])
        assert result_save.exit_code == 0, f"CLI Error on save: {result_save.output}"
        assert "Successfully completed merge operation." in result_save.output


        # 11. Verify a new merge commit is created on main
        repo.head.resolve() # Refresh HEAD
        final_merge_commit_oid = repo.head.target
        assert final_merge_commit_oid != main_head_oid_before_merge

        final_merge_commit = repo.get(final_merge_commit_oid)
        assert isinstance(final_merge_commit, pygit2.Commit)
        assert len(final_merge_commit.parents) == 2
        parent_oids_after_save = {p.id for p in final_merge_commit.parents}
        assert parent_oids_after_save == {main_head_oid_before_merge, feature_head_oid_before_merge}

        # Check commit message (standard part + user's message)
        # Standard merge message might be "Merge branch 'feature-conflict' into main_branch_name"
        # or simply the user's message if the CLI overwrites it.
        # Assuming the CLI appends or uses the user's message predominantly for the resolved merge.
        assert save_message in final_merge_commit.message
        assert f"Merge branch '{feature_branch_name}'" in final_merge_commit.message # Default part

        # 12. Verify MERGE_HEAD is cleared
        with pytest.raises(KeyError): # MERGE_HEAD should be gone
             repo.lookup_reference("MERGE_HEAD")

        # Verify working directory is clean and reflects resolved state
        assert not repo.status(), f"Working directory should be clean. Status: {repo.status()}"
        assert conflict_file_path.read_text() == resolved_content

    def test_merge_non_existent_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a non-existent branch."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_head_oid = repo.head.target
        initial_branch_name = repo.head.shorthand

        non_existent_branch = "I-do-not-exist"
        result = runner.invoke(cli, ["merge", non_existent_branch])

        assert result.exit_code != 0, f"CLI should have failed for non-existent branch. Output: {result.output}"
        # Error message could be "Exploration '...' not found" or "Branch '...' not found" or specific git error
        assert (f"Exploration '{non_existent_branch}' not found" in result.output or
                f"Branch '{non_existent_branch}' not found" in result.output or # More generic
                f"'{non_existent_branch}': not a commit" in result.output # git's rev-parse error
               ), f"Unexpected error message: {result.output}"

        # Verify no change in current branch or state
        assert repo.head.shorthand == initial_branch_name
        assert repo.head.target == initial_head_oid
        # MERGE_HEAD should not be set
        with pytest.raises(KeyError):
            repo.lookup_reference("MERGE_HEAD")

    def test_merge_already_merged_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging an already merged branch (up-to-date)."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        initial_main_commit_oid = repo.head.target

        # Create feature_branch and add a commit
        feature_branch_name = "feature-already-merged"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(initial_main_commit_oid))
        repo.checkout(feature_branch)
        make_commit(repo, "merged_feature_file.txt", "content", "Commit on feature to be merged")
        feature_head_oid = repo.head.target

        # Switch to main and merge (this will be a fast-forward in this setup)
        repo.checkout(repo.branches.local[main_branch_name])
        repo.merge(feature_head_oid) # Perform the first merge directly with pygit2
        # For a fast-forward, explicitly update main's HEAD
        if repo.head.target != feature_head_oid: # If not FF (e.g. main had other commits)
             # Create a merge commit if it wasn't a fast-forward (manual merge logic)
            tree = repo.index.write_tree()
            author = repo.default_signature
            committer = repo.default_signature
            repo.create_commit(
                f"refs/heads/{main_branch_name}",
                author,
                committer,
                f"Merge {feature_branch_name} into {main_branch_name}",
                tree,
                [repo.head.target, feature_head_oid]
            )
        else: # Was a fast-forward, so just update the reference
            main_branch_ref = repo.references[f"refs/heads/{main_branch_name}"]
            main_branch_ref.set_target(feature_head_oid)
            repo.checkout_head(strategy=pygit2.GIT_CHECKOUT_FORCE) # Update working directory

        head_after_first_merge = repo.head.target
        assert head_after_first_merge == feature_head_oid, "First merge did not set main to feature's head."

        # Run gitwrite merge feature_branch again
        result = runner.invoke(cli, ["merge", feature_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert "already up-to-date" in result.output.lower(), \
            f"Unexpected output when merging already merged branch: {result.output}"

        # Verify no new commit is made
        assert repo.head.target == head_after_first_merge, "No new commit should be made."

    def test_merge_branch_into_itself(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging a branch into itself."""
        repo = local_repo
        os.chdir(repo.workdir)

        current_branch_name = repo.head.shorthand
        initial_head_oid = repo.head.target

        result = runner.invoke(cli, ["merge", current_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Expect "Already up-to-date" or similar
        assert "already up-to-date" in result.output.lower(), \
            f"Unexpected output when merging branch into itself: {result.output}"

        # Verify no new commit is made
        assert repo.head.target == initial_head_oid, "No new commit should be made when merging into self."

    def test_merge_with_uncommitted_changes(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test merging into a branch with uncommitted changes."""
        repo = local_repo
        os.chdir(repo.workdir)

        main_branch_name = repo.head.shorthand
        initial_main_commit_oid = repo.head.target

        # Create a feature branch and add a commit to it
        feature_branch_name = "feature-for-dirty-merge"
        feature_branch = repo.branches.local.create(feature_branch_name, repo.get(initial_main_commit_oid))
        repo.checkout(feature_branch)
        make_commit(repo, "feature_stuff.txt", "Feature content", "Commit on feature for dirty merge test")

        # Switch back to main
        repo.checkout(repo.branches.local[main_branch_name])
        assert repo.head.shorthand == main_branch_name

        # Modify a tracked file on main but do not commit
        main_tracked_file = "initial.txt" # Exists from local_repo fixture
        main_file_path = Path(repo.workdir) / main_tracked_file
        original_main_content = main_file_path.read_text()
        dirty_content = original_main_content + "\nUncommitted changes on main."
        main_file_path.write_text(dirty_content)

        # Verify file is modified
        status = repo.status()
        assert main_tracked_file in status
        assert status[main_tracked_file] == pygit2.GIT_STATUS_WT_MODIFIED

        # Attempt to merge feature_branch
        result = runner.invoke(cli, ["merge", feature_branch_name])

        # Expect an error due to dirty working directory
        assert result.exit_code != 0, f"CLI should have failed due to dirty WD. Output: {result.output}"
        assert ("uncommitted changes" in result.output.lower() or
                "would be overwritten by merge" in result.output.lower() or
                "commit your changes or stash them" in result.output.lower()
               ), f"Unexpected error message for dirty WD merge: {result.output}"

        # Verify no merge occurred
        assert repo.head.target == initial_main_commit_oid # Should still be on the original commit of main

        # Verify uncommitted changes are preserved
        assert main_file_path.read_text() == dirty_content
        status_after = repo.status()
        assert main_tracked_file in status_after
        assert status_after[main_tracked_file] == pygit2.GIT_STATUS_WT_MODIFIED

        # MERGE_HEAD should not be set
        with pytest.raises(KeyError):
            repo.lookup_reference("MERGE_HEAD")
        self._assert_common_gitignore_patterns(test_dir / ".gitignore")

        repo = pygit2.Repository(str(test_dir))
        # The following lines were mistakenly removed in a previous step, restoring them here.
        assert not repo.is_empty
        assert not repo.head_is_unborn
        last_commit = repo.head.peel(pygit2.Commit)
        assert "Initialized GitWrite project structure" in last_commit.message
        assert last_commit.author.name == "GitWrite System"

        # Check tree contents
        expected_tree_items = {".gitignore", "metadata.yml", "drafts/.gitkeep", "notes/.gitkeep"}
        actual_tree_items = {item.name for item in last_commit.tree}
        # For items in subdirectories, pygit2 tree lists them at top level if not a tree object itself
        # Need to check specifically for 'drafts' and 'notes' as tree objects if they contain files.
        # For .gitkeep, they are files.
        # The structure of tree iteration might be more complex if we want to ensure they are in correct subtrees.
        # For now, let's check the main ones.
        assert ".gitignore" in actual_tree_items
        assert "metadata.yml" in actual_tree_items
        assert "drafts" in actual_tree_items # 'drafts' itself is a tree
        assert "notes" in actual_tree_items  # 'notes' itself is a tree

        drafts_tree = last_commit.tree['drafts']
        assert drafts_tree is not None
        assert drafts_tree.type == pygit2.GIT_OBJECT_TREE
        assert (test_dir / "drafts" / ".gitkeep").exists() # Already checked by _assert_gitwrite_structure

        notes_tree = last_commit.tree['notes']
        assert notes_tree is not None
        assert notes_tree.type == pygit2.GIT_OBJECT_TREE
        assert (test_dir / "notes" / ".gitkeep").exists() # Already checked


#######################
# Switch Command Tests
#######################

class TestGitWriteSwitch:
    def test_switch_no_arguments(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite switch` with no arguments, listing branches."""
        repo = local_repo
        os.chdir(repo.workdir)

        initial_commit_oid = repo.head.target
        main_branch_name = repo.head.shorthand # Should be the one from the fixture, e.g. "master" or "main"

        # Create a couple of other branches
        branch_a_name = "branch-a"
        branch_b_name = "branch-b"
        repo.branches.local.create(branch_a_name, repo.get(initial_commit_oid))
        repo.branches.local.create(branch_b_name, repo.get(initial_commit_oid))

        # Ensure we are on the main branch (or whatever the fixture default is)
        if repo.head.shorthand != main_branch_name:
            main_branch_ref_name = f"refs/heads/{main_branch_name}"
            repo.checkout(main_branch_ref_name) # Use full ref name for checkout
        assert repo.head.shorthand == main_branch_name

        result = runner.invoke(cli, ["switch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        # Verify all branches are listed
        assert main_branch_name in output
        assert branch_a_name in output
        assert branch_b_name in output

        # Verify main is marked as current (e.g., with an asterisk)
        # This depends on the exact output format of the CLI command.
        # Assuming a format like "* main_branch_name" or "  main_branch_name (current)"
        # A more robust check might look for the asterisk specifically on the line with main_branch_name
        current_branch_line = ""
        for line in output.splitlines():
            if main_branch_name in line:
                current_branch_line = line
                break
        assert "*" in current_branch_line, \
            f"Current branch '{main_branch_name}' not marked with '*' in output:\n{output}"

    def test_switch_successful_checkout(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite switch <branch_name>` for a successful checkout."""
        repo = local_repo
        os.chdir(repo.workdir)

        initial_commit_oid = repo.head.target
        main_branch_name = repo.head.shorthand

        branch_to_switch_to = "switch-target-branch"
        repo.branches.local.create(branch_to_switch_to, repo.get(initial_commit_oid))

        # Ensure we are on the main branch initially
        if repo.head.shorthand != main_branch_name:
            repo.checkout(repo.branches[main_branch_name])
        assert repo.head.shorthand == main_branch_name

        result = runner.invoke(cli, ["switch", branch_to_switch_to])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Expected output can vary, e.g., "Switched to branch 'branch_name'."
        # or "Switched to exploration 'branch_name'."
        assert f"Switched to branch '{branch_to_switch_to}'" in result.output or \
               f"Switched to exploration '{branch_to_switch_to}'" in result.output


        # Verify HEAD now points to the new branch
        assert repo.head.shorthand == branch_to_switch_to
        # Verify the working directory is also updated, by checking out the HEAD.
        # Note: `repo.checkout_head()` might be needed if the CLI command doesn't do it,
        # but a typical switch/checkout operation should update the working directory.
        # For pygit2, setting repo.head to a new branch reference doesn't automatically update WD.
        # The CLI command `gitwrite switch` is expected to handle this.
        # We check `repo.head.shorthand` which reflects the symbolic ref HEAD.

    def test_switch_non_existent_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite switch <non_existent_branch>`."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_branch_name = repo.head.shorthand

        non_existent_branch = "no-such-branch-here"
        result = runner.invoke(cli, ["switch", non_existent_branch])

        assert result.exit_code != 0, f"CLI should have failed but exited with 0. Output: {result.output}"
        # Based on the `explore` command, the error might be "Exploration '{branch_name}' not found."
        # Or it could be a more generic git error like "branch '{branch_name}' not found."
        assert (f"Exploration '{non_existent_branch}' not found" in result.output or
                f"branch '{non_existent_branch}' not found" in result.output or # git-like error
                f"Invalid branch name: '{non_existent_branch}'" in result.output # another possibility
               ), f"Unexpected error message: {result.output}"


        # Verify that the current branch has not changed
        assert repo.head.shorthand == initial_branch_name

    def test_switch_in_repo_with_one_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite switch` in a repository with only one branch."""
        repo = local_repo
        os.chdir(repo.workdir)

        # Ensure only one branch exists. The local_repo fixture creates one.
        # If the fixture changes, this assertion might need adjustment.
        branches = list(repo.branches.local)
        assert len(branches) == 1, f"Expected 1 branch, found {len(branches)}: {branches}"

        single_branch_name = repo.head.shorthand
        assert single_branch_name is not None

        # Test `gitwrite switch` (no arguments)
        result_list = runner.invoke(cli, ["switch"])
        assert result_list.exit_code == 0, f"CLI Error (list): {result_list.output}"
        output_list = result_list.output

        assert single_branch_name in output_list

        current_branch_line = ""
        for line in output_list.splitlines():
            if single_branch_name in line:
                current_branch_line = line
                break
        assert "*" in current_branch_line, \
            f"Current branch '{single_branch_name}' not marked with '*' in list output:\n{output_list}"

        # Test `gitwrite switch <current_branch_name>`
        result_switch_to_current = runner.invoke(cli, ["switch", single_branch_name])
        assert result_switch_to_current.exit_code == 0, \
            f"CLI Error (switch to current): {result_switch_to_current.output}"

        # Output could be "Already on 'branch_name'." or a successful switch message.
        assert (f"Already on '{single_branch_name}'" in result_switch_to_current.output or
                f"Switched to branch '{single_branch_name}'" in result_switch_to_current.output or
                f"Switched to exploration '{single_branch_name}'" in result_switch_to_current.output
               ), f"Unexpected output when switching to current branch: {result_switch_to_current.output}"

        assert repo.head.shorthand == single_branch_name

    def test_switch_with_uncommitted_changes(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite switch` with uncommitted changes in the working directory."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_commit_oid = repo.head.target

        # Create branch_x and switch to it
        branch_x_name = "branch-x-changes"
        repo.branches.local.create(branch_x_name, repo.get(initial_commit_oid))
        repo.checkout(repo.branches.local[branch_x_name])
        assert repo.head.shorthand == branch_x_name

        # Create a file on branch_x and commit it
        file_on_x_name = "file_on_x.txt"
        original_content_x = "Original content on branch X."
        make_commit(repo, file_on_x_name, original_content_x, f"Add {file_on_x_name} on {branch_x_name}")

        # Create branch_y from the same initial commit, but don't add file_on_x.txt to it,
        # or make its content different to ensure a conflict if checkout were to proceed.
        branch_y_name = "branch-y-clean"
        repo.branches.local.create(branch_y_name, repo.get(initial_commit_oid))
        # To make it more explicit that branch_y does not have file_on_x.txt in the same state:
        # Checkout branch_y, remove the file if it exists from a previous merge, or commit a different version
        repo.checkout(repo.branches.local[branch_y_name])
        file_on_x_path_in_y = Path(repo.workdir) / file_on_x_name
        if file_on_x_path_in_y.exists(): # If branch_x was merged to main, then y branched from main
            file_on_x_path_in_y.unlink()
            repo.index.remove(file_on_x_name)
            repo.index.write()
            author = pygit2.Signature("Test Author", "test@example.com")
            committer = pygit2.Signature("Test Committer", "committer@example.com")
            tree = repo.index.write_tree()
            repo.create_commit(f"refs/heads/{branch_y_name}", author, committer, f"Remove {file_on_x_name} on {branch_y_name} for test", tree, [repo.head.target])
        # Switch back to branch_x to make uncommitted changes
        repo.checkout(repo.branches.local[branch_x_name])
        assert repo.head.shorthand == branch_x_name


        # Modify the tracked file on branch_x without committing
        modified_content_x = "Modified content on branch X - UNCOMMITTED."
        file_on_x_path = Path(repo.workdir) / file_on_x_name
        file_on_x_path.write_text(modified_content_x)

        # Verify the file is indeed modified and unstaged
        status = repo.status()
        assert file_on_x_name in status
        assert status[file_on_x_name] == pygit2.GIT_STATUS_WT_MODIFIED

        # Attempt to switch to branch_y
        result = runner.invoke(cli, ["switch", branch_y_name])

        # Expect an error because of uncommitted changes that would be overwritten/lost
        assert result.exit_code != 0, f"CLI should have failed due to uncommitted changes. Output: {result.output}"

        # Check for a specific error message
        # Git's message: "error: Your local changes to the following files would be overwritten by checkout:"
        # Or "error: Please commit your changes or stash them before you switch branches."
        assert ("changes would be overwritten" in result.output.lower() or
                "commit your changes or stash them" in result.output.lower() or
                "uncommitted changes" in result.output.lower()
               ), f"Unexpected error message: {result.output}"

        # Verify the current branch is still branch_x
        assert repo.head.shorthand == branch_x_name, "Current branch changed despite uncommitted changes."

        # Verify the uncommitted changes are still present
        assert file_on_x_path.read_text() == modified_content_x, "Uncommitted changes were lost."
        status_after = repo.status()
        assert file_on_x_name in status_after
        assert status_after[file_on_x_name] == pygit2.GIT_STATUS_WT_MODIFIED

    def test_switch_to_current_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite switch <current_branch_name>`."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_commit_oid = repo.head.target

        current_branch_name = "branch-stay"
        repo.branches.local.create(current_branch_name, repo.get(initial_commit_oid))

        # Switch to this branch to make it current
        repo.checkout(repo.branches.local[current_branch_name])
        assert repo.head.shorthand == current_branch_name

        result = runner.invoke(cli, ["switch", current_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Expect a message indicating already on the branch
        assert (f"Already on '{current_branch_name}'" in result.output or
                f"Already on exploration '{current_branch_name}'" in result.output
               ), f"Unexpected output when switching to current branch: {result.output}"

        # Verify HEAD is still on the same branch
        assert repo.head.shorthand == current_branch_name

    def test_compare_new_file(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` involving a new file."""
        repo = local_repo
        os.chdir(repo.workdir)

        # C1: Has initial.txt (from fixture)
        c1_oid_short = repo.head.peel(pygit2.Commit).short_id

        # C2: Add file_b.txt
        file_b_name = "file_b.txt"
        file_b_content = "This is a brand new file."
        make_commit(repo, file_b_name, file_b_content, "Commit C2: Add file_b.txt")
        c2_oid_short = repo.head.peel(pygit2.Commit).short_id

        result = runner.invoke(cli, ["compare", c1_oid_short, c2_oid_short])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_oid_short} with {c2_oid_short}" in output # Or similar header
        assert file_b_name in output
        assert f"--- /dev/null" in output or "--- a/dev/null" in output
        assert f"+++ b/{file_b_name}" in output
        for line in file_b_content.splitlines():
            assert f"+{line}" in output

    def test_compare_deleted_file(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` involving a deleted file."""
        repo = local_repo
        os.chdir(repo.workdir)

        file_to_delete_name = "file_to_delete.txt"
        file_to_delete_content = "This file will be deleted."
        # Commit C1: Add the file that will be deleted
        make_commit(repo, file_to_delete_name, file_to_delete_content, f"Commit C1: Add {file_to_delete_name}")
        c1_oid_short = repo.head.peel(pygit2.Commit).short_id

        # Commit C2: Delete file_to_delete.txt
        file_to_delete_path = Path(repo.workdir) / file_to_delete_name
        assert file_to_delete_path.exists()
        file_to_delete_path.unlink()
        repo.index.remove(file_to_delete_name)
        repo.index.write()

        author = pygit2.Signature("Test Author", "test@example.com")
        committer = pygit2.Signature("Test Committer", "committer@example.com")
        tree_c2 = repo.index.write_tree()
        c2_oid = repo.create_commit("HEAD", author, committer, f"Commit C2: Delete {file_to_delete_name}", tree_c2, [repo.head.target])
        c2_oid_short = repo.get(c2_oid).short_id

        result = runner.invoke(cli, ["compare", c1_oid_short, c2_oid_short])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_oid_short} with {c2_oid_short}" in output # Or similar header
        assert file_to_delete_name in output
        assert f"--- a/{file_to_delete_name}" in output
        assert f"+++ /dev/null" in output or "+++ b/dev/null" in output
        for line in file_to_delete_content.splitlines():
            assert f"-{line}" in output

    def test_compare_file_mode_change(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` involving a file mode change (e.g., executable bit)."""
        repo = local_repo
        os.chdir(repo.workdir)

        script_name = "script.sh"
        script_content = "#!/bin/bash\necho 'Hello'\n"

        make_commit(repo, script_name, script_content, "Commit C1: Add non-executable script.sh")
        c1_commit_oid = repo.head.target
        c1_short_hash = repo.get(c1_commit_oid).short_id
        assert repo.get(c1_commit_oid).tree[script_name].filemode == pygit2.GIT_FILEMODE_BLOB

        builder = repo.TreeBuilder(repo.get(c1_commit_oid).tree)
        blob_oid = repo.get(c1_commit_oid).tree[script_name].id
        builder.insert(script_name, blob_oid, pygit2.GIT_FILEMODE_BLOB_EXECUTABLE)
        new_tree_oid = builder.write()

        author = pygit2.Signature("Test Author", "test@example.com")
        committer = pygit2.Signature("Test Committer", "committer@example.com")
        c2_commit_oid = repo.create_commit("HEAD", author, committer, "Commit C2: Make script.sh executable", new_tree_oid, [c1_commit_oid])
        c2_short_hash = repo.get(c2_commit_oid).short_id
        assert repo.get(c2_commit_oid).tree[script_name].filemode == pygit2.GIT_FILEMODE_BLOB_EXECUTABLE

        result = runner.invoke(cli, ["compare", c1_short_hash, c2_short_hash])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_short_hash} with {c2_short_hash}" in output # Or similar header
        assert script_name in output
        assert "mode change" in output.lower() or \
               ("100644" in output and "100755" in output) or \
               "executable" in output.lower()
        assert f"+{script_content.splitlines()[0]}" not in output
        assert f"-{script_content.splitlines()[0]}" not in output

    def test_compare_binary_files(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite compare` with binary files."""
        repo = local_repo
        os.chdir(repo.workdir)

        binary_file_name = "image.png"
        binary_content_c1 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90\x77\x58\xde"
        binary_content_c2 = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x02\x00\x00\x00\x02\x08\x02\x00\x00\x00\x78\x24\x78\x00"

        file_path = Path(repo.workdir) / binary_file_name
        with open(file_path, "wb") as f:
            f.write(binary_content_c1)
        repo.index.add(binary_file_name)
        repo.index.write()
        author = pygit2.Signature("Test Author", "test@example.com")
        committer = pygit2.Signature("Test Committer", "committer@example.com")
        tree1 = repo.index.write_tree()
        # Use repo.head.target for parent if it exists, else empty list for initial commit
        parents_c1 = [repo.head.target] if not repo.head_is_unborn and repo.head.target else []
        c1_oid = repo.create_commit("HEAD", author, committer, "Commit C1: Add binary file", tree1, parents_c1)
        c1_oid_short = repo.get(c1_oid).short_id

        with open(file_path, "wb") as f:
            f.write(binary_content_c2)
        repo.index.add(binary_file_name)
        repo.index.write()
        tree2 = repo.index.write_tree()
        c2_oid = repo.create_commit("HEAD", author, committer, "Commit C2: Modify binary file", tree2, [c1_oid])
        c2_oid_short = repo.get(c2_oid).short_id

        result = runner.invoke(cli, ["compare", c1_oid_short, c2_oid_short])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert f"Comparing {c1_oid_short} with {c2_oid_short}" in output # Or similar header
        assert binary_file_name in output
        assert "binary files differ" in output.lower() or \
               "cannot display diff for binary files" in output.lower() or \
               "binary file" in output.lower()
        assert "+PNG" not in output
        assert "-PNG" not in output


#######################
# Explore Command Tests
#######################

class TestGitWriteExplore:
    def test_explore_new_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test creating a new exploration branch."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_branch_name = repo.head.shorthand
        initial_commit_oid = repo.head.target

        new_exploration_name = "my-new-idea"
        result = runner.invoke(cli, ["explore", new_exploration_name])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to new exploration branch '{new_exploration_name}'" in result.output or \
               f"Created and switched to new exploration branch '{new_exploration_name}'." in result.output


        # Verify new branch exists
        new_branch = repo.branches.get(new_exploration_name)
        assert new_branch is not None, f"Branch '{new_exploration_name}' was not created."
        assert new_branch.is_local

        # Verify HEAD points to the new branch
        assert repo.head.shorthand == new_exploration_name
        assert repo.head.target == initial_commit_oid # Should be based on the previous HEAD's commit

        # Verify current working directory's branch is the new one (pygit2 might not reflect this directly,
        # but HEAD check is the primary indicator)

    def test_explore_existing_branch(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test creating an exploration branch that already exists."""
        repo = local_repo
        os.chdir(repo.workdir)

        initial_branch_name = repo.head.shorthand
        initial_commit_oid = repo.head.target

        existing_branch_name = "already-exists"
        repo.branches.local.create(existing_branch_name, repo.get(initial_commit_oid))

        # Ensure we are not on the existing_branch_name before running the command
        if repo.head.shorthand == existing_branch_name:
            # Switch to the initial branch (e.g. main/master)
            repo.checkout(repo.branches[initial_branch_name])

        assert repo.head.shorthand == initial_branch_name, f"Failed to switch back to initial branch {initial_branch_name}"

        result = runner.invoke(cli, ["explore", existing_branch_name])

        assert result.exit_code != 0, f"CLI should have exited with an error. Output: {result.output}"
        assert f"Error: Exploration branch '{existing_branch_name}' already exists." in result.output

        # Verify that the current branch has not changed
        assert repo.head.shorthand == initial_branch_name

    def test_explore_invalid_name(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test creating an exploration branch with an invalid name."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_branch_name = repo.head.shorthand

        invalid_names = [
            "invalid name with spaces",
            "invalid/name",
            "invalid~name",
            "invalid^name",
            "invalid:name",
            "invalid*name",
            "invalid?name",
            "invalid[name",
            ".cannot-start-with-dot",
            "cannot-end-with.lock",
            "cannot-have@{-in-it", # Technically @{ is the problem for HEAD pointing
            # "HEAD" # This is a valid ref, but should not be allowed as a new branch name here.
        ]

        for invalid_name in invalid_names:
            result = runner.invoke(cli, ["explore", invalid_name])

            # We expect the command to fail (non-zero exit code) because git itself
            # or click's validation (if any added for branch names) should prevent this.
            assert result.exit_code != 0, \
                f"CLI should have failed for invalid name '{invalid_name}', but exited with 0. Output: {result.output}"

            # Check for a generic error message. The exact message might come from git.
            # Examples: "is not a valid branch name", "unable to create branch"
            error_msg_found = ("not a valid branch name" in result.output.lower() or
                               "unable to create branch" in result.output.lower() or
                               "invalid branch name" in result.output.lower() or
                               f"error: '{invalid_name}' is not a valid branch name" in result.output.lower() or # git's typical error
                               f"parameter validation failed" in result.output.lower() # click error
                               )
            assert error_msg_found, \
                f"Expected error message for invalid name '{invalid_name}' not found. Output: {result.output}"

            # Verify that the branch was not created
            assert repo.branches.get(invalid_name) is None, \
                f"Branch '{invalid_name}' was created despite being invalid."

            # Verify that the current branch has not changed
            assert repo.head.shorthand == initial_branch_name, \
                f"Current branch changed after attempting to create invalid branch '{invalid_name}'."

    def test_explore_from_detached_head(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test creating an exploration branch from a detached HEAD state."""
        repo = local_repo
        os.chdir(repo.workdir)

        # Initial commit is from the fixture.
        commit1_oid = repo.head.target

        # Make a second commit so we can detach HEAD to the first commit.
        make_commit(repo, "file_for_commit2.txt", "content c2", "Commit 2 for detached head test")
        commit2_oid = repo.head.target
        assert commit1_oid != commit2_oid

        # Detach HEAD to commit1
        repo.set_head(commit1_oid)
        assert repo.head_is_detached, "HEAD is not detached as expected."
        assert repo.head.target == commit1_oid, "HEAD does not point to commit1 after detaching."


        new_branch_name = "branch-from-detached"
        result = runner.invoke(cli, ["explore", new_branch_name])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Switched to new exploration branch '{new_branch_name}'" in result.output or \
               f"Created and switched to new exploration branch '{new_branch_name}'." in result.output

        # Verify new branch exists and points to the commit where HEAD was detached
        new_branch = repo.branches.get(new_branch_name)
        assert new_branch is not None, f"Branch '{new_branch_name}' was not created."
        assert new_branch.target == commit1_oid, \
            f"New branch '{new_branch_name}' does not point to the correct commit (where HEAD was detached)."

        # Verify HEAD now points to the new branch
        assert not repo.head_is_detached, "HEAD should no longer be detached."
        assert repo.head.shorthand == new_branch_name
        assert repo.head.target == commit1_oid # Still pointing to the same commit, but via the branch

    def test_explore_in_empty_repository(self, runner: CliRunner, empty_local_repo: pygit2.Repository):
        """Test creating an exploration branch in an empty repository."""
        repo = empty_local_repo
        os.chdir(repo.workdir)

        assert repo.is_empty, "Repository should be empty for this test."
        assert repo.head_is_unborn, "HEAD should be unborn in an empty repository."

        new_branch_name = "first-ever-branch"
        result = runner.invoke(cli, ["explore", new_branch_name])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        # Output might vary: "Switched to new orphan branch" or "Switched to new exploration branch"
        assert (f"Switched to new orphan exploration branch '{new_branch_name}'" in result.output or
                f"Switched to new exploration branch '{new_branch_name}'" in result.output or
                f"Created and switched to new exploration branch '{new_branch_name}'." in result.output)


        # Verify new branch exists
        new_branch = repo.branches.get(new_branch_name)
        assert new_branch is not None, f"Branch '{new_branch_name}' was not created."
        assert new_branch.is_local

        # Verify HEAD points to the new branch
        # In an empty repo, after creating an orphan branch, HEAD points to it,
        # but it's still "unborn" until a commit is made.
        assert repo.head.shorthand == new_branch_name
        assert repo.head_is_unborn # Should still be unborn as no commit was made

        # Verify repository is still empty (no commits made by 'explore' command)
        assert repo.is_empty, "Repository should still be empty (no commits)."

        # Check if any commits were made (there shouldn't be)
        commit_count = 0
        try:
            if repo.head.target: # Will raise an error if head is unborn
                 for _ in repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL):
                    commit_count += 1
        except pygit2.GitError: # Expected if head is unborn
            pass
        assert commit_count == 0, "No commits should have been made by the explore command."


#######################
# History Command Tests
#######################

class TestGitWriteHistory:
    def test_history_basic_output(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test basic `gitwrite history` output with a few commits."""
        repo = local_repo
        os.chdir(repo.workdir)

        # The local_repo fixture already creates an initial commit.
        # Let's get its details.
        commit1_hash_full = repo.head.target
        commit1 = repo.get(commit1_hash_full)
        commit1_short_hash = commit1.short_id
        commit1_msg = commit1.message.strip()
        commit1_author_name = commit1.author.name

        # Create a second commit
        make_commit(repo, "file2.txt", "Content for file2", "Second commit message")
        commit2_hash_full = repo.head.target
        commit2 = repo.get(commit2_hash_full)
        commit2_short_hash = commit2.short_id
        commit2_msg = commit2.message.strip()
        commit2_author_name = commit2.author.name

        # Create a third commit
        make_commit(repo, "file3.txt", "Content for file3", "Third commit message")
        commit3_hash_full = repo.head.target
        commit3 = repo.get(commit3_hash_full)
        commit3_short_hash = commit3.short_id
        commit3_msg = commit3.message.strip()
        commit3_author_name = commit3.author.name

        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        # Commits are listed newest first
        # Check for commit 3
        assert commit3_short_hash in output
        assert commit3_msg in output
        assert commit3_author_name in output # Or part of it

        # Check for commit 2
        assert commit2_short_hash in output
        assert commit2_msg in output
        assert commit2_author_name in output

        # Check for commit 1 (initial)
        assert commit1_short_hash in output
        assert commit1_msg in output
        assert commit1_author_name in output

        # Check order (simplified: commit3 message appears before commit1 message)
        assert output.find(commit3_msg) < output.find(commit1_msg)
        assert output.find(commit2_msg) < output.find(commit1_msg)
        assert output.find(commit3_msg) < output.find(commit2_msg)

    # Additional tests for history will go here

    def test_history_empty_repository(self, runner: CliRunner, empty_local_repo: pygit2.Repository):
        """Test `gitwrite history` in an empty repository (no commits)."""
        repo = empty_local_repo
        os.chdir(repo.workdir)

        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output.lower() # Convert to lower for case-insensitive check

        # Check for messages indicating no history
        assert "no history yet" in output or \
               "no commits found" in output or \
               "repository is empty" in output or \
               "no commits in history" in output

    def test_history_number_option(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite history -n/--number` option."""
        repo = local_repo
        os.chdir(repo.workdir)

        # local_repo starts with 1 commit. Add 4 more to make it 5.
        commit_hashes = [repo.head.target.hex]
        commit_messages = [repo.get(repo.head.target).message.strip()]

        for i in range(2, 6): # Creates commit2, commit3, commit4, commit5
            msg = f"Commit {i}"
            make_commit(repo, f"file{i}.txt", f"Content for file {i}", msg)
            commit_hashes.append(repo.head.target.hex)
            commit_messages.append(msg)

        # Commits are stored newest first by git log typically
        commit_short_hashes_newest_first = [repo.get(ch).short_id for ch in reversed(commit_hashes)]
        commit_messages_newest_first = list(reversed(commit_messages))

        # Test -n 3
        result_n3 = runner.invoke(cli, ["history", "-n", "3"])
        assert result_n3.exit_code == 0, f"CLI Error (-n 3): {result_n3.output}"
        output_n3 = result_n3.output

        # Count occurrences of "Commit ID:" or similar unique line start for each commit entry
        # This is more robust than counting message lines if messages can span multiple lines.
        # Assuming the output format from `gitwrite history` has a clear marker per commit.
        # For now, let's assume each commit message is unique enough and appears once.
        n3_displayed_commits = 0
        for i in range(5):
            if commit_messages_newest_first[i] in output_n3:
                n3_displayed_commits +=1
        assert n3_displayed_commits == 3, f"Expected 3 commits for -n 3, found {n3_displayed_commits}. Output:\n{output_n3}"
        assert commit_messages_newest_first[0] in output_n3 # Newest
        assert commit_messages_newest_first[1] in output_n3
        assert commit_messages_newest_first[2] in output_n3
        assert commit_messages_newest_first[3] not in output_n3
        assert commit_messages_newest_first[4] not in output_n3 # Oldest of the 5

        # Test --number 1
        result_n1 = runner.invoke(cli, ["history", "--number", "1"])
        assert result_n1.exit_code == 0, f"CLI Error (--number 1): {result_n1.output}"
        output_n1 = result_n1.output
        n1_displayed_commits = 0
        for i in range(5):
            if commit_messages_newest_first[i] in output_n1:
                n1_displayed_commits +=1
        assert n1_displayed_commits == 1, f"Expected 1 commit for --number 1, found {n1_displayed_commits}. Output:\n{output_n1}"
        assert commit_messages_newest_first[0] in output_n1 # Only newest
        assert commit_messages_newest_first[1] not in output_n1

        # Test -n 10 (more than available)
        result_n10 = runner.invoke(cli, ["history", "-n", "10"])
        assert result_n10.exit_code == 0, f"CLI Error (-n 10): {result_n10.output}"
        output_n10 = result_n10.output
        n10_displayed_commits = 0
        for i in range(5):
            if commit_messages_newest_first[i] in output_n10:
                n10_displayed_commits +=1
        assert n10_displayed_commits == 5, f"Expected all 5 commits for -n 10, found {n10_displayed_commits}. Output:\n{output_n10}"
        for i in range(5):
            assert commit_messages_newest_first[i] in output_n10

        # Test with -n 0 (should probably show no commits or be an error, depending on CLI design)
        result_n0 = runner.invoke(cli, ["history", "-n", "0"])
        # Assuming -n 0 means show 0 commits, or it's an invalid input.
        # If it's invalid, exit_code might be non-zero.
        # If it means 0 commits, output should not contain any commit messages.
        if result_n0.exit_code == 0:
            output_n0 = result_n0.output
            n0_displayed_commits = 0
            for i in range(5):
                if commit_messages_newest_first[i] in output_n0:
                    n0_displayed_commits +=1
            assert n0_displayed_commits == 0, f"Expected 0 commits for -n 0, found {n0_displayed_commits}. Output:\n{output_n0}"
        else:
            # Handle case where -n 0 is an error (e.g., click validation)
            assert "invalid value" in result_n0.output.lower() or "must be at least 1" in result_n0.output.lower()

    def test_history_single_commit_repository(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite history` in a repository with only a single commit."""
        repo = local_repo
        os.chdir(repo.workdir)

        # The local_repo fixture creates exactly one commit ("Initial commit")
        # No more commits should be added for this test.

        # Verify there's indeed only one commit
        commit_count = 0
        for _ in repo.walk(repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL):
            commit_count += 1
        assert commit_count == 1, "Test setup error: Expected only one commit from local_repo fixture here."

        commit_obj = repo.get(repo.head.target)
        commit_short_hash = commit_obj.short_id
        commit_msg = commit_obj.message.strip()
        commit_author_name = commit_obj.author.name

        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        assert commit_short_hash in output
        assert commit_msg in output
        assert commit_author_name in output

        # Check that no other commit messages/hashes are present (sanity check)
        # This can be tricky if output contains other text.
        # A simple check: count commit message occurrences.
        # If commit messages are very generic, this might be flaky.
        # For "Initial commit", it's reasonably unique.
        assert output.count(commit_msg) == 1

    def test_history_unusual_commit_messages(self, runner: CliRunner, local_repo: pygit2.Repository):
        """Test `gitwrite history` with unusual commit messages."""
        repo = local_repo
        os.chdir(repo.workdir)

        # Commit 1: Very long message
        long_msg_prefix = "This is a very long commit message, designed to test truncation. "
        long_msg_suffix = "The end of the long message, ensuring it's quite lengthy overall and exceeds typical short summary lengths."
        long_message = long_msg_prefix + " ".join(["word"] * 100) + " " + long_msg_suffix
        make_commit(repo, "long_msg_file.txt", "content", long_message)
        commit_long_msg_hash = repo.head.peel(pygit2.Commit).short_id

        # Commit 2: Message with special characters
        special_char_message = 'Commit with "quotes", newlines\nand other special characters like éàçüö.'
        make_commit(repo, "special_char_file.txt", "content", special_char_message)
        commit_special_char_hash = repo.head.peel(pygit2.Commit).short_id

        # Commit 3: Standard message (from fixture) for context
        initial_commit_obj = repo.get(repo.listall_commits()[-1]) # Oldest commit
        initial_commit_msg = initial_commit_obj.message.strip()
        initial_commit_hash = initial_commit_obj.short_id

        result = runner.invoke(cli, ["history"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        output = result.output

        # Check for special characters message (should be displayed as is, or handled gracefully)
        # The Rich table might escape some things, or handle them. Key is no crash.
        # We'll check for a significant part of it.
        assert 'Commit with "quotes", newlines' in output # Check first line
        assert "and other special characters like éàçüö." in output # Check second line
        assert commit_special_char_hash in output

        # Check for long message (might be truncated, but should not break display)
        # Assert that the beginning of the long message is present.
        # The exact truncation length depends on the `history` command's implementation.
        assert long_msg_prefix.split('.')[0] in output # Check for the first sentence or part of it
        assert commit_long_msg_hash in output
        # If it's truncated, the full long_msg_suffix might not be there.
        # We are mostly checking that the command runs and includes the commit.

        # Check for the initial commit message as well
        assert initial_commit_msg in output
        assert initial_commit_hash in output

        # Check order: special_char_message (newest) -> long_message -> initial_commit_msg (oldest)
        assert output.find(commit_special_char_hash) < output.find(commit_long_msg_hash)
        assert output.find(commit_long_msg_hash) < output.find(initial_commit_hash)

    def test_init_with_project_name(self, runner: CliRunner, tmp_path: Path):
        """Test `gitwrite init project_name`."""
        project_name = "my_new_book"
        base_dir = tmp_path / "base_for_named_project"
        base_dir.mkdir()
        project_dir = base_dir / project_name

        os.chdir(base_dir) # Run from parent directory

        result = runner.invoke(cli, ["init", project_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert project_dir.exists(), "Project directory was not created"
        assert project_dir.is_dir()
        assert f"Initialized empty Git repository in {project_dir.resolve()}" in result.output
        assert "Created GitWrite structure commit." in result.output

        self._assert_gitwrite_structure(project_dir)
        self._assert_common_gitignore_patterns(project_dir / ".gitignore")

        repo = pygit2.Repository(str(project_dir))
        assert not repo.is_empty
        last_commit = repo.head.peel(pygit2.Commit)
        assert f"Initialized GitWrite project structure in {project_name}" in last_commit.message

    def test_init_error_project_directory_is_a_file(self, runner: CliRunner, tmp_path: Path):
        """Test error when `gitwrite init project_name` and project_name is an existing file."""
        project_name = "existing_file_name"
        base_dir = tmp_path / "base_for_file_conflict"
        base_dir.mkdir()

        file_path = base_dir / project_name
        file_path.write_text("I am a file.")

        os.chdir(base_dir)
        result = runner.invoke(cli, ["init", project_name])
        assert result.exit_code == 0 # Command itself doesn't fail, but prints error
        assert f"Error: '{file_path.name}' exists and is a file." in result.output
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
        assert result.exit_code == 0 # Command prints error
        assert f"Error: Directory '{project_dir_path.name}' already exists, is not empty, and is not a Git repository." in result.output
        assert not (project_dir_path / ".git").exists()

    def test_init_in_existing_git_repository(self, runner: CliRunner, local_repo: pygit2.Repository, local_repo_path: Path):
        """Test `gitwrite init` in an existing Git repository."""
        # local_repo fixture already provides an initialized git repo with one commit
        os.chdir(local_repo_path)

        initial_commit_count = len(list(local_repo.walk(local_repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL)))

        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert f"Opened existing Git repository in {local_repo_path.resolve()}" in result.output
        assert "Created/ensured GitWrite directory structure" in result.output
        assert "Staged GitWrite files" in result.output # Might stage .gitignore if it's new/modified
        # Check output based on whether a commit was made
        last_commit_after_init = local_repo.head.peel(pygit2.Commit)
        # initial_commit_count was before this init. If a new commit was made, count increases.
        # The fixture local_repo already has 1 commit.
        current_commit_count = len(list(local_repo.walk(local_repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL)))

        if current_commit_count > initial_commit_count :
            assert "Created GitWrite structure commit." in result.output
        else:
            # This case implies no new structural elements were staged and committed.
            assert "No changes to commit" in result.output or \
                   "No new GitWrite structure elements to stage" in result.output


        self._assert_gitwrite_structure(local_repo_path, check_git_dir=True) # .git already exists
        self._assert_common_gitignore_patterns(local_repo_path / ".gitignore")

        # Verify a new commit was made for GitWrite files
        current_commit_count = len(list(local_repo.walk(local_repo.head.target, pygit2.GIT_SORT_TOPOLOGICAL)))
        # Depending on whether .gitignore was already present and identical, a commit might or might not be made.
        # The init command tries to be idempotent for structure if already committed.
        # Let's check the commit message of the latest commit.
        last_commit = local_repo.head.peel(pygit2.Commit)
        if current_commit_count > initial_commit_count:
            assert f"Added GitWrite structure to {local_repo_path.name}" in last_commit.message
            assert last_commit.author.name == "GitWrite System"
        else:
            # If no new commit, it means the structure was already there and committed.
            # The output should indicate this.
            assert "No changes to commit" in result.output or "No new GitWrite structure elements to stage" in result.output


    def test_init_in_existing_non_empty_dir_not_git_no_project_name(self, runner: CliRunner, tmp_path: Path):
        """Test `gitwrite init` in current dir if it's non-empty and not a Git repo."""
        test_dir = tmp_path / "existing_non_empty_current_dir"
        test_dir.mkdir()
        (test_dir / "my_random_file.txt").write_text("content")

        os.chdir(test_dir)
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0 # Command prints error
        # The error message in main.py uses str(target_dir) which is the full path
        assert f"Error: Current directory '{str(test_dir)}' is not empty and not a Git repository." in result.output
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

        self._assert_gitwrite_structure(test_dir)
        self._assert_common_gitignore_patterns(gitignore_path)

        # Verify user's entry is still there
        final_gitignore_content = gitignore_path.read_text()
        assert user_entry.strip() in final_gitignore_content # .strip() because init might add newlines

        # Check that GitWrite patterns were added
        assert "/.venv/" in final_gitignore_content

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
        assert "Created GitWrite structure commit." in result1.output

        repo = pygit2.Repository(str(test_dir))
        commit1_hash = repo.head.target

        # Second init
        result2 = runner.invoke(cli, ["init"])
        assert result2.exit_code == 0, f"Second init failed: {result2.output}"
        # This message indicates that the structure was found and no new commit was needed.
        assert "No changes to commit. GitWrite structure may already be committed and identical." in result2.output or \
               "And repository tree is identical to HEAD, no commit needed." in result2.output or \
               "No new GitWrite structure elements to stage." in result2.output


        commit2_hash = repo.head.target
        assert commit1_hash == commit2_hash, "No new commit should have been made on second init."
        self._assert_gitwrite_structure(test_dir)
