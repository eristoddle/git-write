# Troubleshooting Common Issues

This guide covers the most common issues users encounter with GitWrite and provides step-by-step solutions. Issues are organized by category with clear symptoms, causes, and resolution steps.

## Installation and Setup Issues

### Python Version Problems

**Symptoms:**
- `gitwrite` command not found after installation
- ModuleNotFoundError when running GitWrite
- Cryptic errors about Python version compatibility

**Diagnosis:**
```bash
# Check Python version
python --version
python3 --version

# Check if GitWrite is installed
pip list | grep gitwrite
pip3 list | grep gitwrite

# Check Python path
which python
which python3
```

**Solutions:**

**For Python Version Issues:**
```bash
# Install for specific Python version
python3.10 -m pip install gitwrite

# Or use pyenv to manage Python versions
pyenv install 3.10
pyenv global 3.10
pip install gitwrite
```

**For Command Not Found:**
```bash
# Add pip install directory to PATH
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc

# Or install with --user flag
pip install --user gitwrite

# For macOS with homebrew Python
/usr/local/bin/python3 -m pip install gitwrite
```

**For Virtual Environment Issues:**
```bash
# Create clean virtual environment
python3 -m venv gitwrite-env
source gitwrite-env/bin/activate  # Linux/Mac
# gitwrite-env\Scripts\activate   # Windows
pip install gitwrite
```

### pygit2 Installation Failures

**Symptoms:**
- Error: Microsoft Visual C++ 14.0 is required (Windows)
- fatal error: 'git2.h' file not found (macOS/Linux)
- Building wheel for pygit2 failed

**Diagnosis:**
```bash
# Check if libgit2 is installed
pkg-config --exists libgit2 && echo "libgit2 found" || echo "libgit2 missing"

# Check for build tools
gcc --version    # Linux/Mac
cl               # Windows (Visual Studio)
```

**Solutions:**

**Linux (Ubuntu/Debian):**
```bash
# Install dependencies
sudo apt-get update
sudo apt-get install libgit2-dev build-essential python3-dev

# Then install GitWrite
pip install gitwrite
```

**Linux (CentOS/RHEL):**
```bash
sudo yum install libgit2-devel gcc python3-devel
# or for newer versions:
sudo dnf install libgit2-devel gcc python3-devel
```

**macOS:**
```bash
# Using Homebrew
brew install libgit2
pip install gitwrite

# If still failing, try:
export LDFLAGS="-L$(brew --prefix)/lib"
export CPPFLAGS="-I$(brew --prefix)/include"
pip install gitwrite
```

**Windows:**
```bash
# Install Visual Studio Build Tools
# Download from: https://visualstudio.microsoft.com/visual-cpp-build-tools/

# Or use conda-forge
conda install -c conda-forge pygit2
pip install gitwrite
```

### Git Configuration Issues

**Symptoms:**
- Error: "Please tell me who you are"
- Authentication failures with remote repositories
- Permission denied errors

**Diagnosis:**
```bash
# Check Git configuration
git config --global user.name
git config --global user.email
git config --list
```

**Solutions:**
```bash
# Set required Git configuration
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"

# For GitWrite-specific config
gitwrite config set user.name "Your Name"
gitwrite config set user.email "your.email@example.com"

# Fix line ending issues (Windows)
git config --global core.autocrlf true

# Fix line ending issues (Mac/Linux)
git config --global core.autocrlf input
```

## Project and Repository Issues

### "Not a GitWrite project" Errors

**Symptoms:**
- Error when running GitWrite commands in a directory
- Commands work in one directory but not another
- Project appears corrupted or unrecognized

**Diagnosis:**
```bash
# Check if you're in the right directory
pwd
ls -la

# Look for GitWrite indicators
ls -la .git
ls -la .gitwrite
ls -la gitwrite.yaml

# Check repository status
git status
```

**Solutions:**

**For Missing GitWrite Structure:**
```bash
# Initialize GitWrite in existing Git repository
gitwrite init --existing

# Or start fresh
gitwrite init my-project
cd my-project
```

**For Corrupted GitWrite Configuration:**
```bash
# Backup current work
cp -r . ../backup-$(date +%Y%m%d)

# Recreate GitWrite configuration
rm -rf .gitwrite
gitwrite init --existing --force

# Restore custom settings if needed
gitwrite config set author "Your Name"
```

**For Permission Issues:**
```bash
# Fix file permissions
chmod -R u+rw .git .gitwrite
sudo chown -R $(whoami) .git .gitwrite

# Fix directory permissions
find . -type d -exec chmod u+rwx {} \;
```

### Repository Corruption

**Symptoms:**
- "object not found" errors
- "bad object" messages
- GitWrite commands hang or crash
- History appears incomplete

**Diagnosis:**
```bash
# Check repository integrity
git fsck --full

# Check GitWrite integrity
gitwrite doctor --check-integrity

# Look for large or corrupted files
du -sh .git/objects/*
```

**Solutions:**

**For Git Repository Corruption:**
```bash
# Create backup first
cp -r . ../corrupted-backup

# Try automatic repair
git fsck --full --auto

# Force cleanup
git gc --prune=now --aggressive

# If severely corrupted, recover from remote
git clone <remote-url> recovered-project
# Then manually copy your latest work
```

**For GitWrite-Specific Corruption:**
```bash
# Run GitWrite doctor
gitwrite doctor --repair

# Recreate GitWrite structure
rm -rf .gitwrite
gitwrite init --existing

# Restore configuration
gitwrite config restore --from-backup
```

### File System Issues

**Symptoms:**
- "Permission denied" errors
- "No space left on device"
- "File name too long" errors
- Slow GitWrite operations

**Diagnosis:**
```bash
# Check disk space
df -h .

# Check file permissions
ls -la
stat .git
stat .gitwrite

# Check for file system errors
fsck /dev/your-disk  # Linux
diskutil verifyVolume /  # macOS
```

**Solutions:**

**For Disk Space Issues:**
```bash
# Clean up Git repository
git gc --aggressive --prune=now

# Remove large files from history
git filter-branch --tree-filter 'rm -f large-file.txt' HEAD

# Use GitWrite cleanup
gitwrite clean --optimize --force
```

**For Permission Issues:**
```bash
# Fix ownership (Linux/Mac)
sudo chown -R $(whoami):$(whoami) .

# Fix permissions
chmod -R u+rw .
find . -type d -exec chmod u+x {} \;
```

## Workflow and Operation Issues

### Save (Commit) Problems

**Symptoms:**
- "nothing to commit" when you know files changed
- Changes not being tracked
- Save operations hang or fail

**Diagnosis:**
```bash
# Check working directory status
gitwrite status --detailed
git status --porcelain

# Check if files are being ignored
git check-ignore problematic-file.md

# Verify file contents changed
git diff HEAD -- filename.md
```

**Solutions:**

**For Untracked Changes:**
```bash
# Force add specific files
git add filename.md
gitwrite save "Fixed tracking issue"

# Check and update .gitignore
cat .gitignore
# Remove any patterns that might be ignoring your files

# Force add ignored files if needed
git add --force filename.md
```

**For Large File Issues:**
```bash
# Check file sizes
find . -type f -size +50M

# Use Git LFS for large files
git lfs track "*.pdf"
git lfs track "*.docx"
git add .gitattributes
gitwrite save "Added LFS tracking"
```

**For Line Ending Issues:**
```bash
# Normalize line endings
git add --renormalize .
gitwrite save "Normalized line endings"

# Fix configuration
git config core.autocrlf true  # Windows
git config core.autocrlf input # Mac/Linux
```

### Exploration (Branch) Issues

**Symptoms:**
- Can't switch between explorations
- Explorations appear to be missing
- Changes lost when switching explorations

**Diagnosis:**
```bash
# List all explorations
gitwrite explore list --detailed
git branch -a

# Check current exploration
gitwrite status
git branch --show-current

# Check for uncommitted changes
git status
gitwrite diff --since-last-save
```

**Solutions:**

**For Switching Problems:**
```bash
# Save current work before switching
gitwrite save "Work in progress - switching explorations"
gitwrite explore switch target-exploration

# Or stash changes temporarily
git stash push -m "Temporary stash for exploration switch"
gitwrite explore switch target-exploration
git stash pop
```

**For Missing Explorations:**
```bash
# Check if exploration exists in Git
git branch -a
git show-ref

# Recreate exploration if needed
gitwrite explore create recovered-exploration \
  --from-commit <last-known-commit>

# Restore from backup
gitwrite backup list
gitwrite backup restore --exploration lost-exploration
```

**For Lost Changes:**
```bash
# Check Git reflog for lost commits
git reflog
git show <commit-hash>

# Recover lost work
git checkout <commit-hash>
gitwrite explore create recovered-work
gitwrite save "Recovered lost changes"
```

### Export Problems

**Symptoms:**
- Export commands fail with errors
- Generated documents are malformed
- Missing content in exported files
- Pandoc not found errors

**Diagnosis:**
```bash
# Check if Pandoc is installed
pandoc --version

# Check export dependencies
gitwrite doctor --check-export-deps

# Test basic export
pandoc --version
gitwrite export html --output test.html
```

**Solutions:**

**For Missing Pandoc:**
```bash
# Install Pandoc (Linux)
sudo apt-get install pandoc

# Install Pandoc (macOS)
brew install pandoc

# Install Pandoc (Windows)
# Download from: https://pandoc.org/installing.html

# Verify installation
pandoc --version
```

**For Template Issues:**
```bash
# Use built-in templates
gitwrite export epub --template default

# List available templates
gitwrite templates list

# Reset to default templates
gitwrite templates reset
```

**For Content Issues:**
```bash
# Check source files
gitwrite validate --check-structure

# Export with debug info
gitwrite --verbose export epub

# Try simpler export first
gitwrite export markdown --output debug.md
```

## Performance Issues

### Slow Operations

**Symptoms:**
- GitWrite commands take a long time to complete
- High CPU or memory usage
- System becomes unresponsive during operations

**Diagnosis:**
```bash
# Check repository size
du -sh .git
git count-objects -vH

# Check for large files
find . -type f -size +10M

# Monitor system resources
top
htop  # If available
```

**Solutions:**

**For Large Repository Issues:**
```bash
# Clean up repository
git gc --aggressive
git repack -ad

# Remove large files from history
git filter-branch --index-filter 'git rm --cached --ignore-unmatch large-file.pdf'

# Use shallow clone for collaboration
git clone --depth 1 <repository-url>
```

**For Memory Issues:**
```bash
# Increase Git memory limits
git config pack.windowMemory "100m"
git config pack.packSizeLimit "100m"

# Process files in smaller batches
gitwrite save "Batch 1" --files file1.md file2.md
gitwrite save "Batch 2" --files file3.md file4.md
```

### Network Issues

**Symptoms:**
- Collaboration features not working
- Sync operations failing
- Timeout errors

**Diagnosis:**
```bash
# Test network connectivity
ping github.com
curl -I https://api.gitwrite.com

# Check firewall settings
sudo ufw status  # Linux
# Check corporate firewall/proxy
```

**Solutions:**

**For Proxy Issues:**
```bash
# Configure Git for proxy
git config --global http.proxy http://proxy.company.com:8080
git config --global https.proxy https://proxy.company.com:8080

# Configure GitWrite for proxy
gitwrite config set network.proxy "http://proxy.company.com:8080"
```

**For SSL Issues:**
```bash
# Temporarily disable SSL verification (not recommended for production)
git config --global http.sslVerify false

# Or add certificate to trust store
# (Specific to your OS and certificate authority)
```

## Platform-Specific Issues

### Windows Issues

**Common Windows Problems:**

**Path Length Limitations:**
```bash
# Enable long paths (requires admin privileges)
git config --global core.longpaths true

# Or use shorter project paths
cd C:\Projects\  # Instead of C:\Users\VeryLongUsername\Documents\...
```

**Line Ending Issues:**
```bash
# Configure line endings for Windows
git config --global core.autocrlf true
gitwrite config set core.line_endings windows
```

**File Locking Issues:**
```bash
# Check for file locks
lsof filename.md  # If available
fuser filename.md  # If available

# Close applications that might be locking files
# Restart GitWrite operations
```

### macOS Issues

**Common macOS Problems:**

**Permission Issues with System Directories:**
```bash
# Don't install in system directories
pip install --user gitwrite

# Use homebrew Python instead of system Python
brew install python
/usr/local/bin/python3 -m pip install gitwrite
```

**Case Sensitivity Issues:**
```bash
# Check file system case sensitivity
echo "test" > TestFile.txt
ls testfile.txt  # If this works, file system is case-insensitive

# Configure Git appropriately
git config core.ignorecase true  # For case-insensitive file systems
```

### Linux Issues

**Common Linux Distribution Problems:**

**Package Manager Conflicts:**
```bash
# Use virtual environment to avoid conflicts
python3 -m venv ~/.local/share/gitwrite-env
source ~/.local/share/gitwrite-env/bin/activate
pip install gitwrite

# Or use pipx for isolated installation
pipx install gitwrite
```

**SELinux Issues:**
```bash
# Check SELinux status
sestatus

# Temporarily disable if causing issues
sudo setenforce 0

# Or add appropriate SELinux policies
# (Consult your system administrator)
```

## Getting Additional Help

### Diagnostic Commands

```bash
# Run comprehensive diagnostics
gitwrite doctor --full-check

# Get system information
gitwrite info --system

# Generate debug report
gitwrite debug-report --output debug-report.zip
```

### Log Analysis

```bash
# Enable verbose logging
gitwrite --verbose --debug <command>

# Check GitWrite logs
tail -f ~/.local/share/gitwrite/logs/gitwrite.log

# Check Git logs
git log --oneline --graph
```

### Recovery Procedures

**Last Resort Recovery:**
```bash
# Create emergency backup
cp -r . ../emergency-backup-$(date +%Y%m%d-%H%M%S)

# Reset to last known good state
git reflog
git reset --hard <good-commit-hash>
gitwrite doctor --repair

# Rebuild GitWrite structure if needed
rm -rf .gitwrite
gitwrite init --existing
```

### Community Support

**Before Asking for Help:**
1. Run `gitwrite doctor --full-check`
2. Create a minimal reproducible example
3. Include your system information (`gitwrite info --system`)
4. Check existing GitHub issues

**Where to Get Help:**
- GitHub Issues: Report bugs and request features
- Community Forum: General questions and discussions
- Documentation: Comprehensive guides and references
- Stack Overflow: Tag questions with `gitwrite`

### Emergency Contacts

**For Critical Issues:**
- Data loss or corruption: Create backup immediately, then seek help
- Security concerns: Contact maintainers privately
- Production system issues: Include system logs and error messages

---

*Most GitWrite issues can be resolved with the solutions in this guide. When in doubt, create a backup first, then try the simplest solution before moving to more complex recovery procedures.*