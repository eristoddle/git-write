import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { GitWriteClient, type BranchReviewCommit, type CherryPickResponse } from 'gitwrite-sdk';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Skeleton } from '@/components/ui/skeleton';
import { ArrowLeft, GitMerge, Eye, RefreshCw, Loader2 } from 'lucide-react'; // Added GitMerge for Cherry-Pick icon

interface BranchReviewPageParams extends Record<string, string | undefined> {
  repoName: string;
  branchName: string; // The branch being reviewed
}

const BranchReviewPage: React.FC = () => {
  const { repoName, branchName } = useParams<BranchReviewPageParams>();
  const navigate = useNavigate();
  const [reviewCommits, setReviewCommits] = useState<BranchReviewCommit[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [cherryPickStatus, setCherryPickStatus] = useState<{ commitOid: string | null; loading: boolean; error: string | null; success: string | null; conflicts?: string[] | null }>({
    commitOid: null,
    loading: false,
    error: null,
    success: null,
    conflicts: null,
  });

  // Placeholder for current branch of the repository, assuming 'main' or fetched elsewhere
  // In a real app, this would come from global state or an API call indicating the current repository status.
  const currentWorkingBranch = "main";

  const fetchReviewCommits = useCallback(async (showLoadingSpinner = true) => {
    if (!repoName || !branchName) {
      setError("Repository name or branch name is missing.");
      setIsLoading(false);
      return;
    }
    if (showLoadingSpinner) {
      setIsLoading(true);
    }
    setError(null); // Clear previous main error
    // Clear previous cherry-pick status messages on refresh
    setCherryPickStatus(prev => ({ ...prev, error: null, success: null, conflicts: null }));
      try {
        const token = localStorage.getItem('jwtToken');
        if (!token) {
          navigate('/login');
          return;
        }
        const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
        client.setToken(token);

        // The reviewBranch SDK method expects the branch name to review.
        // The API endpoint /repository/review/{branch_name} compares it against current HEAD.
        const response = await client.reviewBranch(branchName, { limit: 100 }); // Added limit for safety

        if (response.status === 'success') {
          setReviewCommits(response.commits);
        } else {
          // Assuming the SDK might return a non-success status in the response object
          // Or it might throw an error which is caught below.
          setError(response.message || `Failed to fetch review commits for branch ${branchName}.`);
        }
      } catch (err: any) {
        console.error("Error fetching review commits:", err);
        setError(err.response?.data?.detail || err.message || 'An unexpected error occurred.');
        if (err.response?.status === 401) {
          navigate('/login');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchReviewCommits();
  }, [repoName, branchName, navigate]);

  const handleCherryPick = (commitOid: string) => {
    // Placeholder for Step 2
    console.log(`Attempting to cherry-pick commit: ${commitOid} into ${currentWorkingBranch}`);
    // Actual implementation will be in the next step.
  };

  if (isLoading) {
    try {
      const token = localStorage.getItem('jwtToken');
      if (!token) {
        navigate('/login');
        return;
      }
      const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
      client.setToken(token);
      const response = await client.reviewBranch(branchName!, { limit: 100 });

      if (response.status === 'success') {
        setReviewCommits(response.commits);
      } else {
        setError(response.message || `Failed to fetch review commits for branch ${branchName}.`);
      }
    } catch (err: any) {
      console.error("Error fetching review commits:", err);
      const apiError = err.response?.data?.detail || err.message;
      const specificError = Array.isArray(apiError) ? apiError[0]?.msg || JSON.stringify(apiError) : apiError;
      setError(specificError || 'An unexpected error occurred while fetching review commits.');
      if (err.response?.status === 401) {
        navigate('/login');
      }
    } finally {
      if (showLoadingSpinner) {
        setIsLoading(false);
      }
    }
  }, [repoName, branchName, navigate]);

  useEffect(() => {
    fetchReviewCommits(true);
  }, [fetchReviewCommits]); // Initial fetch

  const handleCherryPick = async (commitOid: string) => {
    if (!repoName) return;

    setCherryPickStatus({ commitOid, loading: true, error: null, success: null, conflicts: null });
    try {
      const token = localStorage.getItem('jwtToken');
      if (!token) {
        navigate('/login');
        return;
      }
      const client = new GitWriteClient(import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000');
      client.setToken(token);

      const response: CherryPickResponse = await client.cherryPickCommit({ commit_id: commitOid });

      if (response.status === 'success') {
        setCherryPickStatus({ commitOid, loading: false, error: null, success: `Commit ${commitOid.substring(0,7)} cherry-picked successfully. New commit: ${response.new_commit_oid?.substring(0,7)}`, conflicts: null });
        await fetchReviewCommits(false); // Refresh list without full page loading spinner
      } else if (response.status === 'conflict') {
        setCherryPickStatus({ commitOid, loading: false, error: response.message, success: null, conflicts: response.conflicting_files });
      } else {
        // Generic error from cherry-pick response (non-conflict, non-success)
        setCherryPickStatus({ commitOid, loading: false, error: response.message || 'Cherry-pick failed.', success: null, conflicts: null });
      }
    } catch (err: any) {
      console.error("Error during cherry-pick:", err);
      const apiError = err.response?.data?.detail || err.message;
      const specificError = Array.isArray(apiError) ? apiError[0]?.msg || JSON.stringify(apiError) : apiError;
      setCherryPickStatus({ commitOid, loading: false, error: specificError || 'An unexpected error occurred during cherry-pick.', success: null, conflicts: null });
      if (err.response?.status === 401) {
        navigate('/login');
      }
    }
  };

  const renderCherryPickStatusAlert = () => {
    if (!cherryPickStatus.commitOid) return null; // No operation attempted yet or cleared

    if (cherryPickStatus.success) {
      return (
        <Alert variant="default" className="mt-4 bg-green-100 border-green-400 text-green-700">
          <AlertTitle>Cherry-Pick Success</AlertTitle>
          <AlertDescription>{cherryPickStatus.success}</AlertDescription>
        </Alert>
      );
    }
    if (cherryPickStatus.error) {
      return (
        <Alert variant="destructive" className="mt-4">
          <AlertTitle>Cherry-Pick Failed: {cherryPickStatus.commitOid.substring(0,7)}...</AlertTitle>
          <AlertDescription>
            {cherryPickStatus.error}
            {cherryPickStatus.conflicts && cherryPickStatus.conflicts.length > 0 && (
              <>
                <br /><strong>Conflicting files:</strong>
                <ul className="list-disc list-inside">
                  {cherryPickStatus.conflicts.map(file => <li key={file}>{file}</li>)}
                </ul>
                <p className="mt-2 text-sm">Please resolve these conflicts manually in your local repository, commit the changes, and then refresh this view.</p>
              </>
            )}
          </AlertDescription>
        </Alert>
      );
    }
    return null;
  };


  if (isLoading) {
    return (
      <div className="container mx-auto p-4">
        <Card>
          <CardHeader>
            <Skeleton className="h-8 w-3/4" />
            <Skeleton className="h-4 w-1/2 mt-2" />
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {[...Array(3)].map((_, i) => (
                <Skeleton key={i} className="h-12 w-full" />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Main error for fetching commits takes precedence
  if (error && !isLoading) {
    return (
      <div className="container mx-auto p-4">
        <Alert variant="destructive">
          <AlertTitle>Error Fetching Commits</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button variant="outline" onClick={() => navigate(-1)} className="mt-4">
          <ArrowLeft className="mr-2 h-4 w-4" /> Back
        </Button>
      </div>
    );
  }

  return (
    <div className="container mx-auto p-4">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center">
              <Button variant="outline" size="icon" onClick={() => navigate(-1)} className="mr-4">
                <ArrowLeft className="h-4 w-4" />
              </Button>
              <CardTitle>Review & Cherry-Pick Commits</CardTitle>
            </div>
            <Button variant="outline" size="sm" onClick={() => fetchReviewCommits(true)}>
              <RefreshCw className="mr-2 h-4 w-4" /> Refresh List
            </Button>
          </div>
          <CardDescription>
            Reviewing commits from branch <span className="font-semibold">{branchName}</span> for integration into <span className="font-semibold">{currentWorkingBranch}</span>.
            These commits are present in '{branchName}' but not in your current working branch's HEAD.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {renderCherryPickStatusAlert()}
          {reviewCommits.length === 0 && !isLoading ? ( // Check !isLoading again for case where initial fetch is empty
            <p className="mt-4">No unique commits to review on branch '{branchName}' compared to your current branch, or all have been integrated.</p>
          ) : (
            <Table className="mt-4">
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[120px]">SHA</TableHead>
                  <TableHead>Message</TableHead>
                  <TableHead>Author</TableHead>
                  <TableHead className="w-[180px]">Date</TableHead>
                  <TableHead className="text-right w-[250px]">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {reviewCommits.map((commit) => (
                  <TableRow key={commit.oid}>
                    <TableCell className="font-mono text-xs">{commit.short_hash}</TableCell>
                    <TableCell>{commit.message_short}</TableCell>
                    <TableCell>{commit.author_name}</TableCell>
                    <TableCell>{new Date(commit.date).toLocaleString()}</TableCell>
                    <TableCell className="text-right space-x-2">
                      <Button
                        variant="outline"
                        size="sm"
                        asChild
                        disabled={cherryPickStatus.loading && cherryPickStatus.commitOid === commit.oid}
                      >
                        <Link to={`/repository/${repoName}/compare/${commit.oid}^/${commit.oid}`}>
                          <Eye className="mr-1 h-4 w-4" /> Diff
                        </Link>
                      </Button>
                      <Button
                        variant="default"
                        size="sm"
                        onClick={() => handleCherryPick(commit.oid)}
                        disabled={cherryPickStatus.loading && cherryPickStatus.commitOid === commit.oid}
                        title={`Cherry-pick this commit into ${currentWorkingBranch}`}
                      >
                        {cherryPickStatus.loading && cherryPickStatus.commitOid === commit.oid ? (
                          <Loader2 className="mr-1 h-4 w-4 animate-spin" />
                        ) : (
                          <GitMerge className="mr-1 h-4 w-4" />
                        )}
                        Cherry-Pick
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

export default BranchReviewPage;
