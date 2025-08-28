# Export Functionality

GitWrite's export functionality transforms manuscripts into publication-ready documents in multiple formats. Built on Pandoc's document conversion engine, it provides professional-quality output with customizable formatting and publishing workflows.

## Overview

The export system bridges writing and publishing, enabling writers to generate professionally formatted documents from GitWrite projects while preserving version control information and metadata.

```
Writer Interface → Export Engine → Processing Pipeline → Output Documents
    ↓                ↓                ↓                    ↓
Format Selection   Content Assembly   Pandoc Engine      EPUB/PDF/DOCX
Template Choice    Metadata Injection LaTeX Processing   HTML/Markdown
Options Config     Template Processing Font Management   Custom Formats
```

## Core Components

### 1. Export Manager

```python
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

class ExportFormat(Enum):
    EPUB = "epub"
    PDF = "pdf"
    DOCX = "docx"
    HTML = "html"
    LATEX = "latex"
    MARKDOWN = "markdown"

class ExportStatus(Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class ExportConfiguration:
    """Configuration for export operation"""
    format: ExportFormat
    template: Optional[str] = None

    # Content selection
    include_files: Optional[List[str]] = None
    exclude_files: Optional[List[str]] = None

    # Metadata
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None

    # Options
    include_toc: bool = True
    include_version_info: bool = False
    pdf_options: Optional[Dict[str, Any]] = None
    epub_options: Optional[Dict[str, Any]] = None

@dataclass
class ExportResult:
    """Result of export operation"""
    export_id: str
    status: ExportStatus
    format: ExportFormat
    output_file: Optional[str] = None
    started_at: datetime = None
    completed_at: Optional[datetime] = None
    file_size_bytes: Optional[int] = None
    pages_count: Optional[int] = None
    words_count: Optional[int] = None
    error_message: Optional[str] = None

class ExportManager:
    """Manages document export operations"""

    def __init__(self, repository_path: str):
        self.repo_path = repository_path
        self.exports_dir = os.path.join(repository_path, '.gitwrite', 'exports')
        self.templates_dir = os.path.join(repository_path, '.gitwrite', 'templates')

    def export_document(
        self,
        config: ExportConfiguration,
        async_processing: bool = True
    ) -> ExportResult:
        """Export document in specified format"""

        export_id = f"export_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{config.format.value}"

        result = ExportResult(
            export_id=export_id,
            status=ExportStatus.QUEUED,
            format=config.format,
            started_at=datetime.utcnow()
        )

        if async_processing:
            self._queue_export(export_id, config)
        else:
            result = self._process_export(export_id, config)

        return result
```

### 2. Format-Specific Exporters

```python
class EPUBExporter:
    """EPUB-specific export functionality"""

    def export(self, export_id: str, config: ExportConfiguration, content_files: List[str]) -> ExportResult:
        """Export to EPUB format"""

        # Prepare content
        combined_content = self._combine_content_files(content_files)

        # Create metadata
        metadata = self._create_epub_metadata(config)

        # Build Pandoc command
        cmd = [
            'pandoc', combined_content,
            '--from', 'markdown',
            '--to', 'epub',
            '--output', f"{export_id}.epub",
            '--metadata-file', metadata
        ]

        if config.include_toc:
            cmd.extend(['--toc', '--toc-depth=3'])

        if config.cover_image:
            cmd.extend(['--epub-cover-image', config.cover_image])

        # Execute export
        return self._execute_pandoc_export(cmd, export_id)

class PDFExporter:
    """PDF-specific export functionality"""

    def export(self, export_id: str, config: ExportConfiguration, content_files: List[str]) -> ExportResult:
        """Export to PDF format"""

        combined_content = self._combine_content_files(content_files)

        cmd = [
            'pandoc', combined_content,
            '--from', 'markdown',
            '--to', 'pdf',
            '--output', f"{export_id}.pdf",
            '--pdf-engine', 'xelatex'
        ]

        if config.pdf_options:
            if 'margin' in config.pdf_options:
                cmd.extend(['-V', f"geometry:margin={config.pdf_options['margin']}"])
            if 'font_family' in config.pdf_options:
                cmd.extend(['-V', f"mainfont:{config.pdf_options['font_family']}"])

        return self._execute_pandoc_export(cmd, export_id)
```

### 3. Template System

```python
class ExportTemplateManager:
    """Manages export templates and customization"""

    def __init__(self, templates_directory: str):
        self.templates_dir = templates_directory
        self._create_default_templates()

    def _create_default_templates(self):
        """Create default export templates"""

        # Default EPUB CSS
        epub_css = """
        body { font-family: Georgia, serif; line-height: 1.6; margin: 2em; }
        h1, h2, h3 { color: #333; margin-top: 2em; }
        .chapter { page-break-before: always; }
        """

        # Default LaTeX template
        latex_template = """
        \\documentclass[12pt,letterpaper]{book}
        \\usepackage[utf8]{inputenc}
        \\usepackage[margin=1in]{geometry}
        \\title{$title$}
        \\author{$author$}
        \\begin{document}
        \\maketitle
        $if(toc)$\\tableofcontents\\newpage$endif$
        $body$
        \\end{document}
        """

        self._save_template('default.css', epub_css)
        self._save_template('default.latex', latex_template)

    def get_available_templates(self, format: ExportFormat) -> List[str]:
        """Get list of available templates for format"""
        extension = f".{format.value}"
        return [f[:-len(extension)] for f in os.listdir(self.templates_dir) if f.endswith(extension)]

    def create_custom_template(self, name: str, format: ExportFormat, content: str) -> bool:
        """Create a custom export template"""
        template_file = os.path.join(self.templates_dir, f"{name}.{format.value}")
        try:
            with open(template_file, 'w', encoding='utf-8') as f:
                f.write(content)
            return True
        except Exception:
            return False
```

### 4. Version-Aware Exports

```python
class VersionAwareExporter:
    """Export functionality with version control integration"""

    def __init__(self, repository: pygit2.Repository):
        self.repo = repository

    def export_at_version(self, save_id: str, config: ExportConfiguration) -> ExportResult:
        """Export document as it existed at specific save"""

        with tempfile.TemporaryDirectory() as temp_repo:
            # Clone repository to temp location
            cloned_repo = pygit2.clone_repository(self.repo.path, temp_repo)

            # Checkout specific commit
            commit = cloned_repo[save_id]
            cloned_repo.checkout_tree(commit)

            # Perform export from temp repo
            temp_export_manager = ExportManager(temp_repo)
            return temp_export_manager.export_document(config, async_processing=False)

    def export_exploration(self, exploration_name: str, config: ExportConfiguration) -> ExportResult:
        """Export specific exploration"""

        current_branch = self.repo.head.shorthand

        try:
            # Switch to exploration
            exploration_branch = self.repo.branches.local[exploration_name]
            self.repo.checkout(exploration_branch)

            # Perform export
            export_manager = ExportManager(self.repo.workdir)
            return export_manager.export_document(config, async_processing=False)

        finally:
            # Switch back to original branch
            original_branch = self.repo.branches.local[current_branch]
            self.repo.checkout(original_branch)
```

### 5. Export Queue and Processing

```python
import queue
import threading

class ExportQueue:
    """Manages background export processing"""

    def __init__(self, export_manager):
        self.export_manager = export_manager
        self.queue = queue.Queue()
        self.workers = []
        self.running = False

    def start_workers(self, num_workers: int = 2):
        """Start background worker threads"""
        self.running = True

        for i in range(num_workers):
            worker = threading.Thread(
                target=self._worker_loop,
                name=f"ExportWorker-{i}",
                daemon=True
            )
            worker.start()
            self.workers.append(worker)

    def queue_export(self, export_id: str, config: ExportConfiguration):
        """Queue export for background processing"""
        self.queue.put((export_id, config))

    def _worker_loop(self):
        """Worker thread main loop"""
        while self.running:
            try:
                item = self.queue.get(timeout=1)
                if item is None:
                    break

                export_id, config = item
                try:
                    self.export_manager._process_export(export_id, config)
                except Exception as e:
                    # Mark export as failed
                    result = self.export_manager._load_export_result(export_id)
                    result.status = ExportStatus.FAILED
                    result.error_message = str(e)
                    self.export_manager._store_export_result(result)
                finally:
                    self.queue.task_done()

            except queue.Empty:
                continue
```

## Export Workflows

### Common Export Patterns

```python
def export_complete_manuscript(repo_path: str, format: ExportFormat) -> ExportResult:
    """Export complete manuscript with standard settings"""

    config = ExportConfiguration(
        format=format,
        template='professional',
        include_toc=True,
        include_version_info=True
    )

    export_manager = ExportManager(repo_path)
    return export_manager.export_document(config)

def export_for_review(repo_path: str, reviewer_name: str) -> ExportResult:
    """Export formatted for review with annotations"""

    config = ExportConfiguration(
        format=ExportFormat.PDF,
        template='review',
        include_version_info=True,
        pdf_options={
            'margin': '1.5in',  # Extra margin for notes
            'line_spacing': '2'  # Double spacing
        }
    )

    export_manager = ExportManager(repo_path)
    return export_manager.export_document(config)

def export_final_submission(repo_path: str, publisher_requirements: dict) -> ExportResult:
    """Export according to publisher specifications"""

    config = ExportConfiguration(
        format=ExportFormat(publisher_requirements['format']),
        template=publisher_requirements.get('template', 'default'),
        include_toc=publisher_requirements.get('include_toc', True),
        pdf_options=publisher_requirements.get('pdf_options', {}),
        epub_options=publisher_requirements.get('epub_options', {})
    )

    export_manager = ExportManager(repo_path)
    return export_manager.export_document(config)
```

### Integration with Writer Workflows

```python
class WriterExportWorkflows:
    """Writer-centric export workflows"""

    def draft_review_cycle(self, repo_path: str, exploration_name: str = None):
        """Export draft for review cycle"""

        # Export current version for self-review
        pdf_result = export_for_review(repo_path, "self-review")

        # If exploration specified, export comparison
        if exploration_name:
            version_exporter = VersionAwareExporter(pygit2.Repository(repo_path))
            exploration_result = version_exporter.export_exploration(
                exploration_name,
                ExportConfiguration(format=ExportFormat.PDF, template='comparison')
            )

            return {
                'main_draft': pdf_result,
                'exploration_draft': exploration_result
            }

        return {'main_draft': pdf_result}

    def submission_package(self, repo_path: str, formats: List[ExportFormat]):
        """Create complete submission package"""

        results = {}
        export_manager = ExportManager(repo_path)

        for format in formats:
            config = ExportConfiguration(
                format=format,
                template='professional',
                include_toc=True,
                include_version_info=False  # Clean for submission
            )

            results[format.value] = export_manager.export_document(config)

        return results
```

---

*GitWrite's export functionality provides writers with powerful document generation capabilities while maintaining simplicity and integration with version control workflows. The system supports professional publishing requirements while remaining accessible to non-technical users.*