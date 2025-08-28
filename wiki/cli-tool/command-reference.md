# Command Reference

This comprehensive reference covers all GitWrite CLI commands, their syntax, options, and usage examples. Commands are organized by workflow category for easy navigation.

## Command Syntax Conventions

- `<required>` - Required arguments
- `[optional]` - Optional arguments
- `--flag` - Boolean flags (true/false)
- `--option value` - Options that take values
- `|` - Alternative options
- `...` - Multiple values allowed

## Project Management Commands

### `gitwrite init`

Initialize a new GitWrite project.

**Syntax:**
```bash
gitwrite init [project_name] [options]
```

**Options:**
- `--author TEXT` - Project author name (will prompt if not provided)
- `--description TEXT` - Project description
- `--type CHOICE` - Project type: `novel`, `short-story`, `article`, `screenplay`, `academic` (default: `novel`)
- `--template TEXT` - Custom project template name
- `--interactive` - Use interactive setup mode with prompts
- `--no-git` - Create project structure without Git repository
- `--bare` - Create minimal project structure

**Examples:**
```bash
# Basic initialization with prompts
gitwrite init my-novel

# Full specification
gitwrite init my-novel \
  --author "Jane Writer" \
  --description "A thriller set in Victorian London" \
  --type novel

# Interactive mode
gitwrite init --interactive

# Academic paper
gitwrite init research-paper \
  --type academic \
  --author "Dr. Smith"
```

**Project Types:**
- `novel` - Full-length fiction with chapters, characters, notes
- `short-story` - Single story file with minimal structure
- `article` - Non-fiction article with research notes
- `screenplay` - Script format with scenes and characters
- `academic` - Research paper with citations and bibliography

### `gitwrite status`

Show current project status and pending changes.

**Syntax:**
```bash
gitwrite status [options]
```

**Options:**
- `--detailed` - Show individual file changes
- `--stats` - Include writing statistics
- `--porcelain` - Machine-readable output format
- `--branch` - Show current exploration (branch) info

**Examples:**
```bash
# Basic status
gitwrite status

# Detailed file listing
gitwrite status --detailed

# Include writing stats
gitwrite status --stats

# Machine-readable format for scripts
gitwrite status --porcelain
```

**Output Format:**
```
📖 My Great Novel
👤 Jane Writer
🔬 Working in exploration: alternative-ending

📝 3 files changed
  Modified: 1 file
  New: 2 files

📊 Writing Stats:
  Words today: 847
  Total words: 23,156
  Files: 8
```

### `gitwrite config`

Manage GitWrite configuration settings.

**Syntax:**
```bash
gitwrite config <subcommand> [options]
```

**Subcommands:**

#### `gitwrite config set`
```bash
gitwrite config set <key> <value> [--global]
```

**Examples:**
```bash
# Set global user information
gitwrite config set --global user.name "Jane Writer"
gitwrite config set --global user.email "jane@example.com"

# Set project-specific settings
gitwrite config set auto_save true
gitwrite config set export.default_format epub
gitwrite config set editor.command "code"
```

#### `gitwrite config get`
```bash
gitwrite config get <key> [--global]
```

#### `gitwrite config list`
```bash
gitwrite config list [--global] [--project]
```

**Common Configuration Keys:**
- `user.name` - Author name for commits
- `user.email` - Author email
- `auto_save` - Enable automatic saving (true/false)
- `editor.command` - Default editor command
- `export.default_format` - Default export format
- `collaboration.auto_invite` - Auto-invite collaborators
- `ui.color` - Enable colored output

## Writing Workflow Commands

### `gitwrite save`

Save changes with a descriptive message.

**Syntax:**
```bash
gitwrite save <message> [options]
```

**Options:**
- `--files FILE...` - Save only specific files
- `--tag TEXT` - Tag this save as a milestone
- `--interactive` - Review changes before saving
- `--amend` - Modify the last save instead of creating new one
- `--allow-empty` - Allow save with no changes (for milestones)

**Examples:**
```bash
# Basic save
gitwrite save "Completed chapter 3"

# Save specific files
gitwrite save "Updated character profiles" \
  --files characters/protagonist.md characters/villain.md

# Save with milestone tag
gitwrite save "First draft complete" --tag first-draft

# Interactive save (review changes first)
gitwrite save "Major plot revision" --interactive

# Amend previous save
gitwrite save "Fixed typos in chapter 3" --amend
```

**Message Guidelines:**
- Use descriptive, meaningful messages
- Start with action verbs: "Added", "Fixed", "Rewrote", "Completed"
- Be specific about what changed
- Mention character names, chapters, or scenes affected

### `gitwrite history`

View project history and previous saves.

**Syntax:**
```bash
gitwrite history [options]
```

**Options:**
- `--limit N` - Show only N most recent saves (default: 10)
- `--since DATE` - Show saves since date/time
- `--until DATE` - Show saves until date/time
- `--author TEXT` - Show saves by specific author
- `--format FORMAT` - Output format: `table`, `json`, `csv`
- `--oneline` - Compact one-line format
- `--stats` - Include file change statistics

**Examples:**
```bash
# Recent history
gitwrite history

# Last 20 saves
gitwrite history --limit 20

# This week's work
gitwrite history --since "1 week ago"

# Saves by specific author
gitwrite history --author "Jane Writer"

# Compact format
gitwrite history --oneline

# With statistics
gitwrite history --stats
```

**Date Formats:**
- `"2023-12-01"` - Specific date
- `"1 week ago"` - Relative time
- `"yesterday"` - Relative day
- `"2023-12-01 14:30"` - Date and time

### `gitwrite diff`

Compare different versions of your work.

**Syntax:**
```bash
gitwrite diff [reference1] [reference2] [options]
```

**Options:**
- `--files FILE...` - Compare only specific files
- `--word-diff` - Show word-level differences
- `--stat` - Show file change statistics only
- `--name-only` - Show only changed file names
- `--since-last-save` - Compare with last save
- `--no-color` - Disable colored output

**Examples:**
```bash
# Changes since last save
gitwrite diff

# Compare two explorations
gitwrite diff main alternative-ending

# Word-level diff of specific file
gitwrite diff --word-diff chapters/chapter1.md

# Compare with specific save
gitwrite diff a4f7b8c

# Statistics only
gitwrite diff --stat main alternative-ending
```

**Reference Formats:**
- `main` - Main story line
- `exploration-name` - Specific exploration
- `a4f7b8c` - Save ID (commit hash)
- `first-draft` - Tag name
- `HEAD~1` - Previous save

## Exploration Commands

### `gitwrite explore`

Manage explorations (alternative versions of your work).

**Syntax:**
```bash
gitwrite explore <subcommand> [options]
```

### `gitwrite explore create`

Create a new exploration to try different approaches.

**Syntax:**
```bash
gitwrite explore create <name> [options]
```

**Options:**
- `--description TEXT` - Description of what you're exploring
- `--from-commit ID` - Start from specific save point
- `--copy-from EXPLORATION` - Copy from another exploration
- `--switch` - Switch to new exploration immediately

**Examples:**
```bash
# Basic exploration
gitwrite explore create alternative-ending

# With description
gitwrite explore create first-person \
  --description "Trying first-person narration"

# From specific point in history
gitwrite explore create rewrite-ending \
  --from-commit a4f7b8c

# Copy from another exploration
gitwrite explore create ending-v2 \
  --copy-from alternative-ending

# Create and switch immediately
gitwrite explore create different-tone --switch
```

### `gitwrite explore list`

List all explorations in the project.

**Syntax:**
```bash
gitwrite explore list [options]
```

**Options:**
- `--detailed` - Show detailed information
- `--active-only` - Show only active explorations
- `--format FORMAT` - Output format: `table`, `json`

**Examples:**
```bash
# Basic list
gitwrite explore list

# Detailed information
gitwrite explore list --detailed
```

### `gitwrite explore switch`

Switch to a different exploration.

**Syntax:**
```bash
gitwrite explore switch <name> [options]
```

**Options:**
- `--create` - Create exploration if it doesn't exist
- `--force` - Switch even with unsaved changes

**Examples:**
```bash
# Switch to exploration
gitwrite explore switch alternative-ending

# Switch to main story
gitwrite explore switch main

# Create and switch if doesn't exist
gitwrite explore switch new-idea --create
```

### `gitwrite explore merge`

Merge an exploration back into another exploration.

**Syntax:**
```bash
gitwrite explore merge <source> [target] [options]
```

**Options:**
- `--message TEXT` - Custom merge message
- `--no-commit` - Merge but don't commit automatically
- `--strategy STRATEGY` - Merge strategy: `auto`, `manual`, `ours`, `theirs`

**Examples:**
```bash
# Merge into current exploration
gitwrite explore merge alternative-ending

# Merge into specific exploration
gitwrite explore merge alternative-ending main

# Custom merge message
gitwrite explore merge alternative-ending \
  --message "Incorporating dramatic ending"
```

### `gitwrite explore delete`

Delete an exploration that's no longer needed.

**Syntax:**
```bash
gitwrite explore delete <name> [options]
```

**Options:**
- `--force` - Delete even if not merged
- `--keep-saves` - Keep save history but remove exploration

**Examples:**
```bash
# Delete merged exploration
gitwrite explore delete old-idea

# Force delete unmerged exploration
gitwrite explore delete failed-experiment --force
```

## Export Commands

### `gitwrite export`

Export your work to various publication formats.

**Syntax:**
```bash
gitwrite export <format> [options]
```

**Supported Formats:** `epub`, `pdf`, `docx`, `html`, `latex`, `markdown`

### `gitwrite export epub`

Export to EPUB format for e-readers.

**Syntax:**
```bash
gitwrite export epub [options]
```

**Options:**
- `--title TEXT` - Book title (default: project name)
- `--author TEXT` - Author name (default: project author)
- `--cover PATH` - Cover image file
- `--output PATH` - Output file path
- `--template NAME` - Export template
- `--metadata PATH` - Metadata file (YAML/JSON)
- `--css PATH` - Custom CSS file
- `--toc-depth N` - Table of contents depth

**Examples:**
```bash
# Basic EPUB export
gitwrite export epub

# Full customization
gitwrite export epub \
  --title "My Great Novel" \
  --author "Jane Writer" \
  --cover cover.jpg \
  --output "my-novel-v1.epub"

# With custom template
gitwrite export epub --template professional
```

### `gitwrite export pdf`

Export to PDF format for print.

**Syntax:**
```bash
gitwrite export pdf [options]
```

**Options:**
- `--title TEXT` - Document title
- `--author TEXT` - Author name
- `--output PATH` - Output file path
- `--template NAME` - LaTeX template
- `--paper-size SIZE` - Paper size: `letter`, `a4`, `legal`
- `--margins SIZE` - Margin size (e.g., "1in", "2cm")
- `--font-family FONT` - Font family
- `--font-size SIZE` - Font size in points
- `--line-spacing FACTOR` - Line spacing factor

**Examples:**
```bash
# Basic PDF
gitwrite export pdf

# Custom formatting
gitwrite export pdf \
  --paper-size a4 \
  --margins "1.5in" \
  --font-family "Times New Roman" \
  --font-size 12
```

### `gitwrite export docx`

Export to Microsoft Word format.

**Syntax:**
```bash
gitwrite export docx [options]
```

**Options:**
- `--title TEXT` - Document title
- `--author TEXT` - Author name
- `--output PATH` - Output file path
- `--template PATH` - Word template file
- `--reference-doc PATH` - Reference document for styles

**Examples:**
```bash
# Basic Word document
gitwrite export docx

# With custom template
gitwrite export docx --template publisher-format.docx
```

### `gitwrite export all`

Export to multiple formats simultaneously.

**Syntax:**
```bash
gitwrite export all [options]
```

**Options:**
- `--formats FORMAT...` - Specific formats to export
- `--output-dir PATH` - Output directory
- `--prefix TEXT` - File name prefix

**Examples:**
```bash
# Export to all supported formats
gitwrite export all

# Specific formats
gitwrite export all --formats epub pdf docx

# Custom output directory
gitwrite export all --output-dir exports/
```

## Collaboration Commands

### `gitwrite collaborate`

Manage project collaboration and permissions.

**Syntax:**
```bash
gitwrite collaborate <subcommand> [options]
```

### `gitwrite collaborate invite`

Invite collaborators to your project.

**Syntax:**
```bash
gitwrite collaborate invite <email> [options]
```

**Options:**
- `--role ROLE` - User role: `owner`, `editor`, `writer`, `beta-reader`
- `--message TEXT` - Invitation message
- `--expires DURATION` - Invitation expiration time

**Examples:**
```bash
# Invite editor
gitwrite collaborate invite editor@example.com --role editor

# Invite beta reader with message
gitwrite collaborate invite reader@example.com \
  --role beta-reader \
  --message "Please review chapters 1-5"
```

### `gitwrite collaborate list`

List current collaborators and their roles.

**Syntax:**
```bash
gitwrite collaborate list [options]
```

**Examples:**
```bash
gitwrite collaborate list
```

## Annotation Commands

### `gitwrite annotations`

Manage feedback and comments on your work.

**Syntax:**
```bash
gitwrite annotations <subcommand> [options]
```

### `gitwrite annotations list`

List annotations and feedback.

**Syntax:**
```bash
gitwrite annotations list [options]
```

**Options:**
- `--file PATH` - Show annotations for specific file
- `--author TEXT` - Show annotations by specific person
- `--type TYPE` - Show specific type: `comment`, `suggestion`, `correction`
- `--status STATUS` - Show by status: `open`, `resolved`, `rejected`
- `--new` - Show only new/unread annotations

**Examples:**
```bash
# All annotations
gitwrite annotations list

# New feedback
gitwrite annotations list --new

# Feedback on specific chapter
gitwrite annotations list --file chapters/chapter1.md

# Editor's suggestions
gitwrite annotations list --author "editor@example.com"
```

### `gitwrite annotations show`

Show detailed view of an annotation.

**Syntax:**
```bash
gitwrite annotations show <annotation_id> [options]
```

### `gitwrite annotations resolve`

Mark an annotation as resolved.

**Syntax:**
```bash
gitwrite annotations resolve <annotation_id> [options]
```

**Options:**
- `--message TEXT` - Resolution message
- `--action ACTION` - Action taken: `accepted`, `rejected`, `modified`

## Utility Commands

### `gitwrite stats`

Show writing statistics and analytics.

**Syntax:**
```bash
gitwrite stats [options]
```

**Options:**
- `--period PERIOD` - Time period: `today`, `week`, `month`, `all`
- `--detailed` - Show detailed breakdown
- `--export PATH` - Export statistics to file

**Examples:**
```bash
# Today's stats
gitwrite stats --period today

# Weekly summary
gitwrite stats --period week --detailed
```

### `gitwrite clean`

Clean up project files and optimize repository.

**Syntax:**
```bash
gitwrite clean [options]
```

**Options:**
- `--dry-run` - Show what would be cleaned without doing it
- `--force` - Force cleanup of protected files
- `--optimize` - Optimize Git repository

### `gitwrite backup`

Create backups of your project.

**Syntax:**
```bash
gitwrite backup [path] [options]
```

**Options:**
- `--compress` - Create compressed archive
- `--include-history` - Include full Git history
- `--exclude PATTERN` - Exclude files matching pattern

### `gitwrite help`

Get help for GitWrite commands.

**Syntax:**
```bash
gitwrite help [command]
```

**Examples:**
```bash
# General help
gitwrite help

# Command-specific help
gitwrite help save
gitwrite help explore create
```

## Global Options

These options work with all commands:

- `--verbose` - Enable verbose output
- `--quiet` - Suppress non-essential output
- `--no-color` - Disable colored output
- `--config PATH` - Use custom configuration file
- `--help` - Show command help

**Examples:**
```bash
# Verbose save
gitwrite --verbose save "Updated chapter 1"

# Quiet export
gitwrite --quiet export epub

# Custom config
gitwrite --config /path/to/config.yaml status
```

## Exit Codes

GitWrite commands return standard exit codes:

- `0` - Success
- `1` - General error
- `2` - Misuse of command (wrong syntax)
- `3` - Repository error (not a GitWrite project)
- `4` - Network error (collaboration features)
- `5` - Permission error
- `6` - Conflict error (merge conflicts)

---

*This command reference provides comprehensive documentation for all GitWrite CLI commands. Use `gitwrite help <command>` for additional details and examples for any specific command.*