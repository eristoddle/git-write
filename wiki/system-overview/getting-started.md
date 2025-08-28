# Getting Started

Welcome to GitWrite! This guide will help you get up and running with GitWrite quickly, whether you're a complete beginner to version control or an experienced Git user looking to adopt a writer-friendly workflow.

## What You'll Learn

By the end of this guide, you'll know how to:
- Install and set up GitWrite
- Create your first writing project
- Save your work and track changes
- Create explorations to try different approaches
- Export your work to publishable formats
- Collaborate with others

## Prerequisites

### System Requirements

**Minimum Requirements:**
- Operating System: Windows 10+, macOS 10.15+, or Linux (Ubuntu 18.04+)
- Python: 3.9 or higher (3.10+ recommended)
- Memory: 2GB RAM
- Storage: 1GB free space
- Internet connection for initial setup and collaboration features

**Recommended Requirements:**
- Python 3.10+
- 4GB+ RAM for large projects
- SSD storage for better performance
- Git 2.20+ (for compatibility with other tools)

### Installation

#### Option 1: pip Installation (Recommended)

```bash
# Install GitWrite from PyPI
pip install gitwrite

# Verify installation
gitwrite --version
```

#### Option 2: Poetry Installation (for developers)

```bash
# Clone the repository
git clone https://github.com/eristoddle/git-write.git
cd git-write

# Install with Poetry
poetry install

# Activate virtual environment
poetry shell

# Verify installation
gitwrite --version
```

#### Option 3: Docker Installation

```bash
# Run GitWrite in Docker
docker run -it --rm \
  -v $(pwd):/workspace \
  gitwrite/gitwrite:latest \
  gitwrite --help
```

### First-Time Setup

After installation, configure GitWrite with your information:

```bash
# Set your name and email (used for tracking your changes)
gitwrite config --global user.name "Your Name"
gitwrite config --global user.email "your.email@example.com"

# Optional: Set preferred editor
gitwrite config --global core.editor "code"  # VS Code
gitwrite config --global core.editor "vim"   # Vim
gitwrite config --global core.editor "nano"  # Nano

# Verify configuration
gitwrite config --list
```

## Your First Project

### Creating a New Project

Let's create your first GitWrite project - a short story:

```bash
# Create a new short story project
mkdir my-first-story
cd my-first-story

# Initialize GitWrite project
gitwrite init \
  --author "Your Name" \
  --description "My first story using GitWrite" \
  --type short-story

# See what was created
ls -la
```

**What GitWrite Created:**
```
my-first-story/
├── .git/                    # Git repository (version control data)
├── .gitwrite/              # GitWrite configuration
├── manuscript/             # Your writing goes here
│   ├── story.md           # Main story file
│   ├── characters.md      # Character notes
│   └── notes.md           # Research and ideas
├── .gitignore             # Files to ignore
├── README.md              # Project description
└── gitwrite.yaml          # Project settings
```

### Writing Your First Content

Open your preferred text editor and start writing:

```bash
# Open the main story file
code manuscript/story.md  # VS Code
vim manuscript/story.md   # Vim
nano manuscript/story.md  # Nano
```

Add some content to your story:

```markdown
# The Beginning

It was a dark and stormy night when Sarah first discovered the mysterious letter under her door. The envelope was old, yellowed with age, and bore no return address.

She hesitated for a moment before opening it, wondering who could have left such an antiquated message in the modern world of digital communication.

## Chapter 1: The Discovery

The letter contained only a few words, written in elegant handwriting:

*"The truth you seek lies where the old oak stands guard over forgotten secrets."*

Sarah's heart raced. There was only one old oak she knew of - the ancient tree in Millbrook Cemetery, where her grandmother used to take her as a child.
```

### Saving Your Work

GitWrite makes saving your work simple and meaningful:

```bash
# Check what has changed
gitwrite status

# Save your work with a descriptive message
gitwrite save "Added opening scene and first chapter"

# View your project history
gitwrite history
```

**Understanding the Output:**
- `gitwrite status` shows what files have changed since your last save
- `gitwrite save` creates a permanent record of your current work
- `gitwrite history` shows all your save points chronologically

### Making Changes and Tracking Progress

Let's continue writing and see how GitWrite tracks your progress:

1. **Add more content** to your story
2. **Save regularly** with descriptive messages
3. **Track your progress** over time

```bash
# After writing more content
gitwrite save "Developed Sarah's character and added mystery element"

# Check your writing statistics
gitwrite stats

# See what changed since your last save
gitwrite diff --since-last-save
```

## Exploring Different Approaches

One of GitWrite's most powerful features is the ability to safely experiment with different approaches to your story.

### Creating an Exploration

Let's say you want to try writing the story from a different character's perspective:

```bash
# Create an exploration for a different approach
gitwrite explore create "first-person-perspective" \
  --description "Trying the story from Sarah's first-person POV"

# You're now working in the exploration
gitwrite status  # Shows you're in "first-person-perspective"
```

### Working in the Exploration

Now you can rewrite your story without fear of losing the original:

```bash
# Edit your story file
code manuscript/story.md
```

Rewrite the opening from first person:

```markdown
# The Beginning

It was a dark and stormy night when I first discovered the mysterious letter under my door. The envelope was old, yellowed with age, and bore no return address.

I hesitated for a moment before opening it, wondering who could have left such an antiquated message in our modern world of digital communication.

## Chapter 1: The Discovery

The letter contained only a few words, written in elegant handwriting:

*"The truth you seek lies where the old oak stands guard over forgotten secrets."*

My heart raced. There was only one old oak I knew of - the ancient tree in Millbrook Cemetery, where my grandmother used to take me as a child.
```

```bash
# Save your experimental version
gitwrite save "Rewrote opening in first person - feels more intimate"
```

### Comparing Approaches

Now you can compare your different approaches:

```bash
# Compare the two versions
gitwrite compare main first-person-perspective

# See specific differences in the story file
gitwrite diff main:manuscript/story.md first-person-perspective:manuscript/story.md
```

### Choosing the Best Approach

Decide which version you prefer and integrate it:

```bash
# If you like the first-person version better
gitwrite explore merge first-person-perspective \
  --message "Using first-person POV - more engaging"

# Or go back to the original
gitwrite explore switch main

# Or keep both for different purposes
gitwrite explore switch main
# Continue with third person for final version
```

## Collaborating with Others

GitWrite makes it easy to get feedback on your work.

### Sharing for Review

```bash
# Prepare your story for feedback
gitwrite share --format pdf --output "my-story-draft1.pdf"

# Or export to multiple formats
gitwrite export epub --title "My First Story" --author "Your Name"
gitwrite export docx --title "My First Story" --author "Your Name"
```

### Getting Feedback (When collaboration features are available)

```bash
# Share with an editor (future feature)
gitwrite collaborate invite "editor@example.com" \
  --role editor \
  --message "Please review my first draft"

# Check for feedback
gitwrite annotations list --new
```

## Exporting Your Work

When you're ready to share or publish your story:

### Basic Export

```bash
# Export to PDF for printing
gitwrite export pdf \
  --title "My First Story" \
  --author "Your Name" \
  --output "my-story.pdf"

# Export to EPUB for e-readers
gitwrite export epub \
  --title "My First Story" \
  --author "Your Name" \
  --cover cover.jpg \
  --output "my-story.epub"

# Export to Word document
gitwrite export docx \
  --title "My First Story" \
  --author "Your Name" \
  --output "my-story.docx"
```

### Advanced Export Options

```bash
# Export with custom template
gitwrite export pdf \
  --template professional \
  --margins "1in" \
  --font "Times New Roman" \
  --size letter

# Include revision history
gitwrite export pdf \
  --include-history \
  --show-word-count \
  --include-metadata
```

## Essential Commands Reference

Here are the commands you'll use most often:

### Daily Writing Commands

```bash
# Check what's changed
gitwrite status

# Save your work
gitwrite save "Brief description of what you wrote"

# See your writing history
gitwrite history

# Check your progress
gitwrite stats
```

### Exploration Commands

```bash
# Create new exploration
gitwrite explore create "exploration-name" --description "What you're trying"

# Switch between explorations
gitwrite explore switch "exploration-name"
gitwrite explore switch main  # Back to main story

# List all explorations
gitwrite explore list

# Compare explorations
gitwrite compare main exploration-name
```

### Export Commands

```bash
# Quick exports
gitwrite export pdf
gitwrite export epub
gitwrite export docx

# Custom exports
gitwrite export pdf --title "Title" --author "Author"
gitwrite export epub --cover cover.jpg --metadata book-info.yaml
```

### Getting Help

```bash
# General help
gitwrite --help

# Command-specific help
gitwrite save --help
gitwrite explore --help
gitwrite export --help

# Show current status and next steps
gitwrite guide
```

## Next Steps

Now that you've mastered the basics, here's what to explore next:

### Intermediate Features

1. **Advanced Explorations**
   - Create explorations from specific points in history
   - Cherry-pick changes between explorations
   - Use explorations for different story endings

2. **Better Organization**
   - Organize longer works with multiple files
   - Use subdirectories for complex projects
   - Create templates for recurring project types

3. **Enhanced Exports**
   - Create custom export templates
   - Set up automated export workflows
   - Use metadata files for consistent formatting

### Advanced Features

1. **Collaboration**
   - Set up review workflows with editors
   - Manage feedback from multiple beta readers
   - Use annotation systems for detailed feedback

2. **Analytics and Insights**
   - Track writing habits and productivity
   - Analyze text for readability and style
   - Generate progress reports

3. **Integration**
   - Connect with other writing tools
   - Set up automated backup systems
   - Create custom workflows with the API

### Learning Resources

- **Tutorial Projects**: Try different project types (novel, article, screenplay)
- **Community**: Join the GitWrite community for tips and support
- **Documentation**: Explore the full documentation for advanced features
- **Examples**: Study example projects and workflows

## Troubleshooting Common Issues

### Installation Problems

**Python Version Issues:**
```bash
# Check Python version
python --version

# Install specific Python version if needed
# (Instructions vary by operating system)
```

**Permission Errors:**
```bash
# Install for current user only
pip install --user gitwrite

# Or use virtual environment
python -m venv gitwrite-env
source gitwrite-env/bin/activate  # Linux/Mac
gitwrite-env\Scripts\activate     # Windows
pip install gitwrite
```

### Project Issues

**Project Not Recognized:**
```bash
# Check if you're in a GitWrite project
gitwrite status

# Initialize if needed
gitwrite init
```

**Git Configuration Issues:**
```bash
# Set required Git configuration
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Getting More Help

- **Command Help**: `gitwrite [command] --help`
- **Verbose Output**: `gitwrite --verbose [command]`
- **Debug Mode**: `gitwrite --debug [command]`
- **Community Support**: Visit the GitWrite community forums
- **GitHub Issues**: Report bugs and request features

---

*Congratulations! You now know the fundamentals of GitWrite. Start with simple projects and gradually explore more advanced features as your needs grow. Remember, GitWrite is designed to adapt to your writing process, not replace it.*