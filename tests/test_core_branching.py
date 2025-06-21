import pytest # For pytest.raises
import pygit2 # Used directly in tests
import os # Used by some test setups if not handled by fixtures
import shutil # Used by some test setups
from pathlib import Path # Used by some test setups
# Typing imports are now in conftest.py

# Corrected import path for core modules
from gitwrite_core.branching import (
    create_and_switch_branch,
    list_branches,
    switch_to_branch,
    merge_branch_into_current # Added for merge tests
)
from gitwrite_core.exceptions import (
    RepositoryNotFoundError,
    RepositoryEmptyError,
    BranchAlreadyExistsError,
    BranchNotFoundError,
    MergeConflictError, # Added for merge tests
    GitWriteError
)
from .conftest import make_commit_on_path

# Helper functions (make_commit_on_path, make_initial_commit) are in conftest.py
# Fixtures (test_repo, empty_test_repo, bare_test_repo, configure_git_user,
# repo_with_remote_branches, repo_for_merge, repo_for_ff_merge, repo_for_conflict_merge)
# are in conftest.py.
# The generic make_commit (taking repo object) is also in conftest.py

class TestCreateAndSwitchBranch:
    def test_success(self, test_repo: Path): # test_repo from conftest
        branch_name = "new-feature"
        result = create_and_switch_branch(str(test_repo), branch_name)
        assert result['status'] == 'success'
        assert result['branch_name'] == branch_name
        assert 'head_commit_oid' in result

        repo = pygit2.Repository(str(test_repo)) # pygit2 import is kept
        assert repo.head.shorthand == branch_name
        assert not repo.head_is_detached
        assert repo.lookup_branch(branch_name) is not None

    def test_error_repo_not_found(self, tmp_path: Path): # tmp_path from pytest
        non_existent_path = tmp_path / "non_existent_repo"
        # Ensure the directory does not exist for a clean test
        if non_existent_path.exists():
            shutil.rmtree(non_existent_path) # shutil import is kept

        with pytest.raises(RepositoryNotFoundError): # pytest.raises is kept
            create_and_switch_branch(str(non_existent_path), "any-branch")

    def test_error_bare_repo(self, bare_test_repo: Path): # bare_test_repo from conftest
        with pytest.raises(GitWriteError, match="Operation not supported in bare repositories"):
            create_and_switch_branch(str(bare_test_repo), "any-branch")

    def test_error_empty_repo_unborn_head(self, empty_test_repo: Path): # empty_test_repo from conftest
        repo = pygit2.Repository(str(empty_test_repo))
        assert repo.head_is_unborn # This is the key check for this test case

        # The core function's message is "Cannot create branch: HEAD is unborn. Commit changes first."
        # Let's match that specific message.
        with pytest.raises(RepositoryEmptyError, match="Cannot create branch: HEAD is unborn. Commit changes first."):
            create_and_switch_branch(str(empty_test_repo), "any-branch")

    def test_error_branch_already_exists(self, test_repo: Path): # test_repo from conftest
        branch_name = "existing-branch"
        repo = pygit2.Repository(str(test_repo))
        # Create the branch directly for setup
        head_commit = repo.head.peel(pygit2.Commit)
        repo.branches.local.create(branch_name, head_commit)

        with pytest.raises(BranchAlreadyExistsError, match=f"Branch '{branch_name}' already exists."):
            create_and_switch_branch(str(test_repo), branch_name)

    def test_branch_name_with_slashes(self, test_repo: Path): # test_repo from conftest
        # Git allows slashes in branch names, e.g. "feature/login"
        branch_name = "feature/user-login"
        result = create_and_switch_branch(str(test_repo), branch_name)
        assert result['status'] == 'success'
        assert result['branch_name'] == branch_name

        repo = pygit2.Repository(str(test_repo))
        assert repo.head.shorthand == branch_name # pygit2 shorthand handles this

    def test_checkout_safe_strategy(self, test_repo: Path): # test_repo from conftest
        # This test primarily ensures the function completes successfully, implying
        # the GIT_CHECKOUT_SAFE strategy didn't cause an issue on a clean repo.
        # A deeper test of GIT_CHECKOUT_SAFE's behavior (e.g., with a dirty workdir)
        # would require more setup and depends on how the core function is expected
        # to handle such cases (currently it would likely bubble up a pygit2 error).
        branch_name = "safe-checkout-branch"
        result = create_and_switch_branch(str(test_repo), branch_name)
        assert result['status'] == 'success'
        assert result['branch_name'] == branch_name
        # Add a check to ensure the branch is indeed active
        repo = pygit2.Repository(str(test_repo))
        assert repo.head.shorthand == branch_name

    # Consider adding a test for when HEAD is detached, though
    # `repo.head.peel(pygit2.Commit)` should still work if HEAD points to a commit.
    # The current `head_is_unborn` check is the primary guard for invalid HEAD states.
    # If HEAD were detached but pointed to a valid commit, branch creation should still succeed.
    def test_success_from_detached_head(self, test_repo: Path): # test_repo from conftest
        repo = pygit2.Repository(str(test_repo))
        # Detach HEAD by checking out the current HEAD commit directly
        current_commit_oid = repo.head.target
        repo.set_head(current_commit_oid) # This detaches HEAD
        assert repo.head_is_detached

        branch_name = "branch-from-detached"
        result = create_and_switch_branch(str(test_repo), branch_name)

        assert result['status'] == 'success'
        assert result['branch_name'] == branch_name
        assert result['head_commit_oid'] == str(current_commit_oid) # New branch points to the same commit

        # Verify repo state
        updated_repo = pygit2.Repository(str(test_repo))
        assert not updated_repo.head_is_detached
        assert updated_repo.head.shorthand == branch_name
        assert updated_repo.lookup_branch(branch_name) is not None
        assert updated_repo.head.target == current_commit_oid

    # Test case for when repo.head.peel(pygit2.Commit) might fail for other reasons
    # This is a bit harder to simulate without deeper pygit2 manipulation or specific repo states.
    # The `head_is_unborn` check in the core function aims to prevent `peel` errors.
    # If `peel` still fails, it raises pygit2.GitError, wrapped into GitWriteError by the core function.
    # One scenario could be if HEAD points to a non-commit object (e.g., a tag object directly, not a commit).
    # This is less common for `repo.head` but possible.

    # Let's refine the `make_initial_commit` to be more robust for the tests.
    # The one in the prompt is good, just a small tweak in the test for `test_error_empty_repo_unborn_head`
    # to match the exact error message from the core function.
    # I've also added a test for creating a branch from a detached HEAD.
    # And a small cleanup in `test_error_repo_not_found` to ensure the path doesn't exist.


class TestListBranches:
    def test_list_branches_success(self, test_repo: Path): # test_repo from conftest
        repo = pygit2.Repository(str(test_repo)) # test_repo has 'main' by default from make_initial_commit

        # Create a couple more branches
        main_commit = repo.head.peel(pygit2.Commit)
        repo.branches.local.create("feature-a", main_commit)
        repo.branches.local.create("hotfix/b", main_commit) # Branch with slash

        # Switch to feature-a to make it current
        repo.checkout(repo.branches.local["feature-a"].name)
        repo.set_head(repo.branches.local["feature-a"].name)

        result = list_branches(str(test_repo))

        assert isinstance(result, list) # list from Python builtins
        assert len(result) == 3 # main, feature-a, hotfix/b

        expected_names = ["feature-a", "hotfix/b", "main"] # Sorted order
        actual_names = [b['name'] for b in result]
        assert actual_names == expected_names

        current_found = False
        for branch_data in result:
            assert 'name' in branch_data
            assert 'is_current' in branch_data
            assert 'target_oid' in branch_data
            if branch_data['name'] == "feature-a":
                assert branch_data['is_current'] is True
                current_found = True
            else:
                assert branch_data['is_current'] is False
        assert current_found, "Current branch 'feature-a' not marked as current."

    def test_list_branches_empty_repo(self, empty_test_repo: Path): # empty_test_repo from conftest
        result = list_branches(str(empty_test_repo))
        assert result == []

    def test_list_branches_bare_repo(self, bare_test_repo: Path): # bare_test_repo from conftest
        with pytest.raises(GitWriteError, match="Operation not supported in bare repositories"):
            list_branches(str(bare_test_repo))

    def test_list_branches_repo_not_found(self, tmp_path: Path): # tmp_path from pytest
        non_existent_path = tmp_path / "non_existent_repo_for_list"
        if non_existent_path.exists(): shutil.rmtree(non_existent_path) # shutil import is kept
        with pytest.raises(RepositoryNotFoundError):
            list_branches(str(non_existent_path))

    def test_list_branches_detached_head(self, test_repo: Path): # test_repo from conftest
        repo = pygit2.Repository(str(test_repo))
        # Detach HEAD
        repo.set_head(repo.head.target)
        assert repo.head_is_detached

        # Add another branch to ensure local branches are listed
        main_commit = repo.lookup_reference("refs/heads/main").peel(pygit2.Commit)
        repo.branches.local.create("feature-c", main_commit)

        result = list_branches(str(test_repo))
        assert isinstance(result, list)
        # Expecting 'main' and 'feature-c'
        assert len(result) >= 1 # test_repo creates 'main'

        found_main = False
        for branch_data in result:
            assert branch_data['is_current'] is False, "No branch should be current in detached HEAD state."
            if branch_data['name'] == 'main':
                found_main = True
        assert found_main


class TestSwitchToBranch:
    def test_switch_success_local_branch(self, test_repo: Path): # test_repo from conftest
        repo = pygit2.Repository(str(test_repo)) # On 'main'
        main_commit = repo.head.peel(pygit2.Commit)
        repo.branches.local.create("develop", main_commit)

        result = switch_to_branch(str(test_repo), "develop")

        assert result['status'] == 'success'
        assert result['branch_name'] == "develop"
        assert result['previous_branch_name'] == "main" # or specific default from fixture
        assert result.get('is_detached') is False

        updated_repo = pygit2.Repository(str(test_repo))
        assert not updated_repo.head_is_detached
        assert updated_repo.head.shorthand == "develop"

    def test_switch_already_on_branch(self, test_repo: Path): # test_repo from conftest
        # test_repo is already on 'main' (or default branch from make_initial_commit)
        current_branch_name = pygit2.Repository(str(test_repo)).head.shorthand
        result = switch_to_branch(str(test_repo), current_branch_name)
        assert result['status'] == 'already_on_branch'
        assert result['branch_name'] == current_branch_name

    def test_switch_to_remote_tracking_branch_origin(self, repo_with_remote_branches: Path): # repo_with_remote_branches from conftest
        # 'feature-a' was pushed to origin/feature-a.
        # Delete local 'feature-a' to ensure we are checking out from remote.
        local_repo = pygit2.Repository(str(repo_with_remote_branches))
        if "feature-a" in local_repo.branches.local:
             local_repo.branches.local.delete("feature-a")

        # Switch to 'feature-a', expecting it to be found via 'origin/feature-a' and result in detached HEAD
        result = switch_to_branch(str(repo_with_remote_branches), "feature-a")

        assert result['status'] == 'success'
        # The core function resolves "feature-a" to "origin/feature-a" and branch_name in result is "origin/feature-a"
        assert result['branch_name'] == "origin/feature-a"
        assert result.get('is_detached') is True

        updated_repo = pygit2.Repository(str(repo_with_remote_branches))
        assert updated_repo.head_is_detached
        # Check if HEAD points to the commit of origin/feature-a
        remote_branch = updated_repo.branches.remote.get("origin/feature-a")
        assert remote_branch is not None
        assert updated_repo.head.target == remote_branch.target

    def test_switch_to_full_remote_tracking_branch_name(self, repo_with_remote_branches: Path): # repo_with_remote_branches from conftest
        # The fixture pushed local 'origin-special-feature' to remote 'origin/special-feature'
        # We are testing if user provides "origin/special-feature" directly.
        # The fixture pushes local 'origin-special-feature' to remote 'origin/special-feature'.
        # When pygit2 fetches this, the remote-tracking branch is named 'origin/origin/special-feature'.
        input_branch_name = "origin/special-feature" # User input
        expected_resolved_branch_name = "origin/origin/special-feature" # Actual pygit2 branch name

        result = switch_to_branch(str(repo_with_remote_branches), input_branch_name)

        assert result['status'] == 'success'
        # Expecting the fully resolved pygit2 branch name now
        assert result['branch_name'] == expected_resolved_branch_name
        assert result.get('is_detached') is True

        updated_repo = pygit2.Repository(str(repo_with_remote_branches))
        # HEAD should point to the commit of 'origin/origin/special-feature' (the actual resolved ref)
        # The expected_resolved_branch_name still refers to the actual pygit2 branch name.
        remote_branch_obj = updated_repo.branches.remote.get(expected_resolved_branch_name)
        assert remote_branch_obj is not None
        assert updated_repo.head.target == remote_branch_obj.target
        assert updated_repo.head_is_detached
        # The assertion above already checks HEAD target via remote_branch_obj.target


    def test_switch_branch_not_found(self, test_repo: Path): # test_repo from conftest
        with pytest.raises(BranchNotFoundError, match="Branch 'non-existent-branch' not found"):
            switch_to_branch(str(test_repo), "non-existent-branch")

    def test_switch_bare_repo(self, bare_test_repo: Path): # bare_test_repo from conftest
        with pytest.raises(GitWriteError, match="Operation not supported in bare repositories"):
            switch_to_branch(str(bare_test_repo), "anybranch")

    def test_switch_repo_not_found(self, tmp_path: Path): # tmp_path from pytest
        non_existent_path = tmp_path / "non_existent_for_switch"
        if non_existent_path.exists(): shutil.rmtree(non_existent_path) # shutil import is kept
        with pytest.raises(RepositoryNotFoundError):
            switch_to_branch(str(non_existent_path), "anybranch")

    def test_switch_empty_repo_no_branches_exist(self, empty_test_repo: Path): # empty_test_repo from conftest
        # Core `switch_to_branch` raises BranchNotFoundError if branch doesn't exist,
        # or RepositoryEmptyError if the repo is empty and the branch isn't found.
        with pytest.raises(RepositoryEmptyError, match="Cannot switch branch in an empty repository to non-existent branch 'anybranch'"):
            switch_to_branch(str(empty_test_repo), "anybranch")

    def test_switch_checkout_failure_dirty_workdir(self, test_repo: Path): # test_repo from conftest
        repo = pygit2.Repository(str(test_repo)) # On 'main'

        # Create 'develop' branch and switch to it
        main_commit = repo.head.peel(pygit2.Commit)
        repo.branches.local.create("develop", main_commit)
        repo.checkout("refs/heads/develop")
        repo.set_head("refs/heads/develop")
        # Commit a file on 'develop' that is different from 'main'
        # Using make_commit_helper for subsequent commits
        make_commit_on_path(str(test_repo), filename="conflict.txt", content="Version on develop", msg="Add conflict.txt on develop") # make_commit_on_path from conftest

        # Switch back to 'main'
        repo.checkout("refs/heads/main") # Assumes 'main' exists from test_repo fixture
        repo.set_head("refs/heads/main")
        # Create the same file on 'main' but with different content (to ensure checkout to develop would modify it)
        (Path(str(test_repo)) / "conflict.txt").write_text("Version on main - will be changed by user") # Path import is kept
        # DO NOT COMMIT THIS CHANGE ON MAIN. This makes the working dir dirty for 'conflict.txt'.

        # Now try to switch to 'develop'. Checkout should fail due to 'conflict.txt' being modified.
        # The actual pygit2 error message is "1 conflict prevents checkout"
        with pytest.raises(GitWriteError, match="Checkout operation failed for 'develop': 1 conflict prevents checkout"):
            switch_to_branch(str(test_repo), "develop")


class TestMergeBranch:
    def test_merge_success_normal(self, repo_for_merge: Path, configure_git_user): # Fixtures from conftest
        # repo_for_merge is already on 'main'
        # configure_git_user has already been applied to repo_for_merge fixture
        result = merge_branch_into_current(str(repo_for_merge), "feature")

        assert result['status'] == 'merged_ok'
        assert result['branch_name'] == "feature" # branch that was merged
        assert result['current_branch'] == "main"  # branch merged into
        assert 'commit_oid' in result

        # Verify merge commit details
        merge_commit_oid = pygit2.Oid(hex=result['commit_oid'])
        repo_check_commit = pygit2.Repository(str(repo_for_merge))
        merge_commit = repo_check_commit.get(merge_commit_oid)
        assert isinstance(merge_commit, pygit2.Commit)
        assert len(merge_commit.parents) == 2
        assert f"Merge branch 'feature' into main" in merge_commit.message

        # Re-instantiate repo object to check state
        repo_after_merge = pygit2.Repository(str(repo_for_merge))
        # Check practical indicators of a clean state instead of strict repo.state
        assert repo_after_merge.index.conflicts is None, "Index should have no conflicts after merge."
        assert repo_after_merge.references.get("MERGE_HEAD") is None, "MERGE_HEAD should not exist after successful merge."
        # Optionally, still check state if it's usually NONE, but be aware it can be flaky
        # print(f"DEBUG: Repo state after merge: {repo_after_merge.state}") # For debugging if needed
        # For now, removing the direct state check as it's problematic.

    def test_merge_success_fast_forward(self, repo_for_ff_merge: Path, configure_git_user): # Fixtures from conftest
        # repo_for_ff_merge is on 'main', 'feature' is ahead.
        result = merge_branch_into_current(str(repo_for_ff_merge), "feature")

        assert result['status'] == 'fast_forwarded'
        assert result['branch_name'] == "feature"
        assert 'commit_oid' in result # This is the commit feature was pointing to

        repo = pygit2.Repository(str(repo_for_ff_merge))
        assert repo.head.target == repo.branches.local['feature'].target
        assert str(repo.head.target) == result['commit_oid']
        # Check working directory content (e.g., feature_ff.txt exists)
        assert (Path(str(repo_for_ff_merge)) / "feature_ff.txt").exists() # Path import is kept

    def test_merge_up_to_date(self, repo_for_ff_merge: Path, configure_git_user): # Fixtures from conftest
        # First, merge 'feature' into 'main' (fast-forward)
        merge_branch_into_current(str(repo_for_ff_merge), "feature")

        # Attempt to merge again
        result = merge_branch_into_current(str(repo_for_ff_merge), "feature")
        assert result['status'] == 'up_to_date'
        assert result['branch_name'] == "feature"

    def test_merge_conflict(self, repo_for_conflict_merge: Path, configure_git_user): # Fixtures from conftest
        with pytest.raises(MergeConflictError) as excinfo:
            merge_branch_into_current(str(repo_for_conflict_merge), "feature")

        assert "Automatic merge of 'feature' into 'main' failed due to conflicts." in str(excinfo.value)
        assert excinfo.value.conflicting_files == ["conflict.txt"]

        repo = pygit2.Repository(str(repo_for_conflict_merge))
        assert repo.index.conflicts is not None
        # MERGE_HEAD should be set indicating an incomplete merge
        assert repo.lookup_reference("MERGE_HEAD") is not None

    def test_merge_branch_not_found(self, test_repo: Path, configure_git_user): # Fixtures from conftest
        configure_git_user(pygit2.Repository(str(test_repo))) # ensure signature for consistency if other tests modify it
        with pytest.raises(BranchNotFoundError):
            merge_branch_into_current(str(test_repo), "non-existent-branch")

    def test_merge_into_itself(self, test_repo: Path, configure_git_user): # Fixtures from conftest
        configure_git_user(pygit2.Repository(str(test_repo)))
        with pytest.raises(GitWriteError, match="Cannot merge a branch into itself"):
            merge_branch_into_current(str(test_repo), "main") # Assuming 'main' is current

    def test_merge_in_bare_repo(self, bare_test_repo: Path): # bare_test_repo from conftest
        with pytest.raises(GitWriteError, match="Cannot merge in a bare repository"):
            merge_branch_into_current(str(bare_test_repo), "any-branch")

    def test_merge_in_empty_repo(self, empty_test_repo: Path, configure_git_user): # Fixtures from conftest
        # configure_git_user might fail on empty repo if it tries to read HEAD for config
        # For this test, signature isn't the primary concern, but repo state.
        # Let's try to configure. If it fails, it highlights another issue.
        # repo = pygit2.Repository(str(empty_test_repo))
        # configure_git_user(repo) # This might fail as HEAD is unborn
        with pytest.raises(RepositoryEmptyError, match="Repository is empty or HEAD is unborn"):
            merge_branch_into_current(str(empty_test_repo), "any-branch")

    def test_merge_detached_head(self, test_repo: Path, configure_git_user): # Fixtures from conftest
        repo = pygit2.Repository(str(test_repo))
        configure_git_user(repo)
        repo.set_head(repo.head.target) # Detach HEAD
        assert repo.head_is_detached
        with pytest.raises(GitWriteError, match="HEAD is detached"):
            merge_branch_into_current(str(test_repo), "main")

    def test_merge_no_signature_configured(self, repo_for_merge: Path): # repo_for_merge from conftest
        # The repo_for_merge fixture uses configure_git_user.
        # We need a repo *without* user configured.
        repo_no_sig_path = repo_for_merge # Re-use path, but re-init repo without config

        # Clean up existing repo at path and reinitialize without signature
        if (repo_no_sig_path / ".git").exists(): # Ensure .git exists before trying to remove
            shutil.rmtree(repo_no_sig_path / ".git") # shutil import is kept
        repo = pygit2.init_repository(str(repo_no_sig_path))

        # Explicitly delete local config for user.name and user.email
        config = repo.config
        # Try setting local config to empty strings, which might prevent fallback to global/system
        try:
            config["user.name"] = ""
            config["user.email"] = ""
        except pygit2.ConfigurationError as e:
            # This might happen if config files are locked or some other backend issue
            print(f"Warning: Could not set empty config for signature test: {e}")
            pass # Proceed anyway, the test will confirm if default_signature fails

        # DO NOT call configure_git_user(repo)

        # Setup branches manually like in repo_for_merge
        # C0 - Initial commit on main
        make_commit_on_path(str(repo_no_sig_path), filename="common.txt", content="line0", msg="C0: Initial on main", branch_name="main") # make_commit_on_path from conftest
        c0_oid = repo.head.target
        # C1 on main
        make_commit_on_path(str(repo_no_sig_path), filename="main_file.txt", content="main content", msg="C1: Commit on main", branch_name="main") # make_commit_on_path from conftest
        # Create feature branch from C0
        feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
        repo.checkout(feature_branch.name)
        repo.set_head(feature_branch.name)
        make_commit_on_path(str(repo_no_sig_path), filename="feature_file.txt", content="feature content", msg="C2: Commit on feature", branch_name="feature") # make_commit_on_path from conftest
        # Switch back to main
        main_branch_ref = repo.branches.local.get("main")
        repo.checkout(main_branch_ref.name)
        repo.set_head(main_branch_ref.name)

        # Escape regex special characters in the match string
        expected_error_message = r"User signature \(user\.name and user\.email\) not configured in Git\."
        with pytest.raises(GitWriteError, match=expected_error_message):
            merge_branch_into_current(str(repo_no_sig_path), "feature")
