import pytest
import pygit2 # Still used by tests directly
import os # Still used by tests directly
import re # For TestHistoryCommandCLI
from pathlib import Path # Still used by tests directly
from click.testing import CliRunner # For type hinting runner fixture from conftest
from .conftest import make_commit
# shutil was for local_repo fixture, now in conftest

from gitwrite_cli.main import cli
# Fixtures runner, local_repo_path, local_repo and helper make_commit are now in conftest.py

#######################################
# Compare Command Tests (CLI Runner)
#######################################

class TestCompareCommandCLI:

    def test_compare_empty_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite compare` in an empty initialized repo."""
        empty_repo_path = tmp_path / "empty_compare_repo"
        empty_repo_path.mkdir()
        pygit2.init_repository(str(empty_repo_path))

        os.chdir(empty_repo_path)
        result = runner.invoke(cli, ["compare"]) # runner from conftest

        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Not enough history to perform comparison: Repository is empty or HEAD is unborn." in result.output

    def test_compare_initial_commit_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare` in a repo with only the initial commit."""
        repo = local_repo
        os.chdir(repo.workdir)
        head_commit = repo.head.peel(pygit2.Commit)
        assert not head_commit.parents, "Test setup error: local_repo should have initial commit only for this test."

        result = runner.invoke(cli, ["compare"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Not enough history to perform comparison: HEAD is the initial commit and has no parent to compare with." in result.output

    def test_compare_no_differences_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare commitA commitA`."""
        repo = local_repo
        os.chdir(repo.workdir)
        commit_A_oid = str(repo.head.target)

        result = runner.invoke(cli, ["compare", commit_A_oid, commit_A_oid]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"No differences found between {commit_A_oid} and {commit_A_oid}." in result.output

    def test_compare_simple_content_change_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare commitA commitB` for content change."""
        repo = local_repo
        os.chdir(repo.workdir)
        # commit_A_oid = repo.head.target # Initial commit from fixture is parent of this
        # make_commit is in conftest.py
        make_commit(repo, "file.txt", "content line1\ncontent line2", "Commit A - file.txt")
        commit_A_file_oid = repo.head.target

        make_commit(repo, "file.txt", "content line1\nmodified line2", "Commit B - modify file.txt")
        commit_B_file_oid = repo.head.target

        result = runner.invoke(cli, ["compare", str(commit_A_file_oid), str(commit_B_file_oid)]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Diff between {str(commit_A_file_oid)} (a) and \n{str(commit_B_file_oid)} (b):" in result.output # Added \n
        assert "--- a/file.txt" in result.output
        assert "+++ b/file.txt" in result.output
        assert "-content line2" in result.output
        assert "+modified line2" in result.output

    def test_compare_file_addition_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare commitA commitB` for file addition."""
        repo = local_repo
        os.chdir(repo.workdir)
        commit_A_oid = str(repo.head.target)
        make_commit(repo, "new_file.txt", "new content", "Commit B - adds new_file.txt") # make_commit from conftest
        commit_B_oid = str(repo.head.target)

        result = runner.invoke(cli, ["compare", commit_A_oid, commit_B_oid]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "+++ b/new_file.txt" in result.output
        assert "+new content" in result.output

    def test_compare_file_deletion_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare commitA commitB` for file deletion."""
        repo = local_repo
        os.chdir(repo.workdir)
        make_commit(repo, "old_file.txt", "old content", "Commit A - adds old_file.txt") # make_commit from conftest
        commit_A_oid = str(repo.head.target)
        index = repo.index
        index.read()
        index.remove("old_file.txt")
        tree_for_B = index.write_tree()
        author = pygit2.Signature("Test Deleter", "del@example.com", 1234567890, 0) # pygit2 import is kept
        committer = author
        commit_B_oid = str(repo.create_commit("HEAD", author, committer, "Commit B - deletes old_file.txt", tree_for_B, [commit_A_oid]))

        result = runner.invoke(cli, ["compare", commit_A_oid, commit_B_oid]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "--- a/old_file.txt" in result.output
        assert "-old content" in result.output

    def test_compare_one_ref_vs_head_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare <ref>`."""
        repo = local_repo
        os.chdir(repo.workdir)
        commit_A_oid_str = str(repo.head.target)
        make_commit(repo, "file_for_B.txt", "content B", "Commit B") # make_commit from conftest
        commit_B_oid_str = str(repo.head.target)

        result = runner.invoke(cli, ["compare", commit_A_oid_str]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        head_short_oid = commit_B_oid_str[:7]
        assert f"Diff between {commit_A_oid_str} (a) and {head_short_oid} (HEAD) \n(b):" in result.output # Added \n
        assert "+++ b/file_for_B.txt" in result.output

    def test_compare_default_head_vs_parent_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare` (default HEAD~1 vs HEAD)."""
        repo = local_repo
        os.chdir(repo.workdir)
        commit_A_oid_str = str(repo.head.target)
        make_commit(repo, "file_for_default.txt", "new stuff", "Commit for default compare (HEAD)") # make_commit from conftest
        commit_B_oid_str = str(repo.head.target)

        result = runner.invoke(cli, ["compare"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        parent_short_oid = commit_A_oid_str[:7]
        head_short_oid = commit_B_oid_str[:7]
        assert f"Diff between {parent_short_oid} (HEAD~1) (a) and {head_short_oid} (HEAD) (b):" in result.output # Removed \n
        assert "+++ b/file_for_default.txt" in result.output

    def test_compare_invalid_ref_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare invalidREF`."""
        repo = local_repo
        os.chdir(repo.workdir)
        result = runner.invoke(cli, ["compare", "invalidREF"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Could not resolve reference: Reference 'invalidREF' not found or not a commit" in result.output

    def test_compare_not_a_git_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite compare` in a non-Git directory."""
        non_repo_dir = tmp_path / "not_a_repo_for_compare"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)
        result = runner.invoke(cli, ["compare"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Not a Git repository." in result.output

    def test_compare_branch_names_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite compare branchA branchB`."""
        repo = local_repo
        os.chdir(repo.workdir)
        initial_commit_oid = repo.head.target
        repo.branches.create("branch1", repo.get(initial_commit_oid))
        repo.checkout("refs/heads/branch1")
        make_commit(repo, "fileB.txt", "content B", "Commit B on branch1") # make_commit from conftest
        default_branch_name = "main" if repo.branches.get("main") else "master"
        repo.checkout(repo.branches[default_branch_name])
        assert repo.head.target == initial_commit_oid
        repo.branches.create("branch2", repo.get(initial_commit_oid))
        repo.checkout("refs/heads/branch2")
        make_commit(repo, "fileC.txt", "content C", "Commit C on branch2") # make_commit from conftest
        result = runner.invoke(cli, ["compare", "branch1", "branch2"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert f"Diff between branch1 (a) and branch2 (b):" in result.output # Removed \n
        assert "--- a/fileB.txt" in result.output
        assert "+++ b/fileC.txt" in result.output


#######################################
# History Command Tests (CLI Runner)
#######################################

class TestHistoryCommandCLI:

    def test_history_empty_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite history` in an empty initialized repo."""
        empty_repo_path = tmp_path / "empty_history_repo"
        empty_repo_path.mkdir()
        pygit2.init_repository(str(empty_repo_path))
        os.chdir(empty_repo_path)
        result = runner.invoke(cli, ["history"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No history yet." in result.output

    def test_history_bare_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite history` in a bare repo."""
        bare_repo_path = tmp_path / "bare_history_repo.git"
        pygit2.init_repository(str(bare_repo_path), bare=True)
        os.chdir(bare_repo_path)
        result = runner.invoke(cli, ["history"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "No history yet." in result.output

    def test_history_single_commit_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite history` with a single commit."""
        repo = local_repo
        os.chdir(repo.workdir)
        commit_oid = repo.head.target
        commit_obj = repo.get(commit_oid)
        result = runner.invoke(cli, ["history"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Commit" in result.output
        assert "Author" in result.output
        assert "Date" in result.output
        assert "Message" in result.output
        assert str(commit_oid)[:7] in result.output
        assert commit_obj.author.name in result.output
        assert commit_obj.message.splitlines()[0] in result.output

    def test_history_multiple_commits_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite history` with multiple commits."""
        repo = local_repo
        os.chdir(repo.workdir)
        commit1_msg = "Commit Alpha"
        commit1_oid = make_commit(repo, "alpha.txt", "alpha content", commit1_msg) # make_commit from conftest
        commit2_msg = "Commit Beta"
        commit2_oid = make_commit(repo, "beta.txt", "beta content", commit2_msg) # make_commit from conftest
        initial_commit_oid = repo.revparse_single("HEAD~2").id
        initial_commit_obj = repo.get(initial_commit_oid)
        initial_commit_msg = initial_commit_obj.message.splitlines()[0]
        result = runner.invoke(cli, ["history"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Extract commit details from Rich table output lines
        commit_lines = []
        for line in result.output.splitlines():
            if line.startswith("│ ") and "│" in line[2:]: # Basic check for a table data row
                columns = [col.strip() for col in line.split('│')[1:-1]] # Get content between bars
                if len(columns) >= 4: # Expecting Commit, Author, Date, Message
                    commit_lines.append({"short_hash": columns[0], "message": columns[3]})

        assert len(commit_lines) == 3, f"Expected 3 commits in history output, got {len(commit_lines)}"

        # Check order and content (oldest first due to GIT_SORT_TOPOLOGICAL | GIT_SORT_REVERSE)
        assert commit_lines[0]["short_hash"] == str(initial_commit_oid)[:7] # Initial
        assert initial_commit_msg in commit_lines[0]["message"]

        assert commit_lines[1]["short_hash"] == str(commit1_oid)[:7] # Alpha
        assert commit1_msg in commit_lines[1]["message"]

        assert commit_lines[2]["short_hash"] == str(commit2_oid)[:7] # Beta
        assert commit2_msg in commit_lines[2]["message"]

    def test_history_with_limit_n_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite history -n <limit>`."""
        repo = local_repo
        os.chdir(repo.workdir)

        initial_commit_msg = repo.head.peel(pygit2.Commit).message.splitlines()[0]
        initial_commit_oid_str = str(repo.head.target)

        commitA_msg = "Commit A for limit test"
        commitA_oid_str = str(make_commit(repo, "fileA.txt", "contentA", commitA_msg))

        commitB_msg = "Commit B for limit test"
        commitB_oid_str = str(make_commit(repo, "fileB.txt", "contentB", commitB_msg))

        commitC_msg = "Commit C for limit test"
        commitC_oid_str = str(make_commit(repo, "fileC.txt", "contentC", commitC_msg))

        result = runner.invoke(cli, ["history", "-n", "2"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        # Expecting oldest 2: Initial version and Commit A for limit test
        output_text = result.output
        assert initial_commit_oid_str[:7] in output_text
        assert initial_commit_msg in output_text
        assert commitA_oid_str[:7] in output_text
        assert commitA_msg in output_text

        assert commitB_oid_str[:7] not in output_text
        assert commitB_msg not in output_text
        assert commitC_oid_str[:7] not in output_text
        assert commitC_msg not in output_text

        # Check order from parsed lines (oldest first)
        commit_lines = []
        for line in result.output.splitlines():
            if line.startswith("│ ") and "│" in line[2:]:
                columns = [col.strip() for col in line.split('│')[1:-1]]
                if len(columns) >= 4:
                    commit_lines.append({"short_hash": columns[0], "message": columns[3]})

        assert len(commit_lines) == 2
        assert commit_lines[0]["short_hash"] == initial_commit_oid_str[:7] # Initial
        assert initial_commit_msg in commit_lines[0]["message"]
        assert commit_lines[1]["short_hash"] == commitA_oid_str[:7] # Commit A
        assert commitA_msg in commit_lines[1]["message"]

    def test_history_limit_n_greater_than_commits_cli(self, runner: CliRunner, local_repo): # runner & local_repo from conftest
        """Test `gitwrite history -n <limit>` where limit > available commits."""
        repo = local_repo
        os.chdir(repo.workdir)
        # Ensure initial commit message doesn't conflict with search logic
        initial_commit_obj_original = repo.get(repo.head.target)
        original_initial_message = initial_commit_obj_original.message
        # Temporarily change initial commit message if needed, or ensure test commit messages are distinct
        # For this test, let's assume the default "Initial commit" is fine if the logic correctly counts lines.
        # The issue was that "Initial commit" contains "Commit". Let's use a different message.
        # This requires a new initial commit for this specific test or modifying the existing one if possible.
        # Easiest is to ensure subsequent commits don't use "Commit" or "History" if that's the filter.
        # The current problem is "Initial commit" contains "Commit".
        # Let's make the initial commit message for local_repo fixture "Initial version"

        # Re-access initial commit info from the fixture (which should have "Initial version")
        initial_commit_obj = repo.get(repo.revparse_single("HEAD").id) # Assuming local_repo starts with one commit
        initial_commit_msg = initial_commit_obj.message.splitlines()[0]
        initial_commit_oid_str = str(initial_commit_obj.id)

        commitA_msg = "Additional Entry A" # Changed to avoid "Commit"
        commitA_oid_str = str(make_commit(repo, "another_A.txt", "content", commitA_msg)) # make_commit from conftest
        initial_commit_oid_str = str(initial_commit_obj.id) # This is the *original* initial commit OID

        result = runner.invoke(cli, ["history", "-n", "5"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"

        assert commitA_oid_str[:7] in result.output
        assert commitA_msg in result.output
        assert initial_commit_oid_str[:7] in result.output # Original initial commit
        assert initial_commit_msg in result.output # Original initial commit message

        lines_with_short_hash = 0
        # More robust line counting: count lines that start with "│ " and contain a 7-char hash
        for line in result.output.splitlines():
            if line.startswith("│ ") and re.search(r"[0-9a-f]{7}", line.split('│')[1]):
                 lines_with_short_hash +=1
        assert lines_with_short_hash == 2 # Expecting Initial version and Additional Entry A

    def test_history_not_a_git_repo_cli(self, runner: CliRunner, tmp_path: Path): # runner from conftest, tmp_path from pytest
        """Test `gitwrite history` in a directory that is not a Git repository."""
        non_repo_dir = tmp_path / "not_a_repo_for_history"
        non_repo_dir.mkdir()
        os.chdir(non_repo_dir)
        result = runner.invoke(cli, ["history"]) # runner from conftest
        assert result.exit_code == 0, f"CLI Error: {result.output}"
        assert "Error: Not a Git repository (or any of the parent directories)." in result.output
