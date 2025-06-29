import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { GitWriteClient, type CommitDetail } from 'gitwrite-sdk';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft } from 'lucide-react';

interface CommitHistoryViewParams extends Record<string, string | undefined> {
  repoName: string;
  '*': string; // Splat for branch and potential path, though we only use branch for now
}

const CommitHistoryView: React.FC = () => {
  const { repoName, '*': splatPath = '' } = useParams<CommitHistoryViewParams>();
  const navigate = useNavigate();
  const [commits, setCommits] = useState<CommitDetail[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // For now, assume the splatPath is the branch name.
  // This might need to be more sophisticated if the path includes subdirectories.
  const branchName = splatPath || 'main'; // Default to 'main' if no branch in splat

  useEffect(() => {
    if (!repoName) {
      setError("Repository name is missing.");
      setIsLoading(false);
      return;
    }

    const fetchCommits = async () => {
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

        // TODO: The SDK's listCommits doesn't directly take repoName.
        // This implies the API is context-aware or the SDK needs an update
        // for multi-repo support beyond the placeholder.
        // For now, assuming the API is set to the target repo contextually.
        const response = await client.listCommits({ branchName: branchName, maxCount: 100 });
        if (response.status === 'success' || response.status === 'no_commits') {
          setCommits(response.commits || []);
        } else {
          setError(response.message || 'Failed to fetch commits.');
        }
      } catch (err: any) {
        setError(err.message || 'An unexpected error occurred.');
        if (err.response?.status === 401) {
          navigate('/login');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchCommits();
  }, [repoName, branchName, navigate]);

  const handleCommitSelect = (commitSha: string) => {
    // Navigate to the repository browser tree view, using the commit SHA as the ref.
    // The RepositoryBrowser will need to handle this (e.g. if the ref is a SHA, it's not a branch for history/status display)
    navigate(`/repository/${repoName}/tree/${commitSha}/`); // Empty path to start at root of that commit
  };

  if (isLoading) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Commit History for {repoName} ({branchName})</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTitle>Error</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <Button variant="outline" size="icon" onClick={() => navigate(-1)} className="mr-4">
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <CardTitle className="inline-block">Commit History: {repoName} (Branch: {branchName})</CardTitle>
        </div>
      </CardHeader>
      <CardContent>
        {commits.length === 0 ? (
          <p>No commits found for this branch.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead className="w-[150px]">SHA</TableHead>
                <TableHead>Message</TableHead>
                <TableHead>Author</TableHead>
                <TableHead className="w-[200px]">Date</TableHead>
                <TableHead className="text-right w-[100px]">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {commits.map((commit) => (
                <TableRow key={commit.sha}>
                  <TableCell className="font-mono text-xs">
                    {commit.sha.substring(0, 7)}...
                  </TableCell>
                  <TableCell>{commit.message.split('\n')[0]}</TableCell> {/* Show first line */}
                  <TableCell>{commit.author_name}</TableCell>
                  <TableCell>{new Date(commit.author_date).toLocaleString()}</TableCell>
                  <TableCell className="text-right">
                    <Button variant="outline" size="sm" onClick={() => handleCommitSelect(commit.sha)}>
                      View
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
};

export default CommitHistoryView;
