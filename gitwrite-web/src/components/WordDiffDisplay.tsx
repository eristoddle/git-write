import React from 'react';
import { type StructuredDiffFile, type WordDiffHunk, type WordDiffLine, type WordDiffSegment } from 'gitwrite-sdk';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';

interface WordDiffDisplayProps {
  diffData: StructuredDiffFile[] | null;
  isLoading: boolean;
  error: string | null;
  repoName?: string;
  ref1?: string;
  ref2?: string;
}

const renderWordSegments = (segments: WordDiffSegment[]): JSX.Element[] => {
  return segments.map((segment, index) => {
    let className = '';
    if (segment.type === 'added') {
      className = 'bg-green-200 dark:bg-green-700 px-1';
    } else if (segment.type === 'removed') {
      className = 'bg-red-200 dark:bg-red-700 px-1 line-through';
    }
    // Add a space between segments for readability, unless it's the last segment
    // or the content itself ends with a space.
    const content = segment.content + (index < segments.length - 1 && !segment.content.endsWith(' ') ? ' ' : '');
    return (
      <span key={index} className={className}>
        {content}
      </span>
    );
  });
};

const WordDiffDisplay: React.FC<WordDiffDisplayProps> = ({ diffData, isLoading, error, repoName, ref1, ref2 }) => {
  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-8 w-3/4" />
        </CardHeader>
        <CardContent className="space-y-4">
          <Skeleton className="h-6 w-full" />
          <Skeleton className="h-6 w-5/6" />
          <Skeleton className="h-6 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Error Fetching Diff</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!diffData || diffData.length === 0) {
    return (
      <Alert>
        <AlertTitle>No Differences</AlertTitle>
        <AlertDescription>No differences found between {ref1} and {ref2}.</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="space-y-6">
      {diffData.map((fileDiff, fileIndex) => (
        <Card key={fileIndex}>
          <CardHeader>
            <CardTitle className="text-lg font-mono break-all">
              {fileDiff.change_type === 'renamed' || fileDiff.change_type === 'copied' ? (
                <>
                  {fileDiff.old_file_path} &rarr; {fileDiff.new_file_path} ({fileDiff.change_type})
                </>
              ) : (
                <>
                  {fileDiff.file_path} ({fileDiff.change_type})
                </>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {fileDiff.is_binary ? (
              <p className="text-muted-foreground">Binary file differs.</p>
            ) : fileDiff.hunks.length === 0 && fileDiff.change_type !== 'added' && fileDiff.change_type !== 'deleted' ? (
              <p className="text-muted-foreground">File mode changed or other non-content change.</p>
            ) : fileDiff.hunks.length === 0 && (fileDiff.change_type === 'added' || fileDiff.change_type === 'deleted') ? (
                 <p className="text-muted-foreground">
                    {fileDiff.change_type === 'added' ? 'File added.' : 'File deleted.'}
                    {/* Optionally, if we want to show content for newly added files: */}
                    {/* This depends on whether the diff structure provides full content for added files in hunks */}
                 </p>
            ) : (
              <div className="space-y-1 font-mono text-sm overflow-x-auto">
                {fileDiff.hunks.map((hunk, hunkIndex) => (
                  <div key={hunkIndex} className="border-t border-border pt-2 mt-2 first:mt-0 first:border-t-0">
                    {/* Could add hunk header info here if available and desired */}
                    {hunk.lines.map((line, lineIndex) => {
                      let lineClass = 'whitespace-pre-wrap break-all ';
                      let prefix = '';
                      if (line.type === 'addition') {
                        lineClass += 'bg-green-50 dark:bg-green-900/50 text-green-700 dark:text-green-300';
                        prefix = '+ ';
                      } else if (line.type === 'deletion') {
                        lineClass += 'bg-red-50 dark:bg-red-900/50 text-red-700 dark:text-red-300';
                        prefix = '- ';
                      } else if (line.type === 'context') {
                        lineClass += 'text-muted-foreground';
                        prefix = '  ';
                      } else if (line.type === 'no_newline') {
                        lineClass += 'text-muted-foreground italic';
                         return <div key={lineIndex} className={lineClass}>{line.content}</div>;
                      }

                      return (
                        <div key={lineIndex} className={lineClass}>
                          <span className="select-none">{prefix}</span>
                          {line.words && (line.type === 'addition' || line.type === 'deletion')
                            ? renderWordSegments(line.words)
                            : line.content}
                        </div>
                      );
                    })}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
};

export default WordDiffDisplay;
