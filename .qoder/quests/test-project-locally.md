# GitWrite Local Testing Guide

## Overview

This comprehensive guide provides step-by-step instructions for testing the complete GitWrite functionality locally. The guide covers setting up the development environment, running all components (CLI, API, and Web interface), and walking through a complete novel writing workflow including author, editor, and beta reader interactions.

GitWrite is a multi-component writing platform consisting of:
- **Backend API**: FastAPI-based REST service
- **Frontend Web App**: React/TypeScript interface
- **CLI Tool**: Python Click-based command line interface
- **TypeScript SDK**: npm package for API integration
- **Core Engine**: Python library for Git operations

## Prerequisites

Before starting the testing process, ensure your system has the following dependencies installed:

### System Requirements
- **Python**: 3.10 or higher
- **Node.js**: 16 or higher
- **Git**: 2.20 or higher
- **Poetry**: Python dependency management tool
- **Pandoc**: Document conversion tool (for export functionality)

### System Dependencies (Linux/Ubuntu)
```bash
sudo apt-get update
sudo apt-get install -y libgit2-dev build-essential pkg-config
sudo apt-get install pandoc
```

### System Dependencies (macOS)
```bash
brew install libgit2 pandoc
```

### Install Poetry
```bash
curl -sSL https://install.python-poetry.org | python3 -
# Add to PATH if needed
export PATH="$HOME/.local/bin:$PATH"
```

## Environment Setup

### 1. Clone and Navigate to Repository
```bash
git clone https://github.com/eristoddle/git-write.git
cd git-write
```

### 2. Backend Setup (Python/FastAPI)
```bash
# Install Python dependencies
poetry install

# Verify installation by checking CLI
poetry run python -m gitwrite_cli --help
```

### 3. Frontend Setup (React/TypeScript)
```bash
# Navigate to web frontend
cd gitwrite-web

# Install Node.js dependencies
npm install

# Return to project root
cd ..
```

### 4. TypeScript SDK Setup
```bash
# Navigate to SDK directory
cd gitwrite_sdk

# Install and build SDK
npm install
npm run build

# Return to project root
cd ..
```

## Running the Application Components

### Terminal 1: Start Backend API Server
```bash
# From project root
poetry run uvicorn gitwrite_api.main:app --reload --host 0.0.0.0 --port 8000

# Expected output:
# INFO:     Will watch for changes in these directories: ['/path/to/git-write']
# INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Verify API is running:
```bash
curl http://localhost:8000/docs
# Should return OpenAPI documentation HTML
```

### Terminal 2: Start Frontend Development Server
```bash
# From project root
cd gitwrite-web
npm run dev

# Expected output:
# VITE v5.x.x ready in xxx ms
# ➜  Local:   http://localhost:5173/
# ➜  Network: use --host to expose
```

### Terminal 3: CLI Testing Terminal
Keep this terminal available for CLI command testing throughout the workflow.

## Complete Novel Writing Workflow Test

This section walks through a comprehensive test scenario involving creating a novel project, multiple author interactions, editor feedback, and beta reader annotations.

### Phase 1: Project Initialization and Initial Writing

#### 1.1 Initialize Novel Project via CLI
```bash
# Create new writing project
poetry run python -m gitwrite_cli init "mystery-novel"

# Navigate to project directory
cd mystery-novel

# Verify project structure
ls -la
# Expected structure:
# drizzle/
# .git/
# .gitignore
# notes/
# metadata.yml
```

#### 1.2 Examine Project Structure
```bash
# Check metadata file
cat metadata.yml
# Should contain project configuration

# Verify Git initialization
git status
# Should show initialized repository

# Check .gitignore contents
cat .gitignore
# Should contain writing-specific ignore patterns
```

#### 1.3 Create Initial Chapter Content
```bash
# Create first chapter
cat > drafts/chapter01.md << 'EOF'
# Chapter 1: The Discovery

Detective Sarah Chen stared at the peculiar symbol carved into the oak tree. In her fifteen years on the force, she had never seen anything quite like it. The morning mist clung to the forest floor, creating an ethereal atmosphere that made the crime scene feel almost supernatural.

"What do you make of this, Chen?" asked her partner, Detective Mike Rodriguez, pointing at the symbol with his pen.

Sarah pulled out her phone and took several photos from different angles. "I'm not sure, but I have a feeling this is just the beginning."
EOF

# Create character notes
cat > notes/characters.md << 'EOF'
# Main Characters

## Detective Sarah Chen
- Age: 38
- Experience: 15 years on the force
- Specialty: Pattern recognition and cold cases
- Background: Former art history major

## Detective Mike Rodriguez
- Age: 42
- Experience: 18 years on the force
- Specialty: Forensics and evidence analysis
- Background: Military police veteran

## The Antagonist
- Identity: Unknown
- Signature: Carved symbols
- Motive: To be revealed
EOF

# Save initial work
poetry run python -m gitwrite_cli save "Initial chapter and character notes"
```

#### 1.4 View Project History
```bash
# Check commit history
poetry run python -m gitwrite_cli history

# Expected output showing:
# - Initial commit with project structure
# - First save with chapter and notes
```

### Phase 2: Author Exploration and Alternative Versions

#### 2.1 Create Alternative Opening
```bash
# Create exploration branch for alternative opening
poetry run python -m gitwrite_cli explore "alternate-opening"

# Modify the opening
cat > drafts/chapter01.md << 'EOF'
# Chapter 1: The Symbol

The symbol appeared overnight.

Detective Sarah Chen crouched beside the ancient oak tree, her breath visible in the cold morning air. Carved deep into the bark was a mark she had never encountered in fifteen years of police work - intricate lines that seemed to shift and dance when she wasn't looking directly at them.

"This wasn't here yesterday," muttered Detective Mike Rodriguez, consulting his notepad. "Groundskeeper walked this path at sunset. Would have noticed something this... prominent."

Sarah traced the air above the carving, careful not to touch it. "Get forensics out here. And Mike?" She stood, brushing dirt from her knees. "Call the university. I want to know if anyone in their archaeology or anthropology departments has seen anything like this."

The symbol seemed to watch them as they worked.
EOF

# Save alternative version
poetry run python -m gitwrite_cli save "More atmospheric opening with mystery buildup"
```

#### 2.2 Compare Versions
```bash
# Compare the two versions
poetry run python -m gitwrite_cli compare main alternate-opening

# Expected output:
# Word-level differences highlighting the changes between versions
```

#### 2.3 Switch Between Versions
```bash
# Switch to main version
poetry run python -m gitwrite_cli switch main

# Verify content
head -n 5 drafts/chapter01.md

# Switch back to alternate version
poetry run python -m gitwrite_cli switch alternate-opening

# Verify alternate content
head -n 5 drafts/chapter01.md
```

#### 2.4 Continue Writing on Alternative Branch
```bash
# Add more content to Chapter 1
cat >> drafts/chapter01.md << 'EOF'

As the forensics team arrived, Sarah noticed something else. The grass around the tree formed a perfect circle, as if it had been pressed down by something heavy. Or someone dancing.

She made a note to research local folklore about the area. Sometimes the oldest stories held the newest clues.
EOF

# Create Chapter 2
cat > drafts/chapter02.md << 'EOF'
# Chapter 2: The Research

Dr. Elena Vasquez adjusted her glasses as she examined the photos on Sarah's phone. As the head of the university's folklore studies department, she had seen plenty of unusual symbols, but this one made her pause.

"This is fascinating," she murmured, zooming in on the image. "The style is reminiscent of pre-Columbian markings, but the execution is too clean, too modern."

Sarah leaned forward. "So it's fake?"

"Not fake. Just... not ancient. Someone with knowledge of historical symbol systems created this recently. The question is why."
EOF

# Save progress
poetry run python -m gitwrite_cli save "Extended Chapter 1 and added Chapter 2"
```

### Phase 3: Web Interface Testing

#### 3.1 Access Web Interface
Open your web browser and navigate to: `http://localhost:5173`

#### 3.2 Authentication Testing
```bash
# Login with test credentials:
# Username: johndoe (Owner role)
# Password: secret
```

#### 3.3 Repository Browser Testing
1. Navigate to the repository browser
2. Verify you can see the "mystery-novel" project
3. Browse the file structure (drafts/, notes/)
4. Open and view chapter01.md and chapter02.md
5. Verify file content matches CLI version

#### 3.4 Branch Management Testing
1. Access the branch management page
2. Verify both branches are visible: "main" and "alternate-opening"
3. Test switching between branches in the web interface
4. Verify file content changes when switching branches

#### 3.5 Commit History Viewing
1. Navigate to commit history view
2. Verify all commits from CLI are visible
3. Check commit messages and timestamps
4. Examine individual commit details

### Phase 4: Editor Workflow Testing

#### 4.1 Create Editor Branch (CLI)
```bash
# Ensure we're on the main branch
poetry run python -m gitwrite_cli switch main

# Create editor branch
git checkout -b editor-suggestions

# Editor makes structural suggestions
cat > drafts/chapter01.md << 'EOF'
# Chapter 1: The Discovery

Detective Sarah Chen examined the peculiar symbol carved into the ancient oak tree. In her fifteen years on the force, she had developed an eye for details that others missed, and this carving was unlike anything in her experience.

The morning mist created an almost supernatural atmosphere around the crime scene, but Sarah forced herself to focus on the facts. Emotions and atmosphere were for writers, not detectives.

"What's your assessment, Chen?" asked Detective Mike Rodriguez, maintaining a respectful distance from the evidence.

Sarah photographed the symbol from multiple angles, ensuring proper lighting and scale references. "I need to research this symbol. It's deliberate, meaningful. Not random vandalism."

She made detailed notes about the carving's depth, tool marks, and orientation. Whatever this symbol meant, it was the key to understanding why they had been called to this remote location.
EOF

# Editor adds narrative notes
cat > notes/editor-feedback.md << 'EOF'
# Structural Editor Notes

## Chapter 1 Revisions
- Removed purple prose ("ethereal atmosphere")
- Strengthened Sarah's character voice - more professional, analytical
- Improved dialogue tags for clarity
- Added specific detective behaviors (note-taking, evidence photography)
- Maintained mystery while grounding in police procedure

## Suggestions for Continuation
- Develop the partnership dynamic between Chen and Rodriguez
- Consider introducing forensics expert as recurring character
- Ensure symbol research feels authentic to police work
- Balance atmospheric writing with procedural accuracy
EOF

# Save editor's changes
git add .
git commit -m "Structural edits: strengthen character voice and police procedure accuracy"
```

#### 4.2 Author Reviews Editor Changes
```bash
# Switch back to main branch to review changes
poetry run python -m gitwrite_cli switch main

# Review editor's branch
poetry run python -m gitwrite_cli review editor-suggestions

# Expected output:
# List of commits available for review/cherry-picking
```

#### 4.3 Selective Integration of Editor Feedback
```bash
# Get the commit hash from the review (replace with actual hash)
EDITOR_COMMIT_HASH=$(git log editor-suggestions --oneline | head -n 1 | cut -d' ' -f1)

# Cherry-pick the editor's changes
poetry run python -m gitwrite_cli cherry-pick $EDITOR_COMMIT_HASH

# Verify the changes were integrated
cat drafts/chapter01.md
# Should show the editor's improved version

# Check that editor notes were also included
cat notes/editor-feedback.md
```

#### 4.4 Test Web Interface Editor Authentication
```bash
# Logout from current session and login as editor:
# Username: editoruser
# Password: secret

# Test editor permissions:
# - Should be able to view repositories
# - Should be able to create annotations
# - Should NOT be able to create new repositories
```

### Phase 5: Beta Reader Workflow and Annotations

#### 5.1 Prepare Beta Reader Version
```bash
# Ensure we're on the main branch with all changes
poetry run python -m gitwrite_cli switch main

# Create a tag for the beta reader version
git tag -a "beta-v1.0" -m "Version for beta reader review"

# Export to EPUB for beta readers (if Pandoc is installed)
poetry run python -m gitwrite_cli export epub --output mystery-novel-beta.epub

# Expected output:
# Successfully exported to mystery-novel-beta.epub
```

#### 5.2 Simulate Beta Reader Feedback (API Testing)
```bash
# Create a beta reader feedback branch
git checkout -b beta-reader-jane

# Test annotation API endpoints
# First, get an authentication token for a beta reader (if implemented)
```

Test annotation creation via API:
```bash
# Create annotation via REST API
curl -X POST "http://localhost:8000/annotations" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "drafts/chapter01.md",
    "highlighted_text": "ancient oak tree",
    "start_line": 3,
    "end_line": 3,
    "comment": "Consider specifying the species of oak - different species have different cultural significance",
    "author": "jane-beta-reader",
    "feedback_branch": "beta-reader-jane"
  }'

# Create another annotation
curl -X POST "http://localhost:8000/annotations" \
  -H "Content-Type: application/json" \
  -d '{
    "file_path": "drafts/chapter01.md",
    "highlighted_text": "fifteen years on the force",
    "start_line": 3,
    "end_line": 3,
    "comment": "This detail feels repeated. Maybe vary how you reference her experience?",
    "author": "jane-beta-reader",
    "feedback_branch": "beta-reader-jane"
  }'
```

#### 5.3 Review Beta Reader Annotations
```bash
# List annotations via API
curl "http://localhost:8000/annotations?feedback_branch=beta-reader-jane" | jq

# Expected output:
# JSON response with array of annotations
```

#### 5.4 Process Beta Reader Feedback
```bash
# Switch back to main branch
poetry run python -m gitwrite_cli switch main

# Review beta reader branch
poetry run python -m gitwrite_cli review beta-reader-jane

# Make revisions based on feedback
cat > drafts/chapter01.md << 'EOF'
# Chapter 1: The Discovery

Detective Sarah Chen examined the peculiar symbol carved into the towering white oak. With over a decade of investigative experience, she had developed an eye for details that others missed, and this carving was unlike anything she had encountered.

The morning mist created an almost supernatural atmosphere around the crime scene, but Sarah forced herself to focus on the facts. Emotions and atmosphere were for writers, not detectives.

"What's your assessment, Chen?" asked Detective Mike Rodriguez, maintaining a respectful distance from the evidence.

Sarah photographed the symbol from multiple angles, ensuring proper lighting and scale references. "I need to research this symbol. It's deliberate, meaningful. Not random vandalism."

She made detailed notes about the carving's depth, tool marks, and orientation. Whatever this symbol meant, it was the key to understanding why they had been called to this remote location.
EOF

# Save revisions incorporating beta feedback
poetry run python -m gitwrite_cli save "Incorporated beta reader feedback: specified oak species and varied experience references"
```

### Phase 6: Export and Publishing Testing

#### 6.1 Test Multiple Export Formats
```bash
# Test EPUB export
poetry run python -m gitwrite_cli export epub --output final-mystery-novel.epub

# Test PDF export (if Pandoc has LaTeX support)
poetry run python -m gitwrite_cli export pdf --output final-mystery-novel.pdf

# Test DOCX export
poetry run python -m gitwrite_cli export docx --output final-mystery-novel.docx

# Verify exported files exist
ls -la *.epub *.pdf *.docx
```

#### 6.2 Test Version-Specific Exports
```bash
# Export a specific version
poetry run python -m gitwrite_cli export epub --version beta-v1.0 --output mystery-novel-beta-tagged.epub

# Export from a specific branch
git checkout alternate-opening
poetry run python -m gitwrite_cli export epub --output mystery-novel-alternate.epub
git checkout main
```

#### 6.3 Test Export API Endpoints
```bash
# Test export via REST API
curl -X POST "http://localhost:8000/export/epub" \
  -H "Content-Type: application/json" \
  -d '{
    "repository_path": "/path/to/mystery-novel",
    "output_filename": "api-export.epub"
  }'
```

### Phase 7: Advanced Features Testing

#### 7.1 Test Word-Level Diff Visualization
```bash
# Create some content to compare
echo "The detective walked slowly down the dark hallway." > test-diff.txt
git add test-diff.txt
git commit -m "Original sentence"

# Modify the content
echo "The experienced detective walked carefully down the dimly lit hallway." > test-diff.txt
git add test-diff.txt
git commit -m "Enhanced sentence"

# Test word-level diff
poetry run python -m gitwrite_cli compare HEAD~1 HEAD

# Expected output:
# Word-level highlighting showing added/changed words
```

#### 7.2 Test Complex Branch Operations
```bash
# Create multiple branches to test complex scenarios
poetry run python -m gitwrite_cli explore "plot-twist-ending"
poetry run python -m gitwrite_cli explore "character-development"
poetry run python -m gitwrite_cli explore "pacing-improvements"

# List all branches
poetry run python -m gitwrite_cli branches

# Test switching between multiple branches
poetry run python -m gitwrite_cli switch plot-twist-ending
poetry run python -m gitwrite_cli switch character-development
poetry run python -m gitwrite_cli switch main
```

#### 7.3 Test Tagging and Version Management
```bash
# Create semantic version tags
git tag -a "v1.0.0-draft" -m "First complete draft"
git tag -a "v1.1.0-edited" -m "After editor review"
git tag -a "v1.2.0-beta" -m "Beta reader version"

# List all tags
git tag -l

# Test export from specific tags
poetry run python -m gitwrite_cli export epub --version v1.0.0-draft --output draft-version.epub
```

### Phase 8: Error Handling and Edge Cases

#### 8.1 Test Error Scenarios
```bash
# Test initialization in existing Git repository
cd ..
git init error-test-repo
cd error-test-repo
poetry run python -m gitwrite_cli init

# Expected: Should handle existing Git repo gracefully

# Test invalid commands
poetry run python -m gitwrite_cli switch nonexistent-branch
# Expected: Proper error message

# Test CLI with invalid arguments
poetry run python -m gitwrite_cli save
# Expected: Helpful error about missing message
```

#### 8.2 Test API Error Handling
```bash
# Test invalid endpoints
curl "http://localhost:8000/invalid-endpoint"
# Expected: 404 Not Found

# Test malformed requests
curl -X POST "http://localhost:8000/annotations" \
  -H "Content-Type: application/json" \
  -d '{"invalid": "json structure"}'
# Expected: 422 Validation Error

# Test unauthorized access
curl "http://localhost:8000/annotations"
# Expected: 401 Unauthorized (if auth is implemented)
```

#### 8.3 Test Performance with Large Files
```bash
# Create a large text file to test performance
python -c "
content = 'This is a test sentence for performance testing. ' * 10000
with open('drafts/large-chapter.md', 'w') as f:
    f.write('# Large Chapter\\n\\n' + content)
"

# Test save performance
time poetry run python -m gitwrite_cli save "Added large chapter for performance testing"

# Test diff performance
echo "Modified content" >> drafts/large-chapter.md
time poetry run python -m gitwrite_cli compare HEAD~1 HEAD
```

## Verification Checklist

After completing all tests, verify the following functionality:

### ✅ Core CLI Functions
- [ ] Project initialization (`gitwrite init`)
- [ ] Saving changes (`gitwrite save`)
- [ ] Branch creation and switching (`gitwrite explore`, `gitwrite switch`)
- [ ] History viewing (`gitwrite history`)
- [ ] Version comparison (`gitwrite compare`)
- [ ] Export functionality (`gitwrite export`)

### ✅ Web Interface Functions
- [ ] User authentication (Owner/Editor roles)
- [ ] Repository browsing and file viewing
- [ ] Branch management interface
- [ ] Commit history visualization
- [ ] File content editing (if implemented)

### ✅ API Endpoints
- [ ] Authentication endpoints (`/auth/*`)
- [ ] Repository operations (`/repository/*`)
- [ ] Annotation management (`/annotations/*`)
- [ ] File upload endpoints (`/uploads/*`)
- [ ] Export functionality endpoints

### ✅ Collaborative Features
- [ ] Editor branch workflow
- [ ] Beta reader annotation system
- [ ] Cherry-picking commits
- [ ] Role-based access control

### ✅ Integration Features
- [ ] TypeScript SDK functionality
- [ ] Cross-component data consistency
- [ ] Git compatibility (standard Git commands work)
- [ ] Export to multiple formats

### ✅ Error Handling
- [ ] CLI error messages are helpful
- [ ] API returns appropriate HTTP status codes
- [ ] Web interface handles errors gracefully
- [ ] Invalid input validation

## Troubleshooting Common Issues

### Poetry Installation Issues
```bash
# If poetry install fails with pygit2 errors:
export LIBGIT2_LIB_PATH=/usr/local/lib
export LIBGIT2_INCLUDE_PATH=/usr/local/include
poetry install
```

### Frontend Build Issues
```bash
# If npm install fails in gitwrite-web:
cd gitwrite-web
rm -rf node_modules package-lock.json
npm cache clean --force
npm install
```

### API Connection Issues
```bash
# Check if API is running on correct port:
curl http://localhost:8000/health
# If it fails, verify uvicorn is running and check firewall settings
```

### Export Functionality Issues
```bash
# Verify Pandoc installation:
pandoc --version
# If missing, install via package manager or download from pandoc.org
```

### File Permission Issues
```bash
# Ensure proper permissions on project directories:
chmod -R 755 mystery-novel/
chown -R $USER:$USER mystery-novel/
```

This comprehensive testing guide ensures all components of GitWrite are functioning correctly and provides a realistic simulation of a complete writing project workflow from initial creation through publication-ready export.