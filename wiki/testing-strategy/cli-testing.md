# CLI Testing

Comprehensive testing strategy for GitWrite's command-line interface, ensuring reliable operation across different environments, user scenarios, and edge cases. The CLI testing covers command validation, integration testing, user workflow simulation, and cross-platform compatibility.

## Testing Overview

```
CLI Testing Strategy
    │
    ├─ Unit Tests
    │   ├─ Command Parsing
    │   ├─ Argument Validation
    │   └─ Option Processing
    │
    ├─ Integration Tests
    │   ├─ Command Execution
    │   ├─ File System Operations
    │   └─ Git Integration
    │
    ├─ Workflow Tests
    │   ├─ User Scenarios
    │   ├─ Error Handling
    │   └─ Recovery Procedures
    │
    └─ Cross-Platform Tests
        ├─ Windows Compatibility
        ├─ macOS Compatibility
        └─ Linux Distributions
```

## Unit Testing

### Command Structure Testing

```python
# tests/cli/test_commands.py
import pytest
from click.testing import CliRunner
from gitwrite.cli.main import cli
from gitwrite.cli.commands import repository, save, explore

class TestCommandStructure:
    """Test CLI command structure and parsing."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_main_cli_help(self):
        """Test main CLI help output."""
        result = self.runner.invoke(cli, ['--help'])

        assert result.exit_code == 0
        assert 'GitWrite' in result.output
        assert 'Version control for writers' in result.output
        assert 'Commands:' in result.output

    def test_repository_commands_available(self):
        """Test repository subcommands are available."""
        result = self.runner.invoke(cli, ['repository', '--help'])

        assert result.exit_code == 0
        assert 'create' in result.output
        assert 'list' in result.output
        assert 'delete' in result.output
        assert 'info' in result.output

    def test_save_command_options(self):
        """Test save command options."""
        result = self.runner.invoke(cli, ['save', '--help'])

        assert result.exit_code == 0
        assert '--message' in result.output
        assert '--files' in result.output
        assert '--all' in result.output

    def test_explore_command_structure(self):
        """Test exploration command structure."""
        result = self.runner.invoke(cli, ['explore', '--help'])

        assert result.exit_code == 0
        assert 'create' in result.output
        assert 'list' in result.output
        assert 'switch' in result.output
        assert 'merge' in result.output

    def test_invalid_command_handling(self):
        """Test handling of invalid commands."""
        result = self.runner.invoke(cli, ['invalid-command'])

        assert result.exit_code != 0
        assert 'No such command' in result.output

    def test_command_argument_validation(self):
        """Test argument validation for commands."""
        # Test missing required arguments
        result = self.runner.invoke(cli, ['repository', 'create'])
        assert result.exit_code != 0

        # Test invalid argument types
        result = self.runner.invoke(cli, ['save', '--files', 'nonexistent.txt'])
        assert result.exit_code != 0

class TestArgumentParsing:
    """Test command argument and option parsing."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_file_path_parsing(self):
        """Test file path argument parsing."""
        with self.runner.isolated_filesystem():
            # Create test file
            with open('test.md', 'w') as f:
                f.write('# Test')

            result = self.runner.invoke(cli, ['save', '--files', 'test.md', '--message', 'Test save'])
            # Should not fail on parsing
            assert '--files' in str(result)

    def test_boolean_flag_parsing(self):
        """Test boolean flag parsing."""
        result = self.runner.invoke(cli, ['repository', 'create', 'test-repo', '--public'])
        # Should parse public flag correctly
        assert result.exit_code in [0, 1]  # May fail on execution but parsing should work

    def test_multiple_value_options(self):
        """Test options that accept multiple values."""
        result = self.runner.invoke(cli, [
            'save',
            '--files', 'file1.md',
            '--files', 'file2.md',
            '--message', 'Multi-file save'
        ])
        # Should handle multiple file arguments
        assert result.exit_code in [0, 1]

    def test_environment_variable_usage(self):
        """Test environment variable integration."""
        import os

        # Test with environment variable
        os.environ['GITWRITE_REPO'] = 'test-repo'
        result = self.runner.invoke(cli, ['save', '--message', 'Test'])

        # Clean up
        if 'GITWRITE_REPO' in os.environ:
            del os.environ['GITWRITE_REPO']
```

### Configuration Testing

```python
# tests/cli/test_configuration.py
import pytest
import tempfile
import yaml
from pathlib import Path
from gitwrite.cli.config import Configuration

class TestConfiguration:
    """Test CLI configuration management."""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / 'config.yaml'

    def test_default_configuration(self):
        """Test default configuration values."""
        config = Configuration()

        assert config.get('editor.auto_save') == True
        assert config.get('git.default_branch') == 'main'
        assert config.get('ui.theme') == 'auto'

    def test_configuration_file_loading(self):
        """Test loading configuration from file."""
        config_data = {
            'editor': {
                'auto_save': False,
                'save_interval': 60
            },
            'git': {
                'default_branch': 'master',
                'auto_commit': True
            }
        }

        with open(self.config_path, 'w') as f:
            yaml.dump(config_data, f)

        config = Configuration(config_file=self.config_path)

        assert config.get('editor.auto_save') == False
        assert config.get('editor.save_interval') == 60
        assert config.get('git.default_branch') == 'master'

    def test_configuration_override(self):
        """Test configuration value override."""
        config = Configuration()

        # Override value
        config.set('editor.font_size', 14)
        assert config.get('editor.font_size') == 14

        # Override nested value
        config.set('git.user.name', 'Test User')
        assert config.get('git.user.name') == 'Test User'

    def test_configuration_persistence(self):
        """Test configuration persistence to file."""
        config = Configuration(config_file=self.config_path)

        config.set('editor.theme', 'dark')
        config.set('writer.daily_goal', 1000)
        config.save()

        # Load new instance and verify
        new_config = Configuration(config_file=self.config_path)
        assert new_config.get('editor.theme') == 'dark'
        assert new_config.get('writer.daily_goal') == 1000

    def test_environment_variable_override(self):
        """Test environment variable configuration override."""
        import os

        os.environ['GITWRITE_EDITOR_AUTO_SAVE'] = 'false'
        os.environ['GITWRITE_GIT_DEFAULT_BRANCH'] = 'develop'

        config = Configuration()

        assert config.get('editor.auto_save') == False
        assert config.get('git.default_branch') == 'develop'

        # Clean up
        del os.environ['GITWRITE_EDITOR_AUTO_SAVE']
        del os.environ['GITWRITE_GIT_DEFAULT_BRANCH']
```

## Integration Testing

### Command Execution Testing

```python
# tests/cli/test_integration.py
import pytest
import tempfile
import shutil
from pathlib import Path
from click.testing import CliRunner
from gitwrite.cli.main import cli

class TestCommandExecution:
    """Test full command execution workflows."""

    def setup_method(self):
        self.runner = CliRunner()
        self.temp_dir = tempfile.mkdtemp()
        self.original_dir = Path.cwd()

    def teardown_method(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_repository_lifecycle(self):
        """Test complete repository lifecycle."""
        with self.runner.isolated_filesystem():
            # Create repository
            result = self.runner.invoke(cli, [
                'repository', 'create', 'test-novel',
                '--description', 'Test novel repository'
            ])
            assert result.exit_code == 0
            assert 'Created repository' in result.output

            # Verify repository exists
            result = self.runner.invoke(cli, ['repository', 'list'])
            assert result.exit_code == 0
            assert 'test-novel' in result.output

            # Get repository info
            result = self.runner.invoke(cli, ['repository', 'info', 'test-novel'])
            assert result.exit_code == 0
            assert 'test-novel' in result.output

    def test_file_operations_workflow(self):
        """Test file creation and modification workflow."""
        with self.runner.isolated_filesystem():
            # Create repository
            self.runner.invoke(cli, ['repository', 'create', 'test-repo'])

            # Create file
            with open('chapter1.md', 'w') as f:
                f.write('# Chapter 1\n\nThis is the first chapter.')

            # Save file
            result = self.runner.invoke(cli, [
                'save', '--files', 'chapter1.md',
                '--message', 'Added first chapter'
            ])
            assert result.exit_code == 0

            # Modify file
            with open('chapter1.md', 'a') as f:
                f.write('\n\nAdditional content.')

            # Save changes
            result = self.runner.invoke(cli, [
                'save', '--files', 'chapter1.md',
                '--message', 'Added more content'
            ])
            assert result.exit_code == 0

    def test_exploration_workflow(self):
        """Test exploration (branching) workflow."""
        with self.runner.isolated_filesystem():
            # Setup repository with content
            self.runner.invoke(cli, ['repository', 'create', 'test-repo'])

            with open('story.md', 'w') as f:
                f.write('# Main Story\n\nOriginal storyline.')

            self.runner.invoke(cli, [
                'save', '--files', 'story.md',
                '--message', 'Initial story'
            ])

            # Create exploration
            result = self.runner.invoke(cli, [
                'explore', 'create', 'alternate-ending',
                '--description', 'Try different ending'
            ])
            assert result.exit_code == 0

            # Switch to exploration
            result = self.runner.invoke(cli, [
                'explore', 'switch', 'alternate-ending'
            ])
            assert result.exit_code == 0

            # Modify in exploration
            with open('story.md', 'a') as f:
                f.write('\n\nAlternate ending content.')

            self.runner.invoke(cli, [
                'save', '--files', 'story.md',
                '--message', 'Added alternate ending'
            ])

            # List explorations
            result = self.runner.invoke(cli, ['explore', 'list'])
            assert result.exit_code == 0
            assert 'alternate-ending' in result.output

class TestErrorHandling:
    """Test CLI error handling and recovery."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_missing_repository_error(self):
        """Test error when repository doesn't exist."""
        with self.runner.isolated_filesystem():
            result = self.runner.invoke(cli, [
                'save', '--files', 'test.md',
                '--message', 'Test save'
            ])

            assert result.exit_code != 0
            assert 'repository' in result.output.lower()

    def test_invalid_file_path_error(self):
        """Test error handling for invalid file paths."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'test-repo'])

            result = self.runner.invoke(cli, [
                'save', '--files', 'nonexistent.md',
                '--message', 'Test save'
            ])

            assert result.exit_code != 0

    def test_git_operation_error_handling(self):
        """Test handling of Git operation errors."""
        with self.runner.isolated_filesystem():
            # Create repository
            self.runner.invoke(cli, ['repository', 'create', 'test-repo'])

            # Try to create exploration with invalid name
            result = self.runner.invoke(cli, [
                'explore', 'create', 'invalid/name',
                '--description', 'Invalid exploration name'
            ])

            assert result.exit_code != 0

    def test_permission_error_handling(self):
        """Test handling of file permission errors."""
        with self.runner.isolated_filesystem():
            # Create read-only file
            with open('readonly.md', 'w') as f:
                f.write('Read-only content')

            import os
            os.chmod('readonly.md', 0o444)

            self.runner.invoke(cli, ['repository', 'create', 'test-repo'])

            # Try to save read-only file
            result = self.runner.invoke(cli, [
                'save', '--files', 'readonly.md',
                '--message', 'Try to save readonly'
            ])

            # Should handle permission error gracefully
            assert result.exit_code != 0
```

## User Workflow Testing

### Scenario-Based Testing

```python
# tests/cli/test_user_workflows.py
import pytest
from click.testing import CliRunner
from gitwrite.cli.main import cli

class TestWriterWorkflows:
    """Test real-world writer workflows."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_daily_writing_session(self):
        """Test typical daily writing session workflow."""
        with self.runner.isolated_filesystem():
            # Start session - create repository
            result = self.runner.invoke(cli, [
                'repository', 'create', 'my-novel',
                '--description', 'My first novel'
            ])
            assert result.exit_code == 0

            # Create initial chapter
            with open('chapter01.md', 'w') as f:
                f.write('# Chapter 1: The Beginning\n\nIt was a dark and stormy night...')

            # Save initial work
            result = self.runner.invoke(cli, [
                'save', '--files', 'chapter01.md',
                '--message', 'Started Chapter 1'
            ])
            assert result.exit_code == 0

            # Continue writing (simulate editing)
            with open('chapter01.md', 'a') as f:
                f.write('\n\nThe rain pelted against the windows...')

            # Save progress
            result = self.runner.invoke(cli, [
                'save', '--files', 'chapter01.md',
                '--message', 'Added opening scene description'
            ])
            assert result.exit_code == 0

            # Check writing statistics
            result = self.runner.invoke(cli, ['stats', 'word-count'])
            assert result.exit_code == 0

    def test_collaborative_editing_workflow(self):
        """Test collaborative editing workflow."""
        with self.runner.isolated_filesystem():
            # Author creates repository
            self.runner.invoke(cli, [
                'repository', 'create', 'collaborative-story',
                '--description', 'Story written by multiple authors'
            ])

            # Create base content
            with open('story.md', 'w') as f:
                f.write('# Collaborative Story\n\nBase story content.')

            self.runner.invoke(cli, [
                'save', '--files', 'story.md',
                '--message', 'Initial story setup'
            ])

            # Simulate collaborator making changes
            self.runner.invoke(cli, [
                'explore', 'create', 'character-development',
                '--description', 'Focus on character development'
            ])

            self.runner.invoke(cli, [
                'explore', 'switch', 'character-development'
            ])

            # Add character development
            with open('characters.md', 'w') as f:
                f.write('# Characters\n\n## Main Character\nDetailed background...')

            self.runner.invoke(cli, [
                'save', '--files', 'characters.md',
                '--message', 'Added character profiles'
            ])

            # Switch back and merge
            self.runner.invoke(cli, ['explore', 'switch', 'main'])

            result = self.runner.invoke(cli, [
                'explore', 'merge', 'character-development',
                '--message', 'Merged character development'
            ])
            assert result.exit_code == 0

    def test_revision_workflow(self):
        """Test revision and editing workflow."""
        with self.runner.isolated_filesystem():
            # Setup repository and content
            self.runner.invoke(cli, ['repository', 'create', 'revision-test'])

            # Create first draft
            with open('draft.md', 'w') as f:
                f.write('# First Draft\n\nThis is the initial version.')

            self.runner.invoke(cli, [
                'save', '--files', 'draft.md',
                '--message', 'First draft complete'
            ])

            # Create revision exploration
            self.runner.invoke(cli, [
                'explore', 'create', 'second-draft',
                '--description', 'Major revision of first draft'
            ])

            self.runner.invoke(cli, ['explore', 'switch', 'second-draft'])

            # Major revision
            with open('draft.md', 'w') as f:
                f.write('# Second Draft\n\nCompletely rewritten version with better structure.')

            self.runner.invoke(cli, [
                'save', '--files', 'draft.md',
                '--message', 'Major revision completed'
            ])

            # Compare versions
            result = self.runner.invoke(cli, [
                'diff', 'main', 'second-draft', '--file', 'draft.md'
            ])
            assert result.exit_code == 0

class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_large_file_handling(self):
        """Test handling of large files."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'large-files'])

            # Create large file (simulate large manuscript)
            large_content = "This is a test line.\n" * 10000
            with open('large_manuscript.md', 'w') as f:
                f.write(large_content)

            result = self.runner.invoke(cli, [
                'save', '--files', 'large_manuscript.md',
                '--message', 'Added large manuscript'
            ])

            # Should handle large files gracefully
            assert result.exit_code == 0

    def test_special_characters_in_filenames(self):
        """Test handling of special characters in filenames."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'special-chars'])

            # Create files with special characters
            special_files = [
                'file with spaces.md',
                'file-with-dashes.md',
                'file_with_underscores.md',
                'file.with.dots.md'
            ]

            for filename in special_files:
                with open(filename, 'w') as f:
                    f.write(f'# {filename}\n\nContent for {filename}')

                result = self.runner.invoke(cli, [
                    'save', '--files', filename,
                    '--message', f'Added {filename}'
                ])

                # Should handle special characters in filenames
                assert result.exit_code == 0

    def test_concurrent_save_attempts(self):
        """Test handling of concurrent save attempts."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'concurrent-test'])

            # Create test file
            with open('concurrent.md', 'w') as f:
                f.write('# Concurrent Test\n\nOriginal content.')

            # Simulate rapid saves (would need threading for true concurrency)
            for i in range(5):
                with open('concurrent.md', 'a') as f:
                    f.write(f'\nLine {i}')

                result = self.runner.invoke(cli, [
                    'save', '--files', 'concurrent.md',
                    '--message', f'Rapid save {i}'
                ])

                # Should handle rapid saves gracefully
                assert result.exit_code == 0
```

## Cross-Platform Testing

### Platform Compatibility

```python
# tests/cli/test_cross_platform.py
import pytest
import platform
import os
from pathlib import Path
from click.testing import CliRunner
from gitwrite.cli.main import cli

class TestCrossPlatformCompatibility:
    """Test CLI compatibility across different platforms."""

    def setup_method(self):
        self.runner = CliRunner()
        self.platform = platform.system()

    def test_path_handling(self):
        """Test cross-platform path handling."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'path-test'])

            # Test different path formats
            if self.platform == 'Windows':
                test_paths = ['chapter1.md', 'folder\\chapter2.md']
            else:
                test_paths = ['chapter1.md', 'folder/chapter2.md']

            for path in test_paths:
                # Create directory if needed
                path_obj = Path(path)
                if path_obj.parent != Path('.'):
                    path_obj.parent.mkdir(exist_ok=True)

                # Create file
                with open(path, 'w') as f:
                    f.write(f'# Content for {path}')

                result = self.runner.invoke(cli, [
                    'save', '--files', path,
                    '--message', f'Added {path}'
                ])

                assert result.exit_code == 0

    def test_file_permissions(self):
        """Test file permission handling across platforms."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'permissions-test'])

            # Create test file
            with open('permissions.md', 'w') as f:
                f.write('# Permissions Test')

            if self.platform != 'Windows':
                # Test executable permission (Unix-like only)
                os.chmod('permissions.md', 0o755)

                result = self.runner.invoke(cli, [
                    'save', '--files', 'permissions.md',
                    '--message', 'File with execute permission'
                ])

                assert result.exit_code == 0

    def test_line_ending_handling(self):
        """Test line ending handling across platforms."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'line-endings'])

            # Test different line endings
            content_unix = "Line 1\nLine 2\nLine 3\n"
            content_windows = "Line 1\r\nLine 2\r\nLine 3\r\n"

            with open('unix_endings.md', 'w', newline='\n') as f:
                f.write(content_unix)

            with open('windows_endings.md', 'w', newline='\r\n') as f:
                f.write(content_windows)

            # Should handle both line ending types
            for filename in ['unix_endings.md', 'windows_endings.md']:
                result = self.runner.invoke(cli, [
                    'save', '--files', filename,
                    '--message', f'Added {filename}'
                ])
                assert result.exit_code == 0

    @pytest.mark.skipif(platform.system() == 'Windows', reason="Unix-specific test")
    def test_unix_specific_features(self):
        """Test Unix-specific CLI features."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'unix-test'])

            # Test symlink handling
            with open('original.md', 'w') as f:
                f.write('# Original File')

            os.symlink('original.md', 'symlink.md')

            result = self.runner.invoke(cli, [
                'save', '--files', 'symlink.md',
                '--message', 'Added symlink'
            ])

            # Should handle symlinks appropriately
            assert result.exit_code in [0, 1]  # May warn about symlinks

    @pytest.mark.skipif(platform.system() != 'Windows', reason="Windows-specific test")
    def test_windows_specific_features(self):
        """Test Windows-specific CLI features."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'windows-test'])

            # Test long path handling
            long_path = 'very_long_directory_name_that_exceeds_normal_limits'
            Path(long_path).mkdir(exist_ok=True)

            long_file_path = Path(long_path) / 'long_filename.md'
            with open(long_file_path, 'w') as f:
                f.write('# Long Path Test')

            result = self.runner.invoke(cli, [
                'save', '--files', str(long_file_path),
                '--message', 'Added file with long path'
            ])

            # Should handle long paths on Windows
            assert result.exit_code in [0, 1]
```

## Performance Testing

### CLI Performance Benchmarks

```python
# tests/cli/test_performance.py
import pytest
import time
import tempfile
from click.testing import CliRunner
from gitwrite.cli.main import cli

class TestCLIPerformance:
    """Test CLI performance characteristics."""

    def setup_method(self):
        self.runner = CliRunner()

    def test_startup_time(self):
        """Test CLI startup time."""
        start_time = time.time()
        result = self.runner.invoke(cli, ['--help'])
        end_time = time.time()

        startup_time = end_time - start_time

        assert result.exit_code == 0
        assert startup_time < 2.0  # Should start within 2 seconds

    def test_large_repository_performance(self):
        """Test performance with large repositories."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'large-repo'])

            # Create many files
            start_time = time.time()

            for i in range(100):
                filename = f'chapter_{i:03d}.md'
                with open(filename, 'w') as f:
                    f.write(f'# Chapter {i}\n\nContent for chapter {i}.')

            # Save all files
            result = self.runner.invoke(cli, [
                'save', '--all',
                '--message', 'Added 100 chapters'
            ])

            end_time = time.time()
            operation_time = end_time - start_time

            assert result.exit_code == 0
            assert operation_time < 30.0  # Should complete within 30 seconds

    def test_command_response_time(self):
        """Test individual command response times."""
        with self.runner.isolated_filesystem():
            self.runner.invoke(cli, ['repository', 'create', 'response-test'])

            # Test various command response times
            commands_to_test = [
                (['repository', 'list'], 5.0),
                (['repository', 'info', 'response-test'], 5.0),
                (['explore', 'list'], 3.0),
                (['stats', 'word-count'], 10.0)
            ]

            for command, max_time in commands_to_test:
                start_time = time.time()
                result = self.runner.invoke(cli, command)
                end_time = time.time()

                response_time = end_time - start_time

                assert result.exit_code in [0, 1]  # Success or expected failure
                assert response_time < max_time
```

---

*Comprehensive CLI testing ensures GitWrite's command-line interface works reliably across different platforms, user scenarios, and edge cases. The testing strategy covers functionality, error handling, performance, and cross-platform compatibility to deliver a robust user experience.*