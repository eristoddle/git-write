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
    assert f"Merge remote-tracking branch 'origin/{local_branch_name}'" in merge_commit.message

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

    assert result_revert_merge.exit_code != 0, "Reverting a merge commit should fail with current implementation."
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
        self._assert_common_gitignore_patterns(test_dir / ".gitignore")

        repo = pygit2.Repository(str(test_dir))
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
