from pathlib import Path
import pygit2
import os
from typing import Optional, Dict, List, Any

# Common ignore patterns for .gitignore
COMMON_GITIGNORE_PATTERNS = [
    "*.pyc",
    "__pycache__/",
    ".DS_Store",
    "*.swp",
    "*.swo",
    "*.swn",
    # Add other common patterns as needed
]

def initialize_repository(path_str: str, project_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Initializes a new GitWrite repository or adds GitWrite structure to an existing one.

    Args:
        path_str: The string representation of the base path (e.g., current working directory).
        project_name: Optional name of the project directory to be created within path_str.

    Returns:
        A dictionary with 'status', 'message', and 'path' (if successful).
    """
    try:
        base_path = Path(path_str)
        if project_name:
            target_dir = base_path / project_name
        else:
            target_dir = base_path

        # 1. Target Directory Determination & Validation
        if project_name:
            if target_dir.is_file():
                return {'status': 'error', 'message': f"Error: A file named '{project_name}' already exists at '{base_path}'.", 'path': str(target_dir.resolve())}
            if not target_dir.exists():
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    return {'status': 'error', 'message': f"Error: Could not create directory '{target_dir}'. {e}", 'path': str(target_dir.resolve())}
            elif target_dir.exists() and any(target_dir.iterdir()) and not (target_dir / ".git").exists():
                return {'status': 'error', 'message': f"Error: Directory '{target_dir.name}' already exists, is not empty, and is not a Git repository.", 'path': str(target_dir.resolve())}
        else: # No project_name, using path_str as target_dir
            if any(target_dir.iterdir()) and not (target_dir / ".git").exists():
                 # Check if CWD is empty or already a git repo
                if not target_dir.is_dir(): # Should not happen if path_str is CWD
                    return {'status': 'error', 'message': f"Error: Target path '{target_dir}' is not a directory.", 'path': str(target_dir.resolve())}
                return {'status': 'error', 'message': f"Error: Current directory '{target_dir.name}' is not empty and not a Git repository. Specify a project name or run in an empty directory/Git repository.", 'path': str(target_dir.resolve())}

        # 2. Repository Initialization
        is_existing_repo = (target_dir / ".git").exists()
        repo: pygit2.Repository
        if is_existing_repo:
            try:
                repo = pygit2.Repository(str(target_dir))
            except pygit2.Pygit2Error as e:
                return {'status': 'error', 'message': f"Error: Could not open existing Git repository at '{target_dir}'. {e}", 'path': str(target_dir.resolve())}
        else:
            try:
                repo = pygit2.init_repository(str(target_dir))
            except pygit2.Pygit2Error as e:
                return {'status': 'error', 'message': f"Error: Could not initialize Git repository at '{target_dir}'. {e}", 'path': str(target_dir.resolve())}

        # 3. GitWrite Structure Creation
        drafts_dir = target_dir / "drafts"
        notes_dir = target_dir / "notes"
        metadata_file = target_dir / "metadata.yml"

        try:
            drafts_dir.mkdir(exist_ok=True)
            (drafts_dir / ".gitkeep").touch(exist_ok=True)
            notes_dir.mkdir(exist_ok=True)
            (notes_dir / ".gitkeep").touch(exist_ok=True)
            if not metadata_file.exists():
                 metadata_file.write_text("# GitWrite Metadata\n# Add project-specific metadata here in YAML format.\n")
        except OSError as e:
            return {'status': 'error', 'message': f"Error: Could not create GitWrite directory structure in '{target_dir}'. {e}", 'path': str(target_dir.resolve())}

        # 4. .gitignore Management
        gitignore_file = target_dir / ".gitignore"
        gitignore_modified_or_created = False
        existing_ignores: List[str] = []

        if gitignore_file.exists():
            try:
                existing_ignores = gitignore_file.read_text().splitlines()
            except IOError as e:
                 return {'status': 'error', 'message': f"Error: Could not read existing .gitignore file at '{gitignore_file}'. {e}", 'path': str(target_dir.resolve())}


        new_ignores_added = False
        with open(gitignore_file, "a+") as f: # Open in append+read mode, create if not exists
            f.seek(0) # Go to the beginning to read existing content if any (though already read)
            # Ensure there's a newline before adding new patterns if file is not empty and doesn't end with one
            if f.tell() > 0: # File is not empty
                f.seek(0, os.SEEK_END) # Go to the end
                f.seek(f.tell() -1, os.SEEK_SET) # Go to last char
                if f.read(1) != '\n':
                    f.write('\n')

            for pattern in COMMON_GITIGNORE_PATTERNS:
                if pattern not in existing_ignores:
                    f.write(pattern + "\n")
                    new_ignores_added = True
                    if not gitignore_modified_or_created: # Record modification only once
                        gitignore_modified_or_created = True

        if not gitignore_file.exists() and new_ignores_added: # File was created
            gitignore_modified_or_created = True


        # 5. Staging Files
        items_to_stage_relative: List[str] = []
        # Paths must be relative to the repository root (target_dir) for staging
        drafts_gitkeep_rel = Path("drafts") / ".gitkeep"
        notes_gitkeep_rel = Path("notes") / ".gitkeep"
        metadata_yml_rel = Path("metadata.yml")

        items_to_stage_relative.append(str(drafts_gitkeep_rel))
        items_to_stage_relative.append(str(notes_gitkeep_rel))
        items_to_stage_relative.append(str(metadata_yml_rel))

        gitignore_rel_path_str = ".gitignore"

        # Check .gitignore status
        if gitignore_modified_or_created:
            items_to_stage_relative.append(gitignore_rel_path_str)
        elif is_existing_repo: # Even if not modified by us, stage it if it's untracked
            try:
                status = repo.status_file(gitignore_rel_path_str)
                if status == pygit2.GIT_STATUS_WT_NEW or status == pygit2.GIT_STATUS_WT_MODIFIED:
                     items_to_stage_relative.append(gitignore_rel_path_str)
            except KeyError: # File is not in index and not in working dir (e.g. after a clean)
                 if gitignore_file.exists(): # if it exists on disk, it's new
                    items_to_stage_relative.append(gitignore_rel_path_str)
            except pygit2.Pygit2Error as e:
                # Could fail if target_dir is not a repo, but we checked this
                pass # Best effort to check status


        staged_anything = False
        try:
            repo.index.read() # Load existing index if any

            for item_rel_path_str in items_to_stage_relative:
                item_abs_path = target_dir / item_rel_path_str
                if not item_abs_path.exists():
                    # This might happen if e.g. .gitkeep was deleted manually before commit
                    # Or if .gitignore was meant to be staged but somehow failed creation/modification silently
                    # For now, we'll try to add and let pygit2 handle it, or skip.
                    # Consider logging a warning if a robust logging system were in place.
                    continue

                # Check status to decide if it needs staging (especially for existing repos)
                try:
                    status = repo.status_file(item_rel_path_str)
                except KeyError: # File is not in index and not in working dir (but we know it exists)
                    status = pygit2.GIT_STATUS_WT_NEW # Treat as new if status_file errors due to not being tracked
                except pygit2.Pygit2Error: # Other potential errors with status_file
                    status = pygit2.GIT_STATUS_WT_NEW # Default to staging if status check fails


                # Stage if new, modified, or specifically marked for staging (like .gitignore)
                # GIT_STATUS_CURRENT is 0, means it's tracked and unmodified.
                if item_rel_path_str == gitignore_rel_path_str and gitignore_modified_or_created:
                    repo.index.add(item_rel_path_str)
                    staged_anything = True
                elif status & (pygit2.GIT_STATUS_WT_NEW | pygit2.GIT_STATUS_WT_MODIFIED | \
                             pygit2.GIT_STATUS_INDEX_NEW | pygit2.GIT_STATUS_INDEX_MODIFIED ):
                    repo.index.add(item_rel_path_str)
                    staged_anything = True
                elif item_rel_path_str in [str(drafts_gitkeep_rel), str(notes_gitkeep_rel), str(metadata_yml_rel)] and \
                     (status == pygit2.GIT_STATUS_WT_NEW or not repo.lookup_path(item_rel_path_str, flags=pygit2.GIT_LOOKUP_PATH_SKIP_WORKDIR)):
                     # The lookup_path is a more direct way to see if it's in the current commit's tree
                     # If it's WT_NEW or not in current HEAD tree, add it.
                     repo.index.add(item_rel_path_str)
                     staged_anything = True


            if staged_anything:
                repo.index.write()
        except pygit2.Pygit2Error as e:
            return {'status': 'error', 'message': f"Error: Could not stage files in Git repository at '{target_dir}'. {e}", 'path': str(target_dir.resolve())}

        # 6. Commit Creation
        if staged_anything or (is_existing_repo and repo.head_is_unborn): # Commit if files were staged or if it's a new repo (head_is_unborn)
            try:
                # Define author/committer
                author_name = "GitWrite System"
                author_email = "gitwrite@example.com" # Placeholder email
                author = pygit2.Signature(author_name, author_email)
                committer = pygit2.Signature(author_name, author_email)

                # Determine parents
                parents = []
                if not repo.head_is_unborn:
                    parents.append(repo.head.target)

                tree = repo.index.write_tree()

                # Check if tree actually changed compared to HEAD, or if it's the very first commit
                if repo.head_is_unborn or (parents and repo.get(parents[0]).tree_id != tree) or not parents:
                    commit_message_action = "Initialized GitWrite project structure in" if not is_existing_repo or repo.head_is_unborn else "Added GitWrite structure to"
                    commit_message = f"{commit_message_action} {target_dir.name}"

                    repo.create_commit(
                        "HEAD",          # ref_name
                        author,          # author
                        committer,       # committer
                        commit_message,  # message
                        tree,            # tree
                        parents          # parents
                    )
                    action_summary = "Initialized empty Git repository.\n" if not is_existing_repo else ""
                    action_summary += "Created GitWrite directory structure.\n"
                    action_summary += "Staged GitWrite files.\n"
                    action_summary += "Created GitWrite structure commit."
                    return {'status': 'success', 'message': action_summary.replace(".\n", f" in {target_dir.name}.\n").strip(), 'path': str(target_dir.resolve())}
                else:
                    # No changes to commit, but structure is there.
                    action_summary = "GitWrite structure already present and up-to-date."
                    if not is_existing_repo : action_summary = "Initialized empty Git repository.\n" + action_summary
                    return {'status': 'success', 'message': action_summary.replace(".\n", f" in {target_dir.name}.\n").strip(), 'path': str(target_dir.resolve())}

            except pygit2.Pygit2Error as e:
                return {'status': 'error', 'message': f"Error: Could not create commit in Git repository at '{target_dir}'. {e}", 'path': str(target_dir.resolve())}
        else:
            # No files were staged, means structure likely already exists and is tracked.
            message = "GitWrite structure already present and tracked."
            if not is_existing_repo : message = f"Initialized empty Git repository in {target_dir.name}.\n{message}"

            return {'status': 'success', 'message': message, 'path': str(target_dir.resolve())}

    except Exception as e:
        # Catch-all for unexpected errors
        return {'status': 'error', 'message': f"An unexpected error occurred: {e}", 'path': str(target_dir.resolve() if 'target_dir' in locals() else base_path.resolve() if 'base_path' in locals() else path_str)}


def add_pattern_to_gitignore(repo_path_str: str, pattern: str) -> Dict[str, str]:
    """
    Adds a pattern to the .gitignore file in the specified repository.

    Args:
        repo_path_str: String path to the root of the repository.
        pattern: The ignore pattern string to add.

    Returns:
        A dictionary with 'status' and 'message'.
    """
    try:
        gitignore_file_path = Path(repo_path_str) / ".gitignore"
        pattern_to_add = pattern.strip()

        if not pattern_to_add:
            return {'status': 'error', 'message': 'Pattern cannot be empty.'}

        existing_patterns: set[str] = set()
        last_line_had_newline = True # Assume true for new/empty file

        if gitignore_file_path.exists():
            try:
                content_data = gitignore_file_path.read_text()
                if content_data:
                    lines_data = content_data.splitlines()
                    for line_iter_ignore in lines_data:
                        existing_patterns.add(line_iter_ignore.strip())
                    if content_data.endswith("\n") or content_data.endswith("\r"):
                        last_line_had_newline = True
                    else:
                        last_line_had_newline = False
                # If content_data is empty, last_line_had_newline remains True (correct for writing)
            except (IOError, OSError) as e:
                return {'status': 'error', 'message': f"Error reading .gitignore: {e}"}

        if pattern_to_add in existing_patterns:
            return {'status': 'exists', 'message': f"Pattern '{pattern_to_add}' already exists in .gitignore."}

        try:
            with open(gitignore_file_path, "a") as f:
                if not last_line_had_newline:
                    f.write("\n")
                f.write(f"{pattern_to_add}\n")
            return {'status': 'success', 'message': f"Pattern '{pattern_to_add}' added to .gitignore."}
        except (IOError, OSError) as e:
            return {'status': 'error', 'message': f"Error writing to .gitignore: {e}"}

    except Exception as e: # Catch-all for unexpected issues like invalid repo_path_str
        return {'status': 'error', 'message': f"An unexpected error occurred: {e}"}


def list_gitignore_patterns(repo_path_str: str) -> Dict[str, Any]:
    """
    Lists all patterns in the .gitignore file of the specified repository.

    Args:
        repo_path_str: String path to the root of the repository.

    Returns:
        A dictionary with 'status', 'patterns' (list), and 'message'.
    """
    try:
        gitignore_file_path = Path(repo_path_str) / ".gitignore"

        if not gitignore_file_path.exists():
            return {'status': 'not_found', 'patterns': [], 'message': '.gitignore file not found.'}

        try:
            content_data_list = gitignore_file_path.read_text()
        except (IOError, OSError) as e:
            return {'status': 'error', 'patterns': [], 'message': f"Error reading .gitignore: {e}"}

        if not content_data_list.strip(): # empty or whitespace-only
            return {'status': 'empty', 'patterns': [], 'message': '.gitignore is empty.'}

        patterns_list = [line.strip() for line in content_data_list.splitlines() if line.strip()]
        return {'status': 'success', 'patterns': patterns_list, 'message': 'Successfully retrieved patterns.'}

    except Exception as e: # Catch-all for unexpected issues
        return {'status': 'error', 'patterns': [], 'message': f"An unexpected error occurred: {e}"}
