import unittest
import unittest.mock as mock
import pygit2
import shutil
import tempfile
from pathlib import Path
import os
from datetime import datetime, timezone, timedelta

from gitwrite_core.versioning import revert_commit
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, MergeConflictError, GitWriteError

# Default signature for tests
TEST_USER_NAME = "Test User"
TEST_USER_EMAIL = "test@example.com"

def create_test_signature(repo: pygit2.Repository) -> pygit2.Signature:
    """Creates a test signature, trying to use repo default or falling back."""
    try:
        return repo.default_signature
    except pygit2.GitError: # If not configured
        return pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)


class TestRevertCommitCore(unittest.TestCase):
    def setUp(self):
        self.repo_path_obj = Path(tempfile.mkdtemp())
        self.repo_path_str = str(self.repo_path_obj)
        # Initialize a bare repository first for full control, then open it as non-bare
        pygit2.init_repository(self.repo_path_str, bare=False)
        self.repo = pygit2.Repository(self.repo_path_str)

        # Set up a default signature if none is configured globally for git
        try:
            user_name = self.repo.config["user.name"]
            user_email = self.repo.config["user.email"]
        except KeyError: # If not configured
            user_name = None
            user_email = None

        if not user_name or not user_email:
            self.repo.config["user.name"] = TEST_USER_NAME
            self.repo.config["user.email"] = TEST_USER_EMAIL

        self.signature = create_test_signature(self.repo)


    def tearDown(self):
        # Unlock files before removing (Windows specific issue with pygit2)
        if os.name == 'nt':
            for root, dirs, files in os.walk(self.repo_path_str):
                for name in files:
                    try:
                        filepath = os.path.join(root, name)
                        os.chmod(filepath, 0o777)
                    except OSError: # some files might be git internal and not modifiable
                        pass
        shutil.rmtree(self.repo_path_obj)

    def _create_commit(self, message: str, parent_refs: list = None, files_to_add_update: dict = None) -> pygit2.Oid:
        """
        Helper to create a commit.
        files_to_add_update: A dictionary of {filepath_relative_to_repo: content}
        """
        if files_to_add_update is None:
            files_to_add_update = {}

        builder = self.repo.TreeBuilder()

        # If parents exist, use the tree of the first parent as a base
        if parent_refs and self.repo.head_is_unborn == False :
             # Get the tree of the current HEAD (or first parent)
            if self.repo.head.target: # Check if HEAD is pointing to a commit
                parent_commit = self.repo.get(self.repo.head.target)
                if parent_commit:
                    parent_tree = parent_commit.tree
                    # Add existing entries from parent tree
                    for entry in parent_tree:
                         builder.insert(entry.name, entry.id, entry.filemode)
            else: # no HEAD target, likely initial commit or unborn head.
                 pass


        for filepath_str, content_str in files_to_add_update.items():
            filepath_path = Path(filepath_str)
            full_path = self.repo_path_obj / filepath_path

            # Ensure parent directory exists
            full_path.parent.mkdir(parents=True, exist_ok=True)

            blob_oid = self.repo.create_blob(content_str.encode('utf-8'))

            # Handle nested paths for tree builder
            path_parts = list(filepath_path.parts)
            current_builder = builder

            # This logic for nested tree building is a bit simplistic and might need refinement
            # For now, assuming files are at root or one level deep for simplicity in tests
            # For deeper nesting, a recursive approach to build subtrees would be needed.
            # This simplified version assumes files are at the root of the repo for builder.insert
            # If a file is like "dir/file.txt", this will not work correctly without more complex tree building.
            # Let's assume for tests, files are at root, e.g., "file_a.txt", "file_b.txt".

            if len(path_parts) > 1:
                # This is a simplified example; real nested tree building is more complex.
                # For these tests, let's stick to root-level files or ensure paths are handled correctly.
                # For now, we will assume files_to_add_update uses root paths
                # or that the `self.repo.index.add()` and `write_tree()` approach handles it.
                # Switching to index-based commit creation for simplicity and robustness:
                pass # Will use index below

        # Use index for staging changes, it's more robust for paths
        self.repo.index.read() # Load current index
        for filepath_str, content_str in files_to_add_update.items():
            full_path = self.repo_path_obj / filepath_str
            full_path.parent.mkdir(parents=True, exist_ok=True)
            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content_str)
            self.repo.index.add(filepath_str) # Add relative path to index

        tree_oid = self.repo.index.write_tree()
        self.repo.index.write() # Persist index changes

        parents_for_commit = []
        if self.repo.head_is_unborn:
            pass # Initial commit has no parents
        else:
            parents_for_commit = [self.repo.head.target]

        return self.repo.create_commit(
            "HEAD",  # Update HEAD to this new commit
            self.signature,
            self.signature,
            message,
            tree_oid,
            parents_for_commit
        )

    def _read_file_content_from_workdir(self, relative_filepath: str) -> str:
        full_path = self.repo_path_obj / relative_filepath
        if not full_path.exists():
            raise FileNotFoundError(f"File not found in working directory: {full_path}")
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def _read_file_content_at_commit(self, commit_oid: pygit2.Oid, relative_filepath: str) -> str:
        commit = self.repo.get(commit_oid)
        if not commit:
            raise CommitNotFoundError(f"Commit {commit_oid} not found.")

        try:
            tree_entry = commit.tree[relative_filepath]
            blob = self.repo.get(tree_entry.id)
            if blob is None or not isinstance(blob, pygit2.Blob):
                 raise FileNotFoundError(f"File '{relative_filepath}' not found as a blob in commit {commit_oid}.")
            return blob.data.decode('utf-8')
        except KeyError:
            raise FileNotFoundError(f"File '{relative_filepath}' not found in tree of commit {commit_oid}.")


    def test_revert_successful_clean(self):
        # Commit 1
        c1_oid = self._create_commit("Initial content C1", files_to_add_update={"file_a.txt": "Content A from C1"})
        self.assertEqual(self._read_file_content_from_workdir("file_a.txt"), "Content A from C1")

        # Commit 2
        c2_oid = self._create_commit("Second change C2", files_to_add_update={"file_a.txt": "Content A modified by C2", "file_b.txt": "Content B from C2"})
        self.assertEqual(self._read_file_content_from_workdir("file_a.txt"), "Content A modified by C2")
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
        self.assertEqual(self._read_file_content_from_workdir("file_a.txt"), "Content A from C1")
        self.assertFalse((self.repo_path_obj / "file_b.txt").exists(), "File B created in C2 should be gone after revert")

        # Verify HEAD points to the new revert commit
        self.assertEqual(self.repo.head.target, revert_commit_obj.id)

        # Verify index is clean (no staged changes after revert commit)
        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Repository should be clean after revert, but status is: {status}")


    def test_revert_commit_not_found(self):
        self._create_commit("Initial commit", files_to_add_update={"dummy.txt": "content"})
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
        c1_oid = self._create_commit("C1: Base file_c.txt", files_to_add_update={"file_c.txt": "line1\nline2\nline3"})

        # Commit 2: First modification to line2
        c2_oid = self._create_commit("C2: Modify line2 in file_c.txt", files_to_add_update={"file_c.txt": "line1\nMODIFIED_BY_COMMIT_2\nline3"})

        # Commit 3 (HEAD): Conflicting modification to line2
        c3_oid = self._create_commit("C3: Modify line2 again in file_c.txt", files_to_add_update={"file_c.txt": "line1\nMODIFIED_BY_COMMIT_3\nline3"})
        self.assertEqual(self.repo.head.target, c3_oid)

        # Attempt to revert Commit 2 - this should cause a conflict
        with self.assertRaisesRegex(MergeConflictError, "Revert resulted in conflicts. The revert has been aborted and the working directory is clean."):
            revert_commit(self.repo_path_str, str(c2_oid))

        # Verify repository state is clean and HEAD is back to C3
        self.assertEqual(self.repo.head.target, c3_oid, "HEAD should be reset to its pre-revert state (C3)")

        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Repository should be clean after failed revert, but status is: {status}")

        # Verify working directory content is that of C3
        self.assertEqual(self._read_file_content_from_workdir("file_c.txt"), "line1\nMODIFIED_BY_COMMIT_3\nline3")

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
        c1_main_oid_commit = self.repo.get(self._create_commit("C1 on main", files_to_add_update={"file_main.txt": "Main C1", "shared.txt": "Shared C1"}))

        # Ensure 'main' branch exists and HEAD points to it
        if self.repo.head.shorthand != "main":
            self.repo.branches.create("main", c1_main_oid_commit, force=True)
            self.repo.set_head("refs/heads/main")
        self.assertEqual(self.repo.head.shorthand, "main") # Verify we are on main

        # Create feature branch from C1
        feature_branch_name = "feature/test_merge_clean"
        self.repo.create_branch(feature_branch_name, c1_main_oid_commit)

        # Checkout feature branch (by setting HEAD)
        self.repo.set_head(f"refs/heads/{feature_branch_name}")

        # C1_F1 on feature branch
        c1_f1_oid = self._create_commit("C1_F1 on feature", files_to_add_update={"file_feature.txt": "Feature C1_F1", "shared.txt": "Shared C1 modified by Feature"})
        self.assertEqual(self.repo.head.target, c1_f1_oid)

        # Switch back to main branch
        # self.repo.set_head("refs/heads/main") # Already on main or switched above
        main_ref = self.repo.lookup_reference("refs/heads/main")
        self.repo.checkout(main_ref) # Use checkout for robustness
        self.assertEqual(self.repo.head.shorthand, "main")


        # C2 on main
        c2_main_oid_commit_oid = self._create_commit("C2 on main", files_to_add_update={"file_main.txt": "Main C1 then C2"})
        self.assertEqual(self.repo.head.target, c2_main_oid_commit_oid)

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
            [c2_main_oid_commit_oid, c1_f1_oid] # Parents of the merge commit
        )
        self.repo.state_cleanup() # Clean up MERGE_HEAD etc.
        self.assertEqual(self.repo.head.target, c3_merge_oid)

        # Verify merged content
        self.assertEqual(self._read_file_content_from_workdir("file_main.txt"), "Main C1 then C2")
        self.assertEqual(self._read_file_content_from_workdir("file_feature.txt"), "Feature C1_F1")
        self.assertEqual(self._read_file_content_from_workdir("shared.txt"), "Shared C1 modified by Feature")

        # Now, revert C3 (the merge commit)
        result = revert_commit(self.repo_path_str, str(c3_merge_oid))
        self.assertEqual(result['status'], 'success')
        revert_c3_oid_str = result['new_commit_oid']
        revert_c3_commit = self.repo.get(revert_c3_oid_str)
        self.assertIsNotNone(revert_c3_commit)

        expected_revert_c3_msg_start = f"Revert \"{merge_commit_message.splitlines()[0]}\""
        self.assertTrue(revert_c3_commit.message.startswith(expected_revert_c3_msg_start))

        # Verify content (should be back to state of C2 on main)
        self.assertEqual(self._read_file_content_from_workdir("file_main.txt"), "Main C1 then C2")
        self.assertFalse(Path(self.repo_path_obj / "file_feature.txt").exists(), "file_feature.txt from feature branch should be gone")
        self.assertEqual(self._read_file_content_from_workdir("shared.txt"), "Shared C1", "shared.txt should revert to C1 main's version (as C2 didn't change it)")

        # Check HEAD and repo status
        self.assertEqual(self.repo.head.target, revert_c3_commit.id)
        status = self.repo.status()
        self.assertEqual(len(status), 0, f"Repository should be clean after reverting merge, but status is: {status}")

    def test_revert_merge_commit_with_conflict(self):
        # C1 on main
        c1_main_commit_obj = self.repo.get(self._create_commit("C1: main", files_to_add_update={"file.txt": "line1\nline2 from main C1\nline3"}))

        # Ensure 'main' branch exists and HEAD points to it
        if self.repo.head.shorthand != "main":
            self.repo.branches.create("main", c1_main_commit_obj, force=True)
            self.repo.set_head("refs/heads/main")
        self.assertEqual(self.repo.head.shorthand, "main")


        # Create 'dev' branch from C1
        self.repo.create_branch("dev", c1_main_commit_obj)
        dev_ref = self.repo.lookup_reference("refs/heads/dev")
        self.repo.checkout(dev_ref) # Checkout dev
        self.assertEqual(self.repo.head.shorthand, "dev")

        # C2 on dev: Modify line2
        c2_dev_oid = self._create_commit("C2: dev modify line2", files_to_add_update={"file.txt": "line1\nline2 MODIFIED by dev C2\nline3"})

        # Switch back to main
        main_ref = self.repo.lookup_reference("refs/heads/main")
        self.repo.checkout(main_ref)
        self.assertEqual(self.repo.head.shorthand, "main")

        # C3 on main: Modify line2 (different from dev's C2)
        c3_main_oid_commit_oid = self._create_commit("C3: main modify line2 differently", files_to_add_update={"file.txt": "line1\nline2 MODIFIED by main C3\nline3"})

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
        c4_merge_oid = self.repo.create_commit("HEAD", self.signature, self.signature, merge_commit_msg, tree_merge_resolved, [c3_main_oid_commit_oid, c2_dev_oid])
        self.repo.state_cleanup()
        self.assertEqual(self.repo.head.target, c4_merge_oid)
        self.assertEqual(self._read_file_content_from_workdir("file.txt"), resolved_content)

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

        c5_main_oid = self._create_commit("C5: main directly modifies dev's merged line", files_to_add_update={"file.txt": c5_main_content})
        self.assertEqual(self._read_file_content_from_workdir("file.txt"), c5_main_content)


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
        self.assertEqual(self._read_file_content_from_workdir("file.txt"), c5_main_content)
        self.assertIsNone(self.repo.references.get("REVERT_HEAD"))
        self.assertIsNone(self.repo.references.get("MERGE_HEAD"))
        self.assertEqual(self.repo.index.conflicts, None)


if __name__ == '__main__':
    unittest.main()


class TestSaveChangesCore(unittest.TestCase):
    def setUp(self):
        self.repo_path_obj = Path(tempfile.mkdtemp(prefix="gitwrite_test_save_"))
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

    def tearDown(self):
        # Attempt to force remove read-only files, especially on Windows
        for root, dirs, files in os.walk(self.repo_path_obj, topdown=False):
            for name in files:
                filepath = os.path.join(root, name)
                try:
                    os.chmod(filepath, 0o777) # Make it writable
                    os.remove(filepath)
                except OSError as e:
                    print(f"Warning: Could not remove file {filepath}: {e}") # Or log
            for name in dirs:
                dirpath = os.path.join(root, name)
                try:
                    os.rmdir(dirpath)
                except OSError as e:
                    print(f"Warning: Could not remove directory {dirpath}: {e}") # Or log
        try:
            shutil.rmtree(self.repo_path_obj)
        except OSError as e:
            print(f"Warning: shutil.rmtree failed for {self.repo_path_obj}: {e}")


    def _create_file(self, relative_filepath: str, content: str):
        """Helper to create a file in the working directory."""
        full_path = self.repo_path_obj / relative_filepath
        full_path.parent.mkdir(parents=True, exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return str(full_path)

    def _create_commit(self, message: str, files_to_add_update: dict = None, add_to_index: bool = True) -> pygit2.Oid:
        """
        Simplified helper to create a commit, using the index.
        files_to_add_update: A dictionary of {filepath_relative_to_repo: content}
        """
        if files_to_add_update is None:
            files_to_add_update = {}

        self.repo.index.read()
        for filepath_str, content_str in files_to_add_update.items():
            self._create_file(filepath_str, content_str)
            if add_to_index:
                self.repo.index.add(filepath_str)

        if add_to_index:
            self.repo.index.write() # Persist index changes if files were added to it

        tree_oid = self.repo.index.write_tree() # Write tree from current index state

        parents_for_commit = []
        if not self.repo.head_is_unborn:
            parents_for_commit = [self.repo.head.target]

        commit_oid = self.repo.create_commit(
            "HEAD",
            self.signature,
            self.signature,
            message,
            tree_oid,
            parents_for_commit
        )
        # After commit, index is usually cleared by pygit2/git.
        # If we want to keep staged changes for next commit, we might need to re-stage.
        # For most tests, we commit then check state, so this is fine.
        return commit_oid

    def _get_file_content_from_commit(self, commit_oid: pygit2.Oid, filepath: str) -> str:
        commit = self.repo.get(commit_oid)
        tree = commit.tree
        try:
            entry = tree[filepath]
            blob = self.repo.get(entry.id)
            return blob.data.decode('utf-8')
        except KeyError:
            raise FileNotFoundError(f"File '{filepath}' not found in commit {commit_oid}")

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
        self._create_file(filename, content)
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
        c1_oid = self._create_commit("Initial", files_to_add_update={"file_a.txt": "A v1", "file_b.txt": "B v1"})

        self._create_file("file_a.txt", "A v2") # Changed
        self._create_file("file_b.txt", "B v2") # Changed, but not included
        self._create_file("file_c.txt", "C v1") # New, but not included

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
        self._create_commit("Initial", files_to_add_update={"file_a.txt": "A v1", "file_b.txt": "B v1", "file_c.txt": "C v1"})

        self._create_file("file_a.txt", "A v2") # Included
        self._create_file("file_b.txt", "B v2") # Included
        self._create_file("file_c.txt", "C v2") # Not included

        result = save_changes(self.repo_path_str, "Commit file_a and file_b", include_paths=["file_a.txt", "file_b.txt"])
        commit_oid = pygit2.Oid(hex=result['oid'])

        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_a.txt"), "A v2")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_b.txt"), "B v2")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_c.txt"), "C v1") # Unchanged in commit

    def test_save_include_paths_one_changed_one_not(self):
        self._create_commit("Initial", files_to_add_update={"file_a.txt": "A v1", "file_b.txt": "B v1"})

        self._create_file("file_a.txt", "A v2") # Changed, included
        # file_b.txt remains "B v1" (not changed), but included

        result = save_changes(self.repo_path_str, "Commit file_a (changed) and file_b (unchanged)", include_paths=["file_a.txt", "file_b.txt"])
        commit_oid = pygit2.Oid(hex=result['oid'])

        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_a.txt"), "A v2")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_b.txt"), "B v1")

    def test_save_include_paths_file_does_not_exist(self):
        # Core function's save_changes prints a warning for non-existent paths but doesn't fail.
        # The commit should proceed with any valid, changed paths.
        c1_oid = self._create_commit("Initial", files_to_add_update={"file_a.txt": "A v1"})
        self._create_file("file_a.txt", "A v2")

        result = save_changes(self.repo_path_str, "Commit with non-existent path", include_paths=["file_a.txt", "non_existent.txt"])
        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "file_a.txt"), "A v2")
        with self.assertRaises(FileNotFoundError): # Ensure non_existent.txt is not part of commit
            self._get_file_content_from_commit(commit_oid, "non_existent.txt")


    def test_save_include_paths_ignored_file(self):
        self._create_commit("Initial", files_to_add_update={"not_ignored.txt": "content"})

        # Create .gitignore
        self._create_file(".gitignore", "*.ignored\nignored_dir/")
        self._create_commit("Add gitignore", files_to_add_update={".gitignore": "*.ignored\nignored_dir/"})

        self._create_file("file.ignored", "ignored content")
        self._create_file("not_ignored.txt", "new content") # Make a change to a non-ignored file

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
        self._create_commit("Initial", files_to_add_update={"file_a.txt": "A v1", "file_b.txt": "B v1"})
        # file_a and file_b are in repo, but no changes made to them in workdir.
        # A new file_c is created but not included.
        self._create_file("file_c.txt", "C v1")

        with self.assertRaisesRegex(NoChangesToSaveError, "No specified files had changes to stage relative to HEAD"):
            save_changes(self.repo_path_str, "No changes in included files", include_paths=["file_a.txt", "file_b.txt"])

    def test_save_include_paths_directory(self):
        self._create_commit("Initial", files_to_add_update={"file_x.txt": "x"})

        self._create_file("dir_a/file_a1.txt", "A1 v1")
        self._create_file("dir_a/file_a2.txt", "A2 v1")
        self._create_file("dir_b/file_b1.txt", "B1 v1") # Not included

        result = save_changes(self.repo_path_str, "Commit directory dir_a", include_paths=["dir_a"])
        self.assertEqual(result['status'], 'success')
        commit_oid = pygit2.Oid(hex=result['oid'])

        self.assertEqual(self._get_file_content_from_commit(commit_oid, "dir_a/file_a1.txt"), "A1 v1")
        self.assertEqual(self._get_file_content_from_commit(commit_oid, "dir_a/file_a2.txt"), "A2 v1")
        with self.assertRaises(FileNotFoundError):
            self._get_file_content_from_commit(commit_oid, "dir_b/file_b1.txt")

        # Modify a file in dir_a and add a new one, then save dir_a again
        self._create_file("dir_a/file_a1.txt", "A1 v2")
        self._create_file("dir_a/subdir/file_as1.txt", "AS1 v1")

        result2 = save_changes(self.repo_path_str, "Commit directory dir_a again", include_paths=["dir_a"])
        self.assertEqual(result2['status'], 'success')
        commit2_oid = pygit2.Oid(hex=result2['oid'])
        self.assertEqual(self._get_file_content_from_commit(commit2_oid, "dir_a/file_a1.txt"), "A1 v2")
        self.assertEqual(self._get_file_content_from_commit(commit2_oid, "dir_a/subdir/file_as1.txt"), "AS1 v1")

    # 4. Merge Completion
    def _setup_merge_conflict_state(self, resolve_conflict: bool = False):
        # Main branch: C1 -> C2
        c1_main_oid = self._create_commit("C1 main", files_to_add_update={"file.txt": "Content from C1 main\nshared_line\n"})
        original_head_oid = c1_main_oid

        # Feature branch from C1
        feature_branch = self.repo.branches.create("feature/merge_test", self.repo.get(c1_main_oid))
        self.repo.checkout(feature_branch)
        c1_feature_oid = self._create_commit("C1 feature", files_to_add_update={"file.txt": "Content from C1 main\nfeature_line\n", "feature_only.txt": "feature content"})

        # Switch back to main
        main_branch_ref = self.repo.branches["main"].target
        self.repo.checkout(f"refs/heads/main") # Detach HEAD and point to main's tip
        self.repo.set_head(f"refs/heads/main") # Point HEAD ref to main branch

        c2_main_oid = self._create_commit("C2 main", files_to_add_update={"file.txt": "Content from C1 main\nmain_line\n"})

        # Start merge, which will conflict
        self.repo.merge(c1_feature_oid) # This creates MERGE_HEAD and potential conflicts in index

        if self.repo.index.conflicts:
            if resolve_conflict:
                # Simulate resolving conflict: take 'our' version for file.txt, add feature_only.txt
                self.repo.index.read() # re-read index
                # For file.txt, the conflict is there. To resolve, we need to pick a version or merge manually.
                # Let's say we want to keep "main_line" from C2_main for the conflicting part.
                # And then add the "feature_only.txt".
                # The content of file.txt in index after repo.merge() will have conflict markers.
                # We need to write the resolved content to workdir, then add it.
                self._create_file("file.txt", "Content from C1 main\nmain_line\nfeature_line_resolved\n")
                self.repo.index.add("file.txt")

                # feature_only.txt might be staged if no conflict, or need explicit add if part of conflict resolution.
                # If feature_only.txt was part of the merge and didn't conflict, it might already be staged.
                # If it was conflicting (e.g. different versions), it needs resolving.
                # Let's assume it's a new file from feature branch.
                # The merge operation should have staged additions if non-conflicting.
                # We need to check if it's already there from the merge.
                try:
                    _ = self.repo.index['feature_only.txt']
                except KeyError: # Not in index, means it wasn't auto-added or was part of conflict
                     self._create_file("feature_only.txt", "feature content") # Ensure it's in workdir
                     self.repo.index.add("feature_only.txt")

                self.repo.index.write() # Write resolved index
                # Verify no conflicts in index after resolution
                self.assertFalse(self.repo.index.conflicts, "Conflicts should be resolved in index for this test path.")
            # else: leave conflicts in index
        else: # Should not happen for this setup, merge should conflict
            if not resolve_conflict: # if we expect a conflict but don't get one
                raise AssertionError("Test setup error: Expected merge conflict but none occurred.")

        return c2_main_oid, c1_feature_oid # original HEAD (main's C2), and MERGE_HEAD target (feature's C1)


    def test_save_merge_completion_no_conflicts(self):
        head_oid_before_merge, merge_head_target_oid = self._setup_merge_conflict_state(resolve_conflict=True)

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
        head_oid_before_merge, _ = self._setup_merge_conflict_state(resolve_conflict=False)

        self.assertIsNotNone(self.repo.references.get("MERGE_HEAD"), "MERGE_HEAD should exist.")
        self.assertTrue(self.repo.index.conflicts, "Index should have conflicts for this test.")

        with self.assertRaises(MergeConflictError) as cm:
            save_changes(self.repo_path_str, "Attempt to finalize merge with conflicts")

        self.assertIsNotNone(cm.exception.conflicting_files)
        self.assertIn("file.txt", cm.exception.conflicting_files) # From the setup

        self.assertIsNotNone(self.repo.references.get("MERGE_HEAD"), "MERGE_HEAD should still exist after failed merge attempt.")
        self.assertEqual(self.repo.head.target, head_oid_before_merge, "HEAD should not have moved.")

    def test_save_merge_completion_with_include_paths_error(self):
        self._setup_merge_conflict_state(resolve_conflict=True) # State is MERGE_HEAD exists, no index conflict

        with self.assertRaisesRegex(GitWriteError, "Selective staging with --include is not allowed during an active merge operation."):
            save_changes(self.repo_path_str, "Attempt merge with include", include_paths=["file.txt"])

    # 5. Revert Completion
    def _setup_revert_state(self, commit_to_revert_oid: pygit2.Oid, create_conflict: bool = False):
        """
        Helper to simulate a state where a revert has been initiated (REVERT_HEAD exists).
        It does NOT perform the actual revert operations on workdir/index,
        just creates REVERT_HEAD. The calling test should set up workdir/index state.
        """
        self.repo.create_reference("REVERT_HEAD", commit_to_revert_oid)

        if create_conflict:
            # Create a dummy conflict in the index for testing purposes
            # This requires ancestor, ours, theirs entries for a path.
            # For simplicity, we'll create minimal conflicting entries.
            # This is a bit artificial but helps test the conflict detection path.
            conflict_path = "conflicting_revert_file.txt"
            self._create_file(conflict_path + "_ancestor", "ancestor")
            self._create_file(conflict_path + "_our", "our_version")
            self._create_file(conflict_path + "_their", "their_version")

            ancestor_blob_oid = self.repo.create_blob(b"revert_ancestor_content")
            our_blob_oid = self.repo.create_blob(b"revert_our_content")
            their_blob_oid = self.repo.create_blob(b"revert_their_content")

            self.repo.index.read()
            self.repo.index.add_conflict(
                ancestor_path=conflict_path, ancestor_oid=ancestor_blob_oid, ancestor_mode=0o100644,
                our_path=conflict_path, our_oid=our_blob_oid, our_mode=0o100644,
                their_path=conflict_path, their_oid=their_blob_oid, their_mode=0o100644
            )
            self.repo.index.write()
            self.assertTrue(self.repo.index.conflicts, "Index should have conflicts for revert test setup.")


    def test_save_revert_completion_no_conflicts(self):
        c1_oid = self._create_commit("C1", files_to_add_update={"file.txt": "Content C1"})
        c2_oid = self._create_commit("C2 changes file", files_to_add_update={"file.txt": "Content C2"})

        # Simulate that C2 is being reverted.
        # Workdir/index should reflect the state *after* applying C2's inverse to C2 (i.e., state of C1).
        self._create_file("file.txt", "Content C1")
        # Stage this reverted state
        self.repo.index.read()
        self.repo.index.add("file.txt")
        self.repo.index.write()

        self._setup_revert_state(c2_oid, create_conflict=False)
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
        c1_oid = self._create_commit("C1", files_to_add_update={"file.txt": "Content C1"})
        c2_oid = self._create_commit("C2", files_to_add_update={"file.txt": "Content C2"})

        self._setup_revert_state(c2_oid, create_conflict=True)
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
        c1_oid = self._create_commit("C1", files_to_add_update={"file.txt": "Content C1"})
        c2_oid = self._create_commit("C2", files_to_add_update={"file.txt": "Content C2"})
        self._setup_revert_state(c2_oid, create_conflict=False)

        with self.assertRaisesRegex(GitWriteError, "Selective staging with --include is not allowed during an active revert operation."):
            save_changes(self.repo_path_str, "Attempt revert with include", include_paths=["file.txt"])

    # 6. Author/Committer Information
    def test_save_uses_repo_default_signature(self):
        # Ensure repo has a default signature set in its config
        self.repo.config["user.name"] = "Config User"
        self.repo.config["user.email"] = "config@example.com"

        self._create_file("file.txt", "content for signature test")
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

        self._create_file("file.txt", "content for fallback signature test")

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
        self._create_file("file1.txt", "content1")
        self._create_file("file2.txt", "content2")

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
        self._create_file("somefile.txt", "content")
        with self.assertRaisesRegex(NoChangesToSaveError, "No specified files could be staged for the initial commit"):
            save_changes(self.repo_path_str, "Initial commit with non-existent include", include_paths=["doesnotexist.txt"])

    # 2. Normal Commits
    def test_save_normal_commit_stage_all(self):
        c1_oid = self._create_commit("Initial", files_to_add_update={"file_a.txt": "Content A v1"})

        self._create_file("file_a.txt", "Content A v2") # Modify
        self._create_file("file_b.txt", "Content B v1") # Add

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
        self._create_commit("Initial", files_to_add_update={"file_a.txt": "Content A v1"})
        # No changes made after initial commit

        with self.assertRaisesRegex(NoChangesToSaveError, "No changes to save \(working directory and index are clean or match HEAD\)\."):
            save_changes(self.repo_path_str, "Attempt to save no changes")

    def test_save_with_staged_changes_working_dir_clean(self):
        c1_oid = self._create_commit("Initial", files_to_add_update={"file_a.txt": "Original Content"})

        # Stage a change but don't modify working directory further
        self.repo.index.read()
        self._create_file("file_a.txt", "Staged Content")
        self.repo.index.add("file_a.txt")
        self.repo.index.write()

        # For this test, we want to ensure the working directory is "clean" relative to the STAGED content.
        # So, the file_a.txt in workdir IS "Staged Content".
        # The diff between index and HEAD should exist.
        # The diff between workdir and index should NOT exist for file_a.txt.

        # Create another file in workdir but DO NOT STAGE IT
        self._create_file("file_b.txt", "Unstaged Content")

        result = save_changes(self.repo_path_str, "Commit staged changes for file_a")
        # This should commit file_a.txt with "Staged Content" because save_changes (with include_paths=None)
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
        c1_oid = self._create_commit("C1", files_to_add_update={"original.txt": "v1"})

        # Create a new file, add it to index, then REMOVE it from workdir
        self._create_file("only_in_index.txt", "This file is staged then removed from workdir")
        self.repo.index.read()
        self.repo.index.add("only_in_index.txt")
        self.repo.index.write()

        os.remove(self.repo_path_obj / "only_in_index.txt") # Remove from workdir

        # Modify an existing tracked file, stage it, then revert workdir change
        self._create_file("original.txt", "v2_staged") # Modify and stage
        self.repo.index.add("original.txt")
        self.repo.index.write()
        self._create_file("original.txt", "v1") # Revert workdir to original C1 content

        # At this point:
        # - only_in_index.txt is in index, not in workdir (deleted)
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
