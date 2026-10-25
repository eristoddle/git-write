# GitWrite

Version control for writers, on plain git. Save a version, see the history, try a different ending
on an exploration (a branch), compare drafts word by word, mark milestones (tags), merge the ideas
you like, and export to EPUB, DOCX or PDF.

A GitWrite project is an ordinary git repository, so it opens in any git tool and works with any
git host. GitWrite only gives the commands writer-friendly names.

## What is here today

- **`gitwrite_core/`**: the operations, built on [pygit2](https://www.pygit2.org/).
- **`gitwrite_cli/`**: the `gitwrite` command.
- **`tests/`**: the test suite. It uses real temporary repositories, never mocks of git.

A [Veneer](https://github.com/eristoddle/veneer) plugin is coming; it will be the main way to use
GitWrite. See [PLAN.md](PLAN.md) for the direction and the decisions behind it.

## Install the CLI

You need Python 3.12 or newer and [uv](https://docs.astral.sh/uv/). Export needs
[pandoc](https://pandoc.org/installing.html) (PDF also needs a LaTeX engine).

```bash
git clone https://github.com/eristoddle/git-write
cd git-write
uv tool install .      # puts `gitwrite` on your PATH
gitwrite --help
```

To work on GitWrite itself instead:

```bash
uv sync
uv run gitwrite --help
uv run pytest
uv run ruff check .
```

## Commands

```
gitwrite init [PROJECT_NAME]     Start a new writing project or set up version control in...
gitwrite save MESSAGE            Save your writing progress with a descriptive message.
gitwrite status                  Show what's happening in your writing project right now.
gitwrite history                 View your writing journey - all the saves you've made.
gitwrite compare V1 V2           See what changed between different versions of your work.
gitwrite explore BRANCH_NAME     Start exploring new ideas without affecting your main work.
gitwrite switch [BRANCH_NAME]    Switch between different versions of your work or see all...
gitwrite merge BRANCH_NAME       Combine an exploration or collaboration branch with your...
gitwrite review BRANCH_NAME      Review changes from a collaborator or exploration branch.
gitwrite cherry-pick COMMIT_ID   Apply a specific change from another version to your...
gitwrite revert COMMIT_ISH       Undo a specific change by creating a new save that cancels...
gitwrite tag add|list            Create bookmarks for important versions of your work.
gitwrite ignore add|list         Manage .gitignore entries.
gitwrite export epub|docx|pdf    Create finished documents from your writing project.
gitwrite sync                    Share your work with collaborators and get their latest...
gitwrite help [TOPIC]            Get help with GitWrite workflows and concepts.
```

`gitwrite COMMAND --help` explains any command. A short walkthrough is in
[docs/USER_GUIDE.md](docs/USER_GUIDE.md).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). One rule for
tests: never mock pygit2 or `gitwrite_core`. Use real temporary repositories and set the initial
branch explicitly.

## License

MIT. See [LICENSE](LICENSE).
