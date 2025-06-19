import pytest
import pygit2
import os
# shutil was for fixtures, now in conftest
import re # Used by TestMergeCommandCLI
from pathlib import Path # Used by test methods directly
from click.testing import CliRunner # For type hinting runner fixture from conftest
from unittest.mock import patch # Used by TestSyncCommandCLI

from gitwrite_cli.main import cli
# It's good practice to import specific exceptions if they are explicitly caught or expected.
from gitwrite_core.exceptions import FetchError, PushError # Used by test methods directly

# Helper function make_commit is in conftest.py (enhanced version)
# Fixtures runner, local_repo (generic one from conftest), cli_test_repo,
# configure_git_user_for_cli, cli_repo_for_merge, cli_repo_for_ff_merge,
# cli_repo_for_conflict_merge, synctest_repos are all in conftest.py.


class TestMergeCommandCLI:
    def test_merge_normal_success_cli(self, runner: CliRunner, cli_repo_for_merge: Path): # Fixtures from conftest
        os.chdir(cli_repo_for_merge) # os import is kept
        result = runner.invoke(cli, ["merge", "feature"])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Merged 'feature' into 'main'. New commit:" in result.output

        repo = pygit2.Repository(str(cli_repo_for_merge))
        match = re.search(r"New commit: ([a-f0-9]{7,})\.", result.output)
        assert match, "Could not find commit OID in output."
        merge_commit_oid_short = match.group(1)

        merge_commit = repo.revparse_single(merge_commit_oid_short) # pygit2 import is kept
        assert merge_commit is not None
        assert len(merge_commit.parents) == 2
        assert repo.state == pygit2.GIT_REPOSITORY_STATE_NONE

    def test_merge_fast_forward_success_cli(self, runner: CliRunner, cli_repo_for_ff_merge: Path): # Fixtures from conftest
        os.chdir(cli_repo_for_ff_merge)
        result = runner.invoke(cli, ["merge", "feature"])

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Fast-forwarded 'main' to 'feature' (commit " in result.output

        repo = pygit2.Repository(str(cli_repo_for_ff_merge))
        assert repo.head.target == repo.branches.local['feature'].target

    def test_merge_up_to_date_cli(self, runner: CliRunner, cli_repo_for_ff_merge: Path): # Fixtures from conftest
        os.chdir(cli_repo_for_ff_merge)
        runner.invoke(cli, ["merge", "feature"]) # First merge (FF)

        result = runner.invoke(cli, ["merge", "feature"]) # Attempt again
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "'main' is already up-to-date with 'feature'." in result.output

    def test_merge_conflict_cli(self, runner: CliRunner, cli_repo_for_conflict_merge: Path): # Fixtures from conftest
        repo_path = cli_repo_for_conflict_merge
        os.chdir(repo_path)
        result = runner.invoke(cli, ["merge", "feature"])

        assert result.exit_code == 0, f"CLI Error: {result.output}" # CLI handles error gracefully
        assert "Error: Automatic merge of 'feature' into 'main' failed due to conflicts." in result.output
        assert "Conflicting files:" in result.output
        assert "  conflict.txt" in result.output # Assuming 'conflict.txt' is the known conflicting file
        assert "Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge." in result.output

        repo = pygit2.Repository(str(repo_path))
        assert repo.lookup_reference("MERGE_HEAD") is not None # MERGE_HEAD should exist after a failed merge by `gitwrite merge`
        # repo.state should not be GIT_REPOSITORY_STATE_MERGE if core cleaned it up,
        # but MERGE_HEAD indicates that a merge was attempted and needs resolution by user.
        # For `gitwrite merge`, the expectation is that it leaves the repo in a state for `gitwrite save` to complete.
        # So, index will have conflicts, and MERGE_HEAD will be set.
        # `repo.state` might be NONE if only index is modified, not full repo state flags.
        # The crucial part for `gitwrite merge` is `MERGE_HEAD` and index conflicts.
        assert repo.index.conflicts is not None


    def test_merge_branch_not_found_cli(self, runner: CliRunner, cli_test_repo: Path): # Fixtures from conftest
        os.chdir(cli_test_repo)
        result = runner.invoke(cli, ["merge", "no-such-branch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Branch 'no-such-branch' not found" in result.output

    def test_merge_into_itself_cli(self, runner: CliRunner, cli_test_repo: Path): # Fixtures from conftest
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        current_branch = repo.head.shorthand
        result = runner.invoke(cli, ["merge", current_branch])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Cannot merge a branch into itself." in result.output

    def test_merge_detached_head_cli(self, runner: CliRunner, cli_test_repo: Path): # Fixtures from conftest
        os.chdir(cli_test_repo)
        repo = pygit2.Repository(str(cli_test_repo))
        repo.set_head(repo.head.target) # Detach HEAD
        assert repo.head_is_detached

        result = runner.invoke(cli, ["merge", "main"]) # Assuming 'main' exists
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: HEAD is detached. Please switch to a branch to perform a merge." in result.output

    def test_merge_empty_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        empty_repo = tmp_path / "empty_for_merge_cli"
        empty_repo.mkdir()
        pygit2.init_repository(str(empty_repo))
        os.chdir(empty_repo)

        result = runner.invoke(cli, ["merge", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Repository is empty or HEAD is unborn. Cannot perform merge." in result.output

    def test_merge_bare_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        bare_repo_path = tmp_path / "bare_for_merge_cli.git"
        pygit2.init_repository(str(bare_repo_path), bare=True)
        os.chdir(bare_repo_path) # CLI will discover CWD is a bare repo

        result = runner.invoke(cli, ["merge", "anybranch"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Cannot merge in a bare repository." in result.output

    def test_merge_no_signature_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        repo_path_no_sig = tmp_path / "no_sig_repo_for_cli_merge"
        repo_path_no_sig.mkdir()
        repo = pygit2.init_repository(str(repo_path_no_sig))
        # DO NOT configure user.name/user.email for this repo

        make_commit(repo, "common.txt", "line0", "C0: Initial on main", branch_name="main") # make_commit from conftest
        c0_oid = repo.head.target
        make_commit(repo, "main_file.txt", "main content", "C1: Commit on main", branch_name="main") # make_commit from conftest
        repo.branches.local.create("feature", repo.get(c0_oid))
        make_commit(repo, "feature_file.txt", "feature content", "C2: Commit on feature", branch_name="feature") # make_commit from conftest
        repo.checkout(repo.branches.local['main'].name)

        os.chdir(repo_path_no_sig)
        result = runner.invoke(cli, ["merge", "feature"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: User signature (user.name and user.email) not configured in Git." in result.output


class TestSyncCommandCLI:
    def _commit_in_clone(self, clone_repo_path_str: str, remote_bare_repo_path_str: str, filename: str, content: str, message: str, branch_name: str = "main"): # This helper is used by tests, stays in test file.
        if not Path(clone_repo_path_str).exists():
             pygit2.clone_repository(remote_bare_repo_path_str, clone_repo_path_str) # Ensure clone exists

        clone_repo = pygit2.Repository(clone_repo_path_str)
        config_clone = clone_repo.config
        config_clone["user.name"] = "Remote Clone User"
        config_clone["user.email"] = "remote_clone@example.com"

        if branch_name not in clone_repo.branches.local:
            remote_branch = clone_repo.branches.remote.get(f"origin/{branch_name}")
            if remote_branch:
                clone_repo.branches.local.create(branch_name, remote_branch.peel(pygit2.Commit))
            elif not clone_repo.head_is_unborn:
                 clone_repo.branches.local.create(branch_name, clone_repo.head.peel(pygit2.Commit))

        if clone_repo.head.shorthand != branch_name:
             clone_repo.checkout(clone_repo.branches.local[branch_name])

        make_commit(clone_repo, filename, content, message, branch_name=branch_name) # make_commit from conftest, pass branch_name
        clone_repo.remotes["origin"].push([f"refs/heads/{branch_name}:refs/heads/{branch_name}"])

    def test_sync_new_repo_initial_push(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        local_repo = synctest_repos["local_repo"]
        os.chdir(local_repo.workdir)
        new_branch_name = "feature_new_for_sync"
        # Create commit on main first, then branch from it
        main_head_commit = local_repo.head.peel(pygit2.Commit)
        local_repo.branches.local.create(new_branch_name, main_head_commit)
        make_commit(local_repo, "feature_file.txt", "content for new feature", f"Commit on {new_branch_name}", branch_name=new_branch_name) # make_commit from conftest
        current_commit_oid = local_repo.head.target

        result = runner.invoke(cli, ["sync", "--branch", new_branch_name])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Syncing branch '{new_branch_name}' with remote 'origin'..." in result.output
        assert "Fetch complete." in result.output
        assert f"Remote tracking branch 'refs/remotes/origin/{new_branch_name}' not found" in result.output # Or similar for new branch
        assert "Push successful." in result.output
        assert "Sync process completed successfully." in result.output
        remote_bare_repo = synctest_repos["remote_bare_repo"]
        remote_branch_ref = remote_bare_repo.lookup_reference(f"refs/heads/{new_branch_name}")
        assert remote_branch_ref.target == current_commit_oid

    def test_sync_remote_ahead_fast_forward_cli(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        local_repo = synctest_repos["local_repo"]
        remote_bare_repo_path_str = synctest_repos["remote_bare_repo_path_str"]
        remote_clone_repo_path = synctest_repos["remote_clone_repo_path"]
        os.chdir(local_repo.workdir)
        self._commit_in_clone(str(remote_clone_repo_path), remote_bare_repo_path_str,
                              "remote_added_file.txt", "content from remote",
                              "Remote C2 on main", branch_name="main")
        remote_head_commit = synctest_repos["remote_bare_repo"].lookup_reference("refs/heads/main").target
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Fetch complete." in result.output
        assert f"Local branch 'main' fast-forwarded to remote commit {str(remote_head_commit)[:7]}" in result.output
        assert "Push: Nothing to push" in result.output
        assert "Sync process completed successfully." in result.output
        assert local_repo.head.target == remote_head_commit

    def test_sync_diverged_clean_merge_cli(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        local_repo = synctest_repos["local_repo"]
        remote_bare_repo_path_str = synctest_repos["remote_bare_repo_path_str"]
        remote_clone_repo_path = synctest_repos["remote_clone_repo_path"]
        os.chdir(local_repo.workdir)
        make_commit(local_repo, "local_diverge.txt", "local content", "Local C2 on main", branch_name="main") # make_commit from conftest
        local_c2_oid = local_repo.head.target
        self._commit_in_clone(str(remote_clone_repo_path), remote_bare_repo_path_str,
                              "remote_diverge.txt", "remote content",
                              "Remote C2 on main", branch_name="main")
        remote_c2_oid = synctest_repos["remote_bare_repo"].lookup_reference("refs/heads/main").target
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Fetch complete." in result.output
        assert "Successfully merged remote changes into 'main'. New commit:" in result.output
        assert "Push successful." in result.output
        merge_commit_oid_match = re.search(r"New commit: ([0-9a-f]{7,})", result.output) # re import is kept
        assert merge_commit_oid_match is not None
        merge_commit_oid_short = merge_commit_oid_match.group(1)
        merge_commit = local_repo.revparse_single(merge_commit_oid_short)
        assert local_repo.head.target == merge_commit.id
        assert len(merge_commit.parents) == 2
        parent_oids = {p.id for p in merge_commit.parents}
        assert parent_oids == {local_c2_oid, remote_c2_oid}
        assert synctest_repos["remote_bare_repo"].lookup_reference("refs/heads/main").target == merge_commit.id

    def test_sync_specific_branch_cli(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        local_repo = synctest_repos["local_repo"]
        os.chdir(local_repo.workdir)
        main_commit_oid = local_repo.lookup_reference("refs/heads/main").target
        local_repo.branches.local.create("dev", local_repo.get(main_commit_oid))
        make_commit(local_repo, "dev_file.txt", "dev content", "Commit on dev", branch_name="dev") # make_commit from conftest
        local_repo.remotes["origin"].push(["refs/heads/dev:refs/heads/dev"])
        local_repo.checkout(local_repo.branches.local["main"])
        result = runner.invoke(cli, ["sync", "--branch", "dev"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Syncing branch 'dev' with remote 'origin'..." in result.output
        assert "Local branch 'dev' is already up-to-date with remote." in result.output
        assert "Push: Nothing to push" in result.output

    def test_sync_branch_not_found_cli(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        os.chdir(synctest_repos["local_repo_path_str"])
        result = runner.invoke(cli, ["sync", "--branch", "nonexistentbranch"])
        assert result.exit_code == 0
        assert "Error: Branch 'nonexistentbranch' not found." in result.output

    def test_sync_detached_head_cli(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        local_repo = synctest_repos["local_repo"]
        os.chdir(local_repo.workdir)
        local_repo.set_head(local_repo.head.target)
        assert local_repo.head_is_detached
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error: HEAD is detached. Please switch to a branch to sync or specify a branch name." in result.output

    def test_sync_remote_not_found_cli(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        os.chdir(synctest_repos["local_repo_path_str"])
        result = runner.invoke(cli, ["sync", "--remote", "nonexistentremote"])
        assert result.exit_code == 0
        assert "Error: Remote 'nonexistentremote' not found." in result.output

    def test_sync_conflict_cli(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        local_repo = synctest_repos["local_repo"]
        remote_bare_repo_path_str = synctest_repos["remote_bare_repo_path_str"]
        remote_clone_repo_path = synctest_repos["remote_clone_repo_path"]
        os.chdir(local_repo.workdir)
        conflict_filename = "conflict_file.txt" # Define for use in assertions
        c1_oid = local_repo.lookup_reference("refs/heads/main").target
        make_commit(local_repo, conflict_filename, "Local version of line", "Local C2 on main", branch_name="main") # make_commit from conftest
        local_commit_after_local_change = local_repo.head.target # Save this OID

        # Ensure clone starts from C1 before making its own C2
        if Path(str(remote_clone_repo_path)).exists(): shutil.rmtree(str(remote_clone_repo_path))
        pygit2.clone_repository(remote_bare_repo_path_str, str(remote_clone_repo_path))
        clone_repo = pygit2.Repository(str(remote_clone_repo_path))
        config_clone = clone_repo.config
        config_clone["user.name"] = "Remote Conflicter"
        config_clone["user.email"] = "remote_conflict@example.com"
        clone_repo.checkout("refs/heads/main")
        clone_repo.reset(c1_oid, pygit2.GIT_RESET_HARD)
        make_commit(clone_repo, conflict_filename, "Remote version of line", "Remote C2 on main", branch_name="main")
        clone_repo.remotes["origin"].push([f"+refs/heads/main:refs/heads/main"]) # Force push if main already exists
        shutil.rmtree(str(remote_clone_repo_path))

        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error: Merge resulted in conflicts." in result.output or \
               "Conflicts detected during merge." in result.output # More generic message from core
        assert "Conflicting files:" in result.output
        assert conflict_filename in result.output
        assert "Please resolve conflicts and then use 'gitwrite save <message>' to commit the merge." in result.output

        wc_conflict_file_path = Path(local_repo.workdir) / conflict_filename
        assert wc_conflict_file_path.exists()
        wc_conflict_file_content = wc_conflict_file_path.read_text()
        assert "<<<<<<<" in wc_conflict_file_content
        assert "=======" in wc_conflict_file_content
        assert ">>>>>>>" in wc_conflict_file_content

        # Sync command might clean up MERGE_HEAD after reporting conflict, so it might not be present.
        # The repo state should be clean if the core function handles aborting the merge.
        assert local_repo.state == pygit2.GIT_REPOSITORY_STATE_NONE
        # Head should not have moved from the local commit if merge was aborted by sync
        assert local_repo.head.target == local_commit_after_local_change


    def test_sync_no_push_flag_cli(self, runner: CliRunner, synctest_repos): # Fixtures from conftest
        local_repo = synctest_repos["local_repo"]
        os.chdir(local_repo.workdir)
        make_commit(local_repo, "local_only_for_nopush.txt", "content", "Local commit, no push test", branch_name="main") # make_commit from conftest
        result = runner.invoke(cli, ["sync", "--no-push"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Fetch complete." in result.output
        assert "Local branch is ahead of remote. Nothing to merge/ff." in result.output
        assert "Push skipped (--no-push specified)." in result.output
        remote_main_ref = synctest_repos["remote_bare_repo"].lookup_reference("refs/heads/main")
        assert remote_main_ref.target != local_repo.head.target

    def test_sync_outside_git_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        non_repo_dir = tmp_path / "no_repo_for_sync"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error: Not a Git repository" in result.output

    def test_sync_empty_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        empty_repo_path = tmp_path / "empty_for_sync"
        empty_repo_path.mkdir()
        pygit2.init_repository(str(empty_repo_path))
        os.chdir(empty_repo_path)
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error: Repository is empty or HEAD is unborn. Cannot sync." in result.output

    @patch('gitwrite_core.repository.sync_repository') # patch from unittest.mock is kept
    def test_sync_cli_handles_core_fetch_error(self, mock_sync_core, runner: CliRunner, synctest_repos): # Fixtures from conftest
        os.chdir(synctest_repos["local_repo_path_str"])
        mock_sync_core.side_effect = FetchError("Simulated core FetchError") # FetchError import is kept
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error during fetch: Simulated core FetchError" in result.output

    @patch('gitwrite_core.repository.sync_repository') # patch from unittest.mock is kept
    def test_sync_cli_handles_core_push_error(self, mock_sync_core, runner: CliRunner, synctest_repos): # Fixtures from conftest
        os.chdir(synctest_repos["local_repo_path_str"])
        mock_sync_core.side_effect = PushError("Simulated core PushError: Non-fast-forward from core") # PushError import is kept
        result = runner.invoke(cli, ["sync"])
        assert result.exit_code == 0
        assert "Error during push: Simulated core PushError: Non-fast-forward from core" in result.output
