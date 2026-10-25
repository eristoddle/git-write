# Annotation format

How GitWrite stores reader annotations in a git repository. This is the contract between the Python
core (`gitwrite_core/annotations.py`, `gitwrite_core/anchors.py`) and the Veneer plugin, which
implements it in TypeScript on `api.history` (isomorphic-git). Anything either side writes, the
other must read. Decisions: D8, D11, D15.

An annotation is a comment on a highlighted passage of a file. It is stored as a commit, so it
travels with `git push` / `git fetch` like everything else, needs no extra files in the project, and
never shows up in the writer's own files.

## Where annotations live

- On a branch named **`feedback`** by default. The name is a setting; every operation takes the
  branch name as a parameter. Branch names that start with `-` or are not valid git branch names are
  rejected.
- The branch is created from the project's current `HEAD` commit the first time an annotation is
  added. It is never checked out. **Writing an annotation must not move `HEAD`, the index or the
  working tree**; commits are added by updating `refs/heads/<branch>` directly.
- A reader without a local checkout (bare repos) can write annotations the same way.

## Commit shape

Each annotation, and each status change, is one commit on the feedback branch:

- **Tree**: identical to the parent commit's tree. The commit changes no files.
- **Parent**: the previous tip of the feedback branch (for the first one, the `HEAD` commit it was
  branched from).
- **Author and committer**: the writer's git identity. If none is configured, `GitWrite
  <gitwrite@example.com>`. The person who made the annotation is in the `author` field of the body,
  not in the git author.
- **Message**: a subject line, one blank line, then a YAML mapping.

```
<subject line>
<blank line>
<YAML mapping>
```

The subject is for humans (`git log`) and is never parsed. Readers must require the blank second
line and a YAML mapping body; a commit that does not look like that is not an annotation and is
skipped (the feedback branch also contains the project history it was branched from, and a writer
may add ordinary commits to it).

## YAML fields

| Field | Type | Required | Meaning |
|---|---|---|---|
| `file_path` | string | yes | Path of the annotated file, relative to the project root. |
| `highlighted_text` | string | yes | The exact text that was highlighted. |
| `start_line` | integer >= 0 | yes | First line of the highlight. **0-indexed**; lines are split on `\n`. |
| `end_line` | integer >= 0 | yes | Last line of the highlight (0-indexed, inclusive). |
| `comment` | string | yes | The reader's note. |
| `author` | string | yes | Who wrote it (a name or email; free text). |
| `status` | `new` \| `accepted` \| `rejected` | yes | State of the annotation. Starts as `new`. |
| `prefix` | string | no (D15) | Up to 32 characters of file text just before the highlight (fewer at the start of the file). |
| `suffix` | string | no (D15) | Up to 32 characters of file text just after the highlight (fewer at the end of the file). |
| `offset` | integer >= 0 | no (D15) | Where the highlight started in the file text. |
| `original_annotation_id` | string | status commits only | Full SHA of the commit that created the annotation this commit changes. |

Rules for readers:

- A commit with any required field missing, a `status` that is not one of the three values, or a
  required field of the wrong type is **skipped**, not an error.
- `prefix`, `suffix` and `offset` are optional. A value of the wrong type is **ignored** (treated as
  absent); the annotation is still read.
- Unknown extra keys are ignored. Writers should keep field order as above, but readers must not
  depend on order.
- Writers emit the three anchor fields only when they have them, so annotations without anchors are
  byte-identical to the original format.
- **`offset` and the lengths of `prefix` / `suffix` count Unicode code points**, not UTF-8 bytes and
  not UTF-16 code units. In JavaScript, index `Array.from(text)` rather than the string itself when an
  emoji or other astral character could be present.
- The YAML is a plain block mapping, written with the equivalent of PyYAML's
  `yaml.dump(data, sort_keys=False, allow_unicode=True)` and read with `safe_load`. Use a real YAML
  library on the TypeScript side; strings that look like numbers, booleans or contain `: ` need the
  quoting the library applies. In particular a `prefix` or `suffix` that contains a line break is
  written as a quoted scalar with the line break folded into a blank line (see the example below);
  a YAML parser reads it back to the exact original text.

## Status changes

Changing the status of an annotation (accept, reject, reopen) does not edit the original commit; it
adds a new commit on the same branch:

- Same shape as above, with the **full body of the original** carried over and only `status`
  changed, plus `original_annotation_id` set to the full SHA of the commit that created the
  annotation.
- If a status commit is named as the thing to change, its own `original_annotation_id` is used, so a
  chain of changes always points at the creation commit.
- The original commit must be reachable from the feedback branch tip.

Reading rule: walk the branch from the oldest commit to the tip (parents before children). A commit
without `original_annotation_id` creates the annotation whose `id` is that commit's SHA. A commit
with `original_annotation_id` replaces the state of the annotation with that `id`; the last one wins.
The `id` of an annotation is always its creation commit; `commit_id` is the commit that recorded its
current state. Annotations are listed in the order their threads first appear.

## Finding the passage again (`locate`)

Files change after a reader highlights them, so line numbers alone drift. Given the annotation and
the current file text, find where the passage is now. Try in order:

1. **Context**: look for `prefix + highlighted_text + suffix` (only if the annotation has `prefix`
   or `suffix`; a missing one counts as the empty string).
2. **Text**: look for `highlighted_text` alone.
3. **Line**: use lines `start_line` through `end_line`. If `start_line` is beyond the end of the
   file, the passage cannot be placed. `end_line` is clamped to the last line. The range runs from
   the start of `start_line` to the end of `end_line`, not including its line break (or a `\r` before
   it).

The first tier that matches wins and its name is reported (`context`, `text`, `line`).

If a tier matches in several places, pick the match whose highlight starts nearest the stored
`offset`; with no `offset`, the one on the line nearest `start_line`; ties go to the earlier match.
An empty `highlighted_text` skips tiers 1 and 2.

When creating an annotation from file text, `prefix` and `suffix` are the 32 characters before and
after the highlight, clipped at the file edges, and `offset` is the highlight's start. If the text
occurs more than once, the occurrence on (or nearest) `start_line` is used. The Python core computes
this from the file as it is in `HEAD`; a plugin can compute it from the open buffer instead.

## Examples

Both blocks below are produced by `tests/test_annotation_format_doc.py` from real commits and the
test fails if they drift. Run
`UPDATE_ANNOTATION_DOC=1 uv run pytest tests/test_annotation_format_doc.py` to rewrite them after an intentional format change. The status commit's SHA is replaced by a fixed
placeholder, since real SHAs depend on the commit time.

The file being annotated:

<!-- BEGIN GENERATED: file -->
```
chapter1.md

The rain had not stopped for three days, and the river was rising against the old stone bridge.
Marta counted the sandbags twice. Then she counted them again.
By evening the road was gone.
```
<!-- END GENERATED: file -->

A new annotation (the commit message of the first commit):

<!-- BEGIN GENERATED: annotation-commit -->
```
Annotation: chapter1.md (Lines 1-1)

file_path: chapter1.md
highlighted_text: Marta counted the sandbags twice.
start_line: 1
end_line: 1
comment: Show her fear here instead of telling us.
author: beta-reader@example.com
status: new
prefix: 'g against the old stone bridge.

  '
suffix: ' Then she counted them again.

  By'
offset: 96
```
<!-- END GENERATED: annotation-commit -->

The commit that later accepts it:

<!-- BEGIN GENERATED: status-commit -->
```
Update status: chapter1.md (Annotation 8c1f6e0) to accepted

file_path: chapter1.md
highlighted_text: Marta counted the sandbags twice.
start_line: 1
end_line: 1
comment: Show her fear here instead of telling us.
author: beta-reader@example.com
status: accepted
prefix: 'g against the old stone bridge.

  '
suffix: ' Then she counted them again.

  By'
offset: 96
original_annotation_id: 8c1f6e0b4d2a9f37c5e18b60a47d3e92f1b5c7d4
```
<!-- END GENERATED: status-commit -->

## Writing and reading it elsewhere

- Python: `create_annotation_commit`, `list_annotations`, `update_annotation_status`, `locate`,
  `compute_anchor`.
- isomorphic-git: `git.log({ ref: 'feedback' })` returns each commit's message; `git.writeCommit`
  plus `git.writeRef` creates one without touching the working tree. `interop/` contains tests that
  read the feedback branch of a repo GitWrite made with isomorphic-git.
