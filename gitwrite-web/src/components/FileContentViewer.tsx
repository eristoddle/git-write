import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { GitWriteClient, type FileContentResponse as SdkFileContentResponse } from 'gitwrite-sdk';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter';
import { atomDark } from 'react-syntax-highlighter/dist/esm/styles/prism'; // Or any other theme

interface FileContentViewerProps {
  repoName: string;
  filePath: string;
  commitSha: string;
}

const FileContentViewer: React.FC<FileContentViewerProps> = ({ repoName, filePath, commitSha }) => {
  const navigate = useNavigate();
  const [fileContent, setFileContent] = useState<SdkFileContentResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!repoName || !filePath || !commitSha) {
      setError("Repository name, file path, or commit SHA is missing.");
      setIsLoading(false);
      return;
    }

    const fetchFileContent = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const token = localStorage.getItem('jwtToken');
        if (!token) {
          navigate('/login');
          return;
        }
        const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
        client.setToken(token);

        const response = await client.getFileContent(repoName, filePath, commitSha);
        // The SDK method directly returns the data payload or throws an error
        setFileContent(response);

      } catch (err: any) {
        setError(err.response?.data?.detail || err.message || 'An unexpected error occurred while fetching file content.');
        if (err.response?.status === 401) {
          navigate('/login');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchFileContent();
  }, [repoName, filePath, commitSha, navigate]);

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-3/4 mb-2" />
          <Skeleton className="h-4 w-1/2" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-40 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Error Fetching File</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!fileContent) {
    return (
      <Alert>
        <AlertTitle>No Content</AlertTitle>
        <AlertDescription>File content could not be loaded.</AlertDescription>
      </Alert>
    );
  }

  // Determine language for syntax highlighting
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
      default: return undefined; // Let SyntaxHighlighter auto-detect or default
    }
  };

  return (
    <Card className="w-full">
      <CardHeader>
        <CardTitle>{fileContent.file_path}</CardTitle>
        <CardDescription>
          Commit: <span className="font-mono text-xs">{fileContent.commit_sha.substring(0,12)}</span> |
          Size: {fileContent.size} bytes |
          Mode: {fileContent.mode}
        </CardDescription>
      </CardHeader>
      <CardContent>
        {fileContent.is_binary ? (
          <p className="text-muted-foreground">Binary file content cannot be displayed directly.</p>
        ) : (
          <SyntaxHighlighter
            language={getLanguage(fileContent.file_path)}
            style={atomDark}
            showLineNumbers
            wrapLines
            customStyle={{ maxHeight: '600px', overflowY: 'auto', fontSize: '0.875rem' }}
          >
            {fileContent.content}
          </SyntaxHighlighter>
        )}
      </CardContent>
    </Card>
  );
};

export default FileContentViewer;
