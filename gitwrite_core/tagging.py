import pygit2
from gitwrite_core.exceptions import RepositoryNotFoundError, CommitNotFoundError, TagAlreadyExistsError, GitWriteError

def create_tag(repo_path_str: str, tag_name: str, target_commit_ish: str = 'HEAD', message: str = None, force: bool = False, tagger: pygit2.Signature = None):
    """
    Creates a new tag in the repository.

    Args:
        repo_path_str: Path to the Git repository.
        tag_name: The name of the tag to create.
        target_commit_ish: The commit-ish to tag (default: 'HEAD').
        message: If provided, creates an annotated tag with this message. Otherwise, a lightweight tag is created.
        force: If True, overwrite an existing tag with the same name.

    Returns:
        A dictionary containing information about the created tag.

    Raises:
        RepositoryNotFoundError: If the repository is not found at the given path.
        CommitNotFoundError: If the target commit-ish cannot be resolved.
        TagAlreadyExistsError: If the tag already exists and force is False.
    """
    try:
        repo = pygit2.Repository(repo_path_str)
    except pygit2.GitError:
        raise RepositoryNotFoundError(f"Repository not found at '{repo_path_str}'")

    if repo.is_bare:
        raise GitWriteError("Cannot create tags in a bare repository.")

    try:
        target_oid = repo.revparse_single(target_commit_ish).oid
    except (pygit2.GitError, KeyError): # KeyError for non-existent reference
        raise CommitNotFoundError(f"Commit-ish '{target_commit_ish}' not found in repository '{repo_path_str}'")

    tag_ref_name = f'refs/tags/{tag_name}'

    if tag_ref_name in repo.listall_references():
        if not force:
            raise TagAlreadyExistsError(f"Tag '{tag_name}' already exists in repository '{repo_path_str}'")
        else:
            # Delete existing tag reference
            repo.references.delete(tag_ref_name)

    if message:
        # Create an annotated tag
        tagger_signature = tagger if tagger else pygit2.Signature('GitWrite Core', 'core@gitwrite.com')
        try:
            repo.create_tag(tag_name, target_oid, pygit2.GIT_OBJ_COMMIT, tagger_signature, message)
            return {'name': tag_name, 'type': 'annotated', 'target': str(target_oid), 'message': message}
        except pygit2.GitError as e:
            # This might happen if the tag name is invalid or other git related issues
            raise GitWriteError(f"Failed to create annotated tag '{tag_name}': {e}") # Ensure GitWriteError is imported
    else:
        # Create a lightweight tag
        try:
            repo.create_reference(tag_ref_name, target_oid)
            return {'name': tag_name, 'type': 'lightweight', 'target': str(target_oid)}
        except pygit2.GitError as e:
            if "already exists" in str(e).lower():
                # Provide a more specific error message for this race condition
                raise TagAlreadyExistsError(f"Tag '{tag_name}' already exists (race condition detected during create: {e})")
            # This might happen if the tag name is invalid or other git related issues
            raise GitWriteError(f"Failed to create lightweight tag '{tag_name}': {e}")


def list_tags(repo_path_str: str):
    """
    Lists all tags in the repository.

    Args:
        repo_path_str: Path to the Git repository.

    Returns:
        A list of dictionaries, where each dictionary contains information about a tag.
        Example: [{'name': 'v1.0', 'type': 'annotated', 'target': 'commit_oid_str', 'message': 'Release v1.0'},
                  {'name': 'lightweight_tag', 'type': 'lightweight', 'target': 'commit_oid_str'}]

    Raises:
        RepositoryNotFoundError: If the repository is not found at the given path.
    """
    try:
        repo = pygit2.Repository(repo_path_str)
    except pygit2.GitError:
        raise RepositoryNotFoundError(f"Repository not found at '{repo_path_str}'")

    tags_data = []
    for ref_name in repo.listall_references():
        if ref_name.startswith('refs/tags/'):
            tag_name = ref_name.replace('refs/tags/', '')

            try:
                # Resolve the reference to get the Oid of the object it points to
                direct_target_oid = repo.lookup_reference(ref_name).target
                # Get the object itself
                target_object = repo.get(direct_target_oid)
            except (pygit2.GitError, KeyError):
                # Skip problematic refs, or log a warning, or raise a specific error
                # For now, skipping seems reasonable for a listing operation.
                continue

            if isinstance(target_object, pygit2.Tag): # Check if it's a pygit2.Tag object (annotated tag object)
                # It's an annotated tag
                # The target of the tag object is the commit
                commit_oid = target_object.target
                tags_data.append({
                    'name': tag_name,
                    'type': 'annotated',
                    'target': str(commit_oid), # target_object.target is Oid, repo.get(commit_oid).id is also Oid
                    'message': target_object.message.strip() if target_object.message else ""
                })
            elif isinstance(target_object, pygit2.Commit): # Check if it's a pygit2.Commit object (lightweight tag)
                # It's a lightweight tag (points directly to a commit)
                tags_data.append({
                    'name': tag_name,
                    'type': 'lightweight',
                    'target': str(direct_target_oid) # The direct target is the commit OID
                })
            # else:
                # It might be a tag pointing to another object type (e.g. a tree or blob),
                # which is less common for typical tag usage.
                # For this function, we are primarily interested in tags pointing to commits (directly or indirectly).
                # Depending on requirements, this part could be extended or log a warning.

    return tags_data
