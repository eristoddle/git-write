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


# More tests to come
