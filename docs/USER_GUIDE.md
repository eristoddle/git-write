# GitWrite User Guide (command line)

GitWrite is version control for writers. Under the hood a project is an ordinary git repository, so
anything you do here is visible to (and works with) normal git tools.

Words used below: a **save** is a git commit, an **exploration** is a branch, a **tag** is a named
milestone. Install instructions are in the [README](../README.md). Every command has its own
`--help`.

## Start a project

```bash
gitwrite init MyNovel
cd MyNovel
```

This creates the folder, a git repository (on git's default branch: `main` if you have run
`git config --global init.defaultBranch main`, otherwise `master`), a `.gitignore`, a `metadata.yml`, and `drafts/`
and `notes/` folders, and records them as the first save. In an existing folder, `gitwrite init` with
no name sets up version control there.

## Save your work

Write in any editor, then:

```bash
gitwrite status                 # what has changed
gitwrite save "Finished chapter 1"
gitwrite save "Notes only" -i notes/   # save just some files (-i can repeat)
gitwrite history                # every save, oldest first
gitwrite history -n 5           # a limited number
```

Saves are recorded under your git identity. If none is set they are recorded as "GitWrite User", so
set it once: `git config --global user.name "Your Name"` and
`git config --global user.email you@example.com`.

## Compare versions

```bash
gitwrite compare                      # your last save against the one before
gitwrite compare HEAD~2 HEAD          # two points in history
gitwrite compare main alternate-plot  # two explorations
gitwrite compare v1 v2                # two tags
```

Changes inside a line are shown word by word.

## Explore an idea without risking your draft

```bash
gitwrite explore alternate-ending     # create an exploration and move onto it
# ...write, then:
gitwrite save "Tried a bleaker ending"
gitwrite switch main                  # go back; the files change to match
gitwrite switch                       # with no name: list explorations
```

Bring an exploration into your main work:

```bash
gitwrite switch main
gitwrite merge alternate-ending
```

If both sides changed the same lines, GitWrite lists the conflicting files. Open them, choose what
to keep, then `gitwrite save "Resolved conflicts"`.

To look at someone else's branch before merging, or to take just one change from it:

```bash
gitwrite review editor-feedback       # commits on that branch that you do not have
gitwrite cherry-pick <commit-id>      # apply one of them as a new save (--mainline N for merge commits)
```

## Undo a change safely

```bash
gitwrite revert HEAD~1                # a new save that cancels that earlier one
```

History is never rewritten. The working folder must be clean (everything saved) first.

## Mark milestones

```bash
gitwrite tag add v1 -m "First complete draft"   # with a message
gitwrite tag add early --commit abc1234         # tag a specific save
gitwrite tag add v1 --force                     # move an existing tag
gitwrite tag list
```

## Keep files out of your saves

```bash
gitwrite ignore add "*.tmp"
gitwrite ignore list
```

## Export

Pandoc must be installed; PDF also needs a LaTeX engine. File paths are relative to the project, are
read from the saved version (`--commit`, default the latest save), and are joined in the order given.

```bash
gitwrite export epub -o MyNovel.epub . drafts/ch1.md drafts/ch2.md
gitwrite export docx -o MyNovel.docx . drafts/ch1.md drafts/ch2.md
gitwrite export pdf  -o MyNovel.pdf --pdf-engine xelatex . drafts/ch1.md
gitwrite export epub -o v1.epub --commit v1 . drafts/ch1.md   # as of the v1 tag
```

## Share with others

Add a remote with git (`git remote add origin <url>`), then:

```bash
gitwrite sync               # fetch, merge their changes, push yours
gitwrite sync --no-push     # only bring their changes in
```

GitWrite does not host anything; use any git host (GitHub, Gitea, ...).

## Troubleshooting

- **"Not a git repository"**: run the command from inside the project folder.
- **Pandoc errors on export**: check that `pandoc --version` works in the same terminal.
- **Merge conflicts**: see the merge section above; nothing is lost, and `git status` shows the state.
