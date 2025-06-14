# GitWrite

**Git-based version control for writers and writing teams**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![TypeScript](https://img.shields.io/badge/TypeScript-4.9+-blue.svg)](https://www.typescriptlang.org/)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)

GitWrite brings Git's powerful version control to writers through an intuitive, writer-friendly interface. Built on top of Git's proven technology, it maintains full compatibility with existing Git repositories and hosting services while making version control accessible to non-technical writers.

## 🎯 Why GitWrite?

**For Writers:**
- Track every revision of your manuscript with meaningful history
- Experiment with different versions without fear of losing work
- Collaborate seamlessly with editors, beta readers, and co-authors
- Get feedback through an intuitive annotation system
- Export to multiple formats (EPUB, PDF, DOCX) at any point in your writing journey

**For Editors & Publishers:**
- Review and suggest changes using familiar editorial workflows
- Maintain version control throughout the publishing process
- Enable beta readers to provide structured feedback
- Integrate with existing Git-based development workflows

**For Developers:**
- All GitWrite repositories are standard Git repositories
- Use GitWrite alongside existing Git tools and workflows
- Integrate with any Git hosting service (GitHub, GitLab, Bitbucket)
- No vendor lock-in - repositories remain Git-compatible

## ✨ Key Features

### 📝 Writer-Friendly Interface
- **Simple Commands**: `gitwrite save "Finished chapter 3"` instead of `git add . && git commit -m "..."`
- **Intuitive Terminology**: "explorations" instead of "branches", "save" instead of "commit"
- **Word-by-Word Comparison**: See exactly what changed between versions at the word level
- **Visual Diff Viewer**: Compare versions side-by-side with highlighting

### 🤝 Collaborative Writing
- **Author Control**: Repository owners maintain ultimate control over the main manuscript
- **Editorial Workflows**: Role-based permissions for editors, copy editors, and proofreaders
- **Selective Integration**: Cherry-pick individual changes from editors using Git's proven mechanisms
- **Beta Reader Feedback**: Export to EPUB, collect annotations, sync back as Git commits

### 🔧 Multiple Interfaces
- **Command Line**: Full-featured CLI for power users
- **Web Application**: Modern browser-based interface
- **Mobile App**: EPUB reader with annotation capabilities
- **REST API**: Integration with writing tools and services
- **TypeScript SDK**: Easy integration for developers

### 🌐 Git Ecosystem Integration
- **Full Git Compatibility**: Works with any Git hosting service
- **Standard Git Operations**: Use `git` commands alongside `gitwrite` commands
- **Hosting Service Features**: Leverage GitHub/GitLab pull requests, branch protection, and more
- **Developer Friendly**: Integrate with existing development workflows

## 🚀 Quick Start

### Installation

```bash
# Install GitWrite CLI (when available)
pip install git-write

# Or install from source
git clone https://github.com/eristoddle/git-write.git
cd git-write
pip install -e .
```

*Note: GitWrite is currently in development. Installation instructions will be updated as the project progresses.*

### Your First Writing Project

```bash
# Start a new writing project
gitwrite init "my-novel"
cd my-novel

# Create your first file
echo "# Chapter 1\n\nIt was a dark and stormy night..." > chapter1.md

# Save your progress
gitwrite save "Started Chapter 1"

# See your history
gitwrite history

# Create an alternative version to experiment
gitwrite explore "alternate-opening"
echo "# Chapter 1\n\nThe sun was shining brightly..." > chapter1.md
gitwrite save "Trying a different opening"

# Switch back to main version
gitwrite switch main

# Compare the versions
gitwrite compare main alternate-opening
```

### Working with Editors

```bash
# Editor creates their own branch for suggestions
git checkout -b editor-suggestions
# Editor makes changes and commits them

# Author reviews editor's changes individually
gitwrite review editor-suggestions

# Author selectively accepts changes
gitwrite cherry-pick abc1234  # Accept this specific change
gitwrite cherry-pick def5678 --modify  # Accept this change with modifications

# Merge accepted changes
gitwrite merge editor-suggestions
```

### Beta Reader Workflow

```bash
# Export manuscript for beta readers
gitwrite export epub --version v1.0

# Beta reader annotations automatically create commits in their branch
# Author reviews and integrates feedback
gitwrite review beta-reader-jane
gitwrite cherry-pick selected-feedback-commits
```

## 📚 Documentation

- **[User Guide](docs/user-guide.md)** - Complete guide for writers
- **[Editorial Workflows](docs/editorial-workflows.md)** - Guide for editors and publishers
- **[API Documentation](docs/api.md)** - REST API reference
- **[SDK Documentation](docs/sdk.md)** - TypeScript SDK guide
- **[Git Integration](docs/git-integration.md)** - How GitWrite leverages Git
- **[Contributing](CONTRIBUTING.md)** - How to contribute to GitWrite

## 🏗️ Architecture

GitWrite is built as a multi-component platform:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │  Mobile Reader  │    │  Writing Tools  │
│   (React/TS)    │    │ (React Native)  │    │   (3rd Party)   │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                     ┌───────────▼───────────┐
                     │    TypeScript SDK     │
                     │   (npm package)       │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │      REST API         │
                     │   (FastAPI/Python)    │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │    GitWrite CLI       │
                     │   (Python Click)      │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │       Git Core        │
                     │   (libgit2/pygit2)    │
                     └───────────────────────┘
```

## 🛠️ Development

### Prerequisites

- Python 3.9+
- Node.js 16+
- Git 2.20+
- Docker (for development environment)

### Setup Development Environment

```bash
# Clone the repository
git clone https://github.com/eristoddle/git-write.git
cd git-write

# Set up Python environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies (when available)
pip install -r requirements.txt  # or requirements-dev.txt for development

# Run tests (when available)
pytest

# Start development (project-specific commands will be documented as they're implemented)
```

*Note: Development setup instructions will be updated as the project structure is finalized.*

### Project Structure

```
git-write/
├── README.md              # This file
├── LICENSE                # MIT License
├── .gitignore            # Git ignore rules
├── requirements.txt       # Python dependencies
├── setup.py              # Package setup
├── src/                  # Source code
│   └── gitwrite/         # Main package
├── tests/                # Test files
├── docs/                 # Documentation
└── examples/             # Example projects and usage
```

*Note: The actual project structure may differ. Please check the repository directly for the current organization.*

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Ways to Contribute

- **🐛 Bug Reports**: Found a bug? [Open an issue](https://github.com/eristoddle/git-write/issues)
- **💡 Feature Requests**: Have an idea? [Start a discussion](https://github.com/eristoddle/git-write/discussions)
- **📝 Documentation**: Help improve our docs
- **🔧 Code**: Submit pull requests for bug fixes or features
- **🧪 Testing**: Help test new features and report issues
- **🎨 Design**: Improve user interface and experience

## 🌟 Use Cases

### Fiction Writers
- **Novel Writing**: Track character development, plot changes, and multiple endings
- **Short Stories**: Maintain collections with version history
- **Collaborative Fiction**: Co-author stories with real-time collaboration

### Academic Writers
- **Research Papers**: Track citations, methodology changes, and revisions
- **Dissertations**: Manage chapters, advisor feedback, and committee suggestions
- **Grant Proposals**: Version control for funding applications

### Professional Writers
- **Content Marketing**: Track blog posts, whitepapers, and marketing copy
- **Technical Documentation**: Maintain software documentation with code integration
- **Journalism**: Version control for articles and investigative pieces

### Publishers & Editors
- **Manuscript Management**: Track submissions through editorial process
- **Multi-Author Projects**: Coordinate anthology and collection projects
- **Quality Control**: Systematic review and approval workflows

## 🔗 Integrations

GitWrite integrates with popular writing and development tools:

- **Writing Tools**: Scrivener, Ulysses, Bear, Notion
- **Git Hosting**: GitHub, GitLab, Bitbucket, SourceForge
- **Export Formats**: Pandoc integration for EPUB, PDF, DOCX, HTML
- **Editorial Tools**: Track Changes, Google Docs, Microsoft Word
- **Publishing Platforms**: Integration APIs for self-publishing platforms

## 📊 Roadmap

### Core Features (In Development)
- [ ] Core Git integration and CLI
- [ ] Word-by-word diff engine
- [ ] Basic project management commands
- [ ] Git repository compatibility
- [ ] Writer-friendly command interface

### Planned Features
- [ ] Web interface
- [ ] Mobile EPUB reader
- [ ] Beta reader workflow
- [ ] TypeScript SDK
- [ ] Git hosting service integration
- [ ] Advanced selective merge interface
- [ ] Plugin system for writing tools
- [ ] Real-time collaboration features
- [ ] Advanced export options
- [ ] Workflow automation

### Future Enhancements
- [ ] AI-powered writing assistance integration
- [ ] Advanced analytics and insights
- [ ] Team management features
- [ ] Enterprise deployment options

*Note: This project is in early development. Features and timelines may change based on community feedback and development progress.*

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Git Community**: For creating the foundational technology that makes GitWrite possible
- **Writing Community**: For feedback and guidance on writing workflows
- **Open Source Contributors**: For libraries and tools that power GitWrite
- **Beta Testers**: For helping refine the user experience

---

**Made with ❤️ for writers everywhere**

*GitWrite: Where every word matters, and every change is remembered.*