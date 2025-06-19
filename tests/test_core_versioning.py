import unittest
import unittest.mock as mock
import pygit2
import shutil
import tempfile
from pathlib import Path
import os
# datetime, timezone, timedelta are not used directly in this file anymore,
# create_test_signature from conftest handles its own datetime imports.
from unittest.mock import MagicMock

from gitwrite_core.versioning import revert_commit, save_changes # Added save_changes
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, MergeConflictError, GitWriteError, NoChangesToSaveError, RevertConflictError # Added RevertConflictError

# Constants TEST_USER_NAME and TEST_USER_EMAIL are in conftest.py
# The create_test_signature function is now in conftest.py
# The generic create_file helper is in conftest.py
from .conftest import TEST_USER_NAME, TEST_USER_EMAIL, create_test_signature, create_file as conftest_create_file

# --- Standardized Test Helpers ---

# _make_commit remains local as it's specific to these unittest classes (uses self.signature, files_to_change dict)
# _create_and_checkout_branch also remains local

def _create_and_checkout_branch(repo: pygit2.Repository, branch_name: str, from_commit: pygit2.Commit):
    """Helper to create and check out a branch."""
    branch = repo.branches.local.create(branch_name, from_commit)
    repo.checkout(branch)
    repo.set_head(branch.name)
    return branch

class GitWriteCoreTestCaseBase(unittest.TestCase):
    def setUp(self):
        self.repo_path_obj = Path(tempfile.mkdtemp())
        self.repo_path_str = str(self.repo_path_obj)
        pygit2.init_repository(self.repo_path_str, bare=False)
        self.repo = pygit2.Repository(self.repo_path_str)

        try:
            user_name = self.repo.config["user.name"]
            user_email = self.repo.config["user.email"]
        except KeyError:
            user_name = None
            user_email = None

        if not user_name or not user_email:
            self.repo.config["user.name"] = TEST_USER_NAME
            self.repo.config["user.email"] = TEST_USER_EMAIL
        self.signature = create_test_signature(self.repo)

    def _create_file(self, repo: pygit2.Repository, filepath: str, content: str):
        full_path = Path(repo.workdir) / filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

    def _make_commit(self, repo: pygit2.Repository, message: str, files_to_change: dict = None) -> pygit2.Oid:
        if files_to_change is None:
            files_to_change = {}
        repo.index.read()
        for filepath, content in files_to_change.items():
            self._create_file(repo, filepath, content)
            repo.index.add(filepath)
        repo.index.write()
        tree = repo.index.write_tree()
        parents = [] if repo.head_is_unborn else [repo.head.target]
        signature = self.signature
        return repo.create_commit("HEAD", signature, signature, message, tree, parents)

    def tearDown(self):
        if os.name == 'nt':
            for root, dirs, files in os.walk(self.repo_path_str):
                for name in files:
                    try:
                        filepath = os.path.join(root, name)
                        os.chmod(filepath, 0o777)
                    except OSError:
                        pass
        shutil.rmtree(self.repo_path_obj)

class TestRevertCommitCore(GitWriteCoreTestCaseBase):
    def test_revert_successful_clean(self):
        # Commit 1
        self._make_commit(self.repo, "Initial content C1", {"file_a.txt": "Content A from C1"})
        # Verify file in workdir
        file_a_path = self.repo_path_obj / "file_a.txt"
        self.assertTrue(file_a_path.exists())
        self.assertEqual(file_a_path.read_text(encoding="utf-8"), "Content A from C1")

        # Commit 2
        c2_oid = self._make_commit(self.repo, "Second change C2", {"file_a.txt": "Content A modified by C2", "file_b.txt": "Content B from C2"})
        self.assertEqual(file_a_path.read_text(encoding="utf-8"), "Content A modified by C2")
        self.assertTrue((self.repo_path_obj / "file_b.txt").exists())

        # Revert Commit 2
        result = revert_commit(self.repo_path_str, str(c2_oid))

        self.assertEqual(result['status'], 'success')
        self.assertIsNotNone(result.get('new_commit_oid'))
        revert_commit_oid_str = result['new_commit_oid']
        revert_commit_obj = self.repo.get(revert_commit_oid_str)
        self.assertIsNotNone(revert_commit_obj)

        expected_revert_msg_start = f"Revert \"Second change C2\"" # Core function adds commit hash after this
        self.assertTrue(revert_commit_obj.message.startswith(expected_revert_msg_start))

        # Verify content of working directory (should be back to C1 state for affected files)
        self.assertEqual(file_a_path.read_text(encoding="utf-8"), "Content A from C1")
        self.assertFalse((self.repo_path_obj / "file_b.txt").exists(), "File B created in C2 should be gone after revert")

        # Verify HEAD points to the new revert commit
        self.assertEqual(self.repo.head.target, revert_commit_obj.id)

        # Verify index is clean (no staged changes after revert commit)
        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Repository should be clean after revert, but status is: {status}")


    def test_revert_commit_not_found(self):
        self._make_commit(self.repo, "Initial commit", {"dummy.txt": "content"})
        non_existent_sha = "abcdef1234567890abcdef1234567890abcdef12"
        with self.assertRaisesRegex(CommitNotFoundError, f"Commit '{non_existent_sha}' not found"):
            revert_commit(self.repo_path_str, non_existent_sha)

    def test_revert_on_non_repository_path(self):
        # Create a temporary directory that is NOT a git repository
        non_repo_dir = tempfile.mkdtemp()
        try:
            with self.assertRaisesRegex(RepositoryNotFoundError, "No repository found"):
                revert_commit(non_repo_dir, "HEAD") # Commit SHA doesn't matter here
        finally:
            shutil.rmtree(non_repo_dir)

    def test_revert_results_in_conflict(self):
        # Commit 1: Base file
        self._make_commit(self.repo, "C1: Base file_c.txt", {"file_c.txt": "line1\nline2\nline3"})

        # Commit 2: First modification to line2
        c2_oid = self._make_commit(self.repo, "C2: Modify line2 in file_c.txt", {"file_c.txt": "line1\nMODIFIED_BY_COMMIT_2\nline3"})

        # Commit 3 (HEAD): Conflicting modification to line2
        c3_oid = self._make_commit(self.repo, "C3: Modify line2 again in file_c.txt", {"file_c.txt": "line1\nMODIFIED_BY_COMMIT_3\nline3"})
        self.assertEqual(self.repo.head.target, c3_oid)

        # Attempt to revert Commit 2 - this should cause a conflict
        with self.assertRaisesRegex(MergeConflictError, "Revert resulted in conflicts. The revert has been aborted and the working directory is clean."):
            revert_commit(self.repo_path_str, str(c2_oid))

        # Verify repository state is clean and HEAD is back to C3
        self.assertEqual(self.repo.head.target, c3_oid, "HEAD should be reset to its pre-revert state (C3)")

        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Repository should be clean after failed revert, but status is: {status}")

        # Verify working directory content is that of C3
        file_c_path = self.repo_path_obj / "file_c.txt"
        self.assertEqual(file_c_path.read_text(encoding="utf-8"), "line1\nMODIFIED_BY_COMMIT_3\nline3")

        # Verify no merge/revert artifacts like REVERT_HEAD exist
        self.assertIsNone(self.repo.references.get("REVERT_HEAD"), "REVERT_HEAD should not exist after aborted revert")
        self.assertIsNone(self.repo.references.get("MERGE_HEAD"), "MERGE_HEAD should not exist")
        self.assertEqual(self.repo.index.conflicts, None, "Index should have no conflicts")

    def test_revert_merge_commit_clean(self):
        # Setup:
        # main branch: C1 -> C2
        # feature branch (from C1): C1_F1
        # Merge feature into main: C3 (merge commit)

        # C1 on main
        c1_main_oid = self._make_commit(self.repo, "C1 on main", {"file_main.txt": "Main C1", "shared.txt": "Shared C1"})
        # Ensure 'main' branch exists after initial commit
        if self.repo.head.shorthand != "main":
            # If the default branch is 'master', rename it to 'main'
            if self.repo.head.shorthand == "master":
                master_branch = self.repo.lookup_branch("master")
                master_branch.rename("main")
            # If default is something else, just create 'main' from the commit
            else:
                self.repo.branches.local.create("main", self.repo.head.peel(pygit2.Commit))
        # Ensure we are on 'main'
        main_branch_ref = self.repo.lookup_branch("main")
        self.repo.checkout(main_branch_ref)
        c1_main_commit = self.repo.get(c1_main_oid)

        # Ensure 'main' branch exists and HEAD points to it (or default branch if not 'main')
        # Assuming 'main' is the desired primary branch name.
        # If repo initializes with a different default (e.g. 'master'), this logic might need adjustment
        # or tests should adapt to the repo's default. For now, we aim for 'main'.
        if self.repo.head_is_unborn: # Should not happen after a commit
             self.repo.set_head("refs/heads/main") # Should have been created by _make_commit
        elif self.repo.head.shorthand != "main":
            current_branch_commit = self.repo.get(self.repo.head.target)
            self.repo.branches.create("main", current_branch_commit, force=True) # Create main if not current
            self.repo.set_head("refs/heads/main")
        self.assertEqual(self.repo.head.shorthand, "main")


        # Create feature branch from C1
        feature_branch_name = "feature/test_merge_clean"
        _create_and_checkout_branch(self.repo, feature_branch_name, c1_main_commit)

        # C1_F1 on feature branch
        c1_f1_oid = self._make_commit(self.repo, "C1_F1 on feature", {"file_feature.txt": "Feature C1_F1", "shared.txt": "Shared C1 modified by Feature"})
        self.assertEqual(self.repo.head.target, c1_f1_oid)

        # Switch back to main branch
        main_branch_ref = self.repo.branches["main"] # Use updated way to get branch
        self.repo.checkout(main_branch_ref)
        self.repo.set_head(main_branch_ref.name) # Set HEAD to the branch reference
        self.assertEqual(self.repo.head.shorthand, "main")


        # C2 on main
        c2_main_oid = self._make_commit(self.repo, "C2 on main", {"file_main.txt": "Main C1 then C2"})
        self.assertEqual(self.repo.head.target, c2_main_oid)

        # Merge feature branch into main - this will be C3 (merge commit)
        self.repo.merge(c1_f1_oid)
        # Manually create merge commit as repo.merge() only updates index for non-ff.
        # Check for conflicts (should be none for this clean merge scenario)
        self.assertIsNone(self.repo.index.conflicts, "Merge should be clean initially")

        tree_merge = self.repo.index.write_tree()
        merge_commit_message = f"C3: Merge {feature_branch_name} into main"
        c3_merge_oid = self.repo.create_commit(
            "HEAD",
            self.signature,
            self.signature,
            merge_commit_message,
            tree_merge,
            [c2_main_oid, c1_f1_oid] # Parents of the merge commit
        )
        self.repo.state_cleanup() # Clean up MERGE_HEAD etc.
        self.assertEqual(self.repo.head.target, c3_merge_oid)

        # Verify merged content
        self.assertEqual((self.repo_path_obj / "file_main.txt").read_text(encoding="utf-8"), "Main C1 then C2")
        self.assertEqual((self.repo_path_obj / "file_feature.txt").read_text(encoding="utf-8"), "Feature C1_F1")
        self.assertEqual((self.repo_path_obj / "shared.txt").read_text(encoding="utf-8"), "Shared C1 modified by Feature")

        # Now, revert C3 (the merge commit)
        result = revert_commit(self.repo_path_str, str(c3_merge_oid))
        self.assertEqual(result['status'], 'success')
        revert_c3_oid_str = result['new_commit_oid']
        revert_c3_commit = self.repo.get(revert_c3_oid_str)
        self.assertIsNotNone(revert_c3_commit)

        expected_revert_c3_msg_start = f"Revert \"{merge_commit_message.splitlines()[0]}\""
        self.assertTrue(revert_c3_commit.message.startswith(expected_revert_c3_msg_start))

        # Verify content (should be back to state of C2 on main)
        self.assertEqual((self.repo_path_obj / "file_main.txt").read_text(encoding="utf-8"), "Main C1 then C2")
        self.assertFalse(Path(self.repo_path_obj / "file_feature.txt").exists(), "file_feature.txt from feature branch should be gone")
        self.assertEqual((self.repo_path_obj / "shared.txt").read_text(encoding="utf-8"), "Shared C1")

        # Check HEAD and repo status
        self.assertEqual(self.repo.head.target, revert_c3_commit.id)
        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Repository should be clean after reverting merge, but status is: {status}")

    def test_revert_merge_commit_with_conflict(self):
        # C1 on main
        c1_main_oid = self._make_commit(self.repo, "C1: main", {"file.txt": "line1\nline2 from main C1\nline3"})
        # Ensure 'main' branch exists after initial commit
        if self.repo.head.shorthand != "main":
            # If the default branch is 'master', rename it to 'main'
            if self.repo.head.shorthand == "master":
                master_branch = self.repo.lookup_branch("master")
                master_branch.rename("main")
            # If default is something else, just create 'main' from the commit
            else:
                self.repo.branches.local.create("main", self.repo.head.peel(pygit2.Commit))
        # Ensure we are on 'main'
        main_branch_ref = self.repo.lookup_branch("main")
        self.repo.checkout(main_branch_ref)
        c1_main_commit = self.repo.get(c1_main_oid)

        # Ensure 'main' branch exists and HEAD points to it
        if self.repo.head_is_unborn or self.repo.head.shorthand != "main":
            current_branch_commit = self.repo.get(self.repo.head.target) if not self.repo.head_is_unborn else c1_main_commit
            self.repo.branches.create("main", current_branch_commit, force=True)
            self.repo.set_head("refs/heads/main")
        self.assertEqual(self.repo.head.shorthand, "main")


        # Create 'dev' branch from C1
        _create_and_checkout_branch(self.repo, "dev", c1_main_commit)
        self.assertEqual(self.repo.head.shorthand, "dev")

        # C2 on dev: Modify line2
        c2_dev_oid = self._make_commit(self.repo, "C2: dev modify line2", {"file.txt": "line1\nline2 MODIFIED by dev C2\nline3"})

        # Switch back to main
        main_branch_ref = self.repo.branches["main"]
        self.repo.checkout(main_branch_ref)
        self.repo.set_head(main_branch_ref.name)
        self.assertEqual(self.repo.head.shorthand, "main")

        # C3 on main: Modify line2 (different from dev's C2)
        c3_main_oid = self._make_commit(self.repo, "C3: main modify line2 differently", {"file.txt": "line1\nline2 MODIFIED by main C3\nline3"})

        # Merge dev into main (C4 - merge commit) - this will cause a conflict that we resolve
        self.repo.merge(c2_dev_oid)
        self.assertTrue(self.repo.index.conflicts is not None, "Merge should cause conflicts")

        # Resolve conflict: Choose main's version for line2, append dev's unique content
        resolved_content = "line1\nline2 MODIFIED by main C3\nline2 MODIFIED by dev C2\nline3"
        with open(self.repo_path_obj / "file.txt", "w") as f:
            f.write(resolved_content)
        self.repo.index.add("file.txt")
        self.repo.index.write() # Write resolved index state

        tree_merge_resolved = self.repo.index.write_tree()
        merge_commit_msg = "C4: Merge dev into main (conflict resolved)"
        c4_merge_oid = self.repo.create_commit("HEAD", self.signature, self.signature, merge_commit_msg, tree_merge_resolved, [c3_main_oid, c2_dev_oid])
        self.repo.state_cleanup()
        self.assertEqual(self.repo.head.target, c4_merge_oid)
        self.assertEqual((self.repo_path_obj / "file.txt").read_text(encoding="utf-8"), resolved_content)

        # C5 on main: Make another change on top of the resolved merge.
        # This change is crucial: it will conflict with reverting C4 if C4 tries to remove C2_dev's changes
        # which are now part of the history that C5 builds upon.
        # Let's modify a line that was affected by C2_dev (via C4's resolution)
        c5_main_content_parts = resolved_content.splitlines()
        # resolved_content was:
        # "line1"
        # "line2 MODIFIED by main C3"
        # "line2 MODIFIED by dev C2"  <- This is c5_main_content_parts[2]
        # "line3"
        c5_main_content_parts[2] = "line2 MODIFIED by dev C2 AND THEN BY C5" # Directly modify the line from dev's side of the merge
        c5_main_content = "\n".join(c5_main_content_parts)

        c5_main_oid = self._make_commit(self.repo, "C5: main directly modifies dev's merged line", {"file.txt": c5_main_content})
        self.assertEqual((self.repo_path_obj / "file.txt").read_text(encoding="utf-8"), c5_main_content)


        # Attempt to revert C4 (the merge commit)
        # Reverting C4 means trying to undo the introduction of C2_dev's changes.
        # Pygit2's default revert for a merge commit (mainline 1) means it tries to apply the inverse of C2_dev's changes relative to C3_main.
        # Since C5 has modified content that includes parts of C2_dev's changes (via C4's resolution), this can lead to a conflict.
        with self.assertRaisesRegex(MergeConflictError, "Revert resulted in conflicts. The revert has been aborted and the working directory is clean."):
            revert_commit(self.repo_path_str, str(c4_merge_oid))

        # Verify repository state is clean and HEAD is back to C5
        self.assertEqual(self.repo.head.target, c5_main_oid, "HEAD should be reset to its pre-revert state (C5)")
        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Repository should be clean after failed revert of merge, but status is: {status}")
        self.assertEqual((self.repo_path_obj / "file.txt").read_text(encoding="utf-8"), c5_main_content)
        self.assertIsNone(self.repo.references.get("REVERT_HEAD"))
        self.assertIsNone(self.repo.references.get("MERGE_HEAD"))
        self.assertEqual(self.repo.index.conflicts, None)


if __name__ == '__main__':
    unittest.main()


class TestSaveChangesCore(GitWriteCoreTestCaseBase):
    # setUp, tearDown, _make_commit, _create_file are inherited from GitWriteCoreTestCaseBase

    def _get_file_content_from_commit(self, commit_oid: pygit2.Oid, filepath: str) -> str:
        commit = self.repo.get(commit_oid)
        if not commit:
            raise CommitNotFoundError(f"Commit {commit_oid} not found.")
        try:
            tree_entry = commit.tree[filepath]
            blob = self.repo.get(tree_entry.id)
            if not isinstance(blob, pygit2.Blob):
                raise FileNotFoundError(f"'{filepath}' is not a blob in commit {commit_oid}")
            return blob.data.decode('utf-8')
        except KeyError:
            raise FileNotFoundError(f"File '{filepath}' not found in commit {commit_oid}")

    def _read_file_content_from_workdir(self, relative_filepath: str) -> str:
        full_path = self.repo_path_obj / relative_filepath
        if not full_path.exists():
            raise FileNotFoundError(f"File not found in working directory: {full_path}")
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    # 1. Repository Setup and Basic Errors
    def test_save_on_non_repository_path(self):
        non_repo_dir = tempfile.mkdtemp(prefix="gitwrite_test_non_repo_")
        try:
            with self.assertRaisesRegex(RepositoryNotFoundError, "Repository not found at or above"):
                save_changes(non_repo_dir, "Test message")
        finally:
            shutil.rmtree(non_repo_dir)

    def test_save_on_bare_repository(self):
        bare_repo_path = tempfile.mkdtemp(prefix="gitwrite_test_bare_")
        pygit2.init_repository(bare_repo_path, bare=True)
        try:
            with self.assertRaisesRegex(GitWriteError, "Cannot save changes in a bare repository."):
                save_changes(bare_repo_path, "Test message")
        finally:
            shutil.rmtree(bare_repo_path)

    def test_save_initial_commit_in_empty_repository(self):
        # self.repo is already an empty initialized repo from setUp
        self.assertTrue(self.repo.is_empty)
        self.assertTrue(self.repo.head_is_unborn)

        filename = "initial_file.txt"
        content = "Initial content."
        self._create_file(self.repo, filename, content) # Use local _create_file
        # For initial commit, save_changes will do add_all if include_paths is None

        result = save_changes(self.repo_path_str, "Initial commit")

        self.assertEqual(result['status'], 'success')
        self.assertIsNotNone(result['oid'])
        self.assertFalse(self.repo.head_is_unborn)

        commit = self.repo.get(result['oid'])
        self.assertIsNotNone(commit)
        self.assertEqual(len(commit.parents), 0) # No parents for initial commit
        self.assertEqual(commit.message, "Initial commit")
        self.assertEqual(result['message'], "Initial commit")
        self.assertEqual(result['is_merge_commit'], False)
        self.assertEqual(result['is_revert_commit'], False)
        self.assertIn(result['branch_name'], [self.repo.head.shorthand, "DETACHED_HEAD"]) # Depends on default branch name

        # Verify file content in the commit
        self.assertEqual(self._get_file_content_from_commit(commit.id, filename), content)

        # Verify working directory is clean after commit
        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Working directory should be clean. Status: {status}")

    # 3. Selective Staging (include_paths)
    def test_save_include_paths_single_file(self):
        self._make_commit(self.repo, "Initial", {"file_a.txt": "A v1", "file_b.txt": "B v1"}) # Uses local _make_commit

        self._create_file(self.repo, "file_a.txt", "A v2") # Uses local _create_file
        self._create_file(self.repo, "file_b.txt", "B v2") # Uses local _create_file
        self._create_file(self.repo, "file_c.txt", "C v1") # Uses local _create_file

        result = save_changes(self.repo_path_str, "Commit only file_a", include_paths=["file_a.txt"])

        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])
        commit = self.repo.get(commit_oid)

        self.assertEqual(self._get_file_content_from_commit(commit.id, "file_a.txt"), "A v2")
        # File B should remain as B v1 in this commit, as it wasn't included
        self.assertEqual(self._get_file_content_from_commit(commit.id, "file_b.txt"), "B v1")
        # File C should not be in this commit
        with self.assertRaises(FileNotFoundError):
            self._get_file_content_from_commit(commit.id, "file_c.txt")

        # Check working directory and status
        self.assertEqual(self._read_file_content_from_workdir("file_b.txt"), "B v2")
        self.assertEqual(self._read_file_content_from_workdir("file_c.txt"), "C v1")
        status = self.repo.status()
        self.assertIn("file_b.txt", status) # Should be modified but not committed
        self.assertIn("file_c.txt", status) # Should be new but not committed

    def test_save_include_paths_multiple_files(self):
        self._make_commit(self.repo, "Initial", {"file_a.txt": "A v1", "file_b.txt": "B v1", "file_c.txt": "C v1"}) # Uses local _make_commit

        self._create_file(self.repo, "file_a.txt", "A v2") # Uses local _create_file
        self._create_file(self.repo, "file_b.txt", "B v2") # Uses local _create_file
        self._create_file(self.repo, "file_c.txt", "C v2") # Uses local _create_file

        result = save_changes(self.repo_path_str, "Commit file_a and file_b", include_paths=["file_a.txt", "file_b.txt"])
        commit_oid = pygit2.Oid(hex=result['oid'])

        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_a.txt"), "A v2")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_b.txt"), "B v2")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_c.txt"), "C v1") # Unchanged in commit

    def test_save_include_paths_one_changed_one_not(self):
        self._make_commit(self.repo, "Initial", {"file_a.txt": "A v1", "file_b.txt": "B v1"}) # Uses local _make_commit

        self._create_file(self.repo, "file_a.txt", "A v2") # Uses local _create_file
        # file_b.txt content is "B v1" from the initial commit, not changed in workdir for this test

        result = save_changes(self.repo_path_str, "Commit file_a (changed) and file_b (unchanged)", include_paths=["file_a.txt", "file_b.txt"])
        commit_oid = pygit2.Oid(hex=result['oid'])

        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_a.txt"), "A v2")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_b.txt"), "B v1")

    def test_save_include_paths_file_does_not_exist(self):
        # Core function's save_changes prints a warning for non-existent paths but doesn't fail.
        # The commit should proceed with any valid, changed paths.
        self._make_commit(self.repo, "Initial", {"file_a.txt": "A v1"}) # Uses local _make_commit
        self._create_file(self.repo, "file_a.txt", "A v2") # Uses local _create_file

        result = save_changes(self.repo_path_str, "Commit with non-existent path", include_paths=["file_a.txt", "non_existent.txt"])
        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_a.txt"), "A v2")
        with self.assertRaises(FileNotFoundError): # Ensure non_existent.txt is not part of commit
            self._get_file_content_from_commit(commit_oid, "non_existent.txt")


    def test_save_include_paths_ignored_file(self):
        self._make_commit(self.repo, "Initial", {"not_ignored.txt": "content"}) # Uses local _make_commit

        # Create .gitignore and commit it
        self._make_commit(self.repo, "Add gitignore", {".gitignore": "*.ignored\nignored_dir/"}) # Uses local _make_commit

        self._create_file(self.repo, "file.ignored", "ignored content") # Uses local _create_file
        self._create_file(self.repo, "not_ignored.txt", "new content") # Uses local _create_file

        # Attempt to include an ignored file.
        # save_changes -> index.add(path) for pygit2 by default does not add ignored files unless force=True.
        # The current implementation of save_changes does not use force.
        # So, file.ignored should not be added.
        result = save_changes(self.repo_path_str, "Commit with ignored file attempt", include_paths=["file.ignored", "not_ignored.txt"])
        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])

        self.assertEqual(self._get_file_content_from_commit(commit_oid, "not_ignored.txt"), "new content")
        with self.assertRaises(FileNotFoundError): # Ignored file should not be committed
            self._get_file_content_from_commit(commit_oid, "file.ignored")

    def test_save_include_paths_no_specified_files_have_changes(self):
        self._make_commit(self.repo, "Initial", {"file_a.txt": "A v1", "file_b.txt": "B v1"}) # Uses local _make_commit
        # file_a and file_b are in repo, but no changes made to them in workdir by _create_file.
        # A new file_c is created but not included.
        self._create_file(self.repo, "file_c.txt", "C v1") # Uses local _create_file

        with self.assertRaisesRegex(NoChangesToSaveError, "No specified files had changes to stage relative to HEAD"):
            save_changes(self.repo_path_str, "No changes in included files", include_paths=["file_a.txt", "file_b.txt"])

    def test_save_include_paths_directory(self):
        self._make_commit(self.repo, "Initial", {"file_x.txt": "x"}) # Uses local _make_commit

        self._create_file(self.repo, "dir_a/file_a1.txt", "A1 v1") # Uses local _create_file
        self._create_file(self.repo, "dir_a/file_a2.txt", "A2 v1") # Uses local _create_file
        self._create_file(self.repo, "dir_b/file_b1.txt", "B1 v1") # Uses local _create_file

        result = save_changes(self.repo_path_str, "Commit directory dir_a", include_paths=["dir_a"])
        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])

        self.assertEqual(self._get_file_content_from_commit(commit_oid, "dir_a/file_a1.txt"), "A1 v1")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "dir_a/file_a2.txt"), "A2 v1")
        with self.assertRaises(FileNotFoundError):
            self._get_file_content_from_commit(commit_oid, "dir_b/file_b1.txt")

        # Modify a file in dir_a and add a new one, then save dir_a again
        self._create_file(self.repo, "dir_a/file_a1.txt", "A1 v2") # Uses local _create_file
        self._create_file(self.repo, "dir_a/subdir/file_as1.txt", "AS1 v1") # Uses local _create_file

        result2 = save_changes(self.repo_path_str, "Commit directory dir_a again", include_paths=["dir_a"])
        self.assertEqual(result2['status'], 'success')
        commit2_oid = pygit2.Oid(hex=result2['oid'])
        self.assertEqual(self._get_file_content_from_commit(commit2_oid, "dir_a/file_a1.txt"), "A1 v2")
        self.assertEqual(self._get_file_content_from_commit(commit2_oid, "dir_a/subdir/file_as1.txt"), "AS1 v1")

    # 4. Merge Completion
    # _setup_merge_conflict_state removed
    # Tests will be refactored to set up their own state using new helpers or direct pygit2 calls.

    def test_save_merge_completion_no_conflicts(self):
        # Setup: C1(main) -> C2(main)
        #              \ -> C1_F1(feature)
        # Merge C1_F1 into C2 (main) = C3_Merge(main)
        c1_main_oid = self._make_commit(self.repo, "C1 main", {"file.txt": "Content from C1 main\nshared_line\n"}) # Uses local _make_commit
        # Ensure 'main' branch exists after initial commit
        if self.repo.head.shorthand != "main":
            # If the default branch is 'master', rename it to 'main'
            if self.repo.head.shorthand == "master":
                master_branch = self.repo.lookup_branch("master")
                master_branch.rename("main")
            # If default is something else, just create 'main' from the commit
            else:
                self.repo.branches.local.create("main", self.repo.head.peel(pygit2.Commit))
        # Ensure we are on 'main'
        main_branch_ref = self.repo.lookup_branch("main")
        self.repo.checkout(main_branch_ref)
        c1_main_commit = self.repo.get(c1_main_oid)

        # Feature branch from C1
        _create_and_checkout_branch(self.repo, "feature/merge_test", c1_main_commit) # Uses local _create_and_checkout_branch
        c1_feature_oid = self._make_commit(self.repo, "C1 feature", {"file.txt": "Content from C1 main\nfeature_line\n", "feature_only.txt": "feature content"}) # Uses local _make_commit

        # Switch back to main
        main_branch_ref = self.repo.branches["main"]
        self.repo.checkout(main_branch_ref)
        self.repo.set_head(main_branch_ref.name)
        head_oid_before_merge = self._make_commit(self.repo, "C2 main", {"file.txt": "Content from C1 main\nmain_line\n"}) # Uses local _make_commit

        # Start merge, which will conflict. Resolve it.
        self.repo.merge(c1_feature_oid)
        self._create_file(self.repo, "file.txt", "Content from C1 main\nmain_line\nfeature_line_resolved\n") # Uses local _create_file
        self.repo.index.add("file.txt")
        try: # Ensure feature_only.txt is staged
            self.repo.index['feature_only.txt']
        except KeyError:
            self._create_file(self.repo, "feature_only.txt", "feature content") # Uses local _create_file
            self.repo.index.add("feature_only.txt")
        self.repo.index.write()
        self.assertFalse(self.repo.index.conflicts, "Conflicts should be resolved for this test path.")
        # head_oid_before_merge is C2_main's OID
        merge_head_target_oid = c1_feature_oid # MERGE_HEAD points to the commit from the other branch

        self.assertIsNotNone(self.repo.references.get("MERGE_HEAD"), "MERGE_HEAD should exist before save_changes.")
        self.assertFalse(self.repo.index.conflicts, "Index conflicts should be resolved before calling save_changes.")

        result = save_changes(self.repo_path_str, "Finalize merge commit")

        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['is_merge_commit'])
        merge_commit_oid = pygit2.Oid(hex=result['oid'])
        merge_commit = self.repo.get(merge_commit_oid)

        self.assertEqual(len(merge_commit.parents), 2)
        self.assertEqual(merge_commit.parents[0].id, head_oid_before_merge)
        self.assertEqual(merge_commit.parents[1].id, merge_head_target_oid)
        self.assertEqual(self.repo.head.target, merge_commit_oid)
        self.assertIsNone(self.repo.references.get("MERGE_HEAD"), "MERGE_HEAD should be removed after successful merge commit.")

        # Check content of merged files
        self.assertEqual(self._get_file_content_from_commit(merge_commit_oid, "file.txt"), "Content from C1 main\nmain_line\nfeature_line_resolved\n")
        self.assertEqual(self._get_file_content_from_commit(merge_commit_oid, "feature_only.txt"), "feature content")

    def test_save_merge_completion_with_unresolved_conflicts(self):
        c1_main_oid = self._make_commit(self.repo, "C1 main", {"file.txt": "Content from C1 main\nshared_line\n"}) # Uses local _make_commit
        # Ensure 'main' branch exists after initial commit
        if self.repo.head.shorthand != "main":
            # If the default branch is 'master', rename it to 'main'
            if self.repo.head.shorthand == "master":
                master_branch = self.repo.lookup_branch("master")
                master_branch.rename("main")
            # If default is something else, just create 'main' from the commit
            else:
                self.repo.branches.local.create("main", self.repo.head.peel(pygit2.Commit))
        # Ensure we are on 'main'
        main_branch_ref = self.repo.lookup_branch("main")
        self.repo.checkout(main_branch_ref)
        c1_main_commit = self.repo.get(c1_main_oid)
        _create_and_checkout_branch(self.repo, "feature/merge_test", c1_main_commit) # Uses local _create_and_checkout_branch
        c1_feature_oid = self._make_commit(self.repo, "C1 feature", {"file.txt": "Content from C1 main\nfeature_line\n"}) # Uses local _make_commit

        main_branch_ref = self.repo.branches["main"]
        self.repo.checkout(main_branch_ref)
        self.repo.set_head(main_branch_ref.name)
        head_oid_before_merge = self._make_commit(self.repo, "C2 main", {"file.txt": "Content from C1 main\nmain_line\n"}) # Uses local _make_commit

        # Start merge, which will conflict. Do NOT resolve it.
        self.repo.merge(c1_feature_oid)

        self.assertIsNotNone(self.repo.references.get("MERGE_HEAD"), "MERGE_HEAD should exist.")
        self.assertTrue(self.repo.index.conflicts, "Index should have conflicts for this test.")

        with self.assertRaises(MergeConflictError) as cm:
            save_changes(self.repo_path_str, "Attempt to finalize merge with conflicts")

        self.assertIsNotNone(cm.exception.conflicting_files)
        self.assertIn("file.txt", cm.exception.conflicting_files) # From the setup

        self.assertIsNotNone(self.repo.references.get("MERGE_HEAD"), "MERGE_HEAD should still exist after failed merge attempt.")
        self.assertEqual(self.repo.head.target, head_oid_before_merge, "HEAD should not have moved.")

    def test_save_merge_completion_with_include_paths_error(self):
        c1_main_oid = self._make_commit(self.repo, "C1 main", {"file.txt": "shared"}) # Uses local _make_commit
        # Ensure 'main' branch exists after initial commit
        if self.repo.head.shorthand != "main":
            # If the default branch is 'master', rename it to 'main'
            if self.repo.head.shorthand == "master":
                master_branch = self.repo.lookup_branch("master")
                master_branch.rename("main")
            # If default is something else, just create 'main' from the commit
            else:
                self.repo.branches.local.create("main", self.repo.head.peel(pygit2.Commit))
        # Ensure we are on 'main'
        main_branch_ref = self.repo.lookup_branch("main")
        self.repo.checkout(main_branch_ref)
        c1_main_commit = self.repo.get(c1_main_oid)
        _create_and_checkout_branch(self.repo, "feature", c1_main_commit) # Uses local _create_and_checkout_branch
        c1_feature_oid = self._make_commit(self.repo, "C1 feature", {"file.txt": "feature change", "new_file.txt":"new"}) # Uses local _make_commit

        main_ref = self.repo.branches["main"]
        self.repo.checkout(main_ref)
        self.repo.set_head(main_ref.name)
        self._make_commit(self.repo, "C2 main", {"file.txt": "main change"}) # Uses local _make_commit

        self.repo.merge(c1_feature_oid) # Creates MERGE_HEAD
        # Assume conflicts resolved for this test, as error is about include_paths
        self._create_file(self.repo, "file.txt", "resolved content") # Uses local _create_file
        self.repo.index.add("file.txt")
        try:
            self.repo.index['new_file.txt']
        except KeyError:
            self._create_file(self.repo, "new_file.txt", "new") # Uses local _create_file
            self.repo.index.add("new_file.txt")
        self.repo.index.write()
        self.assertFalse(self.repo.index.conflicts, "Index should be clean before testing include_paths error.")

        with self.assertRaisesRegex(GitWriteError, "Selective staging with --include is not allowed during an active merge operation."):
            save_changes(self.repo_path_str, "Attempt merge with include", include_paths=["file.txt"])

    # 5. Revert Completion
    # _setup_revert_state removed
    # Tests will be refactored.

    def test_save_revert_completion_no_conflicts(self):
        self._make_commit(self.repo, "C1", {"file.txt": "Content C1"}) # Uses local _make_commit
        c2_oid = self._make_commit(self.repo, "C2 changes file", {"file.txt": "Content C2"}) # Uses local _make_commit

        # Simulate that C2 is being reverted.
        # Workdir/index should reflect the state *after* applying C2's inverse to C2 (i.e., state of C1).
        self._create_file(self.repo, "file.txt", "Content C1") # Uses local _create_file
        self.repo.index.read()
        self.repo.index.add("file.txt")
        self.repo.index.write()

        # Manually set up REVERT_HEAD state
        self.repo.create_reference("REVERT_HEAD", c2_oid) # REVERT_HEAD points to commit being reverted (C2)
        self.assertIsNotNone(self.repo.references.get("REVERT_HEAD"))
        self.assertFalse(self.repo.index.conflicts, "Index conflicts should be resolved for this test.")

        user_message = "User message for revert"
        result = save_changes(self.repo_path_str, user_message)

        self.assertEqual(result['status'], 'success')
        self.assertTrue(result['is_revert_commit'])
        revert_commit_oid = pygit2.Oid(hex=result['oid'])
        revert_commit_obj = self.repo.get(revert_commit_oid)

        self.assertEqual(len(revert_commit_obj.parents), 1)
        self.assertEqual(revert_commit_obj.parents[0].id, c2_oid) # Parent is the commit just before this revert commit
        self.assertEqual(self.repo.head.target, revert_commit_oid)
        self.assertIsNone(self.repo.references.get("REVERT_HEAD"), "REVERT_HEAD should be removed.")

        expected_revert_msg_start = f"Revert \"C2 changes file\"" # From C2's message
        self.assertTrue(revert_commit_obj.message.startswith(expected_revert_msg_start))
        self.assertIn(f"This reverts commit {c2_oid}.", revert_commit_obj.message)
        self.assertIn(user_message, revert_commit_obj.message)

        self.assertEqual(self._get_file_content_from_commit(revert_commit_oid, "file.txt"), "Content C1")

    def test_save_revert_completion_with_unresolved_conflicts(self):
        self._make_commit(self.repo, "C1", {"file.txt": "Content C1"}) # Uses local _make_commit
        c2_oid = self._make_commit(self.repo, "C2", {"file.txt": "Content C2"}) # Uses local _make_commit

        # Manually set up REVERT_HEAD state and create a conflict
        self.repo.create_reference("REVERT_HEAD", c2_oid)
        # Create a dummy conflict in the index
        conflict_path = "conflicting_revert_file.txt"
        self._create_file(self.repo, conflict_path + "_ancestor", "ancestor") # Uses local _create_file
        self._create_file(self.repo, conflict_path + "_our", "our_version") # Uses local _create_file
        self._create_file(self.repo, conflict_path + "_their", "their_version") # Uses local _create_file

        ancestor_blob_oid = self.repo.create_blob(b"revert_ancestor_content")
        our_blob_oid = self.repo.create_blob(b"revert_our_content")
        their_blob_oid = self.repo.create_blob(b"revert_their_content")

        self.repo.index.read()
        # Simulate conflicts by creating a mock conflict entry
        # The actual content of the conflict entry doesn't matter for this test,
        # only that the 'conflicts' attribute is not None and returns conflicting files.
        from unittest.mock import MagicMock # Import locally for this method
        class MockConflictEntry:
            def __init__(self, path):
                self.our = MagicMock()
                self.our.path = path
                self.their = MagicMock()
                self.their.path = path
                self.ancestor = MagicMock()
                self.ancestor.path = path

        mock_conflict = MockConflictEntry(conflict_path)
        # Ensure the mock returns a list containing a 3-tuple (ancestor, ours, theirs)
        # to match the real structure of repo.index.conflicts iterator items.
        mock_conflict_data = (mock_conflict.ancestor, mock_conflict.our, mock_conflict.their)

        with mock.patch('pygit2.Index.conflicts', new_callable=mock.PropertyMock, return_value=[mock_conflict_data]):
            self.repo.index.write() # This write might not be necessary if conflicts are mocked

            self.assertIsNotNone(self.repo.references.get("REVERT_HEAD"))
            self.assertTrue(self.repo.index.conflicts, "Index should have conflicts.")

            with self.assertRaises(RevertConflictError) as cm:
                save_changes(self.repo_path_str, "Attempt to finalize revert with conflicts")

        self.assertIsNotNone(cm.exception.conflicting_files)
        # The artificial conflict was on 'conflicting_revert_file.txt'
        self.assertIn("conflicting_revert_file.txt", cm.exception.conflicting_files)

        self.assertIsNotNone(self.repo.references.get("REVERT_HEAD"), "REVERT_HEAD should still exist.")
        self.assertEqual(self.repo.head.target, c2_oid, "HEAD should not have moved.")


    def test_save_revert_completion_with_include_paths_error(self):
        self._make_commit(self.repo, "C1", {"file.txt": "Content C1"}) # Uses local _make_commit
        c2_oid = self._make_commit(self.repo, "C2", {"file.txt": "Content C2"}) # Uses local _make_commit
        # Manually set up REVERT_HEAD state (no conflict needed for this test)
        self.repo.create_reference("REVERT_HEAD", c2_oid)

        with self.assertRaisesRegex(GitWriteError, "Selective staging with --include is not allowed during an active revert operation."):
            save_changes(self.repo_path_str, "Attempt revert with include", include_paths=["file.txt"])

    # 6. Author/Committer Information
    def test_save_uses_repo_default_signature(self):
        # Ensure repo has a default signature set in its config
        self.repo.config["user.name"] = "Config User"
        self.repo.config["user.email"] = "config@example.com"

        self._create_file(self.repo, "file.txt", "content for signature test") # Use local _create_file
        result = save_changes(self.repo_path_str, "Commit with default signature")

        self.assertEqual(result['status'], 'success')
        commit = self.repo.get(pygit2.Oid(hex=result['oid']))
        self.assertIsNotNone(commit)
        self.assertEqual(commit.author.name, "Config User")
        self.assertEqual(commit.author.email, "config@example.com")
        self.assertEqual(commit.committer.name, "Config User")
        self.assertEqual(commit.committer.email, "config@example.com")

    @unittest.mock.patch('pygit2.Repository.default_signature', new_callable=unittest.mock.PropertyMock)
    def test_save_uses_fallback_signature_when_default_fails(self, mock_default_signature):
        # Simulate pygit2.GitError when trying to get default_signature
        # This typically happens if user.name/email are not set in any git config.
        mock_default_signature.side_effect = pygit2.GitError("Simulated error: No signature configured")

        self._create_file(self.repo, "file.txt", "content for fallback signature test") # Use local _create_file

        # Temporarily clear any globally set config for this repo object to ensure fallback path
        # This is tricky as default_signature might still pick up system/global if not careful.
        # The mock above is the primary way to test this.
        # We can also try to remove config from the test repo itself, though mock is cleaner.
        original_config = self.repo.config
        temp_config_snapshot = original_config.snapshot() # Save current config

        # Create a new config object that doesn't inherit global settings for this test
        # Note: This doesn't prevent pygit2 from looking at global/system config if it wants to.
        # The mock is the most reliable way.
        # For this specific test, the mock is sufficient.
        # If we wanted to test the code path where repo.config itself is missing values:
        # del self.repo.config["user.name"] # This would error if not present. Better to mock.

        result = save_changes(self.repo_path_str, "Commit with fallback signature")

        self.assertEqual(result['status'], 'success')
        commit = self.repo.get(pygit2.Oid(hex=result['oid']))
        self.assertIsNotNone(commit)

        # Check against the hardcoded fallback in save_changes
        self.assertEqual(commit.author.name, "GitWrite User")
        self.assertEqual(commit.author.email, "user@example.com")
        self.assertEqual(commit.committer.name, "GitWrite User")
        self.assertEqual(commit.committer.email, "user@example.com")

        # Restore original config for other tests (if it was modified)
        # Not strictly necessary here as teardown creates fresh repo, but good practice if repo was reused.
        # For this test, mock ensures the fallback path is hit.

        # Ensure the mock was called
        mock_default_signature.assert_called()

    def test_save_initial_commit_with_include_paths(self):
        self.assertTrue(self.repo.is_empty)
        self._create_file(self.repo, "file1.txt", "content1") # Use local _create_file
        self._create_file(self.repo, "file2.txt", "content2") # Use local _create_file

        result = save_changes(self.repo_path_str, "Initial commit with file1", include_paths=["file1.txt"])

        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])
        commit = self.repo.get(commit_oid)
        self.assertIsNotNone(commit)
        self.assertEqual(len(commit.parents), 0)

        # Check only file1 is in the commit
        with self.assertRaises(FileNotFoundError):
            self._get_file_content_from_commit(commit_oid, "file2.txt")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file1.txt"), "content1")

        # File2 should still be in the working directory, untracked by this commit
        self.assertTrue((self.repo_path_obj / "file2.txt").exists())
        status = self.repo.status()
        self.assertIn("file2.txt", status) # Should be WT_NEW

    def test_save_initial_commit_no_files_staged_error(self):
        # Empty repo, no files created or specified
        with self.assertRaisesRegex(NoChangesToSaveError, "Cannot create an initial commit: no files were staged"):
            save_changes(self.repo_path_str, "Initial commit attempt on empty")

        # Empty repo, files created but not included
        self._create_file(self.repo, "somefile.txt", "content") # Use local _create_file
        with self.assertRaisesRegex(NoChangesToSaveError, "Cannot create an initial commit: no files were staged. If include_paths were specified, they might be invalid or ignored."):
            save_changes(self.repo_path_str, "Initial commit with non-existent include", include_paths=["doesnotexist.txt"])

    # 2. Normal Commits
    def test_save_normal_commit_stage_all(self):
        c1_oid = self._make_commit(self.repo, "Initial", {"file_a.txt": "Content A v1"}) # Uses local _make_commit

        self._create_file(self.repo, "file_a.txt", "Content A v2") # Uses local _create_file
        self._create_file(self.repo, "file_b.txt", "Content B v1") # Uses local _create_file

        result = save_changes(self.repo_path_str, "Second commit with changes")

        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])
        commit = self.repo.get(commit_oid)
        self.assertIsNotNone(commit)
        self.assertEqual(len(commit.parents), 1)
        self.assertEqual(commit.parents[0].id, c1_oid)
        self.assertEqual(self.repo.head.target, commit.id)

        self.assertEqual(self._get_file_content_from_commit(commit.id, "file_a.txt"), "Content A v2")
        self.assertEqual(self._get_file_content_from_commit(commit.id, "file_b.txt"), "Content B v1")
        self.assertEqual(result['message'], "Second commit with changes")
        self.assertFalse(result['is_merge_commit'])
        self.assertFalse(result['is_revert_commit'])

        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Working directory should be clean. Status: {status}")

    def test_save_no_changes_in_non_empty_repo_error(self):
        self._make_commit(self.repo, "Initial", {"file_a.txt": "Content A v1"}) # Uses local _make_commit
        # No changes made after initial commit

        with self.assertRaisesRegex(NoChangesToSaveError, r"No changes to save \(working directory and index are clean or match HEAD\)\."):
            save_changes(self.repo_path_str, "Attempt to save no changes")

    def test_save_with_staged_changes_working_dir_clean(self):
        c1_oid = self._make_commit(self.repo, "Initial", {"file_a.txt": "Original Content"}) # Uses local _make_commit

        # Stage a change but don't modify working directory further
        self.repo.index.read()
        self._create_file(self.repo, "file_a.txt", "Staged Content") # Uses local _create_file; workdir now "Staged Content"
        self.repo.index.add("file_a.txt") # index now "Staged Content"
        self.repo.index.write()

        # For this test, we want to ensure the working directory is "clean" relative to the STAGED content.
        # So, the file_a.txt in workdir IS "Staged Content".
        # The diff between index and HEAD should exist.
        # The diff between workdir and index should NOT exist for file_a.txt.
        # Workdir for file_a.txt is "Staged Content".

        # Create another file in workdir but DO NOT STAGE IT
        self._create_file(self.repo, "file_b.txt", "Unstaged Content") # Uses local _create_file; workdir has file_b.txt

        result = save_changes(self.repo_path_str, "Commit staged changes for file_a")
        # This should commit file_a.txt with "Staged Content" (as it was staged)
        # AND file_b.txt with "Unstaged Content" (because include_paths=None implies add all unstaged)
        # calls add_all(), which respects existing staged changes and adds unstaged changes from workdir.
        # So, file_b.txt will also be committed.

        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])
        commit = self.repo.get(commit_oid)

        self.assertEqual(self._get_file_content_from_commit(commit.id, "file_a.txt"), "Staged Content")
        self.assertEqual(self._get_file_content_from_commit(commit.id, "file_b.txt"), "Unstaged Content")
        self.assertEqual(self.repo.head.target, commit.id)
        self.assertEqual(len(commit.parents), 1)
        self.assertEqual(commit.parents[0].id, c1_oid)

        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Working directory should be clean. Status: {status}")

    def test_save_with_only_index_changes_no_workdir_changes(self):
        # Initial commit
        c1_oid = self._make_commit(self.repo, "C1", {"original.txt": "v1"}) # Uses local _make_commit

        # Create a new file, add it to index, then REMOVE it from workdir
        self._create_file(self.repo, "only_in_index.txt", "This file is staged then removed from workdir") # Uses local _create_file; workdir has file
        self.repo.index.read()
        self.repo.index.add("only_in_index.txt") # index has file
        self.repo.index.write()

        os.remove(self.repo_path_obj / "only_in_index.txt") # workdir no longer has file

        # Modify an existing tracked file, stage it, then revert workdir change
        self._create_file(self.repo, "original.txt", "v2_staged") # Uses local _create_file; workdir has "v2_staged"
        self.repo.index.add("original.txt") # index has "v2_staged"
        self.repo.index.write()
        self._create_file(self.repo, "original.txt", "v1") # Uses local _create_file; workdir now has "v1"

        # At this point:
        # - only_in_index.txt is in index (staged for add), not in workdir (deleted from workdir)
        # - original.txt is "v2_staged" in index, "v1" in workdir (modified)

        # save_changes with include_paths=None will call repo.index.add_all().
        # For "only_in_index.txt", it's staged for addition. add_all() might see it as deleted from workdir.
        # For "original.txt", it's staged as "v2_staged". add_all() will update staging with workdir "v1".
        # This means the commit should reflect the working directory state due to add_all().

        result = save_changes(self.repo_path_str, "Commit with add_all effect")

        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])

        # original.txt should be committed as "v1" (from workdir)
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "original.txt"), "v1")

        # only_in_index.txt was staged for addition but deleted from workdir.
        # git commit -a (which is like add_all then commit) would commit the deletion.
        # Let's verify it's not in the commit.
        with self.assertRaises(FileNotFoundError):
            self._get_file_content_from_commit(commit_oid, "only_in_index.txt")

        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Working directory should be clean. Status: {status}")
