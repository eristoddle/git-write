# Word Diff Visualization

GitWrite's word-level diff visualization system provides writers with intuitive, visual feedback about changes in their manuscripts. Unlike traditional line-based diffs used in programming, this system focuses on word-level granularity and writer-friendly presentation of changes.

## Overview

The word diff visualization system offers:
- **Word-Level Granularity**: Changes tracked at the word level, not line level
- **Writer-Friendly Interface**: Clear visual indicators for additions, deletions, and modifications
- **Context Preservation**: Maintains sentence and paragraph context
- **Interactive Elements**: Clickable diffs for detailed exploration
- **Export Capabilities**: Generate diff reports for editors and collaborators
- **Performance Optimization**: Efficient rendering for large documents

```
Word Diff Visualization Flow
    │
    ├─ Text Input
    │   ├─ Current Version
    │   └─ Previous Version
    │
    ├─ Diff Engine
    │   ├─ Word Tokenization
    │   ├─ Change Detection
    │   └─ Context Analysis
    │
    ├─ Rendering Engine
    │   ├─ Visual Markers
    │   ├─ Interactive Elements
    │   └─ Context Highlighting
    │
    └─ User Interface
        ├─ Diff Viewer
        ├─ Statistics Panel
        └─ Navigation Controls
```

## Core Components

### 1. Word-Level Diff Algorithm

```typescript
// src/lib/wordDiff.ts
interface WordDiffResult {
  type: 'unchanged' | 'added' | 'removed' | 'modified';
  content: string;
  originalContent?: string; // For modified words
  position: {
    start: number;
    end: number;
  };
  confidence: number; // 0-1, how certain we are about the change
}

interface DiffOptions {
  ignoreCase: boolean;
  ignorePunctuation: boolean;
  contextWords: number; // Number of surrounding words to include
  minimumWordLength: number; // Ignore changes to very short words
}

class WordDiffEngine {
  private readonly defaultOptions: DiffOptions = {
    ignoreCase: false,
    ignorePunctuation: false,
    contextWords: 3,
    minimumWordLength: 1,
  };

  generateDiff(
    originalText: string,
    modifiedText: string,
    options: Partial<DiffOptions> = {}
  ): WordDiffResult[] {
    const opts = { ...this.defaultOptions, ...options };

    // Tokenize both texts into words
    const originalWords = this.tokenizeText(originalText, opts);
    const modifiedWords = this.tokenizeText(modifiedText, opts);

    // Use a sophisticated diff algorithm (Myers' algorithm adapted for words)
    const diffMatrix = this.buildDiffMatrix(originalWords, modifiedWords, opts);

    // Backtrack to find the optimal sequence of changes
    const changes = this.extractChanges(
      diffMatrix,
      originalWords,
      modifiedWords,
      opts
    );

    // Post-process to merge adjacent changes and add context
    return this.postProcessChanges(changes, originalWords, modifiedWords, opts);
  }

  private tokenizeText(text: string, options: DiffOptions): string[] {
    // Split into words while preserving whitespace and punctuation context
    const words: string[] = [];
    const regex = /(\s+|[^\s]+)/g;
    let match;

    while ((match = regex.exec(text)) !== null) {
      const word = match[0];

      // Skip if below minimum length (unless it's whitespace or punctuation)
      if (word.trim().length >= options.minimumWordLength ||
          /^\s+$/.test(word) ||
          /^[^\w\s]+$/.test(word)) {
        words.push(word);
      }
    }

    return words;
  }

  private buildDiffMatrix(
    original: string[],
    modified: string[],
    options: DiffOptions
  ): number[][] {
    const matrix: number[][] = [];

    // Initialize matrix
    for (let i = 0; i <= original.length; i++) {
      matrix[i] = new Array(modified.length + 1).fill(0);
      matrix[i][0] = i;
    }

    for (let j = 0; j <= modified.length; j++) {
      matrix[0][j] = j;
    }

    // Fill matrix using dynamic programming
    for (let i = 1; i <= original.length; i++) {
      for (let j = 1; j <= modified.length; j++) {
        const originalWord = original[i - 1];
        const modifiedWord = modified[j - 1];

        if (this.wordsEqual(originalWord, modifiedWord, options)) {
          matrix[i][j] = matrix[i - 1][j - 1];
        } else {
          matrix[i][j] = Math.min(
            matrix[i - 1][j] + 1,     // deletion
            matrix[i][j - 1] + 1,     // insertion
            matrix[i - 1][j - 1] + 1  // substitution
          );
        }
      }
    }

    return matrix;
  }

  private wordsEqual(word1: string, word2: string, options: DiffOptions): boolean {
    let w1 = word1;
    let w2 = word2;

    if (options.ignoreCase) {
      w1 = w1.toLowerCase();
      w2 = w2.toLowerCase();
    }

    if (options.ignorePunctuation) {
      w1 = w1.replace(/[^\w\s]/g, '');
      w2 = w2.replace(/[^\w\s]/g, '');
    }

    return w1 === w2;
  }

  private extractChanges(
    matrix: number[][],
    original: string[],
    modified: string[],
    options: DiffOptions
  ): WordDiffResult[] {
    const changes: WordDiffResult[] = [];
    let i = original.length;
    let j = modified.length;
    let position = 0;

    while (i > 0 || j > 0) {
      if (i > 0 && j > 0 &&
          this.wordsEqual(original[i - 1], modified[j - 1], options)) {
        // Unchanged word
        const word = original[i - 1];
        changes.unshift({
          type: 'unchanged',
          content: word,
          position: { start: position, end: position + word.length },
          confidence: 1.0,
        });
        i--;
        j--;
        position += word.length;
      } else if (j > 0 && (i === 0 || matrix[i][j - 1] < matrix[i - 1][j])) {
        // Addition
        const word = modified[j - 1];
        changes.unshift({
          type: 'added',
          content: word,
          position: { start: position, end: position + word.length },
          confidence: 0.9,
        });
        j--;
        position += word.length;
      } else if (i > 0 && (j === 0 || matrix[i - 1][j] < matrix[i][j - 1])) {
        // Deletion
        const word = original[i - 1];
        changes.unshift({
          type: 'removed',
          content: word,
          position: { start: position, end: position + word.length },
          confidence: 0.9,
        });
        i--;
      } else {
        // Modification
        const originalWord = original[i - 1];
        const modifiedWord = modified[j - 1];
        changes.unshift({
          type: 'modified',
          content: modifiedWord,
          originalContent: originalWord,
          position: {
            start: position,
            end: position + modifiedWord.length
          },
          confidence: this.calculateModificationConfidence(originalWord, modifiedWord),
        });
        i--;
        j--;
        position += modifiedWord.length;
      }
    }

    return changes;
  }

  private calculateModificationConfidence(word1: string, word2: string): number {
    // Use Levenshtein distance to calculate how similar the words are
    const distance = this.levenshteinDistance(word1, word2);
    const maxLength = Math.max(word1.length, word2.length);
    return 1 - (distance / maxLength);
  }

  private levenshteinDistance(str1: string, str2: string): number {
    const matrix: number[][] = [];

    for (let i = 0; i <= str2.length; i++) {
      matrix[i] = [i];
    }

    for (let j = 0; j <= str1.length; j++) {
      matrix[0][j] = j;
    }

    for (let i = 1; i <= str2.length; i++) {
      for (let j = 1; j <= str1.length; j++) {
        if (str2.charAt(i - 1) === str1.charAt(j - 1)) {
          matrix[i][j] = matrix[i - 1][j - 1];
        } else {
          matrix[i][j] = Math.min(
            matrix[i - 1][j - 1] + 1,
            matrix[i][j - 1] + 1,
            matrix[i - 1][j] + 1
          );
        }
      }
    }

    return matrix[str2.length][str1.length];
  }

  private postProcessChanges(
    changes: WordDiffResult[],
    original: string[],
    modified: string[],
    options: DiffOptions
  ): WordDiffResult[] {
    // Merge adjacent changes of the same type
    const merged = this.mergeAdjacentChanges(changes);

    // Add context around changes
    return this.addContext(merged, options.contextWords);
  }

  private mergeAdjacentChanges(changes: WordDiffResult[]): WordDiffResult[] {
    const merged: WordDiffResult[] = [];
    let current: WordDiffResult | null = null;

    for (const change of changes) {
      if (current && current.type === change.type &&
          change.type !== 'unchanged' && change.type !== 'modified') {
        // Merge with previous change
        current.content += change.content;
        current.position.end = change.position.end;
      } else {
        if (current) {
          merged.push(current);
        }
        current = { ...change };
      }
    }

    if (current) {
      merged.push(current);
    }

    return merged;
  }

  private addContext(
    changes: WordDiffResult[],
    contextWords: number
  ): WordDiffResult[] {
    // Add surrounding unchanged words for context
    const withContext: WordDiffResult[] = [];

    for (let i = 0; i < changes.length; i++) {
      const change = changes[i];

      if (change.type !== 'unchanged') {
        // Add preceding context
        const startContext = Math.max(0, i - contextWords);
        for (let j = startContext; j < i; j++) {
          if (changes[j].type === 'unchanged') {
            withContext.push({ ...changes[j] });
          }
        }

        // Add the change itself
        withContext.push(change);

        // Add following context
        const endContext = Math.min(changes.length, i + contextWords + 1);
        for (let j = i + 1; j < endContext; j++) {
          if (changes[j].type === 'unchanged') {
            withContext.push({ ...changes[j] });
          }
        }
      }
    }

    return withContext;
  }
}

export const wordDiffEngine = new WordDiffEngine();
```

### 2. Diff Visualization Components

```typescript
// src/components/diff/WordDiffViewer.tsx
import React, { useMemo, useState } from 'react';
import { WordDiffResult } from '../../lib/wordDiff';

interface WordDiffViewerProps {
  originalText: string;
  modifiedText: string;
  showLineNumbers?: boolean;
  showStatistics?: boolean;
  highlightThreshold?: number; // Only highlight changes above this confidence
  onWordClick?: (change: WordDiffResult) => void;
}

export const WordDiffViewer: React.FC<WordDiffViewerProps> = ({
  originalText,
  modifiedText,
  showLineNumbers = false,
  showStatistics = true,
  highlightThreshold = 0.5,
  onWordClick,
}) => {
  const [selectedChange, setSelectedChange] = useState<WordDiffResult | null>(null);

  const diffResults = useMemo(() => {
    return wordDiffEngine.generateDiff(originalText, modifiedText, {
      ignoreCase: false,
      ignorePunctuation: false,
      contextWords: 3,
      minimumWordLength: 1,
    });
  }, [originalText, modifiedText]);

  const statistics = useMemo(() => {
    const stats = {
      totalWords: diffResults.length,
      added: 0,
      removed: 0,
      modified: 0,
      unchanged: 0,
    };

    diffResults.forEach(change => {
      stats[change.type === 'unchanged' ? 'unchanged' : change.type]++;
    });

    return stats;
  }, [diffResults]);

  const handleWordClick = (change: WordDiffResult) => {
    setSelectedChange(change);
    onWordClick?.(change);
  };

  return (
    <div className="word-diff-viewer">
      {showStatistics && (
        <DiffStatistics statistics={statistics} />
      )}

      <div className="diff-content">
        {showLineNumbers && <LineNumbers content={modifiedText} />}

        <div className="diff-text">
          {diffResults.map((change, index) => (
            <DiffWord
              key={index}
              change={change}
              isSelected={selectedChange === change}
              isHighlighted={change.confidence >= highlightThreshold}
              onClick={() => handleWordClick(change)}
            />
          ))}
        </div>
      </div>

      {selectedChange && (
        <DiffDetailPanel
          change={selectedChange}
          onClose={() => setSelectedChange(null)}
        />
      )}
    </div>
  );
};

// Individual word component with change styling
const DiffWord: React.FC<{
  change: WordDiffResult;
  isSelected: boolean;
  isHighlighted: boolean;
  onClick: () => void;
}> = ({ change, isSelected, isHighlighted, onClick }) => {
  const getWordClassName = () => {
    const baseClass = 'diff-word';
    const classes = [baseClass];

    if (change.type !== 'unchanged') {
      classes.push(`diff-word--${change.type}`);
    }

    if (isSelected) {
      classes.push('diff-word--selected');
    }

    if (isHighlighted && change.type !== 'unchanged') {
      classes.push('diff-word--highlighted');
    }

    return classes.join(' ');
  };

  return (
    <span
      className={getWordClassName()}
      onClick={onClick}
      title={change.type !== 'unchanged' ?
        `${change.type}: ${change.confidence.toFixed(2)} confidence` :
        undefined
      }
      data-change-type={change.type}
      data-confidence={change.confidence}
    >
      {change.content}
      {change.type === 'modified' && change.originalContent && (
        <span className="diff-word__original" title={`Original: ${change.originalContent}`}>
          {change.originalContent}
        </span>
      )}
    </span>
  );
};
```

### 3. Diff Statistics Panel

```typescript
// src/components/diff/DiffStatistics.tsx
interface DiffStatisticsProps {
  statistics: {
    totalWords: number;
    added: number;
    removed: number;
    modified: number;
    unchanged: number;
  };
}

export const DiffStatistics: React.FC<DiffStatisticsProps> = ({ statistics }) => {
  const changePercentage = ((statistics.added + statistics.removed + statistics.modified) /
    statistics.totalWords * 100).toFixed(1);

  return (
    <div className="diff-statistics">
      <div className="diff-statistics__summary">
        <h3>Change Summary</h3>
        <p>{changePercentage}% of text changed</p>
      </div>

      <div className="diff-statistics__details">
        <div className="stat-item stat-item--added">
          <span className="stat-label">Added</span>
          <span className="stat-value">{statistics.added}</span>
        </div>

        <div className="stat-item stat-item--removed">
          <span className="stat-label">Removed</span>
          <span className="stat-value">{statistics.removed}</span>
        </div>

        <div className="stat-item stat-item--modified">
          <span className="stat-label">Modified</span>
          <span className="stat-value">{statistics.modified}</span>
        </div>

        <div className="stat-item stat-item--unchanged">
          <span className="stat-label">Unchanged</span>
          <span className="stat-value">{statistics.unchanged}</span>
        </div>
      </div>

      <div className="diff-statistics__chart">
        <DiffChart statistics={statistics} />
      </div>
    </div>
  );
};

const DiffChart: React.FC<{ statistics: any }> = ({ statistics }) => {
  const total = statistics.totalWords;

  return (
    <div className="diff-chart">
      <div
        className="diff-chart__bar diff-chart__bar--added"
        style={{ width: `${(statistics.added / total) * 100}%` }}
      />
      <div
        className="diff-chart__bar diff-chart__bar--removed"
        style={{ width: `${(statistics.removed / total) * 100}%` }}
      />
      <div
        className="diff-chart__bar diff-chart__bar--modified"
        style={{ width: `${(statistics.modified / total) * 100}%` }}
      />
      <div
        className="diff-chart__bar diff-chart__bar--unchanged"
        style={{ width: `${(statistics.unchanged / total) * 100}%` }}
      />
    </div>
  );
};
```

### 4. Interactive Diff Navigation

```typescript
// src/components/diff/DiffNavigation.tsx
interface DiffNavigationProps {
  changes: WordDiffResult[];
  currentIndex: number;
  onNavigate: (index: number) => void;
}

export const DiffNavigation: React.FC<DiffNavigationProps> = ({
  changes,
  currentIndex,
  onNavigate,
}) => {
  const significantChanges = changes.filter(change =>
    change.type !== 'unchanged' && change.confidence >= 0.5
  );

  const goToNext = () => {
    const nextIndex = currentIndex + 1;
    if (nextIndex < significantChanges.length) {
      onNavigate(nextIndex);
    }
  };

  const goToPrevious = () => {
    const prevIndex = currentIndex - 1;
    if (prevIndex >= 0) {
      onNavigate(prevIndex);
    }
  };

  return (
    <div className="diff-navigation">
      <div className="diff-navigation__controls">
        <button
          onClick={goToPrevious}
          disabled={currentIndex <= 0}
          className="diff-nav-button diff-nav-button--prev"
        >
          Previous Change
        </button>

        <span className="diff-navigation__counter">
          {currentIndex + 1} of {significantChanges.length}
        </span>

        <button
          onClick={goToNext}
          disabled={currentIndex >= significantChanges.length - 1}
          className="diff-nav-button diff-nav-button--next"
        >
          Next Change
        </button>
      </div>

      <div className="diff-navigation__minimap">
        <DiffMinimap
          changes={significantChanges}
          currentIndex={currentIndex}
          onIndexClick={onNavigate}
        />
      </div>
    </div>
  );
};

const DiffMinimap: React.FC<{
  changes: WordDiffResult[];
  currentIndex: number;
  onIndexClick: (index: number) => void;
}> = ({ changes, currentIndex, onIndexClick }) => {
  return (
    <div className="diff-minimap">
      {changes.map((change, index) => (
        <div
          key={index}
          className={`diff-minimap__marker diff-minimap__marker--${change.type} ${
            index === currentIndex ? 'diff-minimap__marker--current' : ''
          }`}
          onClick={() => onIndexClick(index)}
          title={`${change.type}: ${change.content.substring(0, 20)}...`}
        />
      ))}
    </div>
  );
};
```

### 5. Export and Sharing

```typescript
// src/components/diff/DiffExport.tsx
import { WordDiffResult } from '../../lib/wordDiff';

interface DiffExportOptions {
  format: 'html' | 'markdown' | 'pdf' | 'docx';
  includeStatistics: boolean;
  includeMetadata: boolean;
  highlightThreshold: number;
}

class DiffExporter {
  exportToHTML(
    originalText: string,
    modifiedText: string,
    changes: WordDiffResult[],
    options: DiffExportOptions
  ): string {
    const html = [];

    if (options.includeMetadata) {
      html.push(this.generateHTMLMetadata(originalText, modifiedText));
    }

    if (options.includeStatistics) {
      const stats = this.calculateStatistics(changes);
      html.push(this.generateHTMLStatistics(stats));
    }

    html.push('<div class="diff-content">');

    for (const change of changes) {
      if (change.type === 'unchanged') {
        html.push(`<span>${this.escapeHTML(change.content)}</span>`);
      } else if (change.confidence >= options.highlightThreshold) {
        html.push(
          `<span class="diff-${change.type}" data-confidence="${change.confidence}">` +
          `${this.escapeHTML(change.content)}</span>`
        );
      } else {
        html.push(`<span>${this.escapeHTML(change.content)}</span>`);
      }
    }

    html.push('</div>');

    return this.wrapInHTMLDocument(html.join(''));
  }

  exportToMarkdown(
    originalText: string,
    modifiedText: string,
    changes: WordDiffResult[],
    options: DiffExportOptions
  ): string {
    const markdown = [];

    markdown.push('# Document Changes\n');

    if (options.includeMetadata) {
      markdown.push(this.generateMarkdownMetadata(originalText, modifiedText));
    }

    if (options.includeStatistics) {
      const stats = this.calculateStatistics(changes);
      markdown.push(this.generateMarkdownStatistics(stats));
    }

    markdown.push('## Changes\n');

    for (const change of changes) {
      if (change.type === 'added' && change.confidence >= options.highlightThreshold) {
        markdown.push(`**${change.content}**`);
      } else if (change.type === 'removed' && change.confidence >= options.highlightThreshold) {
        markdown.push(`~~${change.content}~~`);
      } else if (change.type === 'modified' && change.confidence >= options.highlightThreshold) {
        markdown.push(`~~${change.originalContent}~~ **${change.content}**`);
      } else {
        markdown.push(change.content);
      }
    }

    return markdown.join('');
  }

  private generateHTMLMetadata(originalText: string, modifiedText: string): string {
    return `
      <div class="diff-metadata">
        <h2>Document Metadata</h2>
        <table>
          <tr><td>Original word count:</td><td>${this.countWords(originalText)}</td></tr>
          <tr><td>Modified word count:</td><td>${this.countWords(modifiedText)}</td></tr>
          <tr><td>Export date:</td><td>${new Date().toLocaleDateString()}</td></tr>
        </table>
      </div>
    `;
  }

  private generateMarkdownMetadata(originalText: string, modifiedText: string): string {
    return `
## Metadata

- **Original word count:** ${this.countWords(originalText)}
- **Modified word count:** ${this.countWords(modifiedText)}
- **Export date:** ${new Date().toLocaleDateString()}

`;
  }

  private calculateStatistics(changes: WordDiffResult[]) {
    return changes.reduce((stats, change) => {
      stats[change.type]++;
      return stats;
    }, { unchanged: 0, added: 0, removed: 0, modified: 0 });
  }

  private countWords(text: string): number {
    return text.trim().split(/\s+/).length;
  }

  private escapeHTML(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  private wrapInHTMLDocument(content: string): string {
    return `
<!DOCTYPE html>
<html>
<head>
  <title>Document Changes</title>
  <style>
    .diff-added { background-color: #d4edda; }
    .diff-removed { background-color: #f8d7da; text-decoration: line-through; }
    .diff-modified { background-color: #fff3cd; }
    .diff-metadata table { border-collapse: collapse; }
    .diff-metadata td { border: 1px solid #ddd; padding: 8px; }
  </style>
</head>
<body>
  ${content}
</body>
</html>`;
  }
}

export const diffExporter = new DiffExporter();
```

### 6. Performance Optimization

```typescript
// src/hooks/useDiffPerformance.ts
import { useMemo, useCallback } from 'react';
import { WordDiffResult } from '../lib/wordDiff';

// Virtualized rendering for large diffs
export const useVirtualizedDiff = (
  changes: WordDiffResult[],
  containerHeight: number,
  itemHeight: number = 20
) => {
  const [startIndex, setStartIndex] = useState(0);
  const [endIndex, setEndIndex] = useState(0);

  const visibleItems = useMemo(() => {
    const visibleCount = Math.ceil(containerHeight / itemHeight);
    const buffer = 5; // Render extra items for smooth scrolling

    const start = Math.max(0, startIndex - buffer);
    const end = Math.min(changes.length, startIndex + visibleCount + buffer);

    return changes.slice(start, end);
  }, [changes, startIndex, containerHeight, itemHeight]);

  const handleScroll = useCallback((scrollTop: number) => {
    const newStartIndex = Math.floor(scrollTop / itemHeight);
    setStartIndex(newStartIndex);
  }, [itemHeight]);

  return {
    visibleItems,
    handleScroll,
    totalHeight: changes.length * itemHeight,
  };
};

// Debounced diff computation
export const useDebouncedDiff = (
  originalText: string,
  modifiedText: string,
  delay: number = 300
) => {
  const [debouncedOriginal, setDebouncedOriginal] = useState(originalText);
  const [debouncedModified, setDebouncedModified] = useState(modifiedText);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedOriginal(originalText);
      setDebouncedModified(modifiedText);
    }, delay);

    return () => clearTimeout(timer);
  }, [originalText, modifiedText, delay]);

  return useMemo(() => {
    if (!debouncedOriginal || !debouncedModified) return [];

    return wordDiffEngine.generateDiff(debouncedOriginal, debouncedModified);
  }, [debouncedOriginal, debouncedModified]);
};
```

## Styling and Themes

```scss
// src/styles/diff.scss
.word-diff-viewer {
  .diff-word {
    cursor: pointer;
    transition: all 0.2s ease;
    padding: 1px 2px;
    border-radius: 2px;

    &--added {
      background-color: #d4edda;
      border-left: 3px solid #28a745;
    }

    &--removed {
      background-color: #f8d7da;
      text-decoration: line-through;
      border-left: 3px solid #dc3545;
    }

    &--modified {
      background-color: #fff3cd;
      border-left: 3px solid #ffc107;
    }

    &--selected {
      outline: 2px solid #007bff;
      outline-offset: 1px;
    }

    &--highlighted {
      box-shadow: 0 0 4px rgba(0, 123, 255, 0.5);
    }

    &:hover {
      opacity: 0.8;
      transform: scale(1.02);
    }
  }

  .diff-statistics {
    margin-bottom: 1rem;
    padding: 1rem;
    border: 1px solid #dee2e6;
    border-radius: 4px;
    background-color: #f8f9fa;
  }
}
```

---

*GitWrite's word diff visualization system provides writers with an intuitive, powerful way to understand and navigate changes in their manuscripts, making revision and collaboration workflows more efficient and less intimidating than traditional technical diff tools.*