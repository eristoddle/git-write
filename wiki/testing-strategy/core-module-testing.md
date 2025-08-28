# Core Module Testing

Comprehensive testing strategy for GitWrite's core modules including the Git abstraction layer, version control engine, annotation system, and export functionality. These tests ensure the reliability of the foundational components that power GitWrite's writing-focused features.

## Testing Architecture

```
Core Module Testing Structure
    │
    ├─ Git Engine Tests
    │   ├─ Repository Operations
    │   ├─ Commit Management
    │   └─ Branch Operations
    │
    ├─ Version Control Tests
    │   ├─ Save Operations
    │   ├─ History Management
    │   └─ Exploration (Branch) Logic
    │
    ├─ Annotation System Tests
    │   ├─ Position Tracking
    │   ├─ Feedback Management
    │   └─ Resolution Workflows
    │
    └─ Export System Tests
        ├─ Format Conversion
        ├─ Template Processing
        └─ Metadata Handling
```

## Git Engine Testing

### Repository Operations Testing

```python
# tests/core/test_git_engine.py
import pytest
import tempfile
import shutil
from pathlib import Path
from gitwrite.core.git_engine import GitEngine
from gitwrite.core.exceptions import RepositoryError, CommitError

@pytest.fixture
def temp_repo_path():
    """Create temporary repository for testing"""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)

@pytest.fixture
def git_engine(temp_repo_path):
    """Initialize Git engine with test repository"""
    engine = GitEngine(temp_repo_path)
    engine.init_repository()
    return engine

class TestGitEngine:

    def test_repository_initialization(self, temp_repo_path):
        """Test repository initialization"""
        engine = GitEngine(temp_repo_path)

        assert not engine.is_repository()

        engine.init_repository()

        assert engine.is_repository()
        assert (temp_repo_path / '.git').exists()
        assert engine.get_current_branch() == 'main'

    def test_file_operations(self, git_engine, temp_repo_path):
        """Test basic file operations"""
        test_file = temp_repo_path / 'test.md'
        content = "# Test Chapter\n\nThis is test content."

        # Create file
        git_engine.write_file('test.md', content)
        assert test_file.exists()
        assert test_file.read_text() == content

        # Update file
        new_content = content + "\n\nAdditional content."
        git_engine.write_file('test.md', new_content)
        assert test_file.read_text() == new_content

        # Delete file
        git_engine.delete_file('test.md')
        assert not test_file.exists()

    def test_commit_operations(self, git_engine):
        """Test commit creation and management"""
        # Create initial commit
        git_engine.write_file('chapter1.md', '# Chapter 1\nContent here.')

        commit_id = git_engine.commit_changes(
            message="Add Chapter 1",
            files=['chapter1.md'],
            author_name="Test Author",
            author_email="test@example.com"
        )

        assert commit_id is not None
        assert len(commit_id) == 40  # SHA-1 hash length

        # Verify commit details
        commit_info = git_engine.get_commit_info(commit_id)
        assert commit_info['message'] == "Add Chapter 1"
        assert commit_info['author']['name'] == "Test Author"
        assert 'chapter1.md' in commit_info['files_changed']

    def test_commit_history(self, git_engine):
        """Test commit history retrieval"""
        # Create multiple commits
        commits = []
        for i in range(3):
            git_engine.write_file(f'file{i}.md', f'Content {i}')
            commit_id = git_engine.commit_changes(
                message=f"Commit {i}",
                files=[f'file{i}.md']
            )
            commits.append(commit_id)

        # Get history
        history = git_engine.get_commit_history(limit=10)

        assert len(history) == 3
        assert history[0]['id'] == commits[2]  # Most recent first
        assert history[1]['id'] == commits[1]
        assert history[2]['id'] == commits[0]

    def test_branch_operations(self, git_engine):
        """Test branch creation and switching"""
        # Create initial commit
        git_engine.write_file('main.md', 'Main content')
        git_engine.commit_changes("Initial commit", ['main.md'])

        # Create new branch
        git_engine.create_branch('feature-branch')
        assert 'feature-branch' in git_engine.list_branches()

        # Switch to new branch
        git_engine.switch_branch('feature-branch')
        assert git_engine.get_current_branch() == 'feature-branch'

        # Make changes on feature branch
        git_engine.write_file('feature.md', 'Feature content')
        git_engine.commit_changes("Add feature", ['feature.md'])

        # Switch back to main
        git_engine.switch_branch('main')
        assert git_engine.get_current_branch() == 'main'
        assert not (Path(git_engine.repo_path) / 'feature.md').exists()

    def test_merge_operations(self, git_engine):
        """Test branch merging"""
        # Setup branches with different content
        git_engine.write_file('base.md', 'Base content')
        base_commit = git_engine.commit_changes("Base commit", ['base.md'])

        # Create and switch to feature branch
        git_engine.create_branch('feature')
        git_engine.switch_branch('feature')
        git_engine.write_file('feature.md', 'Feature content')
        feature_commit = git_engine.commit_changes("Feature commit", ['feature.md'])

        # Switch back to main and merge
        git_engine.switch_branch('main')
        merge_result = git_engine.merge_branch('feature')

        assert merge_result['success'] == True
        assert merge_result['merge_commit'] is not None
        assert (Path(git_engine.repo_path) / 'feature.md').exists()

    def test_conflict_detection(self, git_engine):
        """Test merge conflict detection and handling"""
        # Create file on main branch
        git_engine.write_file('conflict.md', 'Original content')
        git_engine.commit_changes("Original", ['conflict.md'])

        # Create feature branch and modify same file
        git_engine.create_branch('feature')
        git_engine.switch_branch('feature')
        git_engine.write_file('conflict.md', 'Feature content')
        git_engine.commit_changes("Feature change", ['conflict.md'])

        # Modify same file on main branch
        git_engine.switch_branch('main')
        git_engine.write_file('conflict.md', 'Main content')
        git_engine.commit_changes("Main change", ['conflict.md'])

        # Attempt merge - should detect conflict
        merge_result = git_engine.merge_branch('feature')

        assert merge_result['success'] == False
        assert merge_result['conflicts'] == ['conflict.md']
        assert merge_result['merge_commit'] is None

    def test_diff_operations(self, git_engine):
        """Test diff generation between commits"""
        # Create initial file
        git_engine.write_file('test.md', 'Line 1\nLine 2\nLine 3')
        commit1 = git_engine.commit_changes("Initial", ['test.md'])

        # Modify file
        git_engine.write_file('test.md', 'Line 1\nModified Line 2\nLine 3\nLine 4')
        commit2 = git_engine.commit_changes("Modified", ['test.md'])

        # Get diff
        diff = git_engine.get_diff(commit1, commit2)

        assert 'test.md' in diff
        file_diff = diff['test.md']
        assert len(file_diff['additions']) == 2  # Modified line + new line
        assert len(file_diff['deletions']) == 1  # Original line 2
        assert 'Modified Line 2' in file_diff['additions'][0]['content']
```

### Version Control Abstraction Testing

```python
# tests/core/test_version_control.py
import pytest
from gitwrite.core.version_control import VersionControl
from gitwrite.core.models import SaveResult, ExplorationInfo

@pytest.fixture
def version_control(temp_repo_path):
    return VersionControl(temp_repo_path)

class TestVersionControl:

    def test_save_operation(self, version_control):
        """Test the high-level save operation"""
        # Create content
        version_control.write_file('chapter1.md', '# Chapter 1\nContent')

        # Perform save
        result = version_control.save(
            message="Added first chapter",
            files=['chapter1.md']
        )

        assert isinstance(result, SaveResult)
        assert result.success == True
        assert result.commit_id is not None
        assert result.files_changed == ['chapter1.md']
        assert result.word_count_change > 0

    def test_exploration_creation(self, version_control):
        """Test exploration (branch) creation"""
        # Create base content
        version_control.write_file('base.md', 'Base content')
        version_control.save("Base content", ['base.md'])

        # Create exploration
        exploration = version_control.create_exploration(
            name="character-development",
            description="Exploring character backstory"
        )

        assert isinstance(exploration, ExplorationInfo)
        assert exploration.name == "character-development"
        assert exploration.status == "active"
        assert exploration.commits_ahead == 0
        assert exploration.commits_behind == 0

    def test_exploration_workflow(self, version_control):
        """Test complete exploration workflow"""
        # Base setup
        version_control.write_file('story.md', 'Original story')
        base_save = version_control.save("Original story", ['story.md'])

        # Create exploration
        exploration = version_control.create_exploration(
            name="alternate-plot",
            description="Trying different plot direction"
        )

        # Switch to exploration
        version_control.switch_exploration("alternate-plot")

        # Make changes
        version_control.write_file('story.md', 'Alternate story direction')
        version_control.save("Alternate plot", ['story.md'])

        # Check exploration status
        updated_exploration = version_control.get_exploration("alternate-plot")
        assert updated_exploration.commits_ahead == 1
        assert updated_exploration.word_count_difference != 0

        # Merge exploration
        merge_result = version_control.merge_exploration(
            exploration_name="alternate-plot",
            message="Merged alternate plot"
        )

        assert merge_result.success == True
        assert merge_result.files_merged == ['story.md']

    def test_word_count_tracking(self, version_control):
        """Test word count calculation and tracking"""
        # Initial content
        content1 = "This is a test with exactly eight words here."
        version_control.write_file('test.md', content1)
        result1 = version_control.save("Initial content", ['test.md'])

        # Updated content
        content2 = content1 + " Adding five more words here."
        version_control.write_file('test.md', content2)
        result2 = version_control.save("Added content", ['test.md'])

        assert result1.word_count_change == 8  # Initial word count
        assert result2.word_count_change == 5  # Added words
        assert result2.total_word_count == 13  # Total after addition

    def test_file_history_tracking(self, version_control):
        """Test file-specific history tracking"""
        filename = 'tracked_file.md'

        # Create file with multiple versions
        versions = [
            "Version 1 content",
            "Version 2 with more content",
            "Version 3 with even more comprehensive content"
        ]

        for i, content in enumerate(versions):
            version_control.write_file(filename, content)
            version_control.save(f"Version {i+1}", [filename])

        # Get file history
        history = version_control.get_file_history(filename)

        assert len(history) == 3
        assert history[0]['message'] == "Version 3"  # Most recent first
        assert history[1]['message'] == "Version 2"
        assert history[2]['message'] == "Version 1"

    def test_rollback_operations(self, version_control):
        """Test rollback to previous versions"""
        # Create initial state
        version_control.write_file('rollback_test.md', 'Original content')
        original_save = version_control.save("Original", ['rollback_test.md'])

        # Make unwanted changes
        version_control.write_file('rollback_test.md', 'Unwanted changes')
        version_control.save("Unwanted changes", ['rollback_test.md'])

        # Rollback to original
        rollback_result = version_control.rollback_to_save(original_save.commit_id)

        assert rollback_result.success == True

        # Verify content is restored
        content = version_control.read_file('rollback_test.md')
        assert content == 'Original content'
```

## Annotation System Testing

```python
# tests/core/test_annotation_system.py
import pytest
from gitwrite.core.annotation_system import AnnotationManager
from gitwrite.core.models import Annotation, AnnotationPosition

@pytest.fixture
def annotation_manager(temp_repo_path):
    return AnnotationManager(temp_repo_path)

class TestAnnotationSystem:

    def test_annotation_creation(self, annotation_manager):
        """Test creating annotations with position tracking"""
        # Create file content
        content = """# Chapter 1

This is the first paragraph of the chapter.
It contains multiple sentences for testing.

This is the second paragraph with different content.
"""

        position = AnnotationPosition(
            file_path='chapter1.md',
            line_start=3,
            line_end=4,
            character_start=0,
            character_end=50
        )

        annotation = annotation_manager.create_annotation(
            content="This paragraph needs more detail about the setting.",
            position=position,
            annotation_type="suggestion"
        )

        assert annotation.id is not None
        assert annotation.content == "This paragraph needs more detail about the setting."
        assert annotation.position.file_path == 'chapter1.md'
        assert annotation.type == "suggestion"

    def test_position_persistence(self, annotation_manager):
        """Test that annotation positions persist across file changes"""
        # Create initial content with annotation
        initial_content = "Line 1\nLine 2\nLine 3\nLine 4"

        annotation = annotation_manager.create_annotation(
            content="Comment on line 3",
            position=AnnotationPosition(
                file_path='test.md',
                line_start=3,
                line_end=3
            )
        )

        # Modify file by adding content before the annotated line
        modified_content = "New Line 1\nNew Line 2\nLine 1\nLine 2\nLine 3\nLine 4"

        # Update annotation positions
        annotation_manager.update_positions_for_file_change(
            'test.md',
            initial_content,
            modified_content
        )

        # Verify annotation position was updated
        updated_annotation = annotation_manager.get_annotation(annotation.id)
        assert updated_annotation.position.line_start == 5  # Moved down 2 lines

    def test_annotation_resolution(self, annotation_manager):
        """Test annotation resolution workflow"""
        annotation = annotation_manager.create_annotation(
            content="Fix this typo",
            position=AnnotationPosition(file_path='test.md', line_start=1, line_end=1),
            annotation_type="issue"
        )

        # Resolve annotation
        resolution_result = annotation_manager.resolve_annotation(
            annotation.id,
            resolution="fixed",
            message="Fixed the typo as suggested"
        )

        assert resolution_result.success == True

        # Verify resolution
        resolved_annotation = annotation_manager.get_annotation(annotation.id)
        assert resolved_annotation.status == "resolved"
        assert resolved_annotation.resolution_message == "Fixed the typo as suggested"
        assert resolved_annotation.resolved_at is not None

    def test_threaded_annotations(self, annotation_manager):
        """Test threaded annotation conversations"""
        # Create parent annotation
        parent = annotation_manager.create_annotation(
            content="What do you think about this character's motivation?",
            position=AnnotationPosition(file_path='chapter.md', line_start=10, line_end=15),
            annotation_type="question"
        )

        # Create reply
        reply = annotation_manager.create_annotation(
            content="I think the motivation needs to be clearer in the previous chapter.",
            position=AnnotationPosition(file_path='chapter.md', line_start=10, line_end=15),
            parent_id=parent.id,
            annotation_type="comment"
        )

        # Get conversation thread
        thread = annotation_manager.get_annotation_thread(parent.id)

        assert len(thread) == 2
        assert thread[0].id == parent.id
        assert thread[1].id == reply.id
        assert thread[1].parent_id == parent.id

    def test_bulk_annotation_operations(self, annotation_manager):
        """Test bulk operations on annotations"""
        # Create multiple annotations
        annotations = []
        for i in range(5):
            annotation = annotation_manager.create_annotation(
                content=f"Comment {i}",
                position=AnnotationPosition(
                    file_path='bulk_test.md',
                    line_start=i+1,
                    line_end=i+1
                )
            )
            annotations.append(annotation)

        # Test bulk resolution
        annotation_ids = [a.id for a in annotations[:3]]
        bulk_result = annotation_manager.resolve_annotations_bulk(
            annotation_ids,
            resolution="batch_resolved"
        )

        assert bulk_result.success == True
        assert bulk_result.resolved_count == 3

        # Verify resolutions
        for annotation_id in annotation_ids:
            annotation = annotation_manager.get_annotation(annotation_id)
            assert annotation.status == "resolved"
```

## Export System Testing

```python
# tests/core/test_export_system.py
import pytest
from pathlib import Path
from gitwrite.core.export_system import ExportEngine
from gitwrite.core.models import ExportConfiguration, ExportFormat

@pytest.fixture
def export_engine(temp_repo_path):
    return ExportEngine(temp_repo_path)

class TestExportSystem:

    def test_markdown_to_html_export(self, export_engine, temp_repo_path):
        """Test basic markdown to HTML export"""
        # Create source content
        markdown_content = """# My Novel

## Chapter 1: The Beginning

This is the opening chapter of my novel.
It has **bold text** and *italic text*.

- List item 1
- List item 2

> This is a blockquote.
"""

        source_file = temp_repo_path / 'novel.md'
        source_file.write_text(markdown_content)

        # Configure export
        config = ExportConfiguration(
            format=ExportFormat.HTML,
            include_toc=True,
            include_metadata=True,
            title="My Novel"
        )

        # Perform export
        result = export_engine.export_file('novel.md', config)

        assert result.success == True
        assert result.output_path.suffix == '.html'

        # Verify HTML content
        html_content = result.output_path.read_text()
        assert '<h1>My Novel</h1>' in html_content
        assert '<h2>Chapter 1: The Beginning</h2>' in html_content
        assert '<strong>bold text</strong>' in html_content
        assert '<em>italic text</em>' in html_content

    def test_epub_export(self, export_engine, temp_repo_path):
        """Test EPUB export with multiple chapters"""
        # Create multiple chapter files
        chapters = [
            ("chapter01.md", "# Chapter 1\n\nFirst chapter content"),
            ("chapter02.md", "# Chapter 2\n\nSecond chapter content"),
            ("chapter03.md", "# Chapter 3\n\nThird chapter content")
        ]

        for filename, content in chapters:
            (temp_repo_path / filename).write_text(content)

        # Configure EPUB export
        config = ExportConfiguration(
            format=ExportFormat.EPUB,
            title="Test Novel",
            author="Test Author",
            include_toc=True,
            chapter_files=['chapter01.md', 'chapter02.md', 'chapter03.md']
        )

        # Perform export
        result = export_engine.export_project(config)

        assert result.success == True
        assert result.output_path.suffix == '.epub'

        # Verify EPUB structure (simplified check)
        assert result.output_path.exists()
        assert result.output_path.stat().st_size > 1000  # Non-empty file

    def test_pdf_export_with_template(self, export_engine, temp_repo_path):
        """Test PDF export with custom template"""
        # Create content
        content = """# Test Document

This is a test document for PDF export.

## Section 1

Content for section 1.

## Section 2

Content for section 2.
"""

        (temp_repo_path / 'document.md').write_text(content)

        # Configure PDF export
        config = ExportConfiguration(
            format=ExportFormat.PDF,
            template='manuscript',
            page_size='letter',
            margin_top='1in',
            margin_bottom='1in',
            font_family='Times New Roman',
            font_size='12pt',
            line_spacing='double'
        )

        # Perform export
        result = export_engine.export_file('document.md', config)

        assert result.success == True
        assert result.output_path.suffix == '.pdf'
        assert result.output_path.exists()

    def test_export_with_custom_filters(self, export_engine, temp_repo_path):
        """Test export with custom content filters"""
        # Create content with annotations and comments
        content = """# Chapter 1

This is normal content.

<!-- TODO: Expand this section -->

This paragraph has [ANNOTATION: Fix grammar] some issues.

[DRAFT: This is draft content that should be filtered out]

This is final content.
"""

        (temp_repo_path / 'draft.md').write_text(content)

        # Configure export with filters
        config = ExportConfiguration(
            format=ExportFormat.HTML,
            filters=[
                'remove_comments',
                'remove_annotations',
                'remove_draft_markers'
            ]
        )

        # Perform export
        result = export_engine.export_file('draft.md', config)

        assert result.success == True

        # Verify filtered content
        html_content = result.output_path.read_text()
        assert '<!-- TODO:' not in html_content
        assert '[ANNOTATION:' not in html_content
        assert '[DRAFT:' not in html_content
        assert 'This is normal content' in html_content
        assert 'This is final content' in html_content

    def test_export_metadata_inclusion(self, export_engine, temp_repo_path):
        """Test metadata inclusion in exports"""
        # Create content with metadata
        content = """---
title: Test Document
author: Test Author
date: 2024-01-01
keywords: [test, document, export]
---

# Test Document

Content here.
"""

        (temp_repo_path / 'with_metadata.md').write_text(content)

        # Configure export with metadata
        config = ExportConfiguration(
            format=ExportFormat.HTML,
            include_metadata=True,
            metadata_template='standard'
        )

        # Perform export
        result = export_engine.export_file('with_metadata.md', config)

        assert result.success == True

        # Verify metadata in output
        html_content = result.output_path.read_text()
        assert '<title>Test Document</title>' in html_content
        assert 'Test Author' in html_content
        assert '2024-01-01' in html_content

    def test_export_error_handling(self, export_engine, temp_repo_path):
        """Test export error handling"""
        # Test with non-existent file
        config = ExportConfiguration(format=ExportFormat.HTML)
        result = export_engine.export_file('nonexistent.md', config)

        assert result.success == False
        assert 'file not found' in result.error_message.lower()

        # Test with invalid template
        (temp_repo_path / 'test.md').write_text('# Test')
        config = ExportConfiguration(
            format=ExportFormat.PDF,
            template='nonexistent_template'
        )

        result = export_engine.export_file('test.md', config)
        assert result.success == False
        assert 'template' in result.error_message.lower()
```

## Performance and Load Testing

```python
# tests/core/test_performance.py
import pytest
import time
from concurrent.futures import ThreadPoolExecutor

class TestCorePerformance:

    def test_large_file_handling(self, git_engine):
        """Test performance with large files"""
        # Create large content (10MB)
        large_content = "This is a test line.\n" * 500000

        start_time = time.time()
        git_engine.write_file('large_file.md', large_content)
        write_time = time.time() - start_time

        start_time = time.time()
        read_content = git_engine.read_file('large_file.md')
        read_time = time.time() - start_time

        assert write_time < 5.0  # Should complete within 5 seconds
        assert read_time < 2.0   # Should read within 2 seconds
        assert read_content == large_content

    def test_concurrent_operations(self, git_engine):
        """Test concurrent file operations"""
        def create_file(index):
            content = f"File {index} content with some text."
            git_engine.write_file(f'concurrent_{index}.md', content)
            return git_engine.commit_changes(f"Add file {index}", [f'concurrent_{index}.md'])

        # Perform concurrent operations
        with ThreadPoolExecutor(max_workers=5) as executor:
            start_time = time.time()
            futures = [executor.submit(create_file, i) for i in range(10)]
            results = [future.result() for future in futures]
            duration = time.time() - start_time

        assert len(results) == 10
        assert all(result is not None for result in results)
        assert duration < 10.0  # Should complete within 10 seconds

    def test_history_performance(self, git_engine):
        """Test performance with large commit history"""
        # Create many commits
        for i in range(100):
            git_engine.write_file(f'history_test.md', f'Version {i} content')
            git_engine.commit_changes(f"Version {i}", ['history_test.md'])

        # Test history retrieval performance
        start_time = time.time()
        history = git_engine.get_commit_history(limit=50)
        duration = time.time() - start_time

        assert len(history) == 50
        assert duration < 2.0  # Should complete within 2 seconds
```

---

*Comprehensive core module testing ensures GitWrite's foundational components are reliable, performant, and maintain data integrity. These tests validate the critical Git abstraction layer, version control logic, annotation system, and export functionality that power GitWrite's writer-focused features.*