import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { GitWriteClient, type FileContentResponse as SdkFileContentResponse, type Annotation, AnnotationStatus } from 'gitwrite-sdk';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import AnnotationSidebar from './AnnotationSidebar'; // Import the new sidebar
import { Skeleton } from '@/components/ui/skeleton';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism'; // Or any other theme

interface FileContentViewerProps {
  repoName: string;
  filePath: string;
  commitSha: string;
  feedbackBranch: string; // Added prop for feedback branch
}

const FileContentViewer: React.FC<FileContentViewerProps> = ({ repoName, filePath, commitSha, feedbackBranch }) => {
  const navigate = useNavigate();
  const [fileContent, setFileContent] = useState<SdkFileContentResponse | null>(null);
  const [isLoadingFile, setIsLoadingFile] = useState(true);
  const [fileError, setFileError] = useState<string | null>(null);

  const [annotations, setAnnotations] = useState<Annotation[]>([]);
  const [isLoadingAnnotations, setIsLoadingAnnotations] = useState(true); // Separate loading for annotations
  const [annotationError, setAnnotationError] = useState<string | null>(null);
  const [isLoadingStatusUpdate, setIsLoadingStatusUpdate] = useState<{ [annotationId: string]: boolean }>({});

  const fetchFileAndAnnotations = useCallback(async () => {
    if (!repoName || !filePath || !commitSha || !feedbackBranch) {
      setFileError("Repository name, file path, commit SHA, or feedback branch is missing.");
      setIsLoadingFile(false);
      setIsLoadingAnnotations(false);
      return;
    }

    setIsLoadingFile(true);
    setFileError(null);
    setIsLoadingAnnotations(true);
    setAnnotationError(null);

    try {
      const token = localStorage.getItem('jwtToken');
      if (!token) {
        navigate('/login');
        return;
      }
      const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
      client.setToken(token);

      // Fetch file content
      const filePromise = client.getFileContent(repoName, filePath, commitSha);
      // Fetch annotations
      const annotationsPromise = client.listAnnotations(repoName, feedbackBranch);

      const [fileResponse, annotationResponse] = await Promise.all([filePromise, annotationsPromise]);

      setFileContent(fileResponse);
      // No need to filter annotations here, AnnotationSidebar will do it based on its currentFilePath prop (filePath)
      setAnnotations(annotationResponse.annotations);

    } catch (err: any) {
      // Handle errors for file fetching specifically
      if (err.response?.data?.detail && (err.config?.url?.includes('/file-content'))) {
         setFileError(err.response.data.detail || 'Failed to load file content.');
      } else if (err.response?.data?.detail && (err.config?.url?.includes('/annotations'))) {
         setAnnotationError(err.response.data.detail || 'Failed to load annotations.');
      } else {
        const generalError = err.message || 'An unexpected error occurred.';
        setFileError(generalError); // Show general error related to file if source unknown
        setAnnotationError(generalError); // Or a general annotation error
      }
      if (err.response?.status === 401) navigate('/login');
    } finally {
      setIsLoadingFile(false);
      setIsLoadingAnnotations(false);
    }
  }, [repoName, filePath, commitSha, feedbackBranch, navigate]);

  useEffect(() => {
    fetchFileAndAnnotations();
  }, [fetchFileAndAnnotations]);

  const handleUpdateAnnotationStatus = useCallback(async (annotationId: string, newStatus: AnnotationStatus) => {
    if (!repoName || !feedbackBranch) {
      setAnnotationError("Client-side error: Repo name or feedback branch missing for status update.");
      return;
    }
    setIsLoadingStatusUpdate(prev => ({ ...prev, [annotationId]: true }));
    setAnnotationError(null); // Clear previous general annotation errors

    try {
      const token = localStorage.getItem('jwtToken');
      if (!token) {
        navigate('/login');
        return;
      }
      const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
      client.setToken(token);

      await client.updateAnnotationStatus(annotationId, {
        new_status: newStatus,
        feedback_branch: feedbackBranch,
      });

      // Refresh annotations after update by re-fetching all for the branch
      const refreshedAnnotationResponse = await client.listAnnotations(repoName, feedbackBranch);
      setAnnotations(refreshedAnnotationResponse.annotations);

    } catch (err: any) {
      setAnnotationError(err.response?.data?.detail || err.message || 'Failed to update annotation status.');
      if (err.response?.status === 401) navigate('/login');
    } finally {
      setIsLoadingStatusUpdate(prev => ({ ...prev, [annotationId]: false }));
    }
  }, [repoName, feedbackBranch, navigate]); // filePath is not directly used but relevant for overall context

  // Loading state for the main file content
  if (isLoadingFile) {
    return (
      <div className="flex flex-row space-x-4 p-4 h-[calc(100vh-var(--header-height,8rem))]"> {/* Adjust height as needed */}
        <div className="flex-grow"> {/* File content viewer takes remaining space */}
          <Card className="h-full">
            <CardHeader>
              <Skeleton className="h-6 w-3/4 mb-2" />
              <Skeleton className="h-4 w-1/2" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-[calc(100%-4rem)] w-full" /> {/* Adjust skeleton height */}
            </CardContent>
          </Card>
        </div>
        <div className="w-1/3 max-w-sm lg:max-w-md flex-shrink-0"> {/* Sidebar with fixed/max width */}
           <Card className="h-full">
            <CardHeader>
              <Skeleton className="h-5 w-1/2 mb-2" />
              <Skeleton className="h-3 w-3/4" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-10 w-full mb-2" />
              <Skeleton className="h-10 w-full mb-2" />
              <Skeleton className="h-10 w-full" />
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Error state for file fetching
  if (fileError) {
    return (
      <Alert variant="destructive" className="m-4">
        <AlertTitle>Error Fetching File</AlertTitle>
        <AlertDescription>{fileError}</AlertDescription>
      </Alert>
    );
  }

  // No file content loaded
  if (!fileContent) {
    return (
      <Alert className="m-4">
        <AlertTitle>No Content</AlertTitle>
        <AlertDescription>File content could not be loaded or file is empty.</AlertDescription>
      </Alert>
    );
  }

  const getLanguage = (filename: string): string | undefined => {
    const extension = filename.split('.').pop()?.toLowerCase();
    switch (extension) {
      case 'js': return 'javascript';
      case 'jsx': return 'jsx';
      case 'ts': return 'typescript';
      case 'tsx': return 'tsx';
      case 'py': return 'python';
      case 'java': return 'java';
      case 'c': return 'c';
      case 'cpp': return 'cpp';
      case 'cs': return 'csharp';
      case 'go': return 'go';
      case 'rb': return 'ruby';
      case 'php': return 'php';
      case 'html': return 'html';
      case 'css': return 'css';
      case 'scss': return 'scss';
      case 'json': return 'json';
      case 'yaml':
      case 'yml': return 'yaml';
      case 'md': return 'markdown';
      case 'sh': return 'bash';
      case 'sql': return 'sql';
      default: return undefined;
    }
  };

  return (
    <div className="flex flex-row space-x-4 p-4 h-[calc(100vh-var(--header-height,8rem))]"> {/* Adjust parent height */}
      <div className="flex-grow overflow-hidden"> {/* File content viewer takes remaining space */}
        <Card className="w-full h-full flex flex-col">
          <CardHeader>
            <CardTitle>{fileContent.file_path}</CardTitle>
            <CardDescription>
              Commit: <span className="font-mono text-xs">{fileContent.commit_sha.substring(0,12)}</span> |
              Size: {fileContent.size} bytes |
              Mode: {fileContent.mode}
            </CardDescription>
          </CardHeader>
          <CardContent className="flex-grow overflow-auto"> {/* Make content scrollable */}
            {fileContent.is_binary ? (
              <p className="text-muted-foreground p-4">Binary file content cannot be displayed directly.</p>
            ) : (
              <SyntaxHighlighter
                language={getLanguage(fileContent.file_path)}
                style={atomDark}
                showLineNumbers
                wrapLines
                customStyle={{ fontSize: '0.875rem', margin: 0 }} // Removed maxHeight for flex-grow to work
                lineNumberStyle={{ minWidth: '3.25em', paddingRight: '1em', textAlign: 'right', color: '#777' }}
              >
                {fileContent.content}
              </SyntaxHighlighter>
            )}
          </CardContent>
        </Card>
      </div>
      <div className="w-1/3 max-w-sm lg:max-w-md flex-shrink-0 h-full"> {/* Sidebar with fixed/max width and full height */}
        {isLoadingAnnotations ? (
           <Card className="h-full">
             <CardHeader>
               <Skeleton className="h-5 w-1/2 mb-2" />
               <Skeleton className="h-3 w-3/4" />
             </CardHeader>
             <CardContent>
               <Skeleton className="h-10 w-full mb-2" />
               <Skeleton className="h-10 w-full mb-2" />
               <Skeleton className="h-10 w-full" />
             </CardContent>
           </Card>
        ) : annotationError ? (
          <Alert variant="destructive" className="h-full">
            <AlertTitle>Error Loading Annotations</AlertTitle>
            <AlertDescription>{annotationError}</AlertDescription>
          </Alert>
        ) : (
          <AnnotationSidebar
            annotations={annotations}
            onUpdateStatus={handleUpdateAnnotationStatus}
            isLoadingStatusUpdate={isLoadingStatusUpdate}
            currentFilePath={filePath} // Pass current file path for filtering in sidebar
          />
        )}
      </div>
    </div>
  );
};

export default FileContentViewer;
