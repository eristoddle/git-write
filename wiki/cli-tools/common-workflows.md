# Common Workflows

This document outlines the most common GitWrite CLI workflows that writers use in their daily practice. These workflows demonstrate how GitWrite's commands work together to support different writing processes and collaboration patterns.

## Overview

GitWrite CLI workflows are designed around common writing activities:
- **Daily Writing Sessions**: Regular writing and saving progress
- **Project Management**: Starting, organizing, and maintaining writing projects
- **Collaboration**: Working with editors, beta readers, and co-authors
- **Revision and Editing**: Managing drafts and incorporating feedback
- **Publishing Preparation**: Finalizing manuscripts for submission or publication

```
Workflow Categories
    │
    ├─ Individual Writing
    │   ├─ Daily writing sessions
    │   ├─ Project organization
    │   └─ Progress tracking
    │
    ├─ Collaboration
    │   ├─ Sharing and permissions
    │   ├─ Feedback incorporation
    │   └─ Co-authoring
    │
    ├─ Revision Management
    │   ├─ Draft versioning
    │   ├─ Exploration branching
    │   └─ Change tracking
    │
    └─ Publishing
        ├─ Manuscript preparation
        ├─ Format conversion
        └─ Submission packaging
```

## Individual Writing Workflows

### 1. Starting a New Project

```bash
# Create a new repository for your writing project
gitwrite create my-novel --description "My first novel project"

# Navigate to the project directory
cd my-novel

# Set up project structure
gitwrite init --template novel

# Configure project-specific settings
gitwrite config set writing.target_word_count 80000
gitwrite config set writing.daily_goal 500

# Create initial files
gitwrite new chapter chapters/chapter-01.md --template chapter
gitwrite new outline outline.md --template outline
gitwrite new notes notes/characters.md

# Add project description and goals
echo "# My Novel Project

## Overview
A compelling story about...

## Goals
- Target length: 80,000 words
- Daily goal: 500 words
- Target completion: December 2024

## Structure
- 20 chapters
- 3 acts
- Character-driven plot
" > README.md

# Make initial save
gitwrite save "Initial project setup" --add-all
```

### 2. Daily Writing Session

```bash
# Start writing session
gitwrite session start

# Check current status
gitwrite status

# Open your current chapter for editing
gitwrite edit chapters/chapter-05.md

# While writing, save progress periodically
gitwrite save "Added dialogue scene between protagonist and mentor"

# Check word count progress
gitwrite stats --today

# At end of session, create a milestone if you hit a goal
gitwrite milestone "Completed Chapter 5" --word-count-goal 2500

# End writing session
gitwrite session end --summary "Productive session, completed Chapter 5 dialogue"
```

### 3. Organizing and Restructuring

```bash
# View current project structure
gitwrite list --tree

# Move files to better organize content
gitwrite move chapters/old-chapter-03.md archive/unused-scenes.md

# Rename files following naming convention
gitwrite rename chapters/chapter-3.md chapters/chapter-03-the-discovery.md

# Create new structural elements
gitwrite new part parts/part-02-rising-action.md
gitwrite new appendix appendices/character-glossary.md

# Update project outline with changes
gitwrite edit outline.md

# Save organizational changes
gitwrite save "Restructured project organization and naming"
```

### 4. Progress Tracking and Goal Management

```bash
# Check overall project statistics
gitwrite stats --comprehensive

# View writing progress over time
gitwrite progress --chart --last 30days

# Set and track writing goals
gitwrite goals set daily 500
gitwrite goals set weekly 3500
gitwrite goals set monthly 15000

# Check goal achievement
gitwrite goals check

# View detailed writing analytics
gitwrite analytics --report monthly

# Create progress milestone
gitwrite milestone "Reached 50,000 words" --celebration "Halfway point!"
```

## Collaboration Workflows

### 1. Sharing Project with Collaborators

```bash
# Make repository available for collaboration
gitwrite share enable

# Invite collaborators with specific roles
gitwrite invite editor@example.com --role editor --message "Please review my latest chapters"
gitwrite invite betareader@example.com --role beta_reader --files "chapters/chapter-*.md"

# Set collaboration preferences
gitwrite config set collaboration.auto_pull true
gitwrite config set collaboration.notification_level important

# Create collaboration guidelines
echo "# Collaboration Guidelines

## For Editors
- Use comments for suggestions
- Track changes in separate exploration
- Focus on story structure and character development

## For Beta Readers
- Provide feedback on readability and engagement
- Mark confusing sections
- Note emotional reactions
" > COLLABORATION.md

gitwrite save "Added collaboration guidelines"
```

### 2. Receiving and Managing Feedback

```bash
# Check for new feedback and comments
gitwrite feedback list --new

# View specific feedback item
gitwrite feedback show comment-123

# Respond to feedback
gitwrite feedback reply comment-123 "Great suggestion! I'll incorporate this change."

# Apply suggested changes
gitwrite feedback apply suggestion-456 --create-exploration

# Mark feedback as resolved
gitwrite feedback resolve comment-123 --message "Implemented suggested character motivation"

# Thank collaborators
gitwrite feedback thank betareader@example.com --message "Your insights were invaluable"
```

### 3. Co-authoring Workflow

```bash
# Create shared exploration for collaborative writing
gitwrite exploration create "collaborative-chapter-12" --description "Co-writing Chapter 12 with John"

# Switch to collaboration exploration
gitwrite exploration switch collaborative-chapter-12

# Check what others are working on
gitwrite activity --collaborators

# Work on your section
gitwrite edit chapters/chapter-12.md

# Save your contributions with clear attribution
gitwrite save "Added protagonist's perspective (Jane)" --co-author "john@example.com"

# Sync with collaborator changes
gitwrite sync --resolve-conflicts interactive

# When ready, merge collaborative work
gitwrite exploration merge collaborative-chapter-12 --message "Completed collaborative Chapter 12"
```

## Revision Management Workflows

### 1. Creating and Managing Draft Versions

```bash
# Create exploration for major revision
gitwrite exploration create "second-draft-revision" --description "Structural changes for second draft"

# Switch to revision exploration
gitwrite exploration switch second-draft-revision

# Make significant changes
gitwrite edit chapters/chapter-01.md
gitwrite edit outline.md

# Save revision progress
gitwrite save "Restructured opening chapter for better pacing"

# Compare with original version
gitwrite diff main second-draft-revision --summary

# View word count changes
gitwrite stats --compare main

# Create milestone for draft completion
gitwrite milestone "Second Draft Complete" --exploration second-draft-revision

# Merge when satisfied
gitwrite exploration merge second-draft-revision --delete-after-merge
```

### 2. Experimental Writing

```bash
# Create exploration for trying different approach
gitwrite exploration create "alternate-ending" --description "Exploring different resolution"

# Work on experimental version
gitwrite edit chapters/chapter-20.md

# Save experimental work
gitwrite save "Tried more optimistic ending"

# Compare different approaches
gitwrite diff main alternate-ending --visual

# If not satisfied, abandon exploration
gitwrite exploration abandon alternate-ending --reason "Original ending works better"

# Or if satisfied, merge the changes
gitwrite exploration merge alternate-ending --strategy theirs
```

### 3. Incorporating Editorial Feedback

```bash
# Create exploration for editorial changes
gitwrite exploration create "editorial-round-1" --from-save milestone-first-draft

# Review editor's feedback
gitwrite feedback list --author editor@example.com --priority high

# Work through feedback systematically
gitwrite feedback show --interactive

# Make changes based on feedback
gitwrite edit chapters/chapter-03.md

# Save with reference to feedback
gitwrite save "Addressed editor feedback on character motivation" --reference feedback-789

# Mark feedback as addressed
gitwrite feedback resolve feedback-789 --commit-reference HEAD

# Generate summary of changes made
gitwrite changelog --since milestone-first-draft --format editorial

# When all feedback addressed, merge changes
gitwrite exploration merge editorial-round-1 --message "Incorporated all Round 1 editorial feedback"
```

## Publishing Preparation Workflows

### 1. Manuscript Finalization

```bash
# Create final manuscript exploration
gitwrite exploration create "final-manuscript" --description "Publication-ready version"

# Perform final editing pass
gitwrite edit chapters/*.md

# Run comprehensive checks
gitwrite validate --spelling --grammar --formatting

# Check manuscript statistics
gitwrite stats --final-count

# Create publication-ready exports
gitwrite export --format epub --output manuscript.epub
gitwrite export --format pdf --template manuscript --output manuscript.pdf
gitwrite export --format docx --template submission --output manuscript.docx

# Create final milestone
gitwrite milestone "Final Manuscript" --tag final-v1.0 --exploration final-manuscript

# Merge final version
gitwrite exploration merge final-manuscript --tag submission-ready
```

### 2. Submission Package Creation

```bash
# Create submission directory
mkdir submission-package

# Export in required formats
gitwrite export --format docx --template submission \
    --output submission-package/manuscript.docx \
    --include-title-page \
    --double-space

# Generate cover letter template
gitwrite template cover-letter --output submission-package/cover-letter-template.md

# Create synopsis
gitwrite synopsis generate --length 500 --output submission-package/synopsis.md

# Generate author bio
gitwrite author-bio --length 100 --output submission-package/author-bio.md

# Create submission checklist
gitwrite submission checklist --publisher "Publisher Name" \
    --output submission-package/checklist.md

# Package everything
tar -czf submission-package.tar.gz submission-package/

# Create submission record
gitwrite submission record "Publisher Name" \
    --package submission-package.tar.gz \
    --guidelines "https://publisher.com/guidelines" \
    --deadline "2024-12-31"
```

### 3. Self-Publishing Workflow

```bash
# Prepare for self-publishing
gitwrite exploration create "self-publishing-prep"

# Create marketing materials
gitwrite marketing blurb --length 150 --output marketing/blurb.md
gitwrite marketing keywords --genre "literary fiction" --output marketing/keywords.txt

# Format for different platforms
gitwrite export --format epub3 --output releases/book.epub
gitwrite export --format pdf --template print --output releases/book-print.pdf
gitwrite export --format mobi --output releases/book.mobi

# Generate metadata files
gitwrite metadata generate --format onix --output metadata/

# Create promotional materials
gitwrite promo social-media --platforms twitter,instagram --output promo/
gitwrite promo press-release --template launch --output promo/press-release.md

# Track version and release
gitwrite tag "v1.0.0-release" --message "First published edition"
gitwrite release create v1.0.0 --title "First Edition" --files releases/*
```

## Advanced Workflow Patterns

### 1. Multi-Project Management

```bash
# List all your writing projects
gitwrite projects list

# Switch between projects
gitwrite projects switch my-novel
gitwrite projects switch short-story-collection

# Cross-project operations
gitwrite projects stats --all
gitwrite projects backup --all --output backups/

# Share resources between projects
gitwrite resource link ../shared/character-template.md templates/
```

### 2. Automated Workflows

```bash
# Set up automated daily backups
gitwrite automation schedule backup --daily --time "23:00"

# Configure automatic milestone creation
gitwrite automation milestone --trigger word_count --threshold 5000

# Set up progress notifications
gitwrite automation notify --daily-summary --goal-reminders

# Create writing habit tracking
gitwrite automation habit track --daily-goal 500 --reminder "09:00"
```

### 3. Integration Workflows

```bash
# Sync with external tools
gitwrite integration scrivener import --project my-novel.scriv
gitwrite integration google-docs sync --document "Novel Outline"

# Export to publishing platforms
gitwrite publish kindle --draft --metadata metadata.json
gitwrite publish medium --chapter chapters/chapter-01.md --draft

# Connect with writing communities
gitwrite community share --platform critique-circle --chapter chapters/latest.md
```

## Troubleshooting Common Issues

### 1. Handling Conflicts

```bash
# When conflicts arise during collaboration
gitwrite status  # Check for conflicts
gitwrite conflicts list  # See conflicted files
gitwrite conflicts resolve chapters/chapter-05.md --interactive
gitwrite save "Resolved collaboration conflict in Chapter 5"
```

### 2. Recovery Workflows

```bash
# Recover accidentally deleted content
gitwrite recover file chapters/lost-chapter.md --from last-week
gitwrite recover exploration deleted-exploration --confirm

# Restore from backup
gitwrite backup restore --date 2024-01-15 --confirm
```

### 3. Performance Optimization

```bash
# Clean up large repositories
gitwrite cleanup --remove-temp-files --optimize-history

# Compress large files
gitwrite optimize --compress-images --remove-duplicates
```

---

*These workflows demonstrate how GitWrite CLI commands work together to support real writing processes. Writers can adapt these patterns to their specific needs while maintaining version control, collaboration, and professional manuscript management throughout their creative process.*