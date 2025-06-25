import unittest
import unittest.mock as mock
import pygit2
import shutil
import tempfile
from pathlib import Path
import os
import pytest
from unittest.mock import MagicMock
import pprint # Added for debugging

from gitwrite_core.versioning import revert_commit, save_changes, get_word_level_diff
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, MergeConflictError, GitWriteError, NoChangesToSaveError, RevertConflictError

from .conftest import TEST_USER_NAME, TEST_USER_EMAIL, create_test_signature, create_file

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
        create_file(repo, filepath, content)

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
        self._make_commit(self.repo, "Initial content C1", {"file_a.txt": "Content A from C1"})
        file_a_path = self.repo_path_obj / "file_a.txt"
        c2_oid = self._make_commit(self.repo, "Second change C2", {"file_a.txt": "Content A modified by C2", "file_b.txt": "Content B from C2"})
        result = revert_commit(self.repo_path_str, str(c2_oid))
        self.assertEqual(result['status'], 'success')
        revert_commit_obj = self.repo.get(result['new_commit_oid'])
        self.assertTrue(revert_commit_obj.message.startswith(f"Revert \"Second change C2\""))
        self.assertEqual(file_a_path.read_text(encoding="utf-8"), "Content A from C1")
        self.assertFalse((self.repo_path_obj / "file_b.txt").exists())
        self.assertEqual(self.repo.head.target, revert_commit_obj.id)
        self.assertEqual(len(self.repo.status()), 0)

    def test_revert_commit_not_found(self):
        self._make_commit(self.repo, "Initial commit", {"dummy.txt": "content"})
        with self.assertRaisesRegex(CommitNotFoundError, "not found"):
            revert_commit(self.repo_path_str, "abcdef1234567890abcdef1234567890abcdef12")

    def test_revert_on_non_repository_path(self):
        non_repo_dir = tempfile.mkdtemp()
        try:
            with self.assertRaisesRegex(RepositoryNotFoundError, "No repository found"):
                revert_commit(non_repo_dir, "HEAD")
        finally:
            shutil.rmtree(non_repo_dir)

    def test_revert_results_in_conflict(self):
        self._make_commit(self.repo, "C1", {"file_c.txt": "line1\nline2\nline3"})
        c2_oid = self._make_commit(self.repo, "C2", {"file_c.txt": "line1\nMODIFIED_BY_COMMIT_2\nline3"})
        c3_oid = self._make_commit(self.repo, "C3", {"file_c.txt": "line1\nMODIFIED_BY_COMMIT_3\nline3"})
        with self.assertRaisesRegex(MergeConflictError, "Revert resulted in conflicts"):
            revert_commit(self.repo_path_str, str(c2_oid))
        self.assertEqual(self.repo.head.target, c3_oid)
        self.assertEqual(len(self.repo.status()), 0)

class TestSaveChangesCore(GitWriteCoreTestCaseBase):
    def _get_file_content_from_commit(self, commit_oid: pygit2.Oid, filepath: str) -> str:
        commit = self.repo.get(commit_oid)
        tree_entry = commit.tree[filepath]
        blob = self.repo.get(tree_entry.id)
        return blob.data.decode('utf-8')

    def test_save_initial_commit_in_empty_repository(self):
        self._create_file(self.repo, "initial_file.txt", "Initial content.")
        result = save_changes(self.repo_path_str, "Initial commit")
        self.assertEqual(result['status'], 'success')
        commit = self.repo.get(result['oid'])
        self.assertEqual(len(commit.parents), 0)
        self.assertEqual(self._get_file_content_from_commit(commit.id, "initial_file.txt"), "Initial content.")

class TestCherryPickCommitCore(GitWriteCoreTestCaseBase):
     def setUp(self):
        super().setUp()
        if self.repo.head_is_unborn:
            self._make_commit(self.repo, "Initial commit for setup", {"initial.txt": "initial"})
            if self.repo.head.shorthand != "main" and self.repo.branches.get("master"):
                master_branch = self.repo.branches.lookup("master")
                master_branch.rename("main", True)
                self.repo.set_head("refs/heads/main")
            elif self.repo.head.shorthand != "main":
                 main_b = self.repo.branches.local.create("main", self.repo.head.peel(pygit2.Commit))
                 self.repo.set_head(main_b.name)

class TestGetWordLevelDiff(unittest.TestCase):
    def test_empty_patch_text(self):
        self.assertEqual(get_word_level_diff(""), [])

    def test_no_changes_patch(self):
        patch = """diff --git a/file.txt b/file.txt
index e69de29..e69de29 100644
"""
        self.assertEqual(get_word_level_diff(patch), [])

    def test_simple_addition_only_file(self):
        patch = """diff --git a/new_file.txt b/new_file.txt
new file mode 100644
index 0000000..9e2f97e
--- /dev/null
+++ b/new_file.txt
@@ -0,0 +1,2 @@
+Hello world
+This is a new line.
"""
        expected = [
            {
                "file_path": "new_file.txt",
                "change_type": "added",
                "hunks": [
                    {
                        "lines": [
                            {"type": "addition", "content": "Hello world", "words": [{"type": "added", "content": "Hello world"}]},
                            {"type": "addition", "content": "This is a new line.", "words": [{"type": "added", "content": "This is a new line."}]},
                        ]
                    }
                ],
            }
        ]
        actual_structure = get_word_level_diff(patch)

        # --- DEBUGGING BLOCK: START ---
        # import pprint
        # print("\n\n--- DEBUGGING TRACE for test_simple_addition_only_file ---")
        # print("\n[1] INPUT PATCH TEXT:")
        # print("---------------------")
        # print(patch)
        # print("\n[2] EXPECTED OUTPUT STRUCTURE:")
        # print("----------------------------")
        # pprint.pprint(expected)
        # print("\n[3] ACTUAL OUTPUT STRUCTURE:")
        # print("--------------------------")
        # pprint.pprint(actual_structure)
        # print("\n--- END TRACE ---")
        # --- DEBUGGING BLOCK: END ---

        self.assertEqual(actual_structure, expected)

    def test_simple_deletion_only_file(self):
        patch = """diff --git a/old_file.txt b/old_file.txt
deleted file mode 100644
index 9e2f97e..0000000
--- a/old_file.txt
+++ /dev/null
@@ -1,2 +0,0 @@
-Goodbye world
-This was an old line.
"""
        expected = [
            {
                "file_path": "old_file.txt",
                "change_type": "deleted",
                "hunks": [
                    {
                        "lines": [
                            {"type": "deletion", "content": "Goodbye world", "words": [{"type": "removed", "content": "Goodbye world"}]},
                            {"type": "deletion", "content": "This was an old line.", "words": [{"type": "removed", "content": "This was an old line."}]},
                        ]
                    }
                ],
            }
        ]
        actual_structure = get_word_level_diff(patch)
        # --- DEBUGGING BLOCK: START ---
        # import pprint
        # print("\n\n--- DEBUGGING TRACE for test_simple_deletion_only_file ---")
        # print("\n[1] INPUT PATCH TEXT:")
        # print("---------------------")
        # print(patch)
        # print("\n[2] EXPECTED OUTPUT STRUCTURE:")
        # print("----------------------------")
        # pprint.pprint(expected)
        # print("\n[3] ACTUAL OUTPUT STRUCTURE:")
        # print("--------------------------")
        # pprint.pprint(actual_structure)
        # print("\n--- END TRACE ---")
        # --- DEBUGGING BLOCK: END ---
        self.assertEqual(actual_structure, expected)

    def test_modification_with_word_diff(self):
        input_patch = (
            'diff --git a/file.txt b/file.txt\n'
            'index f9f7733..b2c9567 100644\n'
            '--- a/file.txt\n'
            '+++ b/file.txt\n'
            '@@ -1,3 +1,3 @@\n'
            ' This is an\n'
            '-old line of text.\n'
            '+new line of text, indeed.\n'
            ' It has three lines.\n'
        )
        expected_structure = [
            {
                'file_path': 'file.txt',
                'change_type': 'modified',
                'hunks': [
                    {
                        'lines': [
                            {'type': 'context', 'content': 'This is an'},
                            {
                                'type': 'deletion', 'content': 'old line of text.',
                                'words': [
                                    {'type': 'removed', 'content': 'old'},
                                    {'type': 'context', 'content': 'line of'},
                                    {'type': 'removed', 'content': 'text.'}
                                ]
                            },
                            {
                                'type': 'addition', 'content': 'new line of text, indeed.',
                                'words': [
                                    {'type': 'added', 'content': 'new'},
                                    {'type': 'context', 'content': 'line of'},
                                    {'type': 'added', 'content': 'text, indeed.'}
                                ]
                            },
                            {'type': 'context', 'content': 'It has three lines.'}
                        ]
                    }
                ]
            }
        ]

        actual_structure = get_word_level_diff(input_patch)

        # --- DEBUGGING BLOCK: START ---
        # import pprint
        # print("\n\n--- DEBUGGING TRACE for test_modification_with_word_diff ---")
        # print("\n[1] INPUT PATCH TEXT:")
        # print("---------------------")
        # print(input_patch)
        # print("\n[2] EXPECTED OUTPUT STRUCTURE:")
        # print("----------------------------")
        # pprint.pprint(expected_structure)
        # print("\n[3] ACTUAL OUTPUT STRUCTURE:")
        # print("--------------------------")
        # pprint.pprint(actual_structure)
        # print("\n--- END TRACE ---")
        # --- DEBUGGING BLOCK: END ---

        self.assertEqual(actual_structure, expected_structure)

    def test_multiple_hunks_and_files(self):
        input_patch = (
            'diff --git a/file1.txt b/file1.txt\n'
            'index 03b1a04..50d1547 100644\n'
            '--- a/file1.txt\n'
            '+++ b/file1.txt\n'
            '@@ -1,3 +1,3 @@\n'
            ' line one\n'
            '-line two\n'
            '+line 2\n'
            ' line three\n'
            'diff --git a/file2.txt b/file2.txt\n'
            'index 1234567..abcdef0 100644\n'
            '--- a/file2.txt\n'
            '+++ b/file2.txt\n'
            '@@ -5,2 +5,2 @@\n'
            ' context line\n'
            '-final word\n'
            '+final change\n'
        )
        expected_structure = [
            {
                'file_path': 'file1.txt',
                'change_type': 'modified',
                'hunks': [
                    {
                        'lines': [
                            {'type': 'context', 'content': 'line one'},
                            {'type': 'deletion', 'content': 'line two', 'words': [{'type': 'context', 'content': 'line'}, {'type': 'removed', 'content': 'two'}]},
                            {'type': 'addition', 'content': 'line 2', 'words': [{'type': 'context', 'content': 'line'}, {'type': 'added', 'content': '2'}]},
                            {'type': 'context', 'content': 'line three'}
                        ]
                    }
                ]
            },
            {
                'file_path': 'file2.txt',
                'change_type': 'modified',
                'hunks': [
                    {
                        'lines': [
                            {'type': 'context', 'content': 'context line'},
                            {
                                'type': 'deletion', 'content': 'final word',
                                'words': [
                                    {'type': 'removed', 'content': 'final word'}
                                ]
                            },
                            {
                                'type': 'addition', 'content': 'final change',
                                'words': [
                                    {'type': 'added', 'content': 'final change'}
                                ]
                            }
                        ]
                    }
                ]
            }
        ]
        actual_structure = get_word_level_diff(input_patch)
        self.assertEqual(actual_structure, expected_structure)

    def test_no_newline_at_end_of_file_message(self):
        patch = """diff --git a/file.txt b/file.txt
index 5e0752d..6a2394a 100644
--- a/file.txt
+++ b/file.txt
@@ -1 +1 @@
-old line
\\ No newline at end of file
+new line
\\ No newline at end of file
"""
        expected = [
            {
                "file_path": "file.txt",
                "change_type": "modified",
                # old_file_path and new_file_path should not be present for simple modified files
                "hunks": [
                    {
                        "lines": [
                            {"type": "deletion", "content": "old line", "words": [{"type": "removed", "content": "old line"}]},
                            {"type": "no_newline", "content": "\\ No newline at end of file"},
                            {"type": "addition", "content": "new line", "words": [{"type": "added", "content": "new line"}]},
                            {"type": "no_newline", "content": "\\ No newline at end of file"},
                        ]
                    }
                ],
            }
        ]
        result = get_word_level_diff(patch)
        self.assertEqual(result, expected)

    def test_renamed_file_diff(self):
        patch = """diff --git a/old_name.txt b/new_name.txt
similarity index 90%
rename from old_name.txt
rename to new_name.txt
index 03b1a04..50d1547 100644
--- a/old_name.txt
+++ b/new_name.txt
@@ -1 +1 @@
-Original content
+New content
"""
        expected = [
            {
                "old_file_path": "old_name.txt",
                "new_file_path": "new_name.txt",
                "file_path": "new_name.txt",
                "change_type": "renamed",
                "hunks": [
                    {
                        "lines": [
                            {
                                "type": "deletion",
                                "content": "Original content",
                                "words": [
                                    {"type": "removed", "content": "Original content"}]},
                            {
                                "type": "addition",
                                "content": "New content",
                                "words": [{"type": "added", "content": "New content"}]}
                        ]
                    }
                ]
            }
        ]
        actual_structure = get_word_level_diff(patch)
        # --- DEBUGGING BLOCK: START ---
        # import pprint
        # print("\n\n--- DEBUGGING TRACE for test_renamed_file_diff ---")
        # print("\n[1] INPUT PATCH TEXT:")
        # print("---------------------")
        # print(patch)
        # print("\n[2] EXPECTED OUTPUT STRUCTURE:")
        # print("----------------------------")
        # pprint.pprint(expected)
        # print("\n[3] ACTUAL OUTPUT STRUCTURE:")
        # print("--------------------------")
        # pprint.pprint(actual_structure)
        # print("\n--- END TRACE ---")
        # --- DEBUGGING BLOCK: END ---
        self.assertEqual(actual_structure, expected)


if __name__ == '__main__':
    unittest.main()
