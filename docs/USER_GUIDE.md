# GitWrite User Guide

*A Writer-Friendly Git Version Control System*

## Table of Contents
1. [Getting Started](#getting-started)
2. [Basic Writing Workflow](#basic-writing-workflow)
3. [Using the Web Interface](#using-the-web-interface)
4. [Exploring Ideas with Branches](#exploring-ideas-with-branches)
5. [Collaborative Writing](#collaborative-writing)
6. [Managing Feedback](#managing-feedback)
7. [Exporting Your Work](#exporting-your-work)
8. [Troubleshooting](#troubleshooting)

## Getting Started

### What is GitWrite?

GitWrite is a version control system designed specifically for writers. It uses Git under the hood but presents writer-friendly terminology and workflows. Think of it as "track changes" for serious writers.

**Writer-Friendly Terms:**
- **Project** = Repository (your writing project)
- **Save** = Commit (saving a version of your work)
- **Exploration** = Branch (trying different approaches)
- **Combine** = Merge (bringing ideas together)

### Installation

#### Prerequisites
- Python 3.10 or higher
- Node.js 16 or higher (for web interface)
- Git (installed automatically with GitWrite)

#### Quick Setup
```bash
# Clone the project
git clone <gitwrite-repository-url>
cd git-write

# Install Python dependencies
poetry install

# Start the API server
poetry run uvicorn gitwrite_api.main:app --reload --port 8000

# Start the web interface (in another terminal)
cd gitwrite-web
npm install
npm run dev
```

Your GitWrite system will be available at:
- Web Interface: http://localhost:5174
- API Documentation: http://localhost:8000/docs

### Default Login Credentials

For the demo system:
- **Username:** johndoe
- **Password:** secret

## Basic Writing Workflow

### 1. Starting a New Project

#### Using the Command Line
```bash
# Initialize a new writing project
gitwrite init "MyNovel"

# This creates:
# - A new directory "MyNovel"
# - Git repository structure
# - Writing-friendly folders (drafts/, notes/)
# - Metadata file for project information
```

#### Using the Web Interface
1. Open the web interface at http://localhost:5174
2. Log in with your credentials
3. Click "Create New Project" (if available)
4. Enter your project name

### 2. Writing and Saving Your Work

#### Command Line Workflow
```bash
# Navigate to your project
cd MyNovel

# Write your content (use any text editor)
echo "Chapter 1: The Beginning" > drafts/chapter1.md

# Save your progress
gitwrite save "Started Chapter 1"

# Continue writing
echo "It was a dark and stormy night..." >> drafts/chapter1.md
gitwrite save "Added opening line to Chapter 1"
```

#### Web Interface Workflow
1. Navigate to your project in the web interface
2. Browse to the file you want to edit
3. Click on the file to view/edit
4. Make your changes
5. Save with a descriptive message

### 3. Viewing Your History

#### Command Line
```bash
# See your writing history
gitwrite history

# See detailed history with changes
gitwrite history -n 10  # Last 10 saves
```

#### Web Interface
1. Click "View Branch History" in your project
2. Browse through your saves
3. Click "Compare to Parent" to see what changed
4. View specific versions by clicking on commit links

## Using the Web Interface

### Navigation Overview

#### Main Dashboard
- **Projects List**: Shows all your writing projects
- **Recent Activity**: Your latest work across projects
- **Quick Actions**: Create new projects, access settings

#### Project Browser
- **File Tree**: Navigate your project structure
- **Repository Status**: Current branch, last save info
- **Action Buttons**: History, settings, branch management

#### File Viewer
- **Content Display**: Syntax-highlighted content
- **Version Navigation**: Switch between different saves
- **Annotation Panel**: View and manage feedback (when available)

### Key Features

#### 1. Repository Browsing
- Click on folders to navigate
- Click on files to view content
- Use breadcrumbs to navigate back
- See file sizes and types at a glance

#### 2. History Viewing
- Timeline of all your saves
- Compare any two versions
- See exactly what changed between saves
- Word-by-word comparison highlighting

#### 3. Branch Management
- Create new explorations (branches)
- Switch between different approaches
- Merge successful experiments back to main

## Exploring Ideas with Branches

### What are Explorations?

Explorations (branches) let you try different approaches to your writing without affecting your main work. Think of them as "what if" scenarios.

### Creating an Exploration

#### Command Line
```bash
# Create and switch to a new exploration
gitwrite explore "alternate-ending"

# Make changes
echo "A completely different ending..." > drafts/alternate-chapter10.md
gitwrite save "Trying a happier ending"

# Switch back to main work
gitwrite switch main
```

#### Web Interface
1. Click "Manage Branches" in your project
2. Enter a name for your exploration (e.g., "darker-tone")
3. Click "Create Branch"
4. Make your changes
5. Save as normal

### Combining Ideas

When you like changes from an exploration:

#### Command Line
```bash
# Switch to main branch
gitwrite switch main

# Combine the exploration
gitwrite combine alternate-ending
```

#### Web Interface
1. Go to "Manage Branches"
2. Select the branch to merge
3. Click "Merge Branch"
4. Resolve any conflicts if they arise

## Collaborative Writing

### Roles in GitWrite

- **Owner**: Full control over the project
- **Editor**: Can make changes and manage reviews
- **Writer**: Can write and save content
- **Beta Reader**: Can view and provide feedback

### Sharing Your Work

#### Setting Up Collaboration
1. Initialize your project with a remote repository (GitHub, GitLab, etc.)
2. Share repository access with collaborators
3. Assign appropriate roles to team members

#### Syncing Changes
```bash
# Get latest changes from collaborators
gitwrite sync

# This will:
# - Fetch changes from the remote
# - Merge changes automatically when possible
# - Push your changes back
```

### Review Workflow

#### For Editors
1. Create a review branch: `gitwrite explore "editor-review"`
2. Make suggested changes
3. Save with clear messages: `gitwrite save "Suggested: improve dialogue in Ch 3"`
4. Push for author review

#### For Authors
1. Review editor suggestions: `gitwrite review editor-review`
2. See all changes in the web interface
3. Cherry-pick specific improvements:
   ```bash
   # Apply only specific changes
   gitwrite cherry-pick <commit-hash>
   ```

## Managing Feedback

### Beta Reader Workflow

#### Providing Feedback
1. Access the project through the web interface
2. Navigate to files you want to comment on
3. Use the annotation system to provide feedback
4. Mark text sections and add comments

#### Viewing Annotations
In the web interface:
1. Open any file
2. Annotations appear in the sidebar
3. Click annotations to see details
4. Authors can accept/reject suggestions

### Author Response to Feedback

#### Command Line
```bash
# See all feedback
gitwrite annotations list

# Process feedback
gitwrite annotations accept <annotation-id>
gitwrite annotations reject <annotation-id>
```

#### Web Interface
1. View files with the annotation sidebar
2. Click "Accept" or "Reject" on each suggestion
3. Changes are automatically saved
4. Feedback is marked as processed

## Exporting Your Work

### EPUB Export

#### Command Line
```bash
# Export current version to EPUB
gitwrite export epub output.epub --files "chapter1.md,chapter2.md,chapter3.md"

# Export specific version
gitwrite export epub novel-v1.epub --commit "v1.0-final" --files "*.md"
```

#### Web Interface
1. Navigate to your project
2. Click "Export" or "Settings"
3. Select EPUB format
4. Choose files to include
5. Download the generated file

### Supported Formats
- **EPUB**: E-book format (completed)
- **PDF**: Formatted document (planned)
- **DOCX**: Microsoft Word format (planned)
- **HTML**: Web page format (via existing tools)

## Troubleshooting

### Common Issues

#### "Repository not found" Error
**Problem**: GitWrite can't find your project
**Solution**: 
- Make sure you're in the right directory
- Check if the project was initialized: `ls -la` should show `.git` folder
- Re-initialize if needed: `gitwrite init`

#### "Authentication failed" in Web Interface
**Problem**: Can't log into the web interface
**Solution**:
- Check if API server is running on port 8000
- Verify credentials (default: johndoe/secret)
- Clear browser cache and cookies

#### "Merge conflicts" When Combining
**Problem**: GitWrite can't automatically combine changes
**Solution**:
```bash
# See which files have conflicts
gitwrite status

# Edit conflicted files manually
# Look for conflict markers: <<<<<<<, =======, >>>>>>>
# Remove markers and choose the version you want

# Save the resolved version
gitwrite save "Resolved merge conflicts"
```

#### Web Interface Shows "Loading..." Forever
**Problem**: Frontend can't connect to API
**Solution**:
- Check that API server is running: `curl http://localhost:8000/docs`
- Verify web app environment: check `.env` file in `gitwrite-web/`
- Restart both servers

### Getting Help

#### Command Line Help
```bash
# General help
gitwrite --help

# Help for specific commands
gitwrite save --help
gitwrite explore --help
```

#### Log Files
- API logs: Check terminal where `uvicorn` is running
- Web app logs: Check browser developer console (F12)

#### Community Support
- Check project documentation in the `docs/` folder
- Review API documentation at http://localhost:8000/docs
- Submit issues through the project repository

### Performance Tips

#### For Large Projects
- Keep individual files reasonably sized (< 1MB text files)
- Use `.gitignore` to exclude generated files
- Regularly clean up old explorations you don't need

#### For Collaboration
- Pull changes frequently: `gitwrite sync`
- Use descriptive save messages
- Coordinate major structural changes with your team

## Advanced Features

### Custom Workflows

#### Academic Writing
- Use `notes/` folder for research and citations
- Create exploration branches for different argument approaches
- Use annotations for peer review feedback

#### Fiction Writing
- Create character branches for different character development
- Use exploration branches for plot alternatives
- Export chapters individually for beta reading

#### Technical Writing
- Use structured folder organization
- Version control images and diagrams alongside text
- Create review workflows for technical accuracy

### Integration with Other Tools

#### Text Editors
GitWrite works with any text editor:
- **VS Code**: Excellent Git integration and Markdown support
- **Vim/Emacs**: Command-line workflow fits naturally
- **Scrivener**: Export to plain text, use GitWrite for version control
- **Google Docs**: Copy final versions to GitWrite for version control

#### Writing Tools
- **Grammarly**: Use for final editing passes
- **Hemingway Editor**: For style improvements
- **Pandoc**: Advanced export format conversion

---

## Quick Reference

### Essential Commands
```bash
gitwrite init [project-name]     # Start new project
gitwrite save "message"          # Save current work
gitwrite history                 # View save history
gitwrite explore "branch-name"   # Try new approach
gitwrite switch "branch-name"    # Switch approaches
gitwrite combine "branch-name"   # Merge successful changes
gitwrite sync                    # Sync with collaborators
```

### Web Interface URLs
- Main interface: http://localhost:5174
- API documentation: http://localhost:8000/docs
- Login: johndoe / secret (default demo)

### File Organization
```
MyProject/
├── drafts/          # Your main writing
├── notes/           # Research and planning
├── metadata.yml     # Project information
└── .gitignore       # Files to ignore
```

This completes your GitWrite User Guide. The system is designed to make version control accessible to writers while providing the power and reliability of Git underneath.