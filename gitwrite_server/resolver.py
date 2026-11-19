"""The one validated resolver mapping repo names to paths under the repos root.

The old API's confirmed traversal failure (docs/AUDIT.md) was repo names
flowing into ``Path(base) / repo_name`` so a percent-encoded ``..`` escaped
the root. Here every URL path is split into segments, each segment must match
a strict pattern, and the joined path must still resolve inside the root —
all before anything touches the filesystem or dulwich.

Wire format: ``/name.git/...`` or ``/owner/name.git/...`` — the ``.git``
suffix is required on the wire, matching the plugin's connect form. On-disk
layout: ``<repos_root>/<name>.git`` (or ``<repos_root>/<owner>/<name>.git``)
bare repositories.
"""

import re
from pathlib import Path

# First character alphanumeric, so a segment can never start with a dot and
# can never be "." or "..". The regex also covers the AUDIT's percent-encoded
# escape: ".." fails to match outright.
SEGMENT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

_GIT_SUFFIX = ".git"
_MAX_SEGMENTS = 2  # "name" or "owner/name"


def parse_repo_segments(path_info: str) -> list[str] | None:
    """Extract the validated repo-name segments from a request path.

    The repo name is the leading path segments up to and including the first
    ending in ``.git`` (git smart-HTTP URLs are ``<repo>/info/refs``,
    ``<repo>/git-upload-pack``, ...). Returns None for anything that is not a
    strictly valid repo name.
    """
    segments = [segment for segment in path_info.split("/") if segment]
    repo_segments: list[str] = []
    for segment in segments:
        repo_segments.append(segment)
        if segment.endswith(_GIT_SUFFIX):
            break
    else:
        return None  # no .git-terminated repo path at all
    if not 1 <= len(repo_segments) <= _MAX_SEGMENTS:
        return None
    names: list[str] = []
    for segment in repo_segments:
        name = segment[: -len(_GIT_SUFFIX)] if segment.endswith(_GIT_SUFFIX) else segment
        if not SEGMENT_RE.match(name):
            return None
        names.append(name)
    return names


def resolve_repo(path_info: str, *, repos_root: Path) -> Path | None:
    """Resolve a validated request path to the repo's location under the root.

    Returns the path the repo lives at (which may not exist yet — the caller
    decides between auto-create on push and 404 on read), or None when the
    name is invalid; the caller answers None with a generic 403 that echoes
    no filesystem paths.
    """
    names = parse_repo_segments(path_info)
    if names is None:
        return None
    # Bare repos always end in .git on disk, whether or not the URL said so.
    repo_path = repos_root.joinpath(*names).with_name(names[-1] + _GIT_SUFFIX)
    resolved = repo_path.resolve()
    if not resolved.is_relative_to(repos_root.resolve()):
        return None
    return resolved
