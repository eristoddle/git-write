# Adapter Pattern

The Adapter Pattern is a fundamental design principle in GitWrite, enabling the transformation of Git's developer-centric concepts into writer-friendly terminology and workflows. This pattern bridges the gap between Git's technical complexity and the intuitive needs of writers, editors, and publishers.

## Pattern Overview

The Adapter Pattern in GitWrite creates a writer-centric interface that translates Git operations into familiar writing concepts while maintaining full Git functionality underneath.

```
┌─────────────────────────────────┐
│        Writer Interface         │
│  ┌─────────────────────────────┐ │
│  │  save()   explore()  tag()  │ │
│  │  merge()  export()   undo() │ │
│  └─────────────────────────────┘ │
└─────────────┬───────────────────┘
              │ Adapter Layer
┌─────────────▼───────────────────┐
│         Git Operations          │
│  ┌─────────────────────────────┐ │
│  │ commit() branch() checkout()│ │
│  │ merge()  pull()   reset()   │ │
│  └─────────────────────────────┘ │
└─────────────────────────────────┘
```

## Terminology Adaptation

### Core Concept Mapping

| Git Concept | GitWrite Concept | Writer Context |
|-------------|------------------|----------------|
| Repository | Project | A complete writing work |
| Commit | Save | Preserve current progress |
| Branch | Exploration | Try different approaches |
| Tag | Milestone | Mark important versions |
| Merge | Combine | Integrate changes |
| Cherry-pick | Select | Choose specific improvements |
| Stash | Draft | Temporary save |
| Reset | Undo | Revert to previous state |
| Diff | Compare | See what changed |
| Log | History | Track progress over time |

### Implementation Example

```python
class WriterAdapter:
    """Adapts Git operations to writer-friendly interface"""

    def __init__(self, git_repository):
        self.git_repo = git_repository

    def save(self, message: str, files: List[str] = None) -> SaveResult:
        """
        Writer-friendly save operation
        Adapts: git add + git commit
        """
        try:
            # Stage files (git add)
            if files:
                for file_path in files:
                    self.git_repo.index.add(file_path)
            else:
                self.git_repo.index.add_all()

            # Create commit (git commit)
            signature = self.git_repo.default_signature
            tree = self.git_repo.index.write_tree()

            commit_id = self.git_repo.create_commit(
                'HEAD',
                signature,
                signature,
                message,
                tree,
                [self.git_repo.head.target]
            )

            return SaveResult(
                success=True,
                commit_id=str(commit_id),
                message=message,
                files_saved=len(files) if files else self._count_changed_files()
            )

        except Exception as e:
            return SaveResult(
                success=False,
                error=f"Failed to save: {str(e)}"
            )

    def create_exploration(self, name: str, description: str = "") -> ExplorationResult:
        """
        Writer-friendly branch creation
        Adapts: git checkout -b <branch_name>
        """
        try:
            # Create new branch (git branch)
            branch = self.git_repo.branches.local.create(name, self.git_repo.head.target)

            # Switch to branch (git checkout)
            self.git_repo.checkout(branch)

            # Store exploration metadata
            self._store_exploration_metadata(name, description)

            return ExplorationResult(
                success=True,
                name=name,
                description=description,
                base_commit=str(self.git_repo.head.target)
            )

        except Exception as e:
            return ExplorationResult(
                success=False,
                error=f"Failed to create exploration: {str(e)}"
            )
```

## Command Adaptation

### CLI Command Translation

```python
class CLIAdapter:
    """Adapts Git CLI commands to writer-friendly syntax"""

    COMMAND_MAPPING = {
        # Writer command -> Git equivalent
        'save': 'commit',
        'explore': 'branch',
        'switch': 'checkout',
        'combine': 'merge',
        'compare': 'diff',
        'history': 'log',
        'undo': 'reset',
        'tag': 'tag'
    }

    def translate_command(self, writer_command: str, args: List[str]) -> GitCommand:
        """Translate writer command to Git operation"""

        if writer_command == 'save':
            return self._adapt_save_command(args)
        elif writer_command == 'explore':
            return self._adapt_explore_command(args)
        elif writer_command == 'compare':
            return self._adapt_compare_command(args)
        # ... other adaptations

    def _adapt_save_command(self, args: List[str]) -> GitCommand:
        """Convert 'gitwrite save' to git add + commit"""
        message = self._extract_message(args)
        files = self._extract_files(args)

        git_commands = []

        # Add files
        if files:
            git_commands.append(f"git add {' '.join(files)}")
        else:
            git_commands.append("git add .")

        # Commit with message
        git_commands.append(f'git commit -m "{message}"')

        return GitCommand(
            operations=git_commands,
            description=f"Save: {message}"
        )
```

### API Endpoint Adaptation

```python
class APIAdapter:
    """Adapts REST API endpoints to writer-friendly operations"""

    @router.post("/projects/{project_name}/save")
    async def save_changes(
        project_name: str,
        request: SaveRequest,
        current_user: User = Depends(get_current_user)
    ):
        """Writer-friendly save endpoint"""

        # Validate project access
        project = await self.get_project(project_name, current_user)

        # Adapt to Git operations
        git_adapter = WriterAdapter(project.git_repository)
        result = git_adapter.save(
            message=request.message,
            files=request.files
        )

        if result.success:
            # Notify collaborators
            await self.notify_collaborators(project, result)

            return APIResponse(
                success=True,
                data={
                    "save_id": result.commit_id,
                    "message": result.message,
                    "files_changed": result.files_saved,
                    "timestamp": datetime.utcnow()
                }
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=result.error
            )
```

## User Experience Adaptation

### Error Message Translation

```python
class ErrorAdapter:
    """Translates Git errors to writer-friendly messages"""

    ERROR_TRANSLATIONS = {
        "merge conflict": "Your changes conflict with recent edits. Please review and resolve the differences.",
        "nothing to commit": "No changes detected since your last save.",
        "detached HEAD": "You're viewing an old version. Create an exploration to make changes.",
        "branch already exists": "An exploration with this name already exists. Choose a different name.",
        "index lock": "Another save operation is in progress. Please wait and try again."
    }

    def translate_error(self, git_error: str) -> WriterError:
        """Convert Git error to writer-friendly message"""

        for git_pattern, writer_message in self.ERROR_TRANSLATIONS.items():
            if git_pattern.lower() in git_error.lower():
                return WriterError(
                    message=writer_message,
                    suggestion=self._get_suggestion(git_pattern),
                    recovery_options=self._get_recovery_options(git_pattern)
                )

        # Fallback for unknown errors
        return WriterError(
            message="An unexpected issue occurred while processing your request.",
            suggestion="Please check your project status and try again.",
            contact_support=True
        )
```

### Workflow Adaptation

```python
class WorkflowAdapter:
    """Adapts Git workflows to writing processes"""

    def adapt_collaboration_workflow(self) -> WritingWorkflow:
        """Convert Git collaboration to writing team workflow"""

        return WritingWorkflow([
            Step("Author writes content", "save changes regularly"),
            Step("Create exploration for edits", "explore new-chapter-revision"),
            Step("Share with editor", "invite editor@example.com"),
            Step("Editor provides feedback", "annotations and suggestions"),
            Step("Author reviews feedback", "accept/reject suggestions"),
            Step("Combine approved changes", "merge exploration"),
            Step("Tag completed version", "milestone first-draft")
        ])

    def adapt_publishing_workflow(self) -> PublishingWorkflow:
        """Convert Git release process to publishing workflow"""

        return PublishingWorkflow([
            Step("Finalize manuscript", "save final-manuscript"),
            Step("Create publication tag", "milestone ready-for-publication"),
            Step("Export to formats", "generate EPUB, PDF, DOCX"),
            Step("Archive final version", "create backup"),
            Step("Submit to publisher", "provide export files")
        ])
```

## Advanced Adaptation Features

### Contextual Help System

```python
class ContextualHelpAdapter:
    """Provides context-aware help based on user situation"""

    def get_contextual_help(self, current_state: ProjectState) -> HelpContent:
        """Provide relevant help based on current project state"""

        if current_state.has_conflicts:
            return HelpContent(
                title="Resolving Conflicts",
                message="Your changes conflict with recent edits.",
                actions=[
                    "Review conflicting sections",
                    "Choose which version to keep",
                    "Save resolved version"
                ],
                tutorial_link="/help/resolving-conflicts"
            )

        elif current_state.has_unstaged_changes:
            return HelpContent(
                title="Unsaved Changes",
                message="You have unsaved work.",
                actions=[
                    "Save your changes",
                    "Compare with last saved version",
                    "Create exploration for experiments"
                ]
            )

        # ... other contextual help scenarios
```

### Progressive Disclosure

The adapter implements progressive disclosure to gradually introduce Git concepts:

```python
class ProgressiveDisclosureAdapter:
    """Gradually exposes advanced features as users become comfortable"""

    def get_available_features(self, user_level: UserLevel) -> List[Feature]:
        """Return features appropriate for user's experience level"""

        base_features = [
            Feature("save", "Save your work"),
            Feature("history", "See your progress"),
            Feature("compare", "Compare versions")
        ]

        if user_level >= UserLevel.INTERMEDIATE:
            base_features.extend([
                Feature("explore", "Try different approaches"),
                Feature("tag", "Mark important versions"),
                Feature("export", "Generate documents")
            ])

        if user_level >= UserLevel.ADVANCED:
            base_features.extend([
                Feature("cherry-pick", "Select specific changes"),
                Feature("rebase", "Reorganize history"),
                Feature("submodules", "Include other projects")
            ])

        return base_features
```

## Performance Considerations

### Efficient Adaptation

```python
class EfficientAdapter:
    """Optimized adapter implementation"""

    def __init__(self):
        self._command_cache = {}
        self._translation_cache = LRUCache(maxsize=1000)

    @cached_property
    def git_operations(self) -> GitOperations:
        """Lazy-loaded Git operations interface"""
        return GitOperations(self.repository_path)

    def cached_translate(self, command: str) -> str:
        """Cache frequently used translations"""
        if command not in self._translation_cache:
            self._translation_cache[command] = self._perform_translation(command)
        return self._translation_cache[command]
```

## Testing the Adapter

### Unit Tests

```python
class TestWriterAdapter:
    """Test writer-to-Git adaptations"""

    def test_save_adapts_to_commit(self):
        adapter = WriterAdapter(self.test_repo)
        result = adapter.save("Finished chapter 1")

        # Verify Git commit was created
        latest_commit = self.test_repo.head.target
        commit = self.test_repo[latest_commit]

        assert commit.message == "Finished chapter 1"
        assert result.success is True

    def test_exploration_adapts_to_branch(self):
        adapter = WriterAdapter(self.test_repo)
        result = adapter.create_exploration("alternative-ending")

        # Verify Git branch was created
        branch = self.test_repo.branches["alternative-ending"]
        assert branch is not None
        assert result.success is True
```

## Benefits of the Adapter Pattern

### For Writers
- **Familiar Terminology**: Writing-specific language reduces cognitive load
- **Simplified Operations**: Complex Git workflows become single actions
- **Contextual Guidance**: Help and suggestions tailored to writing tasks
- **Progressive Learning**: Advanced features introduced gradually

### For Developers
- **Clean Separation**: Clear boundary between domain logic and Git operations
- **Maintainability**: Changes to Git interface don't affect writer interface
- **Testability**: Each layer can be tested independently
- **Extensibility**: New writer features can be added without changing Git layer

### For the System
- **Flexibility**: Can adapt to different Git implementations
- **Compatibility**: Full Git functionality remains available when needed
- **Performance**: Optimized operations for common writing workflows
- **Reliability**: Error handling tailored to writing contexts

---

*The Adapter Pattern is crucial to GitWrite's success, enabling writers to leverage Git's powerful version control capabilities without being overwhelmed by its complexity. This pattern ensures that GitWrite feels like a natural writing tool rather than a technical system.*