import unittest
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
