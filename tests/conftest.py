import pytest
import pygit2
import os
import shutil
from pathlib import Path
from click.testing import CliRunner
from gitwrite_cli.main import cli
# Note: Rich and gitwrite_core.exceptions might be needed if other fixtures use them.
from unittest.mock import MagicMock, PropertyMock # For mock_repo fixture

# Helper to create a commit (enhanced version from test_cli_sync_merge.py)
def make_commit(repo, filename, content, message, branch_name=None): # Added branch_name for flexibility
    # Create file
    file_path = Path(repo.workdir) / filename
    file_path.write_text(content)
    # Stage
    repo.index.add(filename)
    repo.index.write()
    # Commit
    author = pygit2.Signature("Test Author", "test@example.com", 946684800, 0)
    committer = pygit2.Signature("Test Committer", "committer@example.com", 946684800, 0)

    # Handle branching if specified
    current_head_ref = "HEAD"
    parents = []

    if branch_name:
        if repo.head_is_unborn:
            # For the very first commit, point HEAD to the target branch directly
            current_head_ref = f"refs/heads/{branch_name}"
            # Parents list is already empty, which is correct for an initial commit
        else:
            # For subsequent commits on a named branch
            if branch_name not in repo.branches.local:
                repo.branches.local.create(branch_name, repo.head.peel(pygit2.Commit))

            # Checkout the branch to ensure the commit happens on it
            # and HEAD points to it.
            if repo.head.shorthand != branch_name:
                 branch_obj = repo.branches.local.get(branch_name)
                 if branch_obj:
                    repo.checkout(branch_obj)
                 else:
                    # This case should ideally not be reached if creation was successful
                    # or if branch_name was meant for an initial commit.
                    # Fallback or error might be needed if branch_obj is None.
                    pass # Or raise an error
            current_head_ref = repo.lookup_reference(f"refs/heads/{branch_name}").name
            parents = [repo.head.target] # Parent is the current commit on this branch
    elif not repo.head_is_unborn:
        # Standard commit on current HEAD if not unborn and no specific branch name given
        parents = [repo.head.target]
    # If repo.head_is_unborn and no branch_name, it's an initial commit on default branch (e.g. main)
    # parents remains empty, current_head_ref remains "HEAD"

    tree = repo.index.write_tree()
    commit_oid = repo.create_commit(current_head_ref, author, committer, message, tree, parents)

    # If it was an initial commit and a specific branch was named,
    # ensure HEAD is correctly pointing to this branch.
    # This is especially important if pygit2's default initial branch (e.g. "master")
    # differs from the desired branch_name (e.g. "main").
    if repo.head_is_unborn and branch_name and current_head_ref == f"refs/heads/{branch_name}":
         # After the commit, HEAD might still be detached or on a default branch like 'master'.
         # Explicitly set HEAD to the new branch.
         new_branch_ref = repo.lookup_reference(f"refs/heads/{branch_name}")
         if new_branch_ref:
             repo.set_head(new_branch_ref.name)
         # If the commit created a branch like 'master' instead of 'main' (older pygit2/libgit2),
         # and 'main' was desired, rename it.
         # However, with current_head_ref set to f"refs/heads/{branch_name}", this should create the correct branch.

    return commit_oid

@pytest.fixture
def runner():
    return CliRunner()

@pytest.fixture
def cli_test_repo(tmp_path: Path):
    """Creates a standard initialized repo for CLI tests, returning its path."""
    repo_path = tmp_path / "cli_git_repo_explore_switch" # Unique name
    repo_path.mkdir()
    repo = pygit2.init_repository(str(repo_path), bare=False)
    # Initial commit
    file_path = repo_path / "initial.txt"
    file_path.write_text("initial content for explore/switch tests")
    repo.index.add("initial.txt")
    repo.index.write()
    author_sig = pygit2.Signature("Test Author CLI", "testcli@example.com") # Use one signature obj
    tree = repo.index.write_tree()
    repo.create_commit("HEAD", author_sig, author_sig, "Initial commit for CLI explore/switch", tree, [])
    return repo_path

@pytest.fixture
def cli_repo_with_remote(tmp_path: Path, runner: CliRunner): # Added runner fixture for potential CLI use
    local_repo_path = tmp_path / "cli_local_for_remote_switch"
    local_repo_path.mkdir()
    local_repo = pygit2.init_repository(str(local_repo_path))
    make_commit(local_repo, "main_file.txt", "content on main", "Initial commit on main")

    bare_remote_path = tmp_path / "cli_remote_server_switch.git"
    pygit2.init_repository(str(bare_remote_path), bare=True)

    origin_remote = local_repo.remotes.create("origin", str(bare_remote_path))
    main_branch_name = local_repo.head.shorthand
    origin_remote.push([f"refs/heads/{main_branch_name}:refs/heads/{main_branch_name}"])

    main_commit = local_repo.head.peel(pygit2.Commit)
    local_repo.branches.local.create("feature-x", main_commit)
    local_repo.checkout("refs/heads/feature-x")
    make_commit(local_repo, "fx_file.txt", "feature-x content", "Commit on feature-x")
    origin_remote.push(["refs/heads/feature-x:refs/heads/feature-x"])

    local_repo.checkout(f"refs/heads/{main_branch_name}")
    main_commit_again = local_repo.head.peel(pygit2.Commit)
    local_repo.branches.local.create("feature-y-local", main_commit_again)
    local_repo.checkout("refs/heads/feature-y-local")
    make_commit(local_repo, "fy_file.txt", "feature-y content", "Commit for feature-y")
    origin_remote.push(["refs/heads/feature-y-local:refs/heads/feature-y"])
    # Checkout main before deleting feature-y-local, as it's the current HEAD
    local_repo.checkout(f"refs/heads/{main_branch_name}")
    local_repo.branches.local.delete("feature-y-local")
    return local_repo_path

@pytest.fixture
def local_repo_path(tmp_path: Path): # Required by local_repo
    return tmp_path / "local_project_for_history_compare"

@pytest.fixture
def local_repo(local_repo_path: Path): # Adapted from test_main.py
    if local_repo_path.exists():
        shutil.rmtree(local_repo_path)
    local_repo_path.mkdir()
    repo = pygit2.init_repository(str(local_repo_path), bare=False)
    # Use the make_commit from conftest.py
    make_commit(repo, "initial.txt", "Initial content", "Initial version") # Changed message
    config = repo.config
    config["user.name"] = "Test Author"
    config["user.email"] = "test@example.com"
    return repo

# Imports for new helpers
from gitwrite_core.repository import COMMON_GITIGNORE_PATTERNS

# Helper functions for init tests (moved from test_cli_init_ignore.py)
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
    for pattern in COMMON_GITIGNORE_PATTERNS:
        assert pattern in content, f"Expected core pattern '{pattern}' not found in .gitignore"

# Fixture for init tests (moved from test_cli_init_ignore.py)
@pytest.fixture
def init_test_dir(tmp_path: Path):
    """Provides a clean directory path for init tests."""
    test_base_dir = tmp_path / "init_tests_base"
    test_base_dir.mkdir(exist_ok=True)
    project_dir = test_base_dir / "test_project"
    if project_dir.exists():
        shutil.rmtree(project_dir)
    return project_dir

@pytest.fixture
def bare_remote_repo_obj(tmp_path: Path) -> pygit2.Repository:
    """Creates a bare repository object for testing remotes."""
    bare_repo_path = tmp_path / "bare_remote_for_conftest.git"
    if bare_repo_path.exists():
        shutil.rmtree(bare_repo_path)
    # Initialize a bare repository
    repo = pygit2.init_repository(str(bare_repo_path), bare=True)
    return repo

# Helper functions for save/revert tests (from test_cli_save_revert.py)
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

def resolve_conflict(repo: pygit2.Repository, filename: str, resolved_content: str):
    """
    Helper function to resolve a conflict in a file.
    This involves writing the resolved content, adding the file to the index.
    Pygit2's index.add() should handle clearing the conflict state for the path.
    """
    file_path = Path(repo.workdir) / filename
    file_path.write_text(resolved_content)
    repo.index.add(filename)
    repo.index.write()

# Fixtures for save/revert command tests (from test_cli_save_revert.py)
@pytest.fixture
def repo_with_unstaged_changes(local_repo: pygit2.Repository):
    """Creates a repository with a file that has unstaged changes."""
    create_file(local_repo, "unstaged_file.txt", "This file has unstaged changes.")
    return local_repo

@pytest.fixture
def repo_with_staged_changes(local_repo: pygit2.Repository):
    """Creates a repository with a file that has staged changes."""
    create_file(local_repo, "staged_file.txt", "This file has staged changes.")
    stage_file(local_repo, "staged_file.txt")
    return local_repo

@pytest.fixture
def repo_with_merge_conflict(local_repo: pygit2.Repository, bare_remote_repo_obj: pygit2.Repository, tmp_path: Path):
    """Creates a repository with a merge conflict."""
    # local_repo is already in the correct CWD due to how local_repo fixture is defined (if it chdirs)
    # If not, we might need os.chdir(local_repo.workdir)
    # For safety, let's ensure CWD is local_repo.workdir
    if Path.cwd() != Path(local_repo.workdir):
         os.chdir(local_repo.workdir)

    branch_name = local_repo.head.shorthand

    # Base file
    conflict_filename = "conflict_file.txt"
    initial_content = "Line 1\nLine 2 for conflict\nLine 3\n"
    make_commit(local_repo, conflict_filename, initial_content, f"Add initial {conflict_filename}")

    if "origin" not in local_repo.remotes:
        local_repo.remotes.create("origin", bare_remote_repo_obj.path) # Use path of the bare repo obj

    # Ensure the remote URL is correctly set to the bare_remote_repo_obj.path
    # This might be redundant if create already sets it, but good for safety.
    local_repo.remotes.set_url("origin", bare_remote_repo_obj.path)

    local_repo.remotes["origin"].push([f"refs/heads/{branch_name}:refs/heads/{branch_name}"])
    base_commit_oid = local_repo.head.target

    # 1. Local change
    local_conflict_content = "Line 1\nLOCAL CHANGE on Line 2\nLine 3\n"
    make_commit(local_repo, conflict_filename, local_conflict_content, "Local conflicting change")

    # 2. Remote change (via a clone of the bare_remote_repo_obj)
    remote_clone_path = tmp_path / "remote_clone_for_merge_conflict_fixture_conftest"
    if remote_clone_path.exists(): shutil.rmtree(remote_clone_path)
    remote_clone_repo = pygit2.clone_repository(bare_remote_repo_obj.path, str(remote_clone_path))

    config = remote_clone_repo.config
    config["user.name"] = "Remote Conflicter"
    config["user.email"] = "conflicter@example.com"

    # Ensure the clone is on the correct branch and reset to base
    # Default clone might already be on the main/master branch if it's the only one.
    # If bare repo was empty initially, the push created the branch.
    cloned_branch_ref = remote_clone_repo.lookup_reference(f"refs/heads/{branch_name}")
    if not cloned_branch_ref:
        pytest.fail(f"Branch {branch_name} not found in cloned remote repository.")
    remote_clone_repo.checkout(cloned_branch_ref.name)
    remote_clone_repo.reset(base_commit_oid, pygit2.GIT_RESET_HARD)

    assert (Path(remote_clone_repo.workdir) / conflict_filename).read_text() == initial_content
    remote_conflict_content = "Line 1\nREMOTE CHANGE on Line 2\nLine 3\n"
    make_commit(remote_clone_repo, conflict_filename, remote_conflict_content, "Remote conflicting change for fixture")
    remote_clone_repo.remotes["origin"].push([f"+refs/heads/{branch_name}:refs/heads/{branch_name}"])
    shutil.rmtree(remote_clone_path)

    # 3. Fetch remote changes to local repo
    local_repo.remotes["origin"].fetch()

    # 4. Attempt merge to create conflict
    remote_tracking_branch_ref = local_repo.branches.get(f"origin/{branch_name}")
    if not remote_tracking_branch_ref: # Fallback if not found directly
        remote_tracking_branch_ref = local_repo.lookup_reference(f"refs/remotes/origin/{branch_name}")

    assert remote_tracking_branch_ref is not None, f"Could not find remote tracking branch origin/{branch_name}"

    merge_result, _ = local_repo.merge_analysis(remote_tracking_branch_ref.target)
    if merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE:
        pytest.skip("Repo already up to date, cannot create merge conflict for test.")

    local_repo.merge(remote_tracking_branch_ref.target)

    assert local_repo.index.conflicts is not None
    conflict_entry_iterator = iter(local_repo.index.conflicts)
    try:
        next(conflict_entry_iterator)
    except StopIteration:
        pytest.fail("Merge did not result in conflicts as expected.")

    assert local_repo.lookup_reference("MERGE_HEAD").target == remote_tracking_branch_ref.target
    return local_repo

@pytest.fixture
def repo_with_revert_conflict(local_repo: pygit2.Repository):
    """Creates a repository with a conflict during a revert operation."""
    # Ensure CWD is local_repo.workdir for safety, if local_repo doesn't chdir itself.
    if Path.cwd() != Path(local_repo.workdir):
        os.chdir(local_repo.workdir)

    file_path = Path("revert_conflict_file.txt")

    content_A = "Version A\nCommon Line\nEnd A\n"
    make_commit(local_repo, str(file_path.name), content_A, "Commit A: Base for revert conflict")

    content_B = "Version B\nModified Common Line by B\nEnd B\n"
    make_commit(local_repo, str(file_path.name), content_B, "Commit B: To be reverted")
    commit_B_hash = local_repo.head.target

    content_C = "Version C\nModified Common Line by C (conflicts with A's version)\nEnd C\n"
    make_commit(local_repo, str(file_path.name), content_C, "Commit C: Conflicting with revert of B")

    try:
        local_repo.revert(local_repo.get(commit_B_hash))
    except pygit2.GitError: # Revert can raise GitError if conflicts prevent it from completing
        pass # Expected in conflict scenarios

    # Check for REVERT_HEAD and conflicts in index
    assert local_repo.lookup_reference("REVERT_HEAD").target == commit_B_hash
    assert local_repo.index.conflicts is not None
    conflict_entry_iterator = iter(local_repo.index.conflicts)
    try:
        next(conflict_entry_iterator) # Check if there's at least one conflict
    except StopIteration:
        pytest.fail("Revert did not result in conflicts in the index as expected.")
    return local_repo

# Fixtures for sync/merge tests (from test_cli_sync_merge.py)
@pytest.fixture
def configure_git_user_for_cli(tmp_path: Path): # tmp_path is a built-in pytest fixture
    """Fixture to configure user.name and user.email for CLI tests requiring commits."""
    def _configure(repo_path_str: str):
        repo = pygit2.Repository(repo_path_str)
        config = repo.config
        # Use set_multivar for consistency if these can be global/system,
        # or just config[...] for local. For testing, local is usually fine.
        config["user.name"] = "CLITest User"
        config["user.email"] = "clitest@example.com"
    return _configure

@pytest.fixture
def cli_repo_for_merge(tmp_path: Path, configure_git_user_for_cli) -> Path:
    repo_path = tmp_path / "cli_merge_normal_repo"
    repo_path.mkdir()
    pygit2.init_repository(str(repo_path))
    configure_git_user_for_cli(str(repo_path)) # Call the config fixture
    repo = pygit2.Repository(str(repo_path))
    # Use the conftest make_commit
    make_commit(repo, "common.txt", "line0", "C0: Initial on main", branch_name="main")
    c0_oid = repo.head.target
    make_commit(repo, "main_file.txt", "main content", "C1: Commit on main", branch_name="main")
    repo.branches.local.create("feature", repo.get(c0_oid))
    make_commit(repo, "feature_file.txt", "feature content", "C2: Commit on feature", branch_name="feature")
    repo.checkout(repo.branches.local['main'].name)
    return repo_path

@pytest.fixture
def cli_repo_for_ff_merge(tmp_path: Path, configure_git_user_for_cli) -> Path:
    repo_path = tmp_path / "cli_repo_for_ff_merge"
    repo_path.mkdir()
    pygit2.init_repository(str(repo_path))
    configure_git_user_for_cli(str(repo_path))
    repo = pygit2.Repository(str(repo_path))
    make_commit(repo, "main_base.txt", "base for ff", "C0: Base on main", branch_name="main")
    c0_oid = repo.head.target
    repo.branches.local.create("feature", repo.get(c0_oid))
    make_commit(repo, "feature_ff.txt", "ff content", "C1: Commit on feature", branch_name="feature")
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
    make_commit(repo, conflict_file, "Line1\nCommon Line\nLine3", "C0: Common ancestor", branch_name="main")
    c0_oid = repo.head.target
    make_commit(repo, conflict_file, "Line1\nChange on Main\nLine3", "C1: Change on main", branch_name="main")
    feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
    repo.checkout(feature_branch.name) # Checkout feature branch
    # Reset feature branch's working dir to match C0 to avoid conflict during next make_commit's checkout
    repo.reset(c0_oid, pygit2.GIT_RESET_HARD)
    make_commit(repo, conflict_file, "Line1\nChange on Feature\nLine3", "C2: Change on feature", branch_name="feature")
    repo.checkout(repo.branches.local['main'].name)
    return repo_path

@pytest.fixture
def synctest_repos(tmp_path: Path, local_repo: pygit2.Repository, bare_remote_repo_obj: pygit2.Repository):
    """
    Sets up a local repository, a bare remote repository, and a path for a second clone.
    Uses the existing `local_repo` from conftest as a base for one of the operations if needed,
    but primarily creates its own isolated set of repos for sync testing.
    """
    base_dir = tmp_path / "sync_test_area_for_cli_conftest"
    base_dir.mkdir(exist_ok=True)

    local_repo_path_for_sync = base_dir / "local_user_repo_sync_conftest"
    if local_repo_path_for_sync.exists():
        shutil.rmtree(local_repo_path_for_sync)
    local_repo_path_for_sync.mkdir()

    # Initialize a new local repo for sync test to avoid interference with the generic local_repo
    cloned_local_repo = pygit2.init_repository(str(local_repo_path_for_sync), bare=False)
    config_local = cloned_local_repo.config
    config_local["user.name"] = "Local Sync User"
    config_local["user.email"] = "localsync@example.com"
    make_commit(cloned_local_repo, "initial_sync_local.txt", "Local's first file for sync", "Initial local sync commit on main", branch_name="main") # Ensure this uses the updated make_commit

    # Use the bare_remote_repo_obj fixture passed in
    # Ensure it's clean or re-initialize if necessary (bare_remote_repo_obj should be fresh from its own fixture scope)

    if "origin" not in cloned_local_repo.remotes: # Create remote if it doesn't exist
        cloned_local_repo.remotes.create("origin", bare_remote_repo_obj.path)
    else: # Ensure URL is correct if it does exist
        cloned_local_repo.remotes.set_url("origin", bare_remote_repo_obj.path)

    active_branch_name_local = cloned_local_repo.head.shorthand # This should be 'main' after fixed make_commit
    cloned_local_repo.remotes["origin"].push([f"refs/heads/{active_branch_name_local}:refs/heads/{active_branch_name_local}"])

    remote_clone_repo_path_for_sync = base_dir / "remote_clone_user_repo_sync_conftest"

    return {
        "local_repo": cloned_local_repo,
        "remote_bare_repo": bare_remote_repo_obj, # This is the pygit2.Repository object
        "remote_clone_repo_path": remote_clone_repo_path_for_sync,
        "local_repo_path_str": str(local_repo_path_for_sync),
        "remote_bare_repo_path_str": bare_remote_repo_obj.path # Use .path for string URL
    }

@pytest.fixture
def mock_repo() -> MagicMock: # Type hint for clarity
    """Fixture to create a mock pygit2.Repository object."""
    repo = MagicMock(spec=pygit2.Repository)
    repo.is_bare = False
    repo.is_empty = False
    repo.head_is_unborn = False
    # Ensuring default_signature is a Signature object if code under test expects one.
    # If only its attributes are accessed, a MagicMock might be enough.
    # For safety, let's make it a real Signature if that's what pygit2.Repository would provide.
    try:
        repo.default_signature = pygit2.Signature("Test User", "test@example.com", 1234567890, 0)
    except Exception: # Handle cases where pygit2 might not be fully available in test env
        repo.default_signature = MagicMock()
        repo.default_signature.name = "Test User"
        repo.default_signature.email = "test@example.com"
        repo.default_signature.time = 1234567890
        repo.default_signature.offset = 0


    mock_head_commit = MagicMock(spec=pygit2.Commit)
    # Create a valid Oid for tests that might need it
    # Changed .id to .oid to match attribute access in core code (e.g. create_tag)
    try:
        mock_head_commit.oid = pygit2.Oid(hex="0123456789abcdef0123456789abcdef01234567")
    except Exception: # Fallback if pygit2.Oid is not available
        mock_head_commit.oid = "0123456789abcdef0123456789abcdef01234567" # Ensure this is also .oid

    # short_id is often derived from id/oid, ensure consistency or mock if used directly
    mock_head_commit.short_id = "0123456" # This is fine if short_id is independently mocked
    mock_head_commit.type = pygit2.GIT_OBJECT_COMMIT # Use actual constant if available
    mock_head_commit.peel.return_value = mock_head_commit # peel() on a commit returns itself

    repo.revparse_single.return_value = mock_head_commit
    repo.references = MagicMock()
    repo.references.create = MagicMock()
    repo.create_tag = MagicMock()
    repo.listall_tags = MagicMock(return_value=[])
    repo.__getitem__ = MagicMock(return_value=mock_head_commit) # For repo[oid] access
    return repo

# --- From tests/test_core_branching.py ---

# Typing imports for fixtures from test_core_branching
from typing import List, Dict, Any, Optional, Callable

# Helper function (renamed from make_commit_helper to avoid clash, takes path)
def make_commit_on_path(repo_path_str: str, filename: str = "default_file.txt", content: str = "Default content", msg: str = "Default commit message", branch_name: Optional[str] = None) -> pygit2.Oid:
    repo = pygit2.Repository(repo_path_str)
    initial_commit_done_here = False
    if branch_name:
        if repo.head_is_unborn:
            pass
        elif branch_name not in repo.branches.local:
            repo.branches.local.create(branch_name, repo.head.peel(pygit2.Commit))
            repo.checkout(f"refs/heads/{branch_name}")
            repo.set_head(f"refs/heads/{branch_name}")

    full_file_path = Path(repo.workdir) / filename
    full_file_path.parent.mkdir(parents=True, exist_ok=True)
    full_file_path.write_text(content)
    repo.index.add(filename)
    repo.index.write()
    try:
        author = repo.default_signature
    except:
        author = pygit2.Signature("Test Author", "test@example.com")
    committer = author
    tree = repo.index.write_tree()
    parents = [] if repo.head_is_unborn else [repo.head.target]
    was_unborn = repo.head_is_unborn
    commit_oid = repo.create_commit("HEAD", author, committer, msg, tree, parents)
    initial_commit_done_here = was_unborn
    if initial_commit_done_here and branch_name:
        current_actual_branch = repo.head.shorthand
        if current_actual_branch != branch_name: # e.g. if first commit made 'master' by default
            # This logic might need refinement based on pygit2's behavior for initial commits
            # when HEAD ref is specified vs. when it's just "HEAD".
            # The goal is to ensure the branch specified by 'branch_name' is the one that exists and is checked out.
            # If pygit2 created 'master' but 'main' was intended:
            if current_actual_branch == "master" and branch_name == "main" and not repo.branches.local.get("main"):
                 master_b = repo.branches.local.get("master")
                 if master_b: master_b.rename(branch_name) # Force in case main somehow exists but is not HEAD

            # Ensure we are on the correctly named branch
            final_branch_ref = repo.branches.local.get(branch_name)
            if final_branch_ref and repo.head.target != final_branch_ref.target:
                repo.checkout(final_branch_ref)
                repo.set_head(final_branch_ref.name) # Redundant if checkout does this
            elif not final_branch_ref:
                # This state implies something went wrong with branch creation/renaming.
                pass # Or raise error

    elif branch_name and repo.head.shorthand != branch_name:
        branch_to_checkout = repo.branches.local.get(branch_name)
        if branch_to_checkout:
            repo.checkout(branch_to_checkout) # Checkout can take branch object
            # repo.set_head(branch_to_checkout.name) # Usually checkout handles setting HEAD
    return commit_oid

def make_initial_commit(repo_path_str: str, filename: str = "initial.txt", content: str = "Initial", msg: str = "Initial commit"):
    repo = pygit2.Repository(repo_path_str)
    if repo.head_is_unborn:
        file_path = Path(repo.workdir) / filename
        file_path.write_text(content)
        repo.index.add(filename)
        repo.index.write()
        author = pygit2.Signature("Test Author", "test@example.com")
        committer = author
        tree = repo.index.write_tree()
        repo.create_commit("HEAD", author, committer, msg, tree, [])
        # After initial commit, if pygit2 created 'master' and 'main' was intended (or any other name)
        # This logic is now largely handled within make_commit if branch_name is passed.
        # If make_commit is called without branch_name for initial commit, it will use default (likely 'main').
        # This part can be simplified or removed if make_commit handles it robustly.
        # For now, let's assume make_commit (if called with branch_name="main") or pygit2 default handles it.
        # If a specific default name is desired here (e.g. "main"), it should be passed to make_commit.
        # If make_commit is called by this function, it should pass the desired default.
        # This function, as is, seems to assume make_commit handles branch naming.
        # The check below is a safeguard.
        if repo.head.shorthand == "master" and "main" not in repo.branches.local:
             # This situation implies the initial commit created 'master' and we prefer 'main'
             master_b = repo.branches.local.get("master")
             if master_b:
                 master_b.rename("main") # force to overwrite if 'main' somehow exists but isn't HEAD
                 repo.checkout(repo.branches.local["main"]) # Switch to 'main'
                 # repo.set_head(...) might be needed if checkout doesn't suffice for all cases.

@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "test_git_repo_core" # Renamed to avoid conflict if used elsewhere
    repo_path.mkdir(exist_ok=True) # exist_ok for safety
    pygit2.init_repository(str(repo_path), bare=False)
    make_initial_commit(str(repo_path))
    return repo_path

@pytest.fixture
def empty_test_repo(tmp_path: Path) -> Path:
    repo_path = tmp_path / "empty_git_repo_core" # Renamed
    repo_path.mkdir(exist_ok=True)
    pygit2.init_repository(str(repo_path), bare=False)
    return repo_path

@pytest.fixture
def bare_test_repo(tmp_path: Path) -> Path: # This returns Path, distinct from bare_remote_repo_obj
    repo_path = tmp_path / "bare_git_repo_core.git" # Renamed
    pygit2.init_repository(str(repo_path), bare=True)
    return repo_path

@pytest.fixture
def configure_git_user() -> Callable[[pygit2.Repository], None]: # Type hint for the returned callable
    """Fixture to configure git user.name and user.email for a repo instance."""
    def _configure(repo: pygit2.Repository):
        config = repo.config
        config["user.name"] = "Test User Core"
        config["user.email"] = "testcore@example.com"
    return _configure

@pytest.fixture
def repo_with_remote_branches(tmp_path: Path, configure_git_user: Callable[[pygit2.Repository], None]) -> Path: # Added configure_git_user
    local_repo_path = tmp_path / "local_for_remote_branch_tests_core" # Renamed
    local_repo_path.mkdir(exist_ok=True)
    local_repo = pygit2.init_repository(str(local_repo_path))
    configure_git_user(local_repo) # Configure user for commits made by make_initial_commit if it uses default_signature
    # make_initial_commit now defaults to 'main' or respects pygit2's default.
    # The commits inside this fixture should ideally use make_commit_on_path for consistency
    # if they need to ensure specific branch context beyond the initial one.
    make_commit_on_path(str(local_repo_path), filename="initial_main.txt", content="Initial on main", msg="Initial commit on main", branch_name="main")


    bare_remote_path = tmp_path / "remote_server_for_branch_tests_core.git" # Renamed
    pygit2.init_repository(str(bare_remote_path), bare=True)

    if "origin" not in local_repo.remotes:
        origin_remote = local_repo.remotes.create("origin", str(bare_remote_path))
    else:
        origin_remote = local_repo.remotes["origin"]
        origin_remote.url = str(bare_remote_path)


    main_commit = local_repo.head.peel(pygit2.Commit)
    # Create feature-a from main's current state
    local_repo.branches.local.create("feature-a", main_commit)
    # No need to checkout 'main' first if we are creating from its commit object.
    # Then commit on feature-a
    make_commit_on_path(str(local_repo_path), filename="fa.txt", content="feature-a content", msg="Commit on feature-a", branch_name="feature-a")
    origin_remote.push(["refs/heads/feature-a:refs/heads/feature-a"])

    # Create feature-b from main's current state (still main_commit)
    local_repo.branches.local.create("feature-b", main_commit)
    make_commit_on_path(str(local_repo_path), filename="fb.txt", content="feature-b content", msg="Commit on feature-b", branch_name="feature-b")
    origin_remote.push(["refs/heads/feature-b:refs/heads/feature-b"])

    # Create origin-special-feature from main's current state
    local_repo.branches.local.create("origin-special-feature", main_commit)
    make_commit_on_path(str(local_repo_path), filename="osf.txt", content="osf content", msg="Commit on origin-special-feature", branch_name="origin-special-feature")
    origin_remote.push(["refs/heads/origin-special-feature:refs/heads/origin/special-feature"])

    # Ensure local repo is back on main branch before returning
    main_branch_ref = local_repo.branches.local.get("main")
    if main_branch_ref:
        local_repo.checkout(main_branch_ref)
    else:
        # Fallback or error if 'main' doesn't exist for some reason
        pass

    return local_repo_path

@pytest.fixture
def repo_for_merge(tmp_path: Path, configure_git_user: Callable[[pygit2.Repository], None]) -> Path:
    repo_path = tmp_path / "repo_for_merge_normal_core" # Renamed
    repo_path.mkdir(exist_ok=True)
    repo = pygit2.init_repository(str(repo_path))
    configure_git_user(repo)
    make_commit_on_path(str(repo_path), filename="common.txt", content="line0", msg="C0: Initial on main", branch_name="main")
    c0_oid = repo.head.target
    make_commit_on_path(str(repo_path), filename="main_file.txt", content="main content", msg="C1: Commit on main", branch_name="main")
    feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
    repo.checkout(feature_branch.name)
    repo.set_head(feature_branch.name)
    make_commit_on_path(str(repo_path), filename="feature_file.txt", content="feature content", msg="C2: Commit on feature", branch_name="feature")
    main_branch_ref = repo.branches.local.get("main")
    repo.checkout(main_branch_ref.name)
    repo.set_head(main_branch_ref.name)
    return repo_path

# --- Constants from tests/test_core_repository.py ---
TEST_USER_NAME = "Test Sync User" # Used by test_core_repository, also usable by core_versioning if needed
TEST_USER_EMAIL = "test_sync@example.com" # Same as above

# For create_test_signature from test_core_versioning
from datetime import datetime, timezone

def create_test_signature(repo: pygit2.Repository) -> pygit2.Signature:
    """Creates a test signature, trying to use repo default or falling back."""
    try:
        # Attempt to use default_signature if configured in the repo object
        # This might have been set by a fixture like configure_git_user
        if repo.default_signature: # Check if it's not None
            return repo.default_signature
        # If repo.default_signature is None (e.g. not configured by fixture, and no global git config)
        # then pygit2 itself might raise an error or return None depending on version/state.
        # Fallback if it's None or raises an error that indicates it's not available.
    except pygit2.GitError: # Catch if accessing default_signature fails
        pass # Fall through to manual creation
    except AttributeError: # Catch if default_signature attribute doesn't exist (less likely for real Repository)
        pass # Fall through

    # Fallback: Use constants if default_signature is not available or not set
    # These constants can be the ones defined in this conftest.py
    return pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)

@pytest.fixture
def repo_for_ff_merge(tmp_path: Path, configure_git_user: Callable[[pygit2.Repository], None]) -> Path:
    repo_path = tmp_path / "repo_for_ff_merge_core" # Renamed
    repo_path.mkdir(exist_ok=True)
    repo = pygit2.init_repository(str(repo_path))
    configure_git_user(repo)
    make_commit_on_path(str(repo_path), filename="main_base.txt", content="base for ff", msg="C0: Base on main", branch_name="main")
    c0_oid = repo.head.target
    feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
    repo.checkout(feature_branch.name)
    repo.set_head(feature_branch.name)
    make_commit_on_path(str(repo_path), filename="feature_ff.txt", content="ff content", msg="C1: Commit on feature", branch_name="feature")
    main_branch_ref = repo.branches.local.get("main")
    repo.checkout(main_branch_ref.name)
    repo.set_head(main_branch_ref.name)
    return repo_path

@pytest.fixture
def repo_for_conflict_merge(tmp_path: Path, configure_git_user: Callable[[pygit2.Repository], None]) -> Path:
    repo_path = tmp_path / "repo_for_conflict_merge_core" # Renamed
    repo_path.mkdir(exist_ok=True)
    repo = pygit2.init_repository(str(repo_path))
    configure_git_user(repo)
    conflict_file = "conflict.txt"
    make_commit_on_path(str(repo_path), filename=conflict_file, content="Line1\nCommon Line\nLine3", msg="C0: Common ancestor", branch_name="main")
    c0_oid = repo.head.target
    make_commit_on_path(str(repo_path), filename=conflict_file, content="Line1\nChange on Main\nLine3", msg="C1: Change on main", branch_name="main")
    feature_branch = repo.branches.local.create("feature", repo.get(c0_oid))
    repo.checkout(feature_branch.name)
    repo.set_head(feature_branch.name)
    make_commit_on_path(str(repo_path), filename=conflict_file, content="Line1\nChange on Feature\nLine3", msg="C2: Change on feature", branch_name="feature")
    main_branch_ref = repo.branches.local.get("main")
    repo.checkout(main_branch_ref.name)
    repo.set_head(main_branch_ref.name)
    return repo_path
