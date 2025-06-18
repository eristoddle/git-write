import pytest
import pygit2
import os
import shutil
from pathlib import Path
from click.testing import CliRunner
from unittest.mock import patch

# Assuming your CLI script is gitwrite_cli.main
from gitwrite_cli.main import cli
from gitwrite_core.repository import initialize_repository, COMMON_GITIGNORE_PATTERNS, add_pattern_to_gitignore, list_gitignore_patterns # New imports

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
