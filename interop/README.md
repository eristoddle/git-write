# interop

Proves that repositories made by GitWrite (pygit2) and by Veneer (isomorphic-git) open in each other.
`tests/test_interop.py` drives it:

- `read-repo.mjs <dir>`: reads branches, history, tags and the feedback branch with isomorphic-git and prints JSON.
- `write-repo.mjs <dir>`: builds a project with isomorphic-git only (commits, an exploration, tags, an annotation and a status change on `feedback`) and prints the ids.
- `lib.mjs`: a plain-JS reader/anchor implementation of `docs/ANNOTATION_FORMAT.md`.

Both directions also run `git fsck --strict`.

```bash
cd interop && npm ci      # once; needs Node 20+
cd .. && uv run pytest tests/test_interop.py
```

Without Node (or without `npm ci`) the tests skip locally with a message. CI sets
`GITWRITE_REQUIRE_INTEROP=1`, which turns that skip into a failure.
`isomorphic-git` and `yaml` are pinned exactly in `package.json`; bump them deliberately.
