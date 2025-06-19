import pytest # For pytest.raises, pytest.skip (if used directly in tests)
import pygit2 # Used directly in tests
import os # Used directly in tests
# shutil was for fixtures, now in conftest
from pathlib import Path # Used directly in tests
from click.testing import CliRunner # For type hinting runner fixture from conftest
from gitwrite_cli.main import cli

# Helper functions (make_commit, create_file, stage_file, resolve_conflict) are in conftest.py
# Fixtures (repo_with_unstaged_changes, repo_with_staged_changes, repo_with_merge_conflict, repo_with_revert_conflict) are in conftest.py
# Also runner, local_repo, bare_remote_repo_obj are in conftest.py
from conftest import make_commit, create_file, stage_file, resolve_conflict


class TestRevertCommandCLI:

    def test_revert_successful_non_merge(self, local_repo: pygit2.Repository, runner: CliRunner): # Fixtures from conftest
        """Test successful revert of a non-merge commit."""
        os.chdir(local_repo.workdir)

        initial_file_path = Path("initial.txt") # Path import is kept
        assert initial_file_path.exists()
        original_content = initial_file_path.read_text()
        commit1_hash = local_repo.head.target

        modified_content = original_content + "More content.\n"
        make_commit(local_repo, "initial.txt", modified_content, "Modify initial.txt") # make_commit from conftest
        commit2_hash = local_repo.head.target
        commit2_obj = local_repo[commit2_hash]
        assert commit1_hash != commit2_hash

        result = runner.invoke(cli, ["revert", str(commit2_hash)])
        assert result.exit_code == 0, f"Revert command failed: {result.output}"

        assert f"Successfully reverted commit {commit2_obj.short_id}" in result.output
        revert_commit_hash_short = result.output.strip().split("New commit: ")[-1][:7]
        revert_commit = local_repo.revparse_single(revert_commit_hash_short)
        assert revert_commit is not None
        assert local_repo.head.target == revert_commit.id

        expected_revert_msg_start = f"Revert \"{commit2_obj.message.splitlines()[0]}\""
        assert revert_commit.message.startswith(expected_revert_msg_start)
        assert initial_file_path.exists()
        assert initial_file_path.read_text() == original_content
        assert revert_commit.tree.id == local_repo[commit1_hash].tree.id


    def test_revert_invalid_commit_ref(self, local_repo: pygit2.Repository, runner: CliRunner): # Fixtures from conftest
        """Test revert with an invalid commit reference."""
        os.chdir(local_repo.workdir)
        result = runner.invoke(cli, ["revert", "non_existent_hash"])
        assert result.exit_code != 0
        assert "Error: Invalid or ambiguous commit reference 'non_existent_hash'" in result.output


    def test_revert_dirty_working_directory(self, local_repo: pygit2.Repository, runner: CliRunner): # Fixtures from conftest
        """Test reverting in a dirty working directory."""
        os.chdir(local_repo.workdir)
        file_path = Path("changeable_file.txt")
        file_path.write_text("Stable content.\n")
        make_commit(local_repo, str(file_path.name), file_path.read_text(), "Add changeable_file.txt") # make_commit from conftest
        commit_hash_to_revert = local_repo.head.target

        dirty_content = "Dirty content that should prevent revert.\n"
        file_path.write_text(dirty_content)

        result = runner.invoke(cli, ["revert", str(commit_hash_to_revert)])
        assert result.exit_code != 0
        assert "Error: Your working directory or index has uncommitted changes." in result.output
        assert "Please commit or stash them before attempting to revert." in result.output
        assert file_path.read_text() == dirty_content
        assert local_repo.head.target == commit_hash_to_revert


    def test_revert_initial_commit(self, local_repo: pygit2.Repository, runner: CliRunner): # Fixtures from conftest
        """Test reverting the initial commit made by the fixture."""
        os.chdir(local_repo.workdir)
        initial_commit_hash = local_repo.head.target
        initial_commit_obj = local_repo[initial_commit_hash]
        initial_file_path = Path("initial.txt")
        assert initial_file_path.exists()

        result = runner.invoke(cli, ["revert", str(initial_commit_hash)])
        assert result.exit_code == 0, f"Revert command failed: {result.output}"

        assert f"Successfully reverted commit {initial_commit_obj.short_id}" in result.output
        revert_commit_hash_short = result.output.strip().split("New commit: ")[-1][:7]
        revert_commit = local_repo.revparse_single(revert_commit_hash_short)
        assert revert_commit is not None
        assert local_repo.head.target == revert_commit.id
        expected_revert_msg_start = f"Revert \"{initial_commit_obj.message.splitlines()[0]}\""
        assert revert_commit.message.startswith(expected_revert_msg_start)
        assert not initial_file_path.exists()
        revert_commit_tree = revert_commit.tree
        assert len(revert_commit_tree) == 0, "Tree of revert commit should be empty"


    def test_revert_a_revert_commit(self, local_repo: pygit2.Repository, runner: CliRunner): # Fixtures from conftest
        """Test reverting a revert commit restores original state."""
        os.chdir(local_repo.workdir)
        file_path = Path("story_for_revert_test.txt")
        original_content = "Chapter 1: The adventure begins.\n"
        make_commit(local_repo, str(file_path.name), original_content, "Commit A: Add story_for_revert_test.txt") # make_commit from conftest
        commit_A_hash = local_repo.head.target
        commit_A_obj = local_repo[commit_A_hash]

        result_revert_A = runner.invoke(cli, ["revert", str(commit_A_hash)])
        assert result_revert_A.exit_code == 0, f"Reverting Commit A failed: {result_revert_A.output}"
        commit_B_short_hash = result_revert_A.output.strip().split("New commit: ")[-1][:7]
        commit_B_obj = local_repo.revparse_single(commit_B_short_hash)
        assert commit_B_obj is not None
        assert not file_path.exists(), "File should be deleted by first revert"
        expected_msg_B_start = f"Revert \"{commit_A_obj.message.splitlines()[0]}\""
        assert commit_B_obj.message.startswith(expected_msg_B_start)

        result_revert_B = runner.invoke(cli, ["revert", commit_B_obj.short_id])
        assert result_revert_B.exit_code == 0, f"Failed to revert Commit B: {result_revert_B.output}"
        commit_C_short_hash = result_revert_B.output.strip().split("New commit: ")[-1][:7]
        commit_C_obj = local_repo.revparse_single(commit_C_short_hash)
        assert commit_C_obj is not None
        expected_msg_C_start = f"Revert \"{commit_B_obj.message.splitlines()[0]}\""
        assert commit_C_obj.message.startswith(expected_msg_C_start)
        assert file_path.exists(), "File should reappear after reverting the revert"
        assert file_path.read_text() == original_content
        assert commit_C_obj.tree.id == commit_A_obj.tree.id

    def test_revert_successful_merge_commit(self, local_repo: pygit2.Repository, runner: CliRunner): # Fixtures from conftest
        """Test reverting a merge commit."""
        os.chdir(local_repo.workdir)
        c1_hash = local_repo.head.target
        main_branch_name = local_repo.head.shorthand
        branch_A_name = "branch-A"
        file_A_path = Path("fileA.txt")
        content_A = "Content for file A\n"
        local_repo.branches.local.create(branch_A_name, local_repo[c1_hash])
        local_repo.checkout(local_repo.branches.local[branch_A_name])
        make_commit(local_repo, str(file_A_path.name), content_A, "Commit C2a on branch-A (add fileA.txt)") # make_commit from conftest
        c2a_hash = local_repo.head.target
        local_repo.checkout(local_repo.branches.local[main_branch_name])
        assert local_repo.head.target == c1_hash
        branch_B_name = "branch-B"
        file_B_path = Path("fileB.txt")
        content_B = "Content for file B\n"
        local_repo.branches.local.create(branch_B_name, local_repo[c1_hash])
        local_repo.checkout(local_repo.branches.local[branch_B_name])
        make_commit(local_repo, str(file_B_path.name), content_B, "Commit C2b on branch-B (add fileB.txt)") # make_commit from conftest
        c2b_hash = local_repo.head.target
        local_repo.checkout(local_repo.branches.local[main_branch_name])
        assert local_repo.head.target == c1_hash
        main_branch_ref = local_repo.branches.local[main_branch_name]
        main_branch_ref.set_target(c2a_hash)
        local_repo.set_head(main_branch_ref.name)
        local_repo.checkout_head(strategy=pygit2.GIT_CHECKOUT_FORCE)
        c3_hash = local_repo.head.target
        assert c3_hash == c2a_hash
        assert file_A_path.exists() and file_A_path.read_text() == content_A
        assert not file_B_path.exists()
        merge_result, _ = local_repo.merge_analysis(c2b_hash)
        assert not (merge_result & pygit2.GIT_MERGE_ANALYSIS_UP_TO_DATE)
        assert not (merge_result & pygit2.GIT_MERGE_ANALYSIS_FASTFORWARD)
        assert (merge_result & pygit2.GIT_MERGE_ANALYSIS_NORMAL)
        local_repo.merge(c2b_hash)
        author = local_repo.default_signature
        committer = local_repo.default_signature
        tree = local_repo.index.write_tree()
        c4_hash = local_repo.create_commit(
            "HEAD",
            author,
            committer,
            f"Commit C4: Merge {branch_B_name} into {main_branch_name}",
            tree,
            [c3_hash, c2b_hash]
        )
        local_repo.state_cleanup()
        c4_obj = local_repo[c4_hash]
        assert len(c4_obj.parents) == 2
        parent_hashes = {p.id for p in c4_obj.parents}
        assert parent_hashes == {c3_hash, c2b_hash}
        assert file_A_path.read_text() == content_A
        assert file_B_path.read_text() == content_B

        result_revert_merge = runner.invoke(cli, ["revert", str(c4_hash)])
        assert result_revert_merge.exit_code == 0, f"CLI Error: {result_revert_merge.output}"
        expected_error_message = f"Error: Commit '{c4_obj.short_id}' is a merge commit. Reverting merge commits directly by creating a revert commit is not supported. Consider reverting the changes introduced by a specific parent."
        assert expected_error_message in result_revert_merge.output
        assert local_repo.head.target == c4_hash
        assert file_A_path.exists() and file_A_path.read_text() == content_A
        assert file_B_path.exists() and file_B_path.read_text() == content_B

    def test_revert_with_conflicts_and_resolve(self, local_repo: pygit2.Repository, runner: CliRunner): # Fixtures from conftest
        """Test reverting a commit that causes conflicts, then resolve and save."""
        os.chdir(local_repo.workdir)
        file_path = Path("conflict_file.txt")
        content_A = "line1\ncommon_line_original\nline3\n"
        make_commit(local_repo, str(file_path.name), content_A, "Commit A: Base for conflict") # make_commit from conftest
        content_B = "line1\ncommon_line_modified_by_B\nline3\n"
        make_commit(local_repo, str(file_path.name), content_B, "Commit B: Modifies common_line") # make_commit from conftest
        commit_B_hash = local_repo.head.target
        commit_B_obj = local_repo[commit_B_hash]
        content_C = "line1\ncommon_line_modified_by_C_after_B\nline3\n"
        make_commit(local_repo, str(file_path.name), content_C, "Commit C: Modifies common_line again") # make_commit from conftest

        result_revert = runner.invoke(cli, ["revert", str(commit_B_hash)])
        assert result_revert.exit_code == 0
        assert "Conflicts detected after revert. Automatic commit aborted." in result_revert.output
        assert f"Conflicting files:\n  {str(file_path.name)}" in result_revert.output
        conflict_content = file_path.read_text()
        assert "<<<<<<< HEAD" in conflict_content
        assert "=======" in conflict_content
        assert "common_line_original" in conflict_content
        assert ">>>>>>> parent of " + commit_B_obj.short_id in conflict_content
        assert local_repo.lookup_reference("REVERT_HEAD").target == commit_B_hash

        resolved_content = "line1\ncommon_line_modified_by_C_after_B\nresolved_conflict_line\nline3\n"
        file_path.write_text(resolved_content)
        local_repo.index.add(file_path.name)
        local_repo.index.write()

        user_save_message = "Resolved conflict after reverting B"
        result_save = runner.invoke(cli, ["save", user_save_message])
        assert result_save.exit_code == 0
        assert f"Finalizing revert of commit {commit_B_obj.short_id}" in result_save.output
        assert "Successfully completed revert operation." in result_save.output
        output_lines = result_save.output.strip().split('\n')
        commit_line = None
        for line in output_lines:
            if line.startswith("[") and "] " in line and not line.startswith("[DEBUG:"):
                commit_line = line
                break
        assert commit_line is not None
        if "[DETACHED HEAD " in commit_line:
             new_commit_hash_short = commit_line.split("[DETACHED HEAD ")[1].split("]")[0]
        else:
             new_commit_hash_short = commit_line.split(" ")[1].split("]")[0]
        final_commit = local_repo.revparse_single(new_commit_hash_short)
        assert final_commit is not None
        expected_final_msg_start = f"Revert \"{commit_B_obj.message.splitlines()[0]}\""
        assert final_commit.message.startswith(expected_final_msg_start)
        assert user_save_message in final_commit.message
        assert file_path.read_text() == resolved_content
        with pytest.raises(KeyError): local_repo.lookup_reference("REVERT_HEAD") # pytest.raises is kept
        with pytest.raises(KeyError): local_repo.lookup_reference("MERGE_HEAD") # pytest.raises is kept

# End of TestRevertCommandCLI class

# #####################
# # Save Command Tests
# #####################

class TestSaveCommandCLI:
    def test_save_initial_commit_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite save "Initial commit"` in a new repository."""
        repo_path = tmp_path / "new_repo_for_initial_save"
        repo_path.mkdir()
        pygit2.init_repository(str(repo_path)) # pygit2 import is kept
        os.chdir(repo_path) # os import is kept
        (repo_path / "first_file.txt").write_text("Hello world") # Path import is kept
        commit_message = "Initial commit"
        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output
        repo = pygit2.Repository(str(repo_path))
        assert not repo.head_is_unborn
        commit = repo.head.peel(pygit2.Commit)
        assert commit.message.strip() == commit_message
        assert "first_file.txt" in commit.tree
        assert not repo.status()

    def test_save_new_file_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        """Test saving a new, unstaged file."""
        repo = local_repo
        os.chdir(repo.workdir)
        filename = "new_data.txt"
        file_content = "Some new data."
        create_file(repo, filename, file_content) # create_file from conftest
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

    def test_save_existing_file_modified_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        """Test saving modifications to an existing, tracked file."""
        repo = local_repo
        os.chdir(repo.workdir)
        filename = "initial.txt"
        original_content = (Path(repo.workdir) / filename).read_text()
        modified_content = original_content + "\nFurther modifications."
        create_file(repo, filename, modified_content) # create_file from conftest
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

    def test_save_no_changes_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        """Test saving when there are no changes."""
        repo = local_repo
        os.chdir(repo.workdir)
        assert not repo.status()
        initial_head_target = repo.head.target
        commit_message = "Attempt no changes"
        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No changes to save (working directory and index are clean or match HEAD)." in result.output
        assert repo.head.target == initial_head_target

    def test_save_staged_changes_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        """Test saving already staged changes."""
        repo = local_repo
        os.chdir(repo.workdir)
        filename = "staged_only.txt"
        file_content = "This content is only staged."
        create_file(repo, filename, file_content) # create_file from conftest
        stage_file(repo, filename) # stage_file from conftest
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

    def test_save_no_message_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        """Test saving without providing a commit message (should fail due to Click)."""
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "some_change.txt", "content") # create_file from conftest
        result = runner.invoke(cli, ["save"])
        assert result.exit_code != 0
        assert "Missing argument 'MESSAGE'." in result.output

    def test_save_outside_git_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite save` outside a Git repository."""
        non_repo_dir = tmp_path / "no_repo_here"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)
        result = runner.invoke(cli, ["save", "Test message"])
        assert result.exit_code == 0
        assert "Error: Not a Git repository (or any of the parent directories)." in result.output

    def test_save_include_single_file_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "file_A.txt", "Content A") # create_file from conftest
        create_file(repo, "file_B.txt", "Content B") # create_file from conftest
        commit_message = "Commit file_A only"
        result = runner.invoke(cli, ["save", "-i", "file_A.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output
        commit = repo.head.peel(pygit2.Commit)
        assert "file_A.txt" in commit.tree
        assert "file_B.txt" not in commit.tree
        assert (Path(repo.workdir) / "file_B.txt").exists()

    def test_save_include_no_changes_in_path_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "other_file.txt", "changes here") # create_file from conftest
        result = runner.invoke(cli, ["save", "-i", "initial.txt", "Try to commit unchanged initial.txt"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No specified files had changes to stage relative to HEAD." in result.output
        commit = repo.head.peel(pygit2.Commit)
        assert "other_file.txt" not in commit.tree

    def test_save_include_non_existent_file_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "actual_file.txt", "actual content") # create_file from conftest
        result = runner.invoke(cli, ["save", "-i", "non_existent.txt", "-i", "actual_file.txt", "Commit with non-existent"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Warning: Could not add path 'non_existent.txt'" in result.output
        commit = repo.head.peel(pygit2.Commit)
        assert "actual_file.txt" in commit.tree
        assert "non_existent.txt" not in commit.tree

    def test_save_complete_merge_cli(self, runner: CliRunner, repo_with_merge_conflict: pygit2.Repository): # Fixtures from conftest
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)
        resolve_conflict(repo, "conflict_file.txt", "Resolved content for merge CLI test") # resolve_conflict from conftest
        assert not repo.index.conflicts
        commit_message = "Finalizing resolved merge"
        result = runner.invoke(cli, ["save", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output
        assert "Successfully completed merge operation." in result.output
        new_commit = repo.head.peel(pygit2.Commit)
        assert len(new_commit.parents) == 2
        with pytest.raises(KeyError): # pytest.raises is kept
            repo.lookup_reference("MERGE_HEAD")

    def test_save_merge_with_unresolved_conflicts_cli(self, runner: CliRunner, repo_with_merge_conflict: pygit2.Repository): # Fixtures from conftest
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)
        result = runner.invoke(cli, ["save", "Attempt merge with conflicts"])
        assert result.exit_code == 0
        assert "Error: Unresolved conflicts detected during merge." in result.output
        assert "Conflicting files:" in result.output
        assert "conflict_file.txt" in result.output
        assert repo.lookup_reference("MERGE_HEAD") is not None

    def test_save_complete_revert_cli(self, runner: CliRunner, repo_with_revert_conflict: pygit2.Repository): # Fixtures from conftest
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)
        reverted_commit_oid = repo.lookup_reference("REVERT_HEAD").target
        reverted_commit_msg_first_line = repo.get(reverted_commit_oid).message.splitlines()[0]
        resolve_conflict(repo, "revert_conflict_file.txt", "Resolved content for revert CLI test") # resolve_conflict from conftest
        assert not repo.index.conflicts
        user_commit_message = "Finalizing resolved revert"
        result = runner.invoke(cli, ["save", user_commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        expected_revert_commit_msg_part = f"Revert \"{reverted_commit_msg_first_line}\""
        assert any(expected_revert_commit_msg_part in line for line in result.output.splitlines() if line.startswith("["))
        assert user_commit_message in result.output
        assert "Successfully completed revert operation." in result.output
        new_commit = repo.head.peel(pygit2.Commit)
        assert len(new_commit.parents) == 1
        assert expected_revert_commit_msg_part in new_commit.message
        assert user_commit_message in new_commit.message
        with pytest.raises(KeyError): # pytest.raises is kept
            repo.lookup_reference("REVERT_HEAD")

    def test_save_revert_with_unresolved_conflicts_cli(self, runner: CliRunner, repo_with_revert_conflict: pygit2.Repository): # Fixtures from conftest
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)
        result = runner.invoke(cli, ["save", "Attempt revert with conflicts"])
        assert result.exit_code == 0
        assert "Error: Unresolved conflicts detected during revert." in result.output
        assert "Conflicting files:" in result.output
        assert "revert_conflict_file.txt" in result.output
        assert repo.lookup_reference("REVERT_HEAD") is not None

    def test_save_include_error_during_merge_cli(self, runner: CliRunner, repo_with_merge_conflict: pygit2.Repository): # Fixtures from conftest
        repo = repo_with_merge_conflict
        os.chdir(repo.workdir)
        resolve_conflict(repo, "conflict_file.txt", "Resolved content") # resolve_conflict from conftest
        result = runner.invoke(cli, ["save", "-i", "conflict_file.txt", "Include during merge"])
        assert result.exit_code == 0
        assert "Error: Selective staging with --include is not allowed during an active merge operation." in result.output
        assert repo.lookup_reference("MERGE_HEAD") is not None

    def test_save_include_multiple_files_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "file_X.txt", "Content X") # create_file from conftest
        create_file(repo, "file_Y.txt", "Content Y") # create_file from conftest
        create_file(repo, "file_Z.txt", "Content Z") # create_file from conftest
        commit_message = "Commit X and Y"
        result = runner.invoke(cli, ["save", "-i", "file_X.txt", "-i", "file_Y.txt", commit_message])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"] {commit_message}" in result.output
        commit = repo.head.peel(pygit2.Commit)
        assert "file_X.txt" in commit.tree
        assert "file_Y.txt" in commit.tree
        assert "file_Z.txt" not in commit.tree
        assert (Path(repo.workdir) / "file_Z.txt").exists()

    def test_save_include_all_specified_are_invalid_or_unchanged_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        repo = local_repo
        os.chdir(repo.workdir)
        initial_head = repo.head.target
        result = runner.invoke(cli, ["save", "-i", "initial.txt", "-i", "non_existent.txt", "Attempt invalid includes"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No specified files had changes to stage relative to HEAD." in result.output
        assert repo.head.target == initial_head

    def test_save_include_empty_path_string_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        repo = local_repo
        os.chdir(repo.workdir)
        create_file(repo, "actual_file.txt", "content") # create_file from conftest
        initial_head = repo.head.target
        result = runner.invoke(cli, ["save", "-i", "", "Empty include path test"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Warning: Could not add path ''" in result.output
        assert "No specified files had changes to stage relative to HEAD." in result.output
        assert repo.head.target == initial_head

    def test_save_include_ignored_file_cli(self, runner: CliRunner, local_repo: pygit2.Repository): # Fixtures from conftest
        repo = local_repo
        os.chdir(repo.workdir)
        (Path(repo.workdir) / ".gitignore").write_text("*.ignored\n")
        make_commit(repo, ".gitignore", "*.ignored\n", "Add .gitignore") # make_commit from conftest
        create_file(repo, "ignored_doc.ignored", "This is ignored") # create_file from conftest
        create_file(repo, "normal_doc.txt", "This is not ignored") # create_file from conftest
        initial_head = repo.head.target
        result = runner.invoke(cli, ["save", "-i", "ignored_doc.ignored", "-i", "normal_doc.txt", "Test ignored include"])
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Warning: Could not add path 'ignored_doc.ignored'" in result.output
        commit = repo.head.peel(pygit2.Commit)
        assert "normal_doc.txt" in commit.tree
        assert "ignored_doc.ignored" not in commit.tree
        assert initial_head != commit.id

    def test_save_include_error_during_revert_cli(self, runner: CliRunner, repo_with_revert_conflict: pygit2.Repository): # Fixtures from conftest
        repo = repo_with_revert_conflict
        os.chdir(repo.workdir)
        result = runner.invoke(cli, ["save", "-i", "revert_conflict_file.txt", "Include during revert"])
        assert result.exit_code == 0
        assert "Error: Selective staging with --include is not allowed during an active revert operation." in result.output
        assert repo.lookup_reference("REVERT_HEAD") is not None
