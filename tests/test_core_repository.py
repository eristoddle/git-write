import unittest
import pygit2
import shutil
import tempfile
from pathlib import Path
import os
from datetime import datetime, timezone
from typing import Tuple, Optional
from unittest import mock

from gitwrite_core.repository import sync_repository, get_conflicting_files # Assuming get_conflicting_files is in repository.py
from gitwrite_core.exceptions import (
    RepositoryNotFoundError, RepositoryEmptyError, DetachedHeadError,
    RemoteNotFoundError, BranchNotFoundError, FetchError,
    MergeConflictError, PushError, GitWriteError
)

# Default signature for tests
TEST_USER_NAME = "Test Sync User"
TEST_USER_EMAIL = "test_sync@example.com"

class TestSyncRepositoryCore(unittest.TestCase):
    def setUp(self):
        # Create a temporary directory to hold both local and remote repos
        self.base_temp_dir = Path(tempfile.mkdtemp(prefix="gitwrite_sync_base_"))

        # Setup local repository
        self.local_repo_path = self.base_temp_dir / "local_repo"
        self.local_repo_path.mkdir()
        self.local_repo = pygit2.init_repository(str(self.local_repo_path), bare=False)
        self._configure_repo_user(self.local_repo)
        self.local_signature = pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)


        # Setup bare remote repository
        self.remote_repo_path = self.base_temp_dir / "remote_repo.git"
        self.remote_repo = pygit2.init_repository(str(self.remote_repo_path), bare=True)
        self._configure_repo_user(self.remote_repo) # Not strictly necessary for bare, but good for consistency if ever non-bare

    def tearDown(self):
        # Force remove read-only files if any, then the directory tree
        for root, dirs, files in os.walk(self.base_temp_dir, topdown=False):
            for name in files:
                filepath = os.path.join(root, name)
                try:
                    os.chmod(filepath, 0o777)
                    os.remove(filepath)
                except OSError: pass # Ignore if not possible
            for name in dirs:
                dirpath = os.path.join(root, name)
                try:
                    os.rmdir(dirpath)
                except OSError: pass # Ignore if not possible
        try:
            shutil.rmtree(self.base_temp_dir)
        except OSError:
            pass # Ignore if cleanup fails, OS might hold locks briefly

    def _configure_repo_user(self, repo: pygit2.Repository):
        config = repo.config
        config["user.name"] = TEST_USER_NAME
        config["user.email"] = TEST_USER_EMAIL
        return config

    def _make_commit(self, repo: pygit2.Repository, filename: str, content: str, message: str, branch_name: Optional[str] = None) -> pygit2.Oid:
        if branch_name:
            if branch_name not in repo.branches.local: # Create branch if it doesn't exist, from current HEAD
                 if repo.head_is_unborn:
                     # Cannot create branch from unborn HEAD without a commit.
                     # For initial commit on a branch, commit to HEAD then branch.
                     pass # Will commit to current HEAD or fail if unborn and no parents
                 else:
                    repo.branches.local.create(branch_name, repo.head.peel(pygit2.Commit))

            # Checkout the branch by updating HEAD reference and workdir
            # Ensure the reference name is correct (e.g. refs/heads/branch_name)
            ref_name = f"refs/heads/{branch_name}"
            if repo.head.name != ref_name :
                 repo.set_head(ref_name) # Point HEAD to the branch
                 # repo.checkout_head(strategy=pygit2.GIT_CHECKOUT_FORCE) # Update working directory - careful if dirty

        # Create file in workdir
        file_path = Path(repo.workdir) / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        # Stage file
        repo.index.add(filename)
        repo.index.write()

        # Commit
        parents = []
        if not repo.head_is_unborn:
            parents = [repo.head.target]

        tree = repo.index.write_tree()
        commit_oid = repo.create_commit(
            "HEAD", # This updates the current branch (or HEAD if detached)
            self.local_signature,
            self.local_signature,
            message,
            tree,
            parents
        )
        return commit_oid

    def _add_remote(self, local_repo: pygit2.Repository, remote_name: str, remote_url: str):
        return local_repo.remotes.create(remote_name, remote_url)

    def _push_to_remote(self, local_repo: pygit2.Repository, remote_name: str, branch_name: str):
        remote = local_repo.remotes[remote_name]
        refspec = f"refs/heads/{branch_name}:refs/heads/{branch_name}"
        remote.push([refspec])

    # --- Start of actual tests ---

    def test_sync_non_repository_path(self):
        non_repo_dir = self.base_temp_dir / "non_repo"
        non_repo_dir.mkdir()
        with self.assertRaisesRegex(RepositoryNotFoundError, "Repository not found at or above"):
            sync_repository(str(non_repo_dir))

    def test_sync_bare_repository(self):
        # self.remote_repo is a bare repo
        with self.assertRaisesRegex(GitWriteError, "Cannot sync a bare repository"):
            sync_repository(str(self.remote_repo_path))

    def test_sync_empty_unborn_repository(self):
        # self.local_repo is initialized but has no commits yet (empty/unborn)
        self.assertTrue(self.local_repo.is_empty)
        self.assertTrue(self.local_repo.head_is_unborn)
        with self.assertRaisesRegex(RepositoryEmptyError, "Repository is empty or HEAD is unborn. Cannot sync."):
            sync_repository(str(self.local_repo_path))

    def test_sync_detached_head_no_branch_specified(self):
        self._make_commit(self.local_repo, "initial.txt", "content", "Initial commit")
        # Detach HEAD by setting it directly to the commit OID
        self.local_repo.set_head(self.local_repo.head.target)
        self.assertTrue(self.local_repo.head_is_detached)

        with self.assertRaisesRegex(DetachedHeadError, "HEAD is detached. Please specify a branch to sync or checkout a branch."):
            sync_repository(str(self.local_repo_path))

    def test_sync_non_existent_remote_name(self):
        self._make_commit(self.local_repo, "initial.txt", "content", "Initial commit", branch_name="main")
        with self.assertRaisesRegex(RemoteNotFoundError, "Remote 'nonexistentremote' not found."):
            sync_repository(str(self.local_repo_path), remote_name="nonexistentremote", branch_name_opt="main")

    def test_sync_non_existent_local_branch(self):
        self._make_commit(self.local_repo, "initial.txt", "content", "Initial commit", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        with self.assertRaisesRegex(BranchNotFoundError, "Local branch 'ghostbranch' not found."):
            sync_repository(str(self.local_repo_path), branch_name_opt="ghostbranch")

    # 2. Fetch Operation
    def test_sync_successful_fetch(self):
        # Setup: local repo with 'main', remote repo (bare)
        # Make a commit in local 'main'
        self._make_commit(self.local_repo, "local_file.txt", "local content", "Commit on local/main", branch_name="main")
        # Add remote 'origin' to local_repo
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        # Push this initial main branch to remote so remote has something
        self._push_to_remote(self.local_repo, "origin", "main")

        # Make another commit on a different "clone" (simulated by direct commit to remote_repo for simplicity)
        # To do this properly for a bare repo, we'd need another non-bare clone, make commit, and push.
        # For testing fetch, it's enough that the remote has a new ref or commit not known to local.
        # Let's simulate remote having a new branch 'feature_on_remote'

        # Create a temporary clone to push a new branch to the bare remote
        temp_clone_path = self.base_temp_dir / "temp_clone_for_fetch_test"
        temp_clone_repo = pygit2.clone_repository(str(self.remote_repo_path), str(temp_clone_path))
        self._configure_repo_user(temp_clone_repo)
        sig_for_clone = pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)

        # Create and commit to 'feature_on_remote' in the clone
        temp_clone_repo.branches.local.create("feature_on_remote", temp_clone_repo.head.peel(pygit2.Commit))
        temp_clone_repo.checkout("refs/heads/feature_on_remote")
        file_path_clone = temp_clone_path / "remote_feature_file.txt"
        file_path_clone.write_text("content on remote feature")
        temp_clone_repo.index.add("remote_feature_file.txt")
        temp_clone_repo.index.write()
        tree_clone = temp_clone_repo.index.write_tree()
        temp_clone_repo.create_commit("HEAD", sig_for_clone, sig_for_clone, "Commit on remote feature", tree_clone, [temp_clone_repo.head.target])

        # Push this new branch from clone to the bare remote
        temp_clone_repo.remotes["origin"].push(["refs/heads/feature_on_remote:refs/heads/feature_on_remote"])
        shutil.rmtree(temp_clone_path) # Clean up temp clone

        # Now, run sync_repository on local_repo for 'main' branch.
        # Fetch should bring info about 'feature_on_remote'.
        # We are testing the fetch part, local update for 'main' should be 'up_to_date' or 'local_ahead'.
        result = sync_repository(str(self.local_repo_path), remote_name="origin", branch_name_opt="main", push=False, allow_no_push=True)

        self.assertEqual(result["fetch_status"]["message"], "Fetch complete.")
        # total_objects might vary based on pack operations, but received_objects should be >0 if new things were fetched.
        # For this specific setup, it fetched the new branch 'feature_on_remote'.
        self.assertTrue(result["fetch_status"]["received_objects"] > 0 or result["fetch_status"]["total_objects"] > 0)

        # Verify the remote tracking branch for 'feature_on_remote' now exists locally
        self.assertIn(f"refs/remotes/origin/feature_on_remote", self.local_repo.listall_references())


    @mock.patch('pygit2.remote.Remote.fetch')
    def test_sync_fetch_failure(self, mock_fetch):
        # Setup: local repo with 'main', remote 'origin'
        self._make_commit(self.local_repo, "initial.txt", "content", "Initial commit", branch_name="main")
        self._add_remote(self.local_repo, "origin", "file://" + str(self.remote_repo_path)) # Using file:// URL

        # Configure mock_fetch to raise GitError
        mock_fetch.side_effect = pygit2.GitError("Simulated fetch failure (e.g., network error)")

        with self.assertRaisesRegex(FetchError, "Failed to fetch from remote 'origin': Simulated fetch failure"):
            sync_repository(str(self.local_repo_path), remote_name="origin", branch_name_opt="main")

        # Alternatively, if we want to check the returned dict status:
        # result = sync_repository(str(self.local_repo_path), remote_name="origin", branch_name_opt="main")
        # self.assertIn("failed", result["fetch_status"]["message"].lower())
        # self.assertEqual(result["status"], "error_in_sub_operation") # Or a more specific error status

    # 3. Local Update Scenarios (with push=False, allow_no_push=True)
    def test_sync_local_up_to_date(self):
        self._make_commit(self.local_repo, "common.txt", "content", "Initial commit", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main") # Ensure remote is same as local

        result = sync_repository(str(self.local_repo_path), branch_name_opt="main", push=False, allow_no_push=True)

        self.assertEqual(result["local_update_status"]["type"], "up_to_date")
        self.assertIn("Local branch is already up-to-date", result["local_update_status"]["message"])
        self.assertEqual(result["status"], "success_up_to_date_nothing_to_push")

    def test_sync_local_ahead(self):
        # Initial remote state
        self._make_commit(self.remote_repo, "remote_file.txt", "remote content", "Initial remote commit", branch_name="main")
        # No, this won't work directly on bare repo. Need to push to it.
        # Setup: commit to local, push, then another local commit.

        c1_local_oid = self._make_commit(self.local_repo, "file1.txt", "content1", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main") # Remote is now at C1

        c2_local_oid = self._make_commit(self.local_repo, "file2.txt", "content2", "C2 local only") # Local is now at C2

        result = sync_repository(str(self.local_repo_path), branch_name_opt="main", push=False, allow_no_push=True)

        self.assertEqual(result["local_update_status"]["type"], "local_ahead")
        self.assertIn("Local branch is ahead of remote", result["local_update_status"]["message"])
        # Even if push=False, if local is ahead, the overall status might just be 'success'
        # because the local update part did what it could (nothing), and push was skipped.
        self.assertEqual(result["status"], "success") # or "success_local_ahead_no_push" if we want more detail

    def test_sync_fast_forward(self):
        # Setup: Remote is ahead of local, FF is possible
        # 1. Initial commit on local 'main', push to remote 'main'
        c1_oid = self._make_commit(self.local_repo, "common_file.txt", "Initial", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main")

        # 2. Simulate remote getting ahead:
        #    Clone remote, add commit, push back to remote.
        temp_clone_path = self.base_temp_dir / "temp_clone_for_ff"
        temp_clone_repo = pygit2.clone_repository(str(self.remote_repo_path), str(temp_clone_path))
        self._configure_repo_user(temp_clone_repo)
        sig_clone = pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)

        # Commit on clone's 'main'
        file_path_clone = temp_clone_path / "remote_only_file.txt"
        file_path_clone.write_text("new remote content")
        temp_clone_repo.index.add("remote_only_file.txt")
        temp_clone_repo.index.write()
        tree_clone = temp_clone_repo.index.write_tree()
        c2_remote_oid = temp_clone_repo.create_commit("HEAD", sig_clone, sig_clone, "C2 on remote", tree_clone, [temp_clone_repo.head.target])
        temp_clone_repo.remotes["origin"].push(["refs/heads/main:refs/heads/main"])
        shutil.rmtree(temp_clone_path)

        # 3. Now local_repo's main is behind. Sync it.
        result = sync_repository(str(self.local_repo_path), branch_name_opt="main", push=False, allow_no_push=True)

        self.assertEqual(result["local_update_status"]["type"], "fast_forwarded")
        self.assertIn(f"Fast-forwarded 'main' to remote commit {str(c2_remote_oid)[:7]}", result["local_update_status"]["message"])
        self.assertEqual(result["local_update_status"]["commit_oid"], str(c2_remote_oid))
        self.assertEqual(self.local_repo.head.target, c2_remote_oid) # Verify local HEAD updated
        self.assertTrue((self.local_repo_path / "remote_only_file.txt").exists()) # Verify workdir updated
        self.assertEqual(result["status"], "success")

    def test_sync_merge_clean(self):
        # Setup: Local and remote have diverged, merge is clean
        # 1. Base commit C1, pushed to remote
        c1_oid = self._make_commit(self.local_repo, "base.txt", "base", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main")

        # 2. Local makes C2
        c2_local_oid = self._make_commit(self.local_repo, "local_change.txt", "local data", "C2 Local")

        # 3. Remote makes C2 (simulated via clone)
        temp_clone_path = self.base_temp_dir / "temp_clone_for_merge"
        temp_clone_repo = pygit2.clone_repository(str(self.remote_repo_path), str(temp_clone_path))
        self._configure_repo_user(temp_clone_repo)
        sig_clone = pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)
        # Ensure clone is on main and at C1
        temp_clone_repo.checkout("refs/heads/main")
        temp_clone_repo.reset(c1_oid, pygit2.GIT_RESET_HARD) # Start from C1

        # Make C2 on remote
        file_path_clone = temp_clone_path / "remote_change.txt"
        file_path_clone.write_text("remote data")
        temp_clone_repo.index.add("remote_change.txt")
        temp_clone_repo.index.write()
        tree_clone = temp_clone_repo.index.write_tree()
        c2_remote_oid = temp_clone_repo.create_commit("HEAD", sig_clone, sig_clone, "C2 Remote", tree_clone, [c1_oid])
        temp_clone_repo.remotes["origin"].push(["refs/heads/main:refs/heads/main"])
        shutil.rmtree(temp_clone_path)

        # 4. Sync local repo
        result = sync_repository(str(self.local_repo_path), branch_name_opt="main", push=False, allow_no_push=True)

        self.assertEqual(result["local_update_status"]["type"], "merged_ok")
        self.assertIn("Successfully merged remote changes into 'main'", result["local_update_status"]["message"])
        self.assertIsNotNone(result["local_update_status"]["commit_oid"])

        merge_commit_oid = pygit2.Oid(hex=result["local_update_status"]["commit_oid"])
        self.assertEqual(self.local_repo.head.target, merge_commit_oid)
        merge_commit = self.local_repo.get(merge_commit_oid)
        self.assertEqual(len(merge_commit.parents), 2)
        parent_oids = {p.id for p in merge_commit.parents}
        self.assertEqual(parent_oids, {c2_local_oid, c2_remote_oid})

        self.assertTrue((self.local_repo_path / "local_change.txt").exists())
        self.assertTrue((self.local_repo_path / "remote_change.txt").exists())
        self.assertEqual(self.local_repo.state, pygit2.GIT_REPOSITORY_STATE_NONE)
        self.assertEqual(result["status"], "success")

    def test_sync_merge_conflicts(self):
        # 1. Base C1, pushed
        c1_oid = self._make_commit(self.local_repo, "conflict_file.txt", "line1\ncommon_line\nline3", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main")

        # 2. Local C2: modifies common_line
        c2_local_oid = self._make_commit(self.local_repo, "conflict_file.txt", "line1\nlocal_change_on_common\nline3", "C2 Local")

        # 3. Remote C2: modifies common_line differently
        temp_clone_path = self.base_temp_dir / "temp_clone_for_conflict"
        temp_clone_repo = pygit2.clone_repository(str(self.remote_repo_path), str(temp_clone_path))
        self._configure_repo_user(temp_clone_repo)
        sig_clone = pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)
        temp_clone_repo.checkout("refs/heads/main")
        temp_clone_repo.reset(c1_oid, pygit2.GIT_RESET_HARD) # Back to C1

        file_path_clone = temp_clone_path / "conflict_file.txt"
        file_path_clone.write_text("line1\nremote_change_on_common\nline3")
        temp_clone_repo.index.add("conflict_file.txt")
        temp_clone_repo.index.write()
        tree_clone = temp_clone_repo.index.write_tree()
        c2_remote_oid = temp_clone_repo.create_commit("HEAD", sig_clone, sig_clone, "C2 Remote conflict", tree_clone, [c1_oid])
        temp_clone_repo.remotes["origin"].push(["refs/heads/main:refs/heads/main"])
        shutil.rmtree(temp_clone_path)

        # 4. Sync local repo - expect MergeConflictError
        with self.assertRaises(MergeConflictError) as cm:
            sync_repository(str(self.local_repo_path), branch_name_opt="main", push=False, allow_no_push=True)

        self.assertIn("Merge resulted in conflicts", str(cm.exception))
        self.assertIsNotNone(cm.exception.conflicting_files)
        self.assertIn("conflict_file.txt", cm.exception.conflicting_files)

        # Check repo state: index should have conflicts, MERGE_HEAD should be gone (due to state_cleanup in core)
        self.assertTrue(self.local_repo.index.conflicts)
        self.assertEqual(self.local_repo.state, pygit2.GIT_REPOSITORY_STATE_MERGE) # state_cleanup does not clear this IIRC, user must resolve
        # The `save_changes` function calls state_cleanup which removes MERGE_HEAD.
        # `sync_repository` also calls `state_cleanup` if conflicts are detected AFTER `repo.merge()`.
        # Let's verify MERGE_HEAD is gone.
        with self.assertRaises(KeyError): # Should be gone
            self.local_repo.lookup_reference("MERGE_HEAD")


    def test_sync_new_local_branch_no_remote_tracking(self):
        # 1. Initial commit on main, pushed
        self._make_commit(self.local_repo, "main_file.txt", "main content", "C1 on main", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main")

        # 2. Create new local branch 'feature_new' from main, make a commit
        self._make_commit(self.local_repo, "feature_file.txt", "feature data", "C1 on feature_new", branch_name="feature_new")

        # 3. Sync 'feature_new'. Remote tracking branch does not exist yet.
        result = sync_repository(str(self.local_repo_path), branch_name_opt="feature_new", push=False, allow_no_push=True)

        self.assertEqual(result["local_update_status"]["type"], "no_remote_branch")
        self.assertIn("Remote tracking branch 'refs/remotes/origin/feature_new' not found", result["local_update_status"]["message"])
        # Overall status should indicate success as fetch/local update part is fine, and push is deferred.
        self.assertEqual(result["status"], "success") # Or a more specific one like "success_new_branch_no_push"

    # 4. Push Operation
    def test_sync_push_successful_local_ahead(self):
        # 1. Local C1, remote is empty for this branch
        c1_local_oid = self._make_commit(self.local_repo, "file_to_push.txt", "content v1", "C1 Local", branch_name="dev")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        # No initial push, so 'dev' does not exist on remote.

        result = sync_repository(str(self.local_repo_path), branch_name_opt="dev", push=True, allow_no_push=False)

        self.assertEqual(result["status"], "success_pushed_new_branch") # Since it's a new branch on remote
        self.assertTrue(result["push_status"]["pushed"])
        self.assertEqual(result["push_status"]["message"], "Push successful.")

        # Verify remote has the commit
        remote_dev_ref = self.remote_repo.lookup_reference("refs/heads/dev")
        self.assertIsNotNone(remote_dev_ref)
        self.assertEqual(remote_dev_ref.target, c1_local_oid)

    def test_sync_nothing_to_push_already_up_to_date(self):
        self._make_commit(self.local_repo, "common.txt", "content", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main")

        result = sync_repository(str(self.local_repo_path), branch_name_opt="main", push=True)

        self.assertEqual(result["status"], "success_up_to_date_nothing_to_push")
        self.assertFalse(result["push_status"]["pushed"])
        self.assertIn("Nothing to push", result["push_status"]["message"])

    @mock.patch('pygit2.remote.Remote.push')
    def test_sync_push_failure_non_fast_forward(self, mock_push_method):
        # 1. Local C1, pushed to remote
        c1_local_oid = self._make_commit(self.local_repo, "file.txt", "v1", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main")

        # 2. Local C2
        c2_local_oid = self._make_commit(self.local_repo, "file.txt", "v2 local", "C2 Local")

        # 3. Simulate remote having a C2' (diverged)
        temp_clone = pygit2.clone_repository(str(self.remote_repo_path), self.base_temp_dir / "remote_clone_for_nff")
        self._configure_repo_user(temp_clone)
        sig_clone = pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)
        temp_clone.checkout("refs/heads/main")
        temp_clone.reset(c1_local_oid, pygit2.GIT_RESET_HARD) # Back to C1
        (temp_clone.workdir / "file.txt").write_text("v2 remote")
        temp_clone.index.add("file.txt")
        temp_clone.index.write()
        tree_clone = temp_clone.index.write_tree()
        temp_clone.create_commit("HEAD", sig_clone, sig_clone, "C2 Remote (for NFF)", tree_clone, [c1_local_oid])
        temp_clone.remotes["origin"].push(["refs/heads/main:refs/heads/main"])
        shutil.rmtree(temp_clone.workdir)

        # Configure mock_push to raise GitError for non-fast-forward
        # The error message should contain "non-fast-forward"
        mock_push_method.side_effect = pygit2.GitError("Push failed: non-fast-forward")

        with self.assertRaisesRegex(PushError, "non-fast-forward"):
            sync_repository(str(self.local_repo_path), branch_name_opt="main", push=True)
            # The function should raise PushError, but the dictionary would also be populated.
            # If we want to check the dictionary, we'd have to catch the error in the test.
            # For now, testing the raised exception is sufficient as per subtask.

    @mock.patch('pygit2.remote.Remote.push')
    def test_sync_push_failure_auth_error(self, mock_push_method):
        self._make_commit(self.local_repo, "file_for_auth_test.txt", "content", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        # Don't push C1 yet, so local is ahead.

        mock_push_method.side_effect = pygit2.GitError("Push failed: Authentication required")

        with self.assertRaisesRegex(PushError, "Authentication required"):
            sync_repository(str(self.local_repo_path), branch_name_opt="main", push=True)

    def test_sync_push_skipped_by_flag(self):
        # Local is ahead, but push=False
        c1_local_oid = self._make_commit(self.local_repo, "file1.txt", "content1", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        # Not pushing C1, so remote 'main' doesn't exist or is behind.

        result = sync_repository(str(self.local_repo_path), branch_name_opt="main", push=False, allow_no_push=True)

        self.assertFalse(result["push_status"]["pushed"])
        self.assertEqual(result["push_status"]["message"], "Push skipped as per 'allow_no_push'.")
        # Status depends on local_update_status. Here, local_update should be 'no_remote_branch' or 'local_ahead'
        # if remote was pre-seeded with an older main.
        # If remote_repo was empty, 'no_remote_branch' is expected for 'main'.
        self.assertIn(result["local_update_status"]["type"], ["no_remote_branch", "local_ahead"])
        self.assertEqual(result["status"], "success") # Overall success because push was intentionally skipped.

    # 5. End-to-End Scenarios
    def test_e2e_fetch_fast_forward_push(self):
        # 1. Initial C1 on local, pushed to remote
        c1_oid = self._make_commit(self.local_repo, "file.txt", "v1", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main")

        # 2. Remote gets C2 (via clone)
        temp_clone = pygit2.clone_repository(str(self.remote_repo_path), self.base_temp_dir / "clone_ff_e2e")
        self._configure_repo_user(temp_clone)
        sig_clone = pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)
        temp_clone.checkout("refs/heads/main") # Ensure on main
        (temp_clone.workdir / "file.txt").write_text("v2 remote")
        temp_clone.index.add("file.txt")
        temp_clone.index.write()
        tree_clone = temp_clone.index.write_tree()
        c2_remote_oid = temp_clone.create_commit("HEAD", sig_clone, sig_clone, "C2 Remote", tree_clone, [c1_oid])
        temp_clone.remotes["origin"].push(["refs/heads/main:refs/heads/main"])
        shutil.rmtree(temp_clone.workdir)

        # 3. Local sync (fetch, ff, push - though push will do nothing new)
        result = sync_repository(str(self.local_repo_path), branch_name_opt="main", push=True)

        self.assertEqual(result["status"], "success") # or success_nothing_to_push if ff means no new local changes to push
        self.assertEqual(result["fetch_status"]["message"], "Fetch complete.")
        self.assertTrue(result["fetch_status"]["received_objects"] > 0 or result["fetch_status"]["total_objects"] > 0)
        self.assertEqual(result["local_update_status"]["type"], "fast_forwarded")
        self.assertEqual(result["local_update_status"]["commit_oid"], str(c2_remote_oid))
        self.assertTrue(result["push_status"]["pushed"] or "Nothing to push" in result["push_status"]["message"]) # Could be True or False with "Nothing to push"

        self.assertEqual(self.local_repo.head.target, c2_remote_oid)
        # Remote should also be at c2_remote_oid (already was, and push shouldn't change it if no new local commits)
        self.assertEqual(self.remote_repo.lookup_reference("refs/heads/main").target, c2_remote_oid)

    def test_e2e_fetch_merge_clean_push(self):
        # 1. Base C1, pushed
        c1_oid = self._make_commit(self.local_repo, "base.txt", "base", "C1", branch_name="main")
        self._add_remote(self.local_repo, "origin", str(self.remote_repo_path))
        self._push_to_remote(self.local_repo, "origin", "main")

        # 2. Local makes C2_local
        c2_local_oid = self._make_commit(self.local_repo, "local_file.txt", "local content", "C2 Local")

        # 3. Remote makes C2_remote (from C1)
        temp_clone = pygit2.clone_repository(str(self.remote_repo_path), self.base_temp_dir / "clone_merge_e2e")
        self._configure_repo_user(temp_clone)
        sig_clone = pygit2.Signature(TEST_USER_NAME, TEST_USER_EMAIL, int(datetime.now(timezone.utc).timestamp()), 0)
        temp_clone.checkout("refs/heads/main")
        temp_clone.reset(c1_oid, pygit2.GIT_RESET_HARD) # Diverge from C1
        (temp_clone.workdir / "remote_file.txt").write_text("remote content")
        temp_clone.index.add("remote_file.txt")
        temp_clone.index.write()
        tree_clone = temp_clone.index.write_tree()
        c2_remote_oid = temp_clone.create_commit("HEAD", sig_clone, sig_clone, "C2 Remote", tree_clone, [c1_oid])
        temp_clone.remotes["origin"].push(["refs/heads/main:refs/heads/main"])
        shutil.rmtree(temp_clone.workdir)

        # 4. Sync local: fetch, merge, push the merge commit
        result = sync_repository(str(self.local_repo_path), branch_name_opt="main", push=True)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["fetch_status"]["message"], "Fetch complete.")
        self.assertEqual(result["local_update_status"]["type"], "merged_ok")
        self.assertIsNotNone(result["local_update_status"]["commit_oid"])
        self.assertTrue(result["push_status"]["pushed"])
        self.assertEqual(result["push_status"]["message"], "Push successful.")

        merge_commit_local_oid = pygit2.Oid(hex=result["local_update_status"]["commit_oid"])
        self.assertEqual(self.local_repo.head.target, merge_commit_local_oid)

        # Verify remote has the merge commit
        remote_main_ref = self.remote_repo.lookup_reference("refs/heads/main")
        self.assertEqual(remote_main_ref.target, merge_commit_local_oid)

        merge_commit_obj = self.local_repo.get(merge_commit_local_oid)
        self.assertEqual(len(merge_commit_obj.parents), 2)
        parent_oids = {p.id for p in merge_commit_obj.parents}
        self.assertEqual(parent_oids, {c2_local_oid, c2_remote_oid})


if __name__ == '__main__':
    unittest.main()
